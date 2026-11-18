"""DiffMOT (Kroery/DiffMOT, CVPR 2024, commit eada72e) on the cached detections + ReID embeddings, CPU only.

Official tracking + motion code runs unmodified: `tracker/DiffMOTtracker.py` (`diffmottracker`, `STrack`) and the
D2MP motion model (`models/autoencoder.py`, `models/diffusion.py`, `models/condition_embedding.py`). Only the
imports of the ReID back end are stubbed (no image is read) and the model is built on CPU.

Settings (README "Track on MOT17" + configs/mot17_test.yaml, everything else is what the tracker hard-codes):
  high_thres 0.6, low_thres 0.1, w_assoc_emb 2.2, aw_param 1.7; diffnet HMINet, encoder_dim 256, tf_layer 3,
  eps 0.001; max_time_lost 30 (frame_rate=30 default of diffmottracker, as diffmot.py builds it); 1-step sampler
  (D2MP_OB.sample forces num_steps = 1), sample=1, bestof=True. Online only, no interpolation, no output filter
  (diffmot.py write_results only skips track_id < 0, never happens). Output = every activated Tracked STrack of the
  frame, its `.tlwh` (the motion model's prediction, replaced by the matched detection box on update).
Checkpoint: MOT_epoch800.pt (MOT17+MOT20, ShuCvlab/DiffMOT release v1.0) in results/baselines_t1/weights/.

`nms = 0.7`: DiffMOT ships ByteTrack-style YOLOX-X detections (Detections.zip); the NMS used for those files is
unverified, 0.7 is the YOLOX MOT default.

The diffusion sampler draws x_T ~ N(0, I): the torch seed is fixed to SEED = 123 (the config's `seed`) at the start
of every sequence, so a run is repeatable (single-thread-count independent up to float round-off).

ReID: EmbeddingComputer.compute_embedding returns `cache[f"{seq}:{frame}"]` when present, one row per detection
above high_thres in order. We fill exactly that cache entry from extra["emb"] (rows of dets with score > 0.6,
the same float32 comparison the tracker makes) and let the official method return it.

Deviations from the official pipeline (none changes the algorithm):
  * ReID/YOLOX imports stubbed (torchreid, external.adaptors.fastreid_adaptor): never called, embeddings are cached.
  * CPU instead of CUDA (`.cuda()` is only in training / the ReID model, not on the eval path); torch.no_grad()
    around update() (diffmot.py has none: it only skips autograd bookkeeping).
  * BaseTrack._count (global track-id counter) reset per sequence; diffmot.py lets it run on across sequences
    (ids are only compared within a sequence).
  * Embedding cache dir (config.reid_dir) points at a throw-away temp dir; nothing is read from or written to it.
  * Detections: float32 tlwh+score, as np.loadtxt(dtype=float32) gives in diffmot.py; image size = native (w, h).
"""
import atexit
import os
import shutil
import sys
import tempfile
import types
from types import SimpleNamespace

import numpy as np
import torch
import yaml

from glaremot.baselines.adapters import REPOS, _repo_import   # noqa: F401  (also installs the numpy aliases)

SEED = 123
CKPT = os.path.join(os.path.dirname(REPOS), "weights", "MOT_epoch800.pt")
_THREADS = int(os.environ.get("DIFFMOT_THREADS", "2"))
_STATE = {}


def _stub(name, **attrs):
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__dict__.update(attrs)
        sys.modules[name] = m
    return sys.modules[name]


def _load():
    """Import the official modules once, build config + D2MP model once per process."""
    if _STATE:
        return _STATE
    torch.set_num_threads(_THREADS)
    repo = os.path.join(REPOS, "DiffMOT")
    # ReID back end is never used (embeddings come from the cache) but tracker/embedding.py imports it at top level
    _stub("torchreid")
    ext = _stub("external")
    ext.__path__ = []
    ada = _stub("external.adaptors")
    ada.__path__ = []
    _stub("external.adaptors.fastreid_adaptor", FastReID=object)
    dm = _repo_import("DiffMOT", "tracker.DiffMOTtracker")
    ae = _repo_import("DiffMOT", "models.autoencoder")
    ce = _repo_import("DiffMOT", "models.condition_embedding")
    bt = _repo_import("DiffMOT", "tracker.basetrack")

    with open(os.path.join(repo, "configs", "mot17_test.yaml")) as f:
        cfg = yaml.safe_load(f)
    reid_tmp = tempfile.mkdtemp(prefix="diffmot_reid_")
    atexit.register(shutil.rmtree, reid_tmp, True)
    cfg["reid_dir"] = reid_tmp
    cfg["dataset"] = "MOT"
    config = SimpleNamespace(**cfg)        # diffmot.py uses EasyDict (attribute access only)

    # diffmot.py DiffMOT._build_encoder / _build_model / _build_dir, eval_mode branch, on CPU
    try:
        ckpt = torch.load(CKPT, map_location="cpu")
    except Exception:                      # torch>=2.6 weights_only=True may refuse the optimizer state
        ckpt = torch.load(CKPT, map_location="cpu", weights_only=False)
    encoder = ce.History_motion_embedding()
    model = ae.D2MP(config, encoder=encoder)
    model = model.eval()
    model.load_state_dict({k.replace("module.", ""): v for k, v in ckpt["ddpm"].items()})
    _STATE.update(dm=dm, bt=bt, config=config, model=model)
    return _STATE


class Tracker:
    nms, needs = 0.7, ("emb",)

    def __init__(self, fps, hw, seq=None):
        st = _load()
        self.st = st
        self.seq = seq or "seq"
        self.h, self.w = hw
        torch.manual_seed(SEED)
        st["bt"].BaseTrack._count = 0
        self.t = st["dm"].diffmottracker(st["config"])
        self.t.embedder.cache_name = self.seq          # no pkl cache on disk: skip load_cache
        self.high = st["config"].high_thres

    def step(self, dets, extra):
        # diffmot.py: dets = loadtxt(float32)[:, 1:6] = x, y, w, h, score
        d = np.zeros((len(dets), 5), np.float32)
        if len(dets):
            d[:, 0], d[:, 1] = dets[:, 0], dets[:, 1]
            d[:, 2], d[:, 3] = dets[:, 2] - dets[:, 0], dets[:, 3] - dets[:, 1]
            d[:, 4] = dets[:, 4]
        n = extra["frame"]
        tag = f"{self.seq}:{n}"
        emb = extra.get("emb")
        high = d[:, 4] > self.high                      # the tracker's own remain_inds (before its tlbr conversion)
        if len(d) and high.any():
            self.t.embedder.cache[tag] = np.ascontiguousarray(emb[high], dtype=np.float32)
        with torch.no_grad():
            out = self.t.update(d, self.st["model"], n - 1, self.w, self.h, tag)
        self.t.embedder.cache.pop(tag, None)
        return [(t.track_id, *t.tlwh) for t in out]
