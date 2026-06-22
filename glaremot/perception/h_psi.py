"""Learned head h_psi (hybrid Stage-1) — present / m_glare / Sigma on a frozen
YOLO backbone tap.

Hybrid split: the ANALYTIC block (`analytic.py`) owns the lamp core, the
beacon point ``mu``, and ``m_glare_analytic``. This learned head adds ONLY the
semantics rules can't reach, on the FROZEN detector backbone (~free):

  - present in [0,1] : is this a PERSON's lamp, or environment light
    (floor reflection / ghost / streak / wall)?
  - m_glare in [0,1] : localization reliability; REFINES ``m_glare_analytic``
    (its regression target) with image context.
  - Sigma (2x2 SPD)  : uncertainty of the beacon point ``mu``, for the weak
    Kalman update.

POOL-FIRST design: because the backbone is frozen, the roi_align happens on
the frozen feature map and the trainable head operates on the pooled
[N, C, roi, roi] tensor. This lets us PRECOMPUTE the pooled features ONCE
(scripts/05) and then train the tiny head for many epochs straight from
RAM/GPU — no per-epoch image I/O or backbone forward.
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision.ops import roi_align

__all__ = ["YoloBackboneTap", "HybridVisibilityHead", "HPsiModel",
           "Stage1HeadLoss", "boxes_to_rois", "sigma_from_params",
           "focal_bce", "gaussian_nll_2d"]


class YoloBackboneTap(nn.Module):
    """Partial forward of an ultralytics DetectionModel up to a neck layer
    (default: P3, stride 8). Weights frozen; channels/stride are inferred with
    a dummy forward so any YOLO variant (n..x) works unchanged."""

    def __init__(self, detection_model, tap_index=16, freeze=True):
        super().__init__()
        self.seq = detection_model.model          # nn.Sequential (each layer has .f)
        self.tap_index = tap_index
        if freeze:
            for p in self.seq.parameters():
                p.requires_grad_(False)
        self.eval()
        with torch.no_grad():
            feat = self._partial_forward(torch.zeros(1, 3, 64, 64))
        self.out_channels = feat.shape[1]
        self.stride = 64 // feat.shape[-1]

    def _partial_forward(self, x):
        y = []
        for i, m in enumerate(self.seq):
            if m.f != -1:
                x = y[m.f] if isinstance(m.f, int) else [x if j == -1 else y[j] for j in m.f]
            x = m(x)
            y.append(x)
            if i == self.tap_index:
                return x
        return x

    def forward(self, img):
        with torch.no_grad():                     # backbone is frozen, always
            return self._partial_forward(img)


def boxes_to_rois(boxes_xyxy, batch_idx):
    """rois [N,5] = (batch_idx, x1, y1, x2, y2) from pixel boxes [N,4]."""
    t = torch.as_tensor(boxes_xyxy, dtype=torch.float32).view(-1, 4)
    bidx = torch.as_tensor(batch_idx, dtype=torch.float32).view(-1, 1)
    return torch.cat([bidx, t], dim=1)


def sigma_from_params(params, eps=1e-3):
    """[N,3] raw -> [N,2,2] SPD covariance via Cholesky L L^T + eps*I."""
    l11 = F.softplus(params[:, 0]) + eps
    l22 = F.softplus(params[:, 1]) + eps
    l21 = params[:, 2]
    z = torch.zeros_like(l11)
    L = torch.stack([torch.stack([l11, z], -1), torch.stack([l21, l22], -1)], -2)
    sigma = L @ L.transpose(-1, -2)
    return sigma + eps * torch.eye(2, device=params.device, dtype=params.dtype)


class HybridVisibilityHead(nn.Module):
    """Trainable head on POOLED frozen features [N,C,roi,roi]."""

    def __init__(self, in_channels, roi_size=7):
        super().__init__()
        self.roi_size = roi_size
        c = 64
        self.roi_conv = nn.Sequential(
            nn.Conv2d(in_channels, c, 3, padding=1), nn.GroupNorm(8, c), nn.ReLU(inplace=True),
            nn.Conv2d(c, c, 3, padding=1), nn.GroupNorm(8, c), nn.ReLU(inplace=True),
        )
        self.mlp = nn.Sequential(
            nn.Linear(c * roi_size * roi_size, 256), nn.ReLU(inplace=True),
            nn.Linear(256, 128), nn.ReLU(inplace=True),
        )
        self.present_head = nn.Linear(128, 1)
        self.m_head = nn.Linear(128, 1)
        self.sigma_head = nn.Linear(128, 3)

    def forward(self, pooled):
        z = self.mlp(self.roi_conv(pooled).flatten(1))
        sp = self.sigma_head(z)
        return {
            "present_logit": self.present_head(z).squeeze(-1),
            "m_glare": torch.sigmoid(self.m_head(z)).squeeze(-1),
            "sigma_params": sp,
            "sigma": sigma_from_params(sp),
        }


class HPsiModel(nn.Module):
    """Frozen YOLO backbone tap + trainable hybrid visibility head."""

    def __init__(self, detection_model, tap_index=16, roi_size=7):
        super().__init__()
        self.backbone = YoloBackboneTap(detection_model, tap_index=tap_index, freeze=True)
        self.head = HybridVisibilityHead(self.backbone.out_channels, roi_size)
        self.stride = self.backbone.stride

    @torch.no_grad()
    def pool(self, img, rois):
        """Frozen ROI features [N,C,roi,roi] for rois [N,5] (image px). Cacheable."""
        feat = self.backbone(img)
        return roi_align(feat, rois, output_size=self.head.roi_size,
                         spatial_scale=1.0 / self.stride, aligned=True)

    def forward(self, img, rois):
        return self.head(self.pool(img, rois))


def focal_bce(logit, target, gamma=2.0, alpha=0.75):
    """Alpha-balanced focal BCE. ``alpha`` weights POSITIVES (lamp-on-person);
    environment-light negatives dominate (~8:1), so alpha > 0.5 keeps
    ``present`` from collapsing while the focal term still punishes confident
    false positives."""
    ce = F.binary_cross_entropy_with_logits(logit, target, reduction="none")
    p = torch.sigmoid(logit)
    pt = torch.where(target > 0.5, p, 1 - p)
    alpha_t = torch.where(target > 0.5, torch.full_like(target, alpha),
                          torch.full_like(target, 1.0 - alpha))
    return (alpha_t * (1 - pt).pow(gamma) * ce).mean()


def gaussian_nll_2d(d, sigma, eps=1e-6):
    """NLL of residual d ~ N(0, sigma). d [N,2], sigma [N,2,2] SPD."""
    a = sigma[:, 0, 0]; b = sigma[:, 0, 1]; c = sigma[:, 1, 0]; dd = sigma[:, 1, 1]
    det = (a * dd - b * c).clamp_min(eps)
    inv00, inv01, inv10, inv11 = dd / det, -b / det, -c / det, a / det
    dx, dy = d[:, 0], d[:, 1]
    maha = dx * (inv00 * dx + inv01 * dy) + dy * (inv10 * dx + inv11 * dy)
    return (0.5 * (maha + torch.log(det))).mean()


class Stage1HeadLoss(nn.Module):
    """L = lambda_p * present (all ROIs) + lambda_m * m (person ROIs)
    + lambda_s * Sigma (person ROIs with a lamp core)."""

    def __init__(self, lambda_present=2.0, lambda_m=1.0, lambda_sigma=0.5,
                 focal_gamma=2.0, focal_alpha=0.75):
        super().__init__()
        self.lp, self.lm, self.ls = lambda_present, lambda_m, lambda_sigma
        self.focal_gamma, self.focal_alpha = focal_gamma, focal_alpha

    def forward(self, pred, target):
        """target keys: present_gt [N] {0,1}; m_glare_analytic [N];
        m_valid [N] bool (person ROIs); mu_gt [N,2], mu_analytic [N,2];
        sigma_valid [N] bool (person ROI with a core)."""
        l_present = focal_bce(pred["present_logit"], target["present_gt"],
                              gamma=self.focal_gamma, alpha=self.focal_alpha)
        mvalid = target.get("m_valid")
        if mvalid is not None and mvalid.any():
            l_m = F.smooth_l1_loss(pred["m_glare"][mvalid], target["m_glare_analytic"][mvalid])
        else:
            l_m = pred["m_glare"].sum() * 0.0
        svalid = target.get("sigma_valid")
        if svalid is not None and svalid.any():
            d = (target["mu_gt"] - target["mu_analytic"])[svalid]
            l_sigma = gaussian_nll_2d(d, pred["sigma"][svalid])
        else:
            l_sigma = pred["sigma"].sum() * 0.0
        total = self.lp * l_present + self.lm * l_m + self.ls * l_sigma
        return {"total": total, "L_present": l_present, "L_m": l_m, "L_sigma": l_sigma}
