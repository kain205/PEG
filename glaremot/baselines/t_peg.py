"""PEG (this repo, glaremot/tracking/beacon_tracker.py) on the shared YOLOX detection cache.

The tracker is PEG's own code, unchanged, at the paper setting: run with GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0
(asserted below; both are read at import time). Only the perception front-end is replaced, because the YOLOX boxes do
not come with PEG's learned head (h_psi reads YOLO11m P3 features):
  dets      YOLOX rows with score >= 0.25 (PEG's detector conf, eval_mot --conf) after NMS 0.7 (ultralytics default),
            mapped into the S x S letterbox the tracker works in (S = imgsz 1536), as Perception.__call__ writes them;
  m_glare   m_glare_analytic of the box on the letterbox frame (the target h_psi regresses to), from scripts/29;
  present   1.0 (no analytic counterpart; h_psi's presence gate on births/confirmation is therefore off);
  core_frac mean of the 512x512 saturation map inside the box, exactly as Perception.__call__;
  sat map   scripts/29, made exactly as Perception.__call__ (letterbox -> INTER_AREA 512 -> fast_saturation_map),
            served through sat_mask()/core_mask() like CachedPerception, so the burn gate phi is PEG's own.
Rows are written like eval_mot.track_sequence (mot_row on the letterbox, then unletterbox_row to native pixels); PEG's
writer has no aspect / area filter. `needs = ("pegsat",)`: the harness gives extra["sat"] (bool 512x512) and
extra["mg"] (m_glare per det row).
"""
import os

import numpy as np

from glaremot.config import load_config
from glaremot.tracking.tracker import PHOTO_S, fast_core_mask, letterbox_params, mot_row, unletterbox_row

S = int(load_config().imgsz)
CONF = 0.25


class _Percep:
    def __init__(self):
        self.sat, self.core = None, None

    def set(self, sat):
        self.sat, self.core = sat, None

    def sat_mask(self):
        return self.sat, PHOTO_S

    def core_mask(self):
        if self.core is None and self.sat is not None:
            self.core = fast_core_mask(self.sat)
        return self.core, PHOTO_S


class Tracker:
    nms, needs = 0.7, ("pegsat",)

    def __init__(self, fps, hw, seq=None):
        assert os.environ.get("GMOT_TRACKER", "").lower() in ("beacon", "peg"), "run with GMOT_TRACKER=beacon"
        assert os.environ.get("GMOT_BIRTH_SIZE_GUARD") == "0", "paper setting: GMOT_BIRTH_SIZE_GUARD=0"
        from glaremot.eval.eval_mot import make_tracker
        self.t = make_tracker()
        self.p = _Percep()
        self.t.attach_perception(self.p)
        self.H, self.W = hw
        self.lb = letterbox_params(self.H, self.W, S)
        self.fi = 0

    def step(self, dets, extra):
        self.fi += 1
        sat = extra["sat"]
        self.p.set(sat)
        keep = dets[:, 4] >= CONF
        d, mg = dets[keep], extra["mg"][keep]
        ps = PHOTO_S / float(S)
        out = []
        for (x1, y1, x2, y2, sc), m in zip(d, mg):
            if self.lb is not None:
                s, px, py = self.lb[:3]
                x1, y1, x2, y2 = x1 * s + px, y1 * s + py, x2 * s + px, y2 * s + py
            ix1, iy1 = max(0, int(x1 * ps)), max(0, int(y1 * ps))
            ix2, iy2 = min(PHOTO_S, int(x2 * ps) + 1), min(PHOTO_S, int(y2 * ps) + 1)
            patch = sat[iy1:iy2, ix1:ix2]
            out.append({
                "box": np.array([((x1 + x2) * 0.5) / S, ((y1 + y2) * 0.5) / S,
                                 max(1.0, x2 - x1) / S, max(1.0, y2 - y1) / S], np.float32),
                "xyxy_s": np.array([x1, y1, x2, y2], np.float32),
                "conf": float(sc), "m_glare": float(np.clip(m, 0.0, 1.0)), "present": 1.0,
                "core_frac": float(patch.mean()) if patch.size else 0.0, "appearance": None,
            })
        res = []
        for t in self.t.step(out, S, S, self.fi, core_fn=self.p.core_mask):
            row = mot_row(self.fi, t.id, t.out_box(), S, S, max(t.m, 0.001))
            if self.lb is not None:
                row = unletterbox_row(row, self.lb, self.W, self.H)
            p = row.split(",")
            res.append((int(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[5])))
        return res
