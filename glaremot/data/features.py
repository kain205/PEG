"""Box-trajectory feature engineering for the forecaster (HBB, 4-D).

Every regressed dim is a small centred delta relative to the LAST observed
past frame, which matches the flow-matching N(0,1) prior.

Encoder feature per past frame (D = 11):
    [cx_abs, cy_abs, cx_rel, cy_rel, d_cx, d_cy,
     logw, logh, d_logw, d_logh, m]
(10 geometric channels + the confidence m as the last channel.)

Future target per horizon frame (4-D), all relative to the last observed past
frame:
    [cx - cx_last, cy - cy_last, logw - logw_last, logh - logh_last]
Decode anchor is the 4-vector (cx_last, cy_last, logw_last, logh_last).

Train (dataloader) and the inference controller MUST share these functions.
"""
import numpy as np

D_FEAT = 11      # encoder channels (10 geometric + 1 confidence)
BOX_DIM = 4      # (cx, cy, log w, log h)
_EPS = 1e-4


def _safe_log_size(bw, bh):
    return np.log(np.clip(bw, _EPS, None)), np.log(np.clip(bh, _EPS, None))


def build_past_features(cx, cy, bw, bh, m):
    """All inputs shape [T_p]. Returns [T_p, D_FEAT] float32 and the 4-tuple
    decode anchor of the last observed past frame."""
    cx = np.asarray(cx, np.float32); cy = np.asarray(cy, np.float32)
    bw = np.asarray(bw, np.float32); bh = np.asarray(bh, np.float32)
    m = np.asarray(m, np.float32)
    Tp = cx.shape[0]

    logw, logh = _safe_log_size(bw, bh)
    cx_last, cy_last = cx[-1], cy[-1]
    logw_last, logh_last = logw[-1], logh[-1]

    cx_abs = cx - cx.mean()
    cy_abs = cy - cy.mean()
    cx_rel = cx - cx_last
    cy_rel = cy - cy_last

    def _diff(a):
        d = np.zeros(Tp, np.float32); d[1:] = a[1:] - a[:-1]; return d

    feat = np.stack([cx_abs, cy_abs, cx_rel, cy_rel, _diff(cx_rel), _diff(cy_rel),
                     logw, logh, _diff(logw), _diff(logh), m], axis=-1).astype(np.float32)
    anchor = (float(cx_last), float(cy_last), float(logw_last), float(logh_last))
    return feat, anchor


def build_future_target(cx, cy, bw, bh, anchor):
    """All inputs shape [T_f]. anchor = 4-tuple. Returns [T_f, 4] float32 deltas."""
    cx = np.asarray(cx, np.float32); cy = np.asarray(cy, np.float32)
    logw, logh = _safe_log_size(np.asarray(bw, np.float32), np.asarray(bh, np.float32))
    cx_last, cy_last, logw_last, logh_last = anchor
    tgt = np.stack([cx - cx_last, cy - cy_last, logw - logw_last, logh - logh_last], axis=-1)
    return tgt.astype(np.float32)


def decode_future(pred, anchor):
    """Inverse of build_future_target: [T_f,4] deltas -> boxes (cx, cy, bw, bh)
    in normalized coords."""
    pred = np.asarray(pred, np.float32).reshape(-1, BOX_DIM)
    cx_last, cy_last, logw_last, logh_last = anchor
    cx = pred[:, 0] + cx_last
    cy = pred[:, 1] + cy_last
    bw = np.exp(pred[:, 2] + logw_last)
    bh = np.exp(pred[:, 3] + logh_last)
    return np.stack([cx, cy, bw, bh], axis=-1)


def apply_online_history(cx, cy, bw, bh, m, rng,
                         ema=0.65, sigma_pos=0.002, sigma_size=0.05,
                         p_drag=0.5, drag_min=0.15, drag_max=0.5):
    """Domain-adaptation augmentation: make a clean GT PAST look like the
    ONLINE history the tracker actually feeds the forecaster at inference
    (the tracker pushes the EMA-smoothed fused Kalman state into its history):
      1. detector jitter on centre/size, amplified where m is low (near glare),
      2. weak-update drag: in a random low-trust segment the fused state only
         moves a fraction of the way toward each new measurement (R ~ 1/m),
      3. the tracker's causal EMA smoothing (lag).
    The future target stays clean GT. Returns new arrays."""
    cx = cx.copy(); cy = cy.copy(); bw = bw.copy(); bh = bh.copy(); m = m.copy()
    Tp = cx.shape[0]
    amp = (1.0 + 2.0 * (1.0 - np.clip(m, 0.0, 1.0))).astype(np.float32)
    cx += rng.normal(0.0, sigma_pos, Tp).astype(np.float32) * amp
    cy += rng.normal(0.0, sigma_pos, Tp).astype(np.float32) * amp
    bw *= np.exp(rng.normal(0.0, sigma_size, Tp).astype(np.float32) * amp)
    bh *= np.exp(rng.normal(0.0, sigma_size, Tp).astype(np.float32) * amp)
    if Tp >= 4 and rng.random() < p_drag:
        s = int(rng.integers(1, Tp - 1))
        L = int(rng.integers(2, Tp - s + 1))
        g = float(rng.uniform(drag_min, drag_max))
        for t in range(s, min(s + L, Tp)):
            cx[t] = cx[t - 1] + g * (cx[t] - cx[t - 1])
            cy[t] = cy[t - 1] + g * (cy[t] - cy[t - 1])
            bw[t] = bw[t - 1] + g * (bw[t] - bw[t - 1])
            bh[t] = bh[t - 1] + g * (bh[t] - bh[t - 1])
            m[t] = min(float(m[t]), g)
    for t in range(1, Tp):
        cx[t] = ema * cx[t - 1] + (1.0 - ema) * cx[t]
        cy[t] = ema * cy[t - 1] + (1.0 - ema) * cy[t]
        bw[t] = ema * bw[t - 1] + (1.0 - ema) * bw[t]
        bh[t] = ema * bh[t - 1] + (1.0 - ema) * bh[t]
    return cx, cy, bw, bh, m


def apply_occlusion_block(cx, cy, bw, bh, m, start, length, gamma=0.85, m_cap=0.5):
    """Scheduled-sampling occlusion: replace a past block [start, start+length)
    with constant-velocity imputation from the last clean anchor and decay
    m = gamma**age (capped at m_cap). Returns new arrays."""
    cx = cx.copy(); cy = cy.copy(); bw = bw.copy(); bh = bh.copy(); m = m.copy()
    Tp = cx.shape[0]
    end = min(start + length, Tp)
    if start <= 0 or start >= Tp:
        return cx, cy, bw, bh, m

    a = start - 1                      # last clean anchor index
    if a >= 1:
        vx, vy = cx[a] - cx[a - 1], cy[a] - cy[a - 1]
        vlw = np.log(max(bw[a], _EPS)) - np.log(max(bw[a - 1], _EPS))
        vlh = np.log(max(bh[a], _EPS)) - np.log(max(bh[a - 1], _EPS))
    else:
        vx = vy = vlw = vlh = 0.0
    la = np.log(max(bw[a], _EPS)); lha = np.log(max(bh[a], _EPS))
    for k, t in enumerate(range(start, end), start=1):
        cx[t] = cx[a] + k * vx
        cy[t] = cy[a] + k * vy
        bw[t] = float(np.exp(la + k * vlw))
        bh[t] = float(np.exp(lha + k * vlh))
        m[t] = min(m_cap, gamma ** k)
    return cx, cy, bw, bh, m
