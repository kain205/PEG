"""ExSORT (minhdq245/exsort @ 0c25ef3, Minh's method) on the shared YOLOX detection cache.

Runs the released tracker unchanged with its frozen configs/selected.json (Bayesian-tuned on val by its author, on
the GT snapshot of 2026-10-28/29; not re-tuned here). Fed exactly like its runner (exsort/runner.py:55-75):
  dets  its cache protocol (exsort/cache.py:159, :196): score floor 0.001, NMS 0.65, top 100 per frame. We re-run NMS
        0.65 on our det_nms0.95 rows (score >= 0.1; the config only uses score >= min(DET, LOW) = 0.101, and a box at
        >= 0.1 can only be suppressed by higher-scoring boxes, so the missing 0.001-0.1 boxes change nothing) and keep
        the top 100; rows below min(DET, LOW) are dropped; box = normalised cx, cy, w, h of the native frame.
  sat   its saturation mask (exsort/cache.py:77-79: original frame stretched to 512x512, V >= 235, S <= 89), made by
        scripts/29 --kind exsort.
Output as its runner writes: Kalman posterior / emitted prediction via out_box(), clipped like runner.py:70-74.
"""
import json
import os
import sys

import numpy as np

from glaremot.baselines import adapters

ROOT = os.environ.get("EXSORT_ROOT") or os.path.join(adapters.REPOS, "exsort")   # another checkout, e.g. b2bca1b
COAST = os.environ.get("EXSORT_COAST")       # override COAST_MODE: budget (0c25ef3) | fps_budget (b2bca1b) | none
TAU = os.environ.get("EXSORT_TAU")           # output filter: emit a box only if frames since last high match <= TAU


class Tracker:
    nms, needs = 0.65, ("exsat",)

    def __init__(self, fps, hw, seq=None):
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from exsort.api import create_tracker
        from exsort.geometry import norm_box_to_xyxy
        self.cfg = json.load(open(os.path.join(ROOT, "configs", "selected.json"), encoding="utf8"))
        if COAST:
            self.cfg["params"]["COAST_MODE"] = COAST
        self.floor = min(self.cfg["params"]["DET"], self.cfg["params"]["LOW"])
        fps_kw = {"fps": float(fps)} if self.cfg["params"]["COAST_MODE"] == "fps_budget" else {}
        self.t = create_tracker(self.cfg, **fps_kw)   # one config per process (module globals), as documented
        self.H, self.W = hw
        self.to_xyxy = norm_box_to_xyxy
        self.k = 0

    def step(self, dets, extra):
        self.k += 1
        d = dets[np.argsort(-dets[:, 4], kind="stable")[:100]] if len(dets) else dets   # cache cap: top 100
        rows = [dict(box=np.array([(x1 + x2) / 2 / self.W, (y1 + y2) / 2 / self.H, (x2 - x1) / self.W,
                                   (y2 - y1) / self.H], np.float32), conf=float(sc))
                for x1, y1, x2, y2, sc in d if sc >= self.floor]
        out = []
        for tr in self.t.step(rows, self.W, self.H, self.k, sat=extra["sat"]):
            if TAU is not None and tr.since_high > int(TAU):
                continue
            x1, y1, x2, y2 = self.to_xyxy(tr.out_box(), self.W, self.H)
            out.append((tr.id, max(0., x1), max(0., y1), max(1., x2 - x1), max(1., y2 - y1)))
        return out
