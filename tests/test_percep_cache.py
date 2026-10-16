"""Perception cache round-trip (no GPU) and PEG+ flags defaulting to the paper's PEG."""
import os

import numpy as np

from glaremot.eval.percep_cache import CachedPerception, RecordingPerception
from glaremot.tracking.tracker import PHOTO_S, fast_core_mask


class FakePerception:
    """Stands in for the detector: 3 frames, a varying number of detections."""
    def __init__(self):
        self.rng = np.random.default_rng(0)
        self._sat = None

    def __call__(self, frame):
        self._sat = self.rng.random((PHOTO_S, PHOTO_S)) > 0.97
        n = int(self.rng.integers(0, 3))
        return [{"box": self.rng.random(4).astype(np.float32),
                 "xyxy_s": (self.rng.random(4) * 1536).astype(np.float32),
                 "conf": float(np.float32(self.rng.random())),
                 "m_glare": float(np.float32(self.rng.random())),
                 "present": float(np.float32(self.rng.random())),
                 "core_frac": float(self.rng.random())} for _ in range(n)]

    def sat_mask(self):
        return self._sat, PHOTO_S

    def core_mask(self):
        return fast_core_mask(self._sat), PHOTO_S


def test_cache_round_trip(tmp_path):
    rec = RecordingPerception(FakePerception())
    live = []
    for _ in range(3):
        dets = rec(None)
        live.append((dets, rec.sat_mask()[0].copy(), rec.core_mask()[0].copy()))
    path = os.path.join(tmp_path, "seq.npz")
    rec.save(path, 0.25)

    cached = CachedPerception(path, 0.25)
    assert cached.n_frames == 3
    for dets, sat, core in live:
        got = cached(None)
        assert len(got) == len(dets)
        for a, b in zip(dets, got):
            assert np.array_equal(a["box"], b["box"]) and a["box"].dtype == b["box"].dtype
            assert np.array_equal(a["xyxy_s"], b["xyxy_s"])
            for k in ("conf", "m_glare", "present", "core_frac"):
                assert a[k] == b[k]                       # bit-exact, not approx
        assert np.array_equal(cached.sat_mask()[0], sat)
        assert np.array_equal(cached.core_mask()[0], core)


def test_peg_plus_flags_default_off():
    from glaremot.tracking import beacon_tracker, tracker
    if "GPEG_SIZE_LOCK" not in os.environ:
        assert tracker.SIZE_LOCK is False
    if "GPEG_LAMP_FOLLOW" not in os.environ:
        assert beacon_tracker.LAMP_FOLLOW is False


def test_appearance_sidecar(tmp_path, monkeypatch):
    import pytest
    from glaremot.eval import percep_cache as pc
    rec = RecordingPerception(FakePerception())
    for _ in range(3):
        rec(None)
    path = os.path.join(tmp_path, "seq.npz")
    rec.save(path, 0.25)
    n = sum(len(d) for d, _ in rec.frames)
    monkeypatch.setattr(pc, "USE_APPEARANCE", True)
    with pytest.raises(FileNotFoundError):                 # flag on, sidecar missing
        CachedPerception(path, 0.25)
    apps = [None if i % 2 else np.full(48, i, np.float32) for i in range(n)]
    pc.save_appearance(pc.app_path(path), apps)
    cached = CachedPerception(path, 0.25)
    got = [d for _ in range(3) for d in cached(None)]
    assert len(got) == n
    for a, d in zip(apps, got):
        assert (a is None and d["appearance"] is None) or np.array_equal(a, d["appearance"])
