"""Step 04 — Train the h_psi head on the cached frozen-backbone ROI features.

Run scripts/02 first. The head is tiny and the cache lives on the GPU, so this
trains in seconds per epoch. Reports ``present`` P/R/F1/AP, ``m_glare`` MAE
and beacon Sigma NLL on the val split; with ``--hardneg`` (after step 03) the
mined lamp blobs join training and the lamp false-positive rate is reported —
checkpoint selection then uses F1 − 0.5·lamp_fp, because a head that keeps F1
but still fires on lamps is exactly the failure the retrain must fix.

Run:  python scripts/04_train_hpsi.py [--hardneg]
"""
import argparse
import glob as _glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import torch

from glaremot.config import cache_dir, load_config, weight_path
from glaremot.perception.h_psi import HybridVisibilityHead, Stage1HeadLoss

KEYS = ("present_gt", "m_glare_analytic", "m_valid", "mu_gt", "mu_analytic", "sigma_valid")


def load_cache(path, device):
    c = torch.load(path, weights_only=False)
    t = {"pooled": c["pooled"].to(device)}
    for k in KEYS:
        t[k] = c[k].to(device)
    return t, c["meta"]


def concat_caches(a, b):
    return {k: torch.cat([a[k], b[k]], 0) for k in a}


def _ap(scores, labels):
    order = np.argsort(-scores)
    tp = np.cumsum(labels[order]); fp = np.cumsum(1 - labels[order])
    rec = tp / max(1, labels.sum()); prec = tp / np.maximum(1, tp + fp)
    mrec = np.concatenate([[0], rec, [1]]); mpre = np.concatenate([[0], prec, [0]])
    for i in range(len(mpre) - 1, 0, -1):
        mpre[i - 1] = max(mpre[i - 1], mpre[i])
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


@torch.no_grad()
def evaluate(head, val, crit, n_lamp=0):
    head.eval()
    out = head(val["pooled"])
    losses = crit(out, val)
    p = torch.sigmoid(out["present_logit"]).cpu().numpy()
    y = val["present_gt"].cpu().numpy()
    pred = (p >= 0.5).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / max(1, tp + fp); rec = tp / max(1, tp + fn)
    f1 = 2 * prec * rec / max(1e-9, prec + rec)
    mv = val["m_valid"]
    mae = float((out["m_glare"][mv] - val["m_glare_analytic"][mv]).abs().mean()) if mv.any() else 0.0
    m = {"present_P": prec, "present_R": rec, "present_F1": f1, "present_AP": _ap(p, y),
         "m_MAE": mae, "L_sigma": float(losses["L_sigma"])}
    if n_lamp:
        lamp_p = p[-n_lamp:]
        m["lamp_present_mean"] = float(lamp_p.mean())
        m["lamp_fp_rate"] = float((lamp_p >= 0.5).mean())
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--batch", type=int, default=1024)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--lambda_present", type=float, default=2.0)
    ap.add_argument("--lambda_m", type=float, default=1.0)
    ap.add_argument("--lambda_sigma", type=float, default=0.5)
    ap.add_argument("--focal_alpha", type=float, default=0.75)
    ap.add_argument("--hardneg", action="store_true",
                    help="concat cache_hardneg_*.pt (step 03) into train/val")
    ap.add_argument("--hardneg_repeat", type=int, default=8,
                    help="oversample the mined lamp negatives (they are dilute vs "
                         "env negatives, so give them real gradient share)")
    args = ap.parse_args()

    cfg = load_config(args.config)
    epochs = args.epochs or int(cfg.train.hpsi.epochs)
    cdir = cache_dir(cfg, "hpsi")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    train, meta = load_cache(os.path.join(cdir, "cache_train.pt"), device)
    val, _ = load_cache(os.path.join(cdir, "cache_val.pt"), device)
    n_lamp_val = 0
    if args.hardneg:
        tr_paths = sorted(_glob.glob(os.path.join(cdir, "cache_hardneg_train*.pt")))
        if not tr_paths:
            raise FileNotFoundError("no cache_hardneg_train*.pt — run scripts/03 first")
        for trp in tr_paths:
            hn_tr, hn_meta = load_cache(trp, device)
            assert hn_meta["tap"] == meta["tap"] and hn_meta["imgsz"] == meta["imgsz"]
            for _ in range(max(1, args.hardneg_repeat)):
                train = concat_caches(train, hn_tr)
            vap = trp.replace("cache_hardneg_train", "cache_hardneg_val")
            n_va = 0
            if os.path.exists(vap):
                hn_va, _ = load_cache(vap, device)
                val = concat_caches(val, hn_va)   # lamp rows stay LAST
                n_va = hn_va["pooled"].shape[0]
                n_lamp_val += n_va
            print(f"hard negatives [{os.path.basename(trp)}]: "
                  f"+{hn_tr['pooled'].shape[0]} train x{args.hardneg_repeat}, +{n_va} val")
    n = train["pooled"].shape[0]
    print(f"train ROIs={n} (present1={int((train['present_gt'] > 0.5).sum())}) | "
          f"val ROIs={val['pooled'].shape[0]} | C={meta['in_channels']} device={device}")

    head = HybridVisibilityHead(meta["in_channels"], roi_size=meta["roi_size"]).to(device)
    crit = Stage1HeadLoss(args.lambda_present, args.lambda_m, args.lambda_sigma,
                          focal_alpha=args.focal_alpha)
    opt = torch.optim.AdamW(head.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, epochs)

    best_score, best_state = -1.0, None
    for ep in range(1, epochs + 1):
        head.train()
        perm = torch.randperm(n, device=device)
        for s in range(0, n, args.batch):
            idx = perm[s:s + args.batch]
            sub = {"pooled": train["pooled"][idx]}
            for k in KEYS:
                sub[k] = train[k][idx]
            loss = crit(head(sub["pooled"]), sub)["total"]
            opt.zero_grad(); loss.backward(); opt.step()
        sched.step()
        if ep % 10 == 0 or ep == epochs:
            m = evaluate(head, val, crit, n_lamp=n_lamp_val)
            lamp = (f" | lamp p_mean={m['lamp_present_mean']:.3f} fp={m['lamp_fp_rate']:.3f}"
                    if n_lamp_val else "")
            print(f"ep {ep:3d}  present P={m['present_P']:.3f} R={m['present_R']:.3f} "
                  f"F1={m['present_F1']:.3f} AP={m['present_AP']:.3f} | "
                  f"m_MAE={m['m_MAE']:.3f}{lamp}", flush=True)
            score = m["present_F1"] - 0.5 * m.get("lamp_fp_rate", 0.0)
            if score > best_score:
                best_score = score
                best_state = {k: v.detach().cpu().clone() for k, v in head.state_dict().items()}

    out_path = weight_path(cfg, "hpsi")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    torch.save({"state_dict": best_state, "meta": meta}, out_path)
    print(f"BEST score (F1 - 0.5*lamp_fp)={best_score:.3f}  saved -> {out_path}")


if __name__ == "__main__":
    main()
