"""Deep-OC-SORT (GerardMaggiolino/Deep-OC-SORT @ 6bb51d0, trackers/integrated_ocsort_embedding/ocsort.py OCSort).

Settings = the README MOT17 command `--grid_off --new_kf_off --dataset mot17 --w_assoc_emb 0.75 --aw_param 0.5`
with main.py / args.py defaults: det_thresh 0.6, iou_thresh 0.3, asso iou, delta_t 3, inertia 0.2,
alpha_fixed_emb 0.95, aw on, cmc on, embeddings on, max_age 30 and min_hits 3 (OCSort defaults, not passed by
main.py:89-104); output filter aspect 1.6 and min_box_area 10 (main.py:140, utils.filter_targets). Detector NMS 0.7.
No --post (interpolation off: online only).
The tracker's own code runs unmodified; the two members that read the image are swapped for cached values:
  embedder.compute_embedding(img, boxes, tag) -> cached FastReID MOT20 SBS-S50 embeddings of those boxes (it embeds the
      dets above det_thresh; computed exactly like its own non-grid crops). Deviation: Deep-OC-SORT's main.py loads the
      SBS weights only with --test_dataset (else OSNet-AIN); all ReID baselines here share the MOT20 SBS-S50 model.
  cmc.compute_affine(img, boxes, tag) -> cached BoT-SORT sparseOptFlow matrix (the default is "file", precomputed
      for MOT17/MOT20 only).
"""
import os
import sys
import types

import numpy as np

from glaremot.baselines import adapters
from glaremot.baselines.adapters import keep_box

PKG = "trackers.integrated_ocsort_embedding"


class _Embedder:
    def __init__(self):
        self.boxes = self.emb = None

    def compute_embedding(self, img, bbox, tag):
        out = np.zeros((len(bbox), self.emb.shape[1]), np.float32)
        for k, d in enumerate(bbox):
            j = int(np.argmin(np.abs(self.boxes - d).sum(1)))
            assert np.abs(self.boxes[j] - d).sum() < 1e-3, "det not found in the cached rows"
            out[k] = self.emb[j]
        return out

    def dump_cache(self):
        pass


class _CMC:
    A = np.eye(2, 3)

    def compute_affine(self, img, bbox, tag):
        return self.A

    def dump_cache(self):
        pass


def _load():
    """Import the repo's ocsort module with its `embedding`/`cmc` modules stubbed. The stub packages stay registered
    (KalmanBoxTracker imports from them lazily); one tracker runs per process, so the `trackers` name is ours."""
    if PKG + ".ocsort" in sys.modules:
        return sys.modules[PKG + ".ocsort"]
    root = os.path.join(adapters.REPOS, "Deep-OC-SORT")
    for name, path in (("trackers", ["trackers"]), (PKG, ["trackers", "integrated_ocsort_embedding"])):
        m = types.ModuleType(name)
        m.__path__ = [os.path.join(root, *path)]
        sys.modules[name] = m
    emb, cmc = types.ModuleType(PKG + ".embedding"), types.ModuleType(PKG + ".cmc")
    emb.EmbeddingComputer = lambda *a, **k: _Embedder()
    cmc.CMCComputer = lambda *a, **k: _CMC()
    sys.modules[emb.__name__], sys.modules[cmc.__name__] = emb, cmc
    import importlib
    return importlib.import_module(PKG + ".ocsort")


class _Shape:
    def __init__(self, shape):
        self.shape = shape


class Tracker:
    nms, needs = 0.7, ("emb", "gmc")

    def __init__(self, fps, hw, seq=None):
        oc = _load()
        args = types.SimpleNamespace(dataset="mot17", test_dataset=False)
        self.t = oc.OCSort(args=args, det_thresh=0.6, iou_threshold=0.3, asso_func="iou", delta_t=3, inertia=0.2,
                           w_association_emb=0.75, alpha_fixed_emb=0.95, embedding_off=False, cmc_off=False,
                           aw_off=False, aw_param=0.5, new_kf_off=True, grid_off=True)
        self.img_t, self.img_np = _Shape((1, 3, hw[0], hw[1])), _Shape((hw[0], hw[1], 3))   # rescale = 1
        self.min_box_area = 10

    def step(self, dets, extra):
        self.t.embedder.boxes, self.t.embedder.emb = dets[:, :4], extra["emb"]
        self.t.cmc.A = extra["gmc"].astype(np.float64)
        out = []
        for x1, y1, x2, y2, tid in self.t.update(dets.astype(np.float64), self.img_t, self.img_np, "seq"):
            tlwh = (x1, y1, x2 - x1, y2 - y1)
            if keep_box(tlwh, self.min_box_area):
                out.append((int(tid), *tlwh))
        return out
