"""BoT-SORT (NirAharon/BoT-SORT @ 2519854, tracker/bot_sort.py BoTSORT) on the shared cache, with ReID.

Settings = tools/track.py with --default-parameters --with-reid for MOT17 (track.py:320-357, argparse :49-65),
without its per-sequence hacks: track_high_thresh 0.6, track_low_thresh 0.1, new_track_thresh 0.7, track_buffer 30,
match_thresh 0.8, proximity_thresh 0.5, appearance_thresh 0.25, mot20 False, BoTSORT(args, frame_rate=30) (args.fps
= 30, track.py:311), output filter aspect 1.6 and min_box_area 10 (track.py:55, :182). Detector NMS 0.7 (YOLOX exp).
The tracker's own code runs unmodified; only its two image-reading members are swapped for cached values:
  encoder.inference(img, dets) -> the cached FastReID MOT20 SBS-S50 embeddings of exactly those dets (BoT-SORT embeds
      only the high-score dets; the cache holds all, so we look the rows up),
  gmc.apply(img, dets) -> the cached sparseOptFlow matrix of this frame (the default --cmc-method is "file", i.e.
      VidStab GMC files that exist only for MOT17/MOT20; sparseOptFlow is BoT-SORT's own python method).
"""
import sys
import types
from types import SimpleNamespace

import numpy as np

from glaremot.baselines.adapters import _repo_import, keep_box


class _Encoder:
    def __init__(self):
        self.boxes = self.emb = None

    def inference(self, img, dets):
        if dets is None or np.size(dets) == 0:
            return []
        out = np.zeros((len(dets), self.emb.shape[1]), np.float64)
        for k, d in enumerate(np.asarray(dets)[:, :4]):
            j = int(np.argmin(np.abs(self.boxes - d).sum(1)))
            assert np.abs(self.boxes[j] - d).sum() < 1e-3, "det not found in the cached rows"
            out[k] = self.emb[j]
        return out


class _GMC:
    H = np.eye(2, 3)

    def apply(self, img, dets=None):
        return self.H


class Tracker:
    nms, needs = 0.7, ("emb", "gmc")

    def __init__(self, fps, hw, seq=None):
        if "fast_reid.fast_reid_interfece" not in sys.modules:       # heavy fastreid import, not needed here
            for name in ("fast_reid", "fast_reid.fast_reid_interfece"):
                sys.modules[name] = types.ModuleType(name)
            sys.modules["fast_reid.fast_reid_interfece"].FastReIDInterface = None
        bs = _repo_import("BoT-SORT", "tracker.bot_sort", pkg="tracker")
        self.args = SimpleNamespace(track_high_thresh=0.6, track_low_thresh=0.1, new_track_thresh=0.7,
                                    track_buffer=30, match_thresh=0.8, proximity_thresh=0.5, appearance_thresh=0.25,
                                    with_reid=False, cmc_method="none", name=seq, ablation=False, mot20=False,
                                    min_box_area=10, aspect_ratio_thresh=1.6)
        self.t = bs.BoTSORT(self.args, frame_rate=30)
        self.args.with_reid = True                       # after __init__, so it does not build FastReIDInterface
        self.t.encoder, self.t.gmc = _Encoder(), _GMC()

    def step(self, dets, extra):
        self.t.encoder.boxes, self.t.encoder.emb = dets[:, :4], extra["emb"]
        self.t.gmc.H = extra["gmc"].astype(np.float64)
        out = []
        for t in self.t.update(dets.astype(np.float64), None):
            if keep_box(t.tlwh, self.args.min_box_area):
                out.append((t.track_id, *t.tlwh))
        return out
