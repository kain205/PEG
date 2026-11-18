"""Thin adapters that feed the cached detections to each baseline's OFFICIAL tracker class.

Every adapter is built per sequence with (fps, (h, w), seq) and exposes:
  nms    detection NMS IoU the method's YOLOX pipeline assumes (applied on det_nms0.95 rows by the harness;
         0.95 = the cached rows as they are)
  needs  extra per-frame inputs, given in `extra`:
           "emb"    float32 [N, 2048] FastReID MOT20 SBS-S50 embeddings of `dets` (L2-normalised), all dets >= 0.1
           "gmc"    float32 [2, 3] previous->current frame affine (BoT-SORT sparseOptFlow, downscale 2)
           "disp"   uint8 [96, 128] MegaDepth disparity / per-frame max * 255 (DIP)
           "dets08" [M, 5] the det_nms0.8 rows of this frame (+ "emb08" [M, 2048] with "emb"); `dets` are then the
                    det_nms0.95 rows (TrackTrack)
         always: "frame" (1-based within the scored range), "hw" (h, w)
  step(dets, extra) -> list of (track_id, x, y, w, h)   dets: [N, 5] x1, y1, x2, y2, score in native pixels
The official repos live in results/baselines_t1/repos (cloned, not vendored; commits in RUNS.md). The trackers get
img_info = img_size = (h, w), so their internal rescale is 1. update() is called on every frame, also with no dets:
the official eval loops skip update() when YOLOX returns nothing at conf 0.001, which never happens in practice,
while our cache stops at 0.1.
Output filter as in the official MOT evaluators: drop w*h <= min_box_area and w/h > 1.6.
"""
import importlib
import os
import sys
import types
from types import SimpleNamespace

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REPOS = os.environ.get("BASELINE_REPOS", os.path.join(ROOT, "results", "baselines_t1", "repos"))
SHIMS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shims")


def _repo_import(repo, module, pkg=None):
    """Import `module` from a cloned repo. `pkg` names a package whose __init__ must NOT run (heavy deps): it is
    registered as an empty namespace that points at the repo dir."""
    path = os.path.join(REPOS, repo)
    if SHIMS not in sys.path:
        sys.path.insert(0, SHIMS)
    if path not in sys.path:
        sys.path.append(path)          # last: repos ship their own copies of common names (e.g. OC_SORT/trackeval)
    if pkg and pkg not in sys.modules:
        m = types.ModuleType(pkg)
        m.__path__ = [os.path.join(path, *pkg.split("."))]
        sys.modules[pkg] = m
    return importlib.import_module(module)


def keep_box(tlwh, min_box_area):
    return tlwh[2] * tlwh[3] > min_box_area and tlwh[2] / max(tlwh[3], 1e-6) <= 1.6


class ByteTrack:
    """ifzhang/ByteTrack tools/track.py defaults (MOT17 settings, no per-seq hacks). Its MOT evaluator builds
    BYTETracker(args) with the default frame_rate=30, so the lost buffer is 30 frames whatever the video fps."""
    nms, needs = 0.7, ()

    def __init__(self, fps, hw, seq=None):
        bt = _repo_import("ByteTrack", "yolox.tracker.byte_tracker", pkg="yolox")
        self.args = SimpleNamespace(track_thresh=0.6, track_buffer=30, match_thresh=0.9, mot20=False,
                                    min_box_area=100)
        self.t = bt.BYTETracker(self.args)
        self.hw = hw

    def step(self, dets, extra):
        out = []
        for t in self.t.update(dets.astype(np.float32), self.hw, self.hw):
            if keep_box(t.tlwh, self.args.min_box_area):
                out.append((t.track_id, *t.tlwh))
        return out


class OCSort:
    """noahcao/OC_SORT utils/args.py defaults (det_thresh 0.6, iou 0.3, delta_t 3, inertia 0.2, asso iou)."""
    nms, needs = 0.7, ()

    def __init__(self, fps, hw, seq=None):
        oc = _repo_import("OC_SORT", "trackers.ocsort_tracker.ocsort", pkg="trackers")
        self.t = oc.OCSort(det_thresh=0.6, iou_threshold=0.3, asso_func="iou", delta_t=3, inertia=0.2)
        self.hw, self.min_box_area = hw, 10

    def step(self, dets, extra):
        out = []
        for x1, y1, x2, y2, tid in self.t.update(dets.astype(np.float64), self.hw, self.hw):
            tlwh = (x1, y1, x2 - x1, y2 - y1)
            if keep_box(tlwh, self.min_box_area):
                out.append((int(tid), *tlwh))
        return out


# numpy 2 removed these aliases; the official repos still use them
for _a, _t in (("float", float), ("int", int), ("bool", bool), ("object", object), ("float_", np.float64)):
    if _a not in np.__dict__:
        setattr(np, _a, _t)

TRACKERS = {"bytetrack": ByteTrack, "ocsort": OCSort}
LAZY = ("botsort", "deepocsort", "hybridsort", "tracktrack", "diffmot", "dip", "peg", "exsort")   # glaremot/baselines/t_<key>.py


def get_tracker(key):
    """Adapter class for `key`: built in above, or the `Tracker` class of glaremot/baselines/t_<key>.py."""
    if key in TRACKERS:
        return TRACKERS[key]
    return importlib.import_module(f"glaremot.baselines.t_{key}").Tracker
