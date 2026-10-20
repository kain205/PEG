r"""PEG -- a Photometric Emission Gate for tracking through sensor saturation.

When a helmet lamp points into a fixed mine camera it saturates the sensor and erases
the body in place: the detector returns nothing and the track is dropped. A
constant-velocity Kalman coast still predicts the near-static body, but a *blind* coast
cannot tell a worker who is **burnt** (still there, washed out) from one who has
**departed**, so it recovers burns only at a heavy false-positive cost. PEG decides this
from the destroying signal itself -- the fraction of the predicted body box that is
photometrically saturated -- and emits the coasting box only while that fraction is high.

The decision (the contribution). For a lost confirmed track with predicted body box
``b_t`` and saturated set ``Omega_t``, form the burn fraction
``phi_t = |Omega_t ∩ b_t| / |b_t|``. A brief miss (up to a short floor ``COAST_FLOOR``)
is bridged as in any tracker; once a track has been unmatched longer than that, its
coasting box is emitted iff ``phi_t >= h`` (re-evaluated each frame, with a short grace
window). This single analytic threshold -- no learning, no appearance model -- replaces
the blind fixed-age coast: the destroying signal itself decides which coasts are worth
holding, recovering burnt workers at far fewer false positives.

Refinements that do not help (opt-in, default OFF; see the ablation): a matched-filter
headlamp confirmation, a CUSUM sequential test, and an NIS spatial gate. The synthetic
burns saturate the whole body, so ``phi_t`` alone is already decisive.

The backbone is the glare-aware OC-SORT tracker (``GlareAwareTracker``): a shared
detector + a learned visibility head gate birth/confirmation/re-entry so glare artefacts
do not spawn identities. PEG overrides only the survival/emission layer (``_try_beacon``,
``step``); association, birth and the Kalman coast are inherited unchanged.

Env knobs (all optional; defaults reproduce the deployed PEG):
  GMOT_TRACKER=beacon         select PEG in the eval harness
  GBEACON_CUSUM_H             gate threshold h (default 0.40)
  GBEACON_COAST_FLOOR         brief-miss floor delta (default 3 frames)
  GBEACON_EMIT_TTL            emission grace window (default 5 frames)
  GBEACON_MF_CONFIRM=1        opt-in matched-filter headlamp confirmation (does not help)
  GBEACON_CUSUM=1             opt-in CUSUM sequential test (does not help)
  GBEACON_NIS=1               opt-in chi-square innovation gate (does not help)

PEG+ (our extension, default off = the paper's PEG): the gate already knows the worker is
still there; these keep the held box ON the worker.
  GPEG_SIZE_LOCK=1            freeze the coast box size (zero Kalman area velocity; tracker.py)
  GPEG_LAMP_FOLLOW=1          while the gate is armed, nudge the box centre to the lamp
                              (the backbone's weak lamp pseudo-measurement)

PEG-O (our extension, default off): while the gate is armed, the saturated "burn disc" is
tracked with a disc matched filter; its displacement from an anchor is a centre-only Kalman
pseudo-measurement (odometry), trusted only when the matched-filter peak is sharp.
  GPEG_ODO=1                  enable photometric odometry (use with GPEG_SIZE_LOCK=1)
  GPEG_ODO_TAU                min peak sharpness k to anchor / update (default 0.06)
  GPEG_ODO_GAMMA              trust ratio: centre gain = 1/(1 + gamma*tau/k) (default 1)
  GPEG_ARMED_SURVIVE=1        "S": a confirmed track with the gate armed is not deleted by the
                              allowed_gap() age budget (hard MAX_AGE cap stays; tracker.py)

PEG-C (our extension, default off; docs/PEG_C_PROTOCOL.md): one constant-velocity model, designed. P = the size
lock above (in by design); V, C, S are online, B, BB are FIXED-LAG (they rewrite / add MOT rows up to L frames in
the past; report them separately from online rows).
  GPEG_VEL_K, GPEG_VEL_T      "V": coast-entry velocity = OLS slope (px/frame) of the last K raw detection centres
                              (< K/2 detection frames in the last 2K -> 0; axis zeroed if |v| <= t*SE; speed guard
                              |v| > 0.1*box height -> 0; then the usual 2*median-step ceiling; tracker.py)
  GPEG_CAP                    "C": the gate may arm a track only while time_since_update <= N (0 = off)
  GPEG_STITCH_K               "S": burn-exit stitch; an unmatched would-be-born detection within k*max(w,h) of the
                              predicted box of a track whose gate armed <= 10 frames ago re-acquires it (1:1 only)
  GPEG_BACKFILL_L, _MODE      "B": backfill the gap of a burn-armed track re-acquired after M <= L missed frames
                              (linear interpolation of the two detection boxes); MODE hidden (add rows only where
                              the id has none) | all (also replace emitted coast boxes)
  GPEG_BACKBIRTH=1            "BB": a track burnt at birth gets rows for its tentative detections and a frozen
                              birth box backwards while phi >= h (at most L = GPEG_BACKFILL_L or 90 frames)
  GPEG_F_STATS=1 prints per-seq counters pegc_* (vel_set/vel_zero, cap_block, stitch, backfill_*, bb_*).

PEG-F (friend's methods; default off, GPEG_F=1 turns on all; an individual var overrides):
  GBEACON_DYNAMIC_H           M3: gate threshold h grows with the loss gap (wall-flare FPs)
  GBEACON_ADAPTIVE_TTL        M3: emit grace window scaled by the burn-evidence strength
  GBEACON_ANCHOR              M5: headlamp centroid pulls the coast box (posture change / turns)
  (M1/M2/M4: GMOT_ADAPTIVE_MOTION / GMOT_REID / GMOT_DORMANT, see tracker.py)
"""
import os

import cv2
import numpy as np

from ..photometric import core_centroid_in_box, mask_area_inside
from .tracker import (BACKBIRTH, BACKFILL_L, BEACON_EXPAND_UP, BEACON_GATE_FRAC,
                      BEACON_HEAD_BAND, BEACON_MIN_PX, FS, OUTPUT_MAX_GAP,
                      GlareAwareTracker, armed_survives, backfill_lag, norm_box_to_xyxy,
                      peg_f_flag, smooth_box, xyxy_to_norm_box)


def _flag(name, default="1"):
    return os.environ.get(name, default) not in ("0", "off", "false", "")


# --- PEG parameters (env-tunable) ------------------------------------
# The core method is the analytic saturation gate (phi threshold). The matched-filter
# headlamp confirmation, the CUSUM sequential test, and the NIS spatial gate are
# OPT-IN refinements (default off): the ablation shows they do not improve the simple
# gate on smooth synthetic burns, so the deployed tracker is the simple gate.
LAMP_ENABLE = _flag("GBEACON_LAMP")              # master switch (0 -> plain coast)
MF_CONFIRM = _flag("GBEACON_MF_CONFIRM", "0")    # require a matched-filter headlamp core
MF_ENABLE = _flag("GBEACON_MF")                  # matched filter vs plain centroid (if confirming)
CUSUM_ENABLE = _flag("GBEACON_CUSUM", "0")       # sequential test vs instantaneous phi
NIS_ENABLE = _flag("GBEACON_NIS", "0")           # spatial innovation gate on the lamp
LAMP_FOLLOW = _flag("GPEG_LAMP_FOLLOW", "0")     # PEG+: armed gate -> box follows the lamp

# --- PEG-O: photometric odometry (default off) ---
ODO_ENABLE = _flag("GPEG_ODO", "0")
ODO_TAU = float(os.environ.get("GPEG_ODO_TAU", "0.06"))      # min matched-filter peak sharpness
ODO_GAMMA = float(os.environ.get("GPEG_ODO_GAMMA", "1.0"))   # trust ratio (R = gamma*tau/k * P)
ODO_KAPPA = 2.0        # search window = predicted box dilated x kappa
ODO_RHO_MIN = 0.3      # disc radius clip, x min(w,h) of the box (PHOTO_S px)
ODO_RHO_MAX = 1.5      # disc radius clip, x max(w,h)
CAP = int(os.environ.get("GPEG_CAP", "0"))   # PEG-C "C": gate may arm only while gap <= CAP (0 = off)
ODO_JUMP = 0.5         # reject a measurement farther than ODO_JUMP * box diagonal from the box centre


def odo_disc_kernel(r):
    """Normalised filled-disc kernel of radius r (px)."""
    r = max(1, int(round(r)))
    k = np.zeros((2 * r + 1, 2 * r + 1), np.float32)
    cv2.circle(k, (r, r), r, 1, -1)
    return k / k.sum()


def odo_measure(lab, stats, c, w, h, sx, sy, S=512, kappa=ODO_KAPPA):
    """PEG-O estimator (shared by the tracker and scripts/19_peg_o_check.py).

    lab, stats: ``cv2.connectedComponentsWithStats(sat_uint8, 8)`` labels / stats on the SxS
    grid. c = predicted burn centre (full-res px), (w, h) = predicted box size (full-res px),
    sx, sy = grid scale. Returns None or (b_px [x, y] full-res px, rho, peak, kx, ky); the
    sharpness of the peak is min(kx, ky)."""
    cx, cy = int(np.clip(c[0] * sx, 0, S - 1)), int(np.clip(c[1] * sy, 0, S - 1))
    k = lab[cy, cx]
    if k == 0:   # label with the most pixels inside the predicted box
        bx = lab[int((c[1] - h / 2) * sy):int((c[1] + h / 2) * sy),
                 int((c[0] - w / 2) * sx):int((c[0] + w / 2) * sx)]
        ids, cnt = np.unique(bx[bx > 0], return_counts=True)
        if len(ids) == 0:
            return None
        k = ids[np.argmax(cnt)]
    rho = np.sqrt(stats[k, 4] / np.pi)
    rho = float(np.clip(rho, ODO_RHO_MIN * min(w * sx, h * sy), ODO_RHO_MAX * max(w * sx, h * sy)))
    comp = (lab == k).astype(np.float32)
    sc = cv2.filter2D(comp, -1, odo_disc_kernel(rho), borderType=cv2.BORDER_CONSTANT)
    x0, y0 = int((c[0] - kappa * w / 2) * sx), int((c[1] - kappa * h / 2) * sy)
    x1, y1 = int((c[0] + kappa * w / 2) * sx), int((c[1] + kappa * h / 2) * sy)
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(S, x1), min(S, y1)
    win = sc[y0:y1, x0:x1]
    if win.size == 0:
        return None
    iy, ix = np.unravel_index(int(np.argmax(win)), win.shape)
    px, py = ix + x0, iy + y0
    dlt = max(2, int(rho / 4))
    pk = sc[py, px]

    def at(xx, yy):
        return sc[int(np.clip(yy, 0, S - 1)), int(np.clip(xx, 0, S - 1))]

    kx = pk - 0.5 * (at(px + dlt, py) + at(px - dlt, py))
    ky = pk - 0.5 * (at(px, py + dlt) + at(px, py - dlt))
    return np.array([px / sx, py / sy]), rho, pk, kx, ky

MF_SIGMA_FRAC = float(os.environ.get("GBEACON_MF_SIGMA", "0.25"))  # of head-band height
MF_MIN_RESP = float(os.environ.get("GBEACON_MF_MINRESP", "0.05"))  # min matched-filter peak
CUSUM_K = float(os.environ.get("GBEACON_CUSUM_K", "0.20"))   # slack on burn fraction phi
CUSUM_H = float(os.environ.get("GBEACON_CUSUM_H", "0.40"))   # decision threshold
NIS_THR = float(os.environ.get("GBEACON_NIS_THR", "9.21"))   # chi2(2): 9.21 = 99%
BODY_OFFSET = float(os.environ.get("GBEACON_BODY_OFFSET", "0.35"))  # head->body, frac h
WEAK_R_MULT = float(os.environ.get("GBEACON_WEAK_R", "6.0"))  # pre-burn lamp = weak nudge
# lamp-signal-gated emission: a coasting box is emitted past the ordinary output cap
# only while the lamp confirms the worker is still present (and burnt). The grace TTL
# lets a flickering lamp keep the track emitted; once the lamp is gone (the worker has
# left) emission stops within TTL frames, so a blind coast never accrues false
# positives. This is the false-positive control that the bare coast lacks.
EMIT_TTL = int(os.environ.get("GBEACON_EMIT_TTL", "5"))
GATE_EMIT = _flag("GBEACON_GATE_EMIT")  # 0 -> inherit the backbone's fixed output cap
# Evidence-gated coast: the backbone emits *every* confirmed track on pure prediction
# for OUTPUT_MAX_GAP frames after the last observation, regardless of whether a burn
# is actually occurring -- on clean scenes this blind coast is the dominant false
# positive. With COAST_FLOOR < OUTPUT_MAX_GAP, a coasted box older than the floor is
# emitted only when the photometric gate confirms it (phi-armed); a brief miss up to
# the floor is still bridged freely. The gate thus decides which coasts are worth
# keeping, instead of holding all of them blindly. Deployed default = 3 frames: a
# brief miss is bridged freely, anything longer must be photometrically confirmed.
COAST_FLOOR = int(os.environ.get("GBEACON_COAST_FLOOR", "3"))


# --- PEG-F (flags default to GPEG_F, default off) ---
DYNAMIC_H = peg_f_flag("GBEACON_DYNAMIC_H")      # M3: h grows with the gap past COAST_FLOOR
H_DECAY = float(os.environ.get("GBEACON_H_DECAY", "0.06"))
ADAPTIVE_TTL = peg_f_flag("GBEACON_ADAPTIVE_TTL")  # M3: EMIT_TTL scaled by phi / h
ANCHOR_ENABLE = peg_f_flag("GBEACON_ANCHOR")     # M5: headlamp centroid anchoring


def _matched_filter_peak(core_patch, sigma_px):
    """Correlate a binary core patch with a normalized Gaussian template and return
    (peak_xy_subpixel, peak_response). The template encodes the expected compact
    lamp blob, so this is a matched filter; for a normalized kernel the response is
    the local core density in [0,1] (a clutter-robust detection statistic). Returns
    (None, 0.0) on an empty patch."""
    if core_patch.size == 0 or core_patch.sum() == 0:
        return None, 0.0
    sigma = max(1.0, float(sigma_px))
    ksz = int(2 * round(2.0 * sigma) + 1)
    ksz = max(3, ksz)
    g = cv2.getGaussianKernel(ksz, sigma)
    kern = (g @ g.T).astype(np.float32)            # sums to 1 -> response in [0,1]
    resp = cv2.filter2D(core_patch.astype(np.float32), -1, kern,
                        borderType=cv2.BORDER_CONSTANT)
    iy, ix = np.unravel_index(int(np.argmax(resp)), resp.shape)
    peak = float(resp[iy, ix])
    # sub-pixel refine: response-weighted centroid in a 3x3 window about the peak
    y0, y1 = max(0, iy - 1), min(resp.shape[0], iy + 2)
    x0, x1 = max(0, ix - 1), min(resp.shape[1], ix + 2)
    win = resp[y0:y1, x0:x1]
    s = float(win.sum())
    if s > 1e-9:
        ys, xs = np.mgrid[y0:y1, x0:x1]
        cx = float((xs * win).sum() / s)
        cy = float((ys * win).sum() / s)
    else:
        cx, cy = float(ix), float(iy)
    return (cx, cy), peak


class PEG(GlareAwareTracker):
    """Photometric Emission Gate. The glare-aware OC-SORT backbone with the survival
    layer replaced by the photometric emission gate: on a missed frame the coasting
    box is emitted iff the predicted body box is saturated (``phi_t >= h``), past a
    short brief-miss floor.

    Only ``_try_beacon`` and ``step`` are overridden; association, birth, identity
    guards, exit gate and the Kalman coast are inherited unchanged. The opt-in
    matched-filter / CUSUM / NIS refinements (default off) do not improve the gate.
    Per-track gate state is attached lazily to the existing MotionTrack objects."""

    def attach_perception(self, percep):
        """Give the tracker the raw saturation map accessor, so the burn gate can
        measure how much of a predicted body box is photometrically saturated."""
        self._sat_fn = getattr(percep, "sat_mask", None)

    def _body_burn_fraction(self, mt, W, H):
        """Fraction of the predicted body box that is photometrically saturated --
        the analytic burn evidence phi in [0,1]. 0 when the saturation map is
        unavailable, so the gate fails safe to a plain coast."""
        sat_fn = getattr(self, "_sat_fn", None)
        if sat_fn is None:
            return 0.0
        sat, S = sat_fn()
        if sat is None:
            return 0.0
        x1, y1, x2, y2 = [float(v) for v in mt.kf.get_state()[0][:4]]
        sx, sy = S / float(W), S / float(H)
        roi = (x1 * sx, y1 * sy, x2 * sx, y2 * sy)
        area = max(1.0, (x2 - x1) * sx) * max(1.0, (y2 - y1) * sy)
        return mask_area_inside(sat, roi) / area

    def step(self, dets, W, H, frame_idx, core_fn=None):
        """Run the backbone step, then add back any confirmed coasting track that
        the lamp currently confirms (matched-filter + CUSUM, NIS-gated) but that the
        ordinary output cap would have suppressed. Emission is thus driven by an
        active lamp measurement, not by a blind fixed-age coast."""
        self._cur_frame = frame_idx
        if BACKBIRTH:
            self._bb_store_mask(frame_idx)
        outputs = super().step(dets, W, H, frame_idx, core_fn=core_fn)
        if BACKBIRTH:
            self._backbirth(W, H, frame_idx)
        if not (LAMP_ENABLE and GATE_EMIT):
            return outputs
        # evidence-gate the inherited blind coast: past the short floor, keep a
        # coasted box only if the photometric gate confirms a burn for it.
        if COAST_FLOOR < OUTPUT_MAX_GAP:
            outputs = [t for t in outputs
                       if int(t.kf.time_since_update) <= COAST_FLOOR
                       or frame_idx <= getattr(t, "_lamp_emit_until", -1)]
        emitted = {id(t) for t in outputs}
        extra = []
        for t in self.tracks:
            if id(t) in emitted or not t.is_confirmed:
                continue
            gap = int(t.kf.time_since_update)
            if gap > t.allowed_gap() and not armed_survives(t, frame_idx, gap):
                continue
            if frame_idx <= getattr(t, "_lamp_emit_until", -1):
                extra.append(t)
        if extra:
            self._update_vis(outputs + extra, W, H)
        return outputs + extra

    # --- PEG-C BB: backward birth (fixed-lag) -------------------------------- #
    def _bb_store_mask(self, frame_idx):
        """Ring buffer of the last L+2 saturation masks (bit-packed), only when BB is on."""
        hist = getattr(self, "_sat_hist", None)
        if hist is None:
            hist = self._sat_hist = {}
        sat_fn = getattr(self, "_sat_fn", None)
        sat, _ = sat_fn() if sat_fn is not None else (None, None)
        if sat is not None:
            sat = np.asarray(sat).astype(bool)
            hist[frame_idx] = (np.packbits(sat, axis=None), sat.shape)
        for f in [f for f in hist if f <= frame_idx - (backfill_lag() + 2)]:
            del hist[f]

    def _bb_phi(self, box, frame, W, H):
        """Saturated fraction of a normalised box on the mask of `frame`; None if that mask is missing."""
        ent = self._sat_hist.get(frame)
        if ent is None:
            return None
        packed, shape = ent
        sat = np.unpackbits(packed, count=shape[0] * shape[1]).reshape(shape)
        S = shape[0]
        x1, y1, x2, y2 = [float(v) for v in norm_box_to_xyxy(box, W, H)]
        sx, sy = S / float(W), S / float(H)
        roi = (x1 * sx, y1 * sy, x2 * sx, y2 * sy)
        area = max(1.0, (x2 - x1) * sx) * max(1.0, (y2 - y1) * sy)
        return mask_area_inside(sat, roi) / area

    def _backbirth(self, W, H, f_c):
        """A track that has just become confirmed and whose birth box was burnt at birth: emit its
        tentative detection boxes and a frozen birth box backwards while phi(birth box) >= h."""
        Lbb = backfill_lag()
        for t in self.tracks:
            if not t.is_confirmed or getattr(t, "_bb_seen", False):
                continue
            t._bb_seen = True
            f_b = t.birth_frame
            phi_b = self._bb_phi(t.birth_box, f_b, W, H)
            if phi_b is None or phi_b < CUSUM_H:
                continue
            n = 0
            for f, b in t._tent_boxes:
                if f < f_c:
                    self.backfill_records.append((int(t.id), f, b.copy(), False))
                    n += 1
            for f in range(f_b - 1, max(1, f_c - Lbb) - 1, -1):
                phi = self._bb_phi(t.birth_box, f, W, H)
                if phi is None or phi < CUSUM_H:
                    break
                self.backfill_records.append((int(t.id), f, t.birth_box.copy(), False))
                n += 1
            if FS.on:
                FS.inc("pegc_bb_tracks")
                FS.inc("pegc_bb_frames", n)

    def _lamp_localize(self, core, roi, sx, sy):
        """Locate the lamp inside the head-band ROI (PHOTO_S coords). Returns
        (u_frame, v_frame, response) or (None, None, 0.0). Matched filter when
        enabled, else the largest-core centroid (the backbone primitive)."""
        rx1, ry1, rx2, ry2 = [int(round(v)) for v in roi]
        H, W = core.shape[:2]
        rx1, ry1 = max(0, rx1), max(0, ry1)
        rx2, ry2 = min(W, rx2), min(H, ry2)
        if rx2 <= rx1 or ry2 <= ry1:
            return None, None, 0.0
        if MF_ENABLE:
            patch = core[ry1:ry2, rx1:rx2]
            sigma = MF_SIGMA_FRAC * max(1.0, (ry2 - ry1))
            pk, resp = _matched_filter_peak(patch, sigma)
            if pk is None:
                return None, None, 0.0
            u = (pk[0] + rx1) / sx
            v = (pk[1] + ry1) / sy
            return u, v, resp
        # ablation: plain core centroid, response = core density in the ROI
        mu = core_centroid_in_box(core, roi)
        if mu is None:
            return None, None, 0.0
        area = max(1.0, (rx2 - rx1) * (ry2 - ry1))
        resp = mask_area_inside(core, roi) / area
        return float(mu[0]) / sx, float(mu[1]) / sy, float(resp)

    @staticmethod
    def _nis_center(kfin, zx, zy, r_x, r_y):
        """Normalized innovation squared of a centre pseudo-measurement against the
        Kalman prediction (2-DoF chi-square statistic)."""
        Hm = kfin.H[:2, :]
        z = np.array([[zx], [zy]], np.float64)
        y = z - Hm @ kfin.x
        S = Hm @ kfin.P @ Hm.T + np.diag([r_x, r_y])
        try:
            return float((y.T @ np.linalg.inv(S) @ y)[0, 0])
        except np.linalg.LinAlgError:
            return float("inf")

    def _odo_cc(self):
        """Connected components (lab, stats) of the current frame's saturation mask, computed
        once per frame. None if there is no saturation map."""
        cache = getattr(self, "_odo_cc_cache", None)
        if cache is not None and cache[0] == self._cur_frame:
            return cache[1], cache[2]
        sat_fn = getattr(self, "_sat_fn", None)
        if sat_fn is None:
            return None
        sat, S = sat_fn()
        if sat is None:
            return None
        _, lab, stats, _ = cv2.connectedComponentsWithStats(np.asarray(sat).astype(np.uint8), 8)
        self._odo_cc_cache = (self._cur_frame, lab, stats)
        return lab, stats

    def _odometry_update(self, mt, W, H):
        """PEG-O: while the gate is armed, measure the displacement of the saturated burn disc
        (disc matched filter, odo_measure) from an anchor and fuse it as a centre-only Kalman
        pseudo-measurement with covariance scaled by the peak sharpness. Size is not touched."""
        cc = self._odo_cc()
        if cc is None:
            return
        lab, stats = cc
        S = lab.shape[0]
        x1, y1, x2, y2 = [float(v) for v in mt.kf.get_state()[0][:4]]
        w, h = x2 - x1, y2 - y1
        c = np.array([(x1 + x2) * 0.5, (y1 + y2) * 0.5], np.float64)
        sx, sy = S / float(W), S / float(H)
        anc = getattr(mt, "_odo_anchor", None)          # (c_anchor, b_anchor) or None
        p = c + (anc[1] - anc[0]) if anc is not None else c   # predicted burn centre
        r = odo_measure(lab, stats, p, w, h, sx, sy, S)
        if r is None:
            return
        b, rho, pk, kx, ky = r
        k = min(kx, ky)
        mt._odo_k = float(k)
        if k < ODO_TAU:
            if FS.on:
                FS.inc("odo_flat")
            return
        if anc is None:
            anc = mt._odo_anchor = (c.copy(), b.copy())
            if FS.on:
                FS.inc("odo_anchors")
        z = anc[0] + (b - anc[1])
        if float(np.hypot(*(z - c))) > ODO_JUMP * float(np.hypot(w, h)):
            return
        P = mt.kf.kf.P
        r_x = max(1e-6, ODO_GAMMA * (ODO_TAU / kx) * float(P[0, 0]))   # relative R: gain = 1/(1+gamma*tau/k)
        r_y = max(1e-6, ODO_GAMMA * (ODO_TAU / ky) * float(P[1, 1]))
        self._weak_center_update(mt.kf.kf, z[0], z[1], r_x, r_y)
        mt._odo_z = (float(z[0]), float(z[1]))
        if FS.on:
            FS.inc("odo_updates")
        mt.box = xyxy_to_norm_box(mt.kf.get_state()[0], W, H)
        mt.smooth = smooth_box(mt.smooth, mt.box)
        mt.beacon = (b[0] * sx, b[1] * sy)             # PHOTO_S coords, like M5

    def _try_beacon(self, mt, core_fn, W, H):
        """Burnt-vs-departed detection gate (overrides the backbone's weak beacon).

        The lamp/saturation is used as a DETECTION signal, not a position
        measurement: the body box stays on the Kalman coast (which already
        localizes a near-stationary burnt worker), and this routine only decides
        WHETHER a missed frame is a recoverable burn (keep emitting) or a true
        departure/occlusion (stop). Pipeline:
          1. burn evidence phi = saturated fraction of the predicted body box;
          2. CUSUM sequential test on phi -> burn state;
          3. matched-filter confirmation that a compact HEADLAMP core sits in the
             predicted head band (so a neighbour's burn or a bright background does
             not extend this track), with an optional NIS spatial gate;
          4. arm the emission grace window. The Kalman state is left untouched.

        Returns True if a confirmed burn is detected for this track."""
        if not LAMP_ENABLE:
            return False
        x1, y1, x2, y2 = [float(v) for v in mt.kf.get_state()[0][:4]]
        bw, bh = x2 - x1, y2 - y1
        if bw <= 1 or bh <= 1:
            return False

        # --- (1) analytic burn evidence + (2) CUSUM sequential test --------- #
        phi = self._body_burn_fraction(mt, W, H)
        mt._phi = phi                      # kept for the failure-analysis diag dump
        gap = int(mt.kf.time_since_update)
        if gap <= 1:                       # first missing frame of a new loss episode
            mt._cusum_g = 0.0
            mt._burn = False
            mt._odo_anchor = None
        if CAP > 0 and gap > CAP:          # PEG-C "C": a coast this old is not licensed any more
            if FS.on:
                FS.inc("pegc_cap_block")
            return False
        g = getattr(mt, "_cusum_g", 0.0) + (phi - CUSUM_K)
        mt._cusum_g = float(max(0.0, g))
        eff_h = CUSUM_H
        if DYNAMIC_H and gap > COAST_FLOOR:
            # PEG-F M3: scale the threshold with the gap to suppress persistent wall-flare FPs
            eff_h = min(0.65, CUSUM_H * (1.0 + H_DECAY * (gap - COAST_FLOOR)))
        if mt._cusum_g > eff_h:
            mt._burn = True
        burn = mt._burn if CUSUM_ENABLE else (phi >= eff_h)
        if FS.on:
            FS.inc("gate_evals")
            if burn:
                FS.inc("gate_burn_frames")
            if DYNAMIC_H and eff_h > CUSUM_H:
                FS.inc("m3_frames_eff_h_gt_base")
                if (not CUSUM_ENABLE) and phi >= CUSUM_H and not burn:
                    FS.inc("m3_burn_flipped_false")
                    FS.event(t="m3_flip", f=self._cur_frame, tid=mt.id, gap=gap, phi=round(float(phi), 3),
                             eff_h=round(float(eff_h), 3))
        if not burn:
            return False

        # --- (3) optional matched-filter headlamp confirmation -------------- #
        # Off by default: requiring a compact lamp core in the head band does not
        # improve the simple gate on smooth synthetic burns (see ablation), and can
        # reject a genuine burn whose core is not compact. Enable to disambiguate
        # close workers / reject a bright background.
        if MF_CONFIRM:
            core, S = core_fn()
            if core is None:
                return False
            sx, sy = S / float(W), S / float(H)
            roi = ((x1 - 0.10 * bw) * sx, (y1 - BEACON_EXPAND_UP * bh) * sy,
                   (x2 + 0.10 * bw) * sx, (y1 + BEACON_HEAD_BAND * bh) * sy)
            if mask_area_inside(core, roi) < BEACON_MIN_PX:
                return False
            u, v, resp = self._lamp_localize(core, roi, sx, sy)
            if u is None or resp < MF_MIN_RESP:
                return False
            if NIS_ENABLE:
                zx, zy = u, v + BODY_OFFSET * bh
                r_x = max(25.0, (0.08 * bh) ** 2)
                if self._nis_center(mt.kf.kf, zx, zy, r_x, 4.0 * r_x) > NIS_THR:
                    return False
            mt.beacon = (u * sx, v * sy)   # PHOTO_S coords, for drawing

        # PEG-F M5: headlamp centroid anchoring (prevents box drift on posture change / turns)
        if ANCHOR_ENABLE and core_fn is not None and not MF_CONFIRM:
            core, S = core_fn()
            if core is not None:
                sx, sy = S / float(W), S / float(H)
                roi = ((x1 - 0.10 * bw) * sx, (y1 - BEACON_EXPAND_UP * bh) * sy,
                       (x2 + 0.10 * bw) * sx, (y1 + BEACON_HEAD_BAND * bh) * sy)
                if mask_area_inside(core, roi) >= BEACON_MIN_PX:
                    mu = core_centroid_in_box(core, roi)
                    if mu is not None:
                        u, v = float(mu[0]) / sx, float(mu[1]) / sy
                        zx, zy = u, v + BODY_OFFSET * bh
                        pcx, pcy = (x1 + x2) * 0.5, (y1 + y2) * 0.5
                        if float(np.hypot(zx - pcx, zy - pcy)) <= BEACON_GATE_FRAC * float(np.hypot(bw, bh)):
                            r_x = WEAK_R_MULT * max(25.0, (0.08 * bh) ** 2)
                            r_y = 4.0 * r_x
                            self._weak_center_update(mt.kf.kf, zx, zy, r_x, r_y)
                            if FS.on:
                                FS.inc("m5_anchor_updates")
                            mt.box = xyxy_to_norm_box(mt.kf.get_state()[0], W, H)
                            mt.smooth = smooth_box(mt.smooth, mt.box)
                            mt.beacon = (u * sx, v * sy)

        # PEG+: the lamp that burns the worker also marks where they are -- reuse the
        # backbone's weak lamp-centre update so the held box follows a moving worker.
        if LAMP_FOLLOW and core_fn is not None:
            GlareAwareTracker._try_beacon(self, mt, core_fn, W, H)

        # PEG-O: photometric odometry -- the burn disc's displacement moves the held box.
        if ODO_ENABLE:
            self._odometry_update(mt, W, H)

        # A confirmed burn licenses emitting the coasting box past the ordinary
        # output cap (see step()): arm the grace window.
        cur_ttl = EMIT_TTL
        if ADAPTIVE_TTL:
            # PEG-F M3: scale the grace window by the burn-evidence strength
            phi_ratio = min(1.0, max(0.4, float(phi) / max(0.5, eff_h)))
            cur_ttl = max(1, int(round(EMIT_TTL * phi_ratio)))
        if FS.on and ADAPTIVE_TTL:
            FS.inc("m3_ttl_evals")
            if cur_ttl < EMIT_TTL:
                FS.inc("m3_ttl_shortened")
                FS.inc("m3_ttl_frames_removed", EMIT_TTL - cur_ttl)
        mt._lamp_emit_until = self._cur_frame + cur_ttl
        mt._armed_frame = self._cur_frame      # PEG-C: last frame the gate armed (S, B)
        return True

    @staticmethod
    def _cusum_decay(mt):
        """No lamp this frame: relax the CUSUM accumulator toward the no-burn state."""
        g = getattr(mt, "_cusum_g", 0.0) - CUSUM_K
        mt._cusum_g = float(max(0.0, g))
        if mt._cusum_g <= 0.0:
            mt._burn = False
