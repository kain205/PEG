"""TrackTrack (kamkyu94/TrackTrack, CVPR 2025, commit ee7f1c5) on our cached detections, ReID embeddings and GMC.

Runs the OFFICIAL `3. Tracker/trackers/tracker.py::Tracker` unmodified (online, raw result, no gb_interpolation, no
per-sequence hacks). Parameters = MOT17 default (else) branch of run.py + utils/etc.py::set_parameters, verified
in the clone ("3. Tracker/"):
    det_thr      0.60   utils/etc.py:29   (else branch of the '01/03/12' / '07' / '14' per-sequence switch, lines 22-29;
                                           our seq names contain such digits, so the switch is NOT applied)
    init_thr     0.70   utils/etc.py:29
    match_thr    0.70   utils/etc.py:30
    min_len      3      run.py:25
    min_box_area 100    run.py:26
    penalty_p    0.20   run.py:28
    penalty_q    0.40   run.py:29
    reduce_step  0.05   run.py:30
    tai_thr      0.55   run.py:31
    max_time_lost = 2 * frameRate   run.py:47 (frameRate read from seqinfo.ini); we use 2 * our integer fps
                                    (e.g. 25 -> 50), the run.py default of 30 is overwritten there as well.
    data_path    "MOT17/test/"  only used through `'Dance' in data_path` (trackers/track.py:92, False for MOT) and
                                `'MOT' in data_path` (run.py:72, aspect filter on)
Inputs (what 2. FastReID/ext_feats.py:63 writes and trackers/track.py:54-66 reads): per frame an array
[x1, y1, x2, y2, score, class, feat(2048)] float32; class = 0 (single person class; det_evaluator.py:52-54 puts the
class prediction there, `Track` never reads it). `update(dets, dets_95)`: dets = the det_nms0.8 rows (+ emb08),
dets_95 = the det_nms0.95 rows (+ emb). Frames where the YOLOX pickle holds None (det_evaluator.py:70,74: no
detection survives) call `update_without_detections()` (run.py:61-64); with our cache that is a frame without
det_nms0.8 rows (the 0.95 rows are a superset, so there are none either).
Output (run.py:68-82, raw result): the tracks returned by update() (state Tracked only), box = Kalman mean
(`x1y1wh`, i.e. the filtered state, not the raw detection); filters: skip w/h > 1.6 (MOT), keep track_id > 0 and
w*h > min_box_area (strict).

Deviations from the official pipeline (all plumbing, no change to the tracking logic):
  * CMC: the official CMC class opens ./trackers/cmc/GMC-<seq>.txt and reads line f-1 for frame f. It is replaced by
    `_FeedCMC`, which returns the [2, 3] matrix of the current frame given in extra["gmc"] (already the f-1 -> f
    matrix, identity at the first frame; BoT-SORT sparseOptFlow downscale 2, same meaning as the BoT-SORT-format file).
  * The repo's `trackers` package is imported under a private sys.modules entry and swapped back out afterwards, so it
    cannot clash with other repos' `trackers` packages (OC_SORT, BoT-SORT); package __init__ files are not run.
  * numpy 2: only `np.float_` (inside the replaced CMC) was affected; nothing else needed patching.
  * Detections are native-pixel 2688x1520 (no rescale needed, YOLOX already divided by scale), clipping to the image
    was done when the cache was built (same rule as det_evaluator.py:65-67).
  * Frames the harness feeds with zero detections also go through update_without_detections(); the official eval
    loop does the same for None frames.
"""
import os
import sys
import types
from types import SimpleNamespace

import numpy as np

from glaremot.baselines import adapters  # noqa: F401  (numpy 2 alias shims)
from glaremot.baselines.adapters import REPOS

_REPO = os.path.join(REPOS, "TrackTrack", "3. Tracker")
_MODS = {}


class _FeedCMC:
    """Stands in for trackers.cmc.CMC: returns the matrix the adapter sets for the current frame."""

    def __init__(self, vid_name=None):
        self.m = np.eye(2, 3)

    def get_warp_matrix(self):
        return np.array(self.m, dtype=np.float64).reshape(2, 3)


def _load():
    """Import trackers.tracker of the TrackTrack clone, isolated from other repos' `trackers` packages."""
    if "tracker" in _MODS:
        return _MODS["tracker"]
    old = {k: sys.modules.pop(k) for k in list(sys.modules) if k == "trackers" or k.startswith("trackers.")}
    try:
        pkg = types.ModuleType("trackers")
        pkg.__path__ = [os.path.join(_REPO, "trackers")]
        sys.modules["trackers"] = pkg
        import importlib
        mod = importlib.import_module("trackers.tracker")
        _MODS["own"] = {k: sys.modules.pop(k) for k in list(sys.modules)
                        if k == "trackers" or k.startswith("trackers.")}
    finally:
        for k in [k for k in sys.modules if k == "trackers" or k.startswith("trackers.")]:
            del sys.modules[k]
        sys.modules.update(old)
    mod.CMC = _FeedCMC          # tracker.py does `from trackers.cmc import *`; Tracker.__init__ looks CMC up here
    _MODS["tracker"] = mod
    return mod


def _pack(d, e):
    """[N,5] x1y1x2y2 score + [N,2048] emb -> [N, 6+2048] float32 with class 0, as in the FastReID pickles."""
    d = np.asarray(d, dtype=np.float32).reshape(-1, 5)
    e = np.asarray(e, dtype=np.float32).reshape(len(d), -1)
    return np.concatenate([d, np.zeros((len(d), 1), np.float32), e], axis=1)


class Tracker:
    nms = 0.95
    needs = ("emb", "gmc", "dets08")

    def __init__(self, fps, hw, seq=None):
        mod = _load()
        self.args = SimpleNamespace(
            det_thr=0.60, init_thr=0.70, match_thr=0.70, min_len=3, min_box_area=100, penalty_p=0.20,
            penalty_q=0.40, reduce_step=0.05, tai_thr=0.55, max_time_lost=int(fps) * 2,
            data_path="MOT17/test/", img_h=hw[0], img_w=hw[1])
        self.t = mod.Tracker(self.args, seq)
        self.cmc = self.t.cmc

    def step(self, dets, extra):
        self.cmc.m = extra["gmc"]
        d08 = extra["dets08"]
        if len(d08) == 0:
            res = self.t.update_without_detections()
        else:
            res = self.t.update(_pack(d08, extra["emb08"]), _pack(dets, extra["emb"]))
        out = []
        for t in res:
            x1y1wh = t.x1y1wh
            if x1y1wh[2] / x1y1wh[3] > 1.6:
                continue
            if t.track_id > 0 and x1y1wh[2] * x1y1wh[3] > self.args.min_box_area:
                out.append((int(t.track_id), *[float(v) for v in x1y1wh]))
        return out
