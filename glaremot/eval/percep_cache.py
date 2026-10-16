"""Per-sequence cache of the perception outputs, so tracker ablations skip the detector.

The tracker step only consumes (a) the detection dicts returned by ``Perception.__call__``
and (b) the frame's saturation map (``sat_mask``; ``core_mask`` is derived from it).
Both are recorded once per sequence into ``<cache_dir>/<seq>.npz`` and replayed by
``CachedPerception``, which reproduces the stored MOT txt byte-for-byte (values are kept
at their original precision: boxes float32, scalars float64).

    rec = RecordingPerception(percep)      # wraps the live detector
    ... track_sequence(seq_dir, rec, out_txt) ...
    rec.save(path, conf)
    cached = CachedPerception(path)       # same interface, no GPU, no image decode

PEG-F appearance (GMOT_REID / GMOT_DORMANT) needs pixels, so it lives in a sidecar
``<seq>.app.npz`` (row i = appearance of the i-th cached det, NaN + valid=False for None),
built offline by ``scripts/12_cache_appearance.py`` or written by ``RecordingPerception.save``
when the live run computed it. ``CachedPerception`` attaches it when present and raises if the
flags need it and it is missing.
"""
import os

import numpy as np

from ..tracking.tracker import PHOTO_S, USE_APPEARANCE, fast_core_mask

SCALARS = ("conf", "m_glare", "present", "core_frac")
APP_DIM = 48


def cache_path(cache_dir, seq):
    return os.path.join(cache_dir, f"{seq}.npz")


def app_path(path):
    """Sidecar appearance file of a perception cache ``<seq>.npz``."""
    return path[:-len(".npz")] + ".app.npz"


def save_appearance(path, apps):
    """apps: per cached det (recorded order), a float32 (48,) vector or None."""
    valid = np.array([a is not None for a in apps], bool)
    arr = np.full((len(apps), APP_DIM), np.nan, np.float32)
    for i, a in enumerate(apps):
        if a is not None:
            arr[i] = a
    tmp = path + ".tmp.npz"
    np.savez_compressed(tmp, app=arr, valid=valid)
    os.replace(tmp, path)


class RecordingPerception:
    """Pass-through wrapper around a live ``Perception`` that records every frame."""
    needs_frame = True

    def __init__(self, percep):
        self.p = percep
        self.frames = []          # per frame: (dets, packed sat)

    def __call__(self, frame):
        dets = self.p(frame)
        sat, _ = self.p.sat_mask()
        self.frames.append((dets, np.packbits(sat.astype(bool), axis=None)))
        return dets

    def core_mask(self):
        return self.p.core_mask()

    def sat_mask(self):
        return self.p.sat_mask()

    def save(self, path, conf):
        det_frame, box, xyxy, scal, apps = [], [], [], [], []
        for fi, (dets, _) in enumerate(self.frames):
            for d in dets:
                apps.append(d.get("appearance"))
                det_frame.append(fi)
                box.append(d["box"])
                xyxy.append(d["xyxy_s"])
                scal.append([d[k] for k in SCALARS])
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp.npz"
        np.savez_compressed(
            tmp, n_frames=np.int32(len(self.frames)), conf=np.float64(conf),
            det_frame=np.asarray(det_frame, np.int32),
            box=np.asarray(box, np.float32).reshape(-1, 4),
            xyxy=np.asarray(xyxy, np.float32).reshape(-1, 4),
            scal=np.asarray(scal, np.float64).reshape(-1, len(SCALARS)),
            sat=np.stack([s for _, s in self.frames]) if self.frames
            else np.zeros((0, PHOTO_S * PHOTO_S // 8), np.uint8))
        os.replace(tmp, path)
        if USE_APPEARANCE:
            save_appearance(app_path(path), apps)


class CachedPerception:
    """Replays a recorded sequence; frames are served in call order."""
    needs_frame = False

    def __init__(self, path, conf=None):
        z = np.load(path)
        if conf is not None and abs(float(z["conf"]) - conf) > 1e-9:
            raise ValueError(f"{path}: cached at conf={float(z['conf'])}, requested {conf}")
        self.n_frames = int(z["n_frames"])
        self._sat_packed = z["sat"]
        df, box, xyxy, scal = z["det_frame"], z["box"], z["xyxy"], z["scal"]
        app = valid = None
        if os.path.exists(app_path(path)):
            za = np.load(app_path(path))
            app, valid = za["app"], za["valid"]
            if len(app) != len(df):
                raise ValueError(f"{app_path(path)}: {len(app)} rows, cache has {len(df)} dets")
        elif USE_APPEARANCE:
            raise FileNotFoundError(
                f"{app_path(path)} missing: GMOT_REID / GMOT_DORMANT need cached appearance; "
                f"build it with scripts/12_cache_appearance.py")
        self._dets = [[] for _ in range(self.n_frames)]
        for i in range(len(df)):
            d = {"box": box[i].copy(), "xyxy_s": xyxy[i].copy()}
            for k, v in zip(SCALARS, scal[i]):
                d[k] = float(v)
            if app is not None:
                d["appearance"] = app[i].copy() if valid[i] else None
            self._dets[int(df[i])].append(d)
        self._i = -1
        self._sat = None
        self._core = None

    def __call__(self, frame=None):
        self._i += 1
        if self._i >= self.n_frames:
            raise IndexError("cache exhausted: more frames than were recorded")
        bits = np.unpackbits(self._sat_packed[self._i], count=PHOTO_S * PHOTO_S)
        self._sat = bits.reshape(PHOTO_S, PHOTO_S).astype(bool)
        self._core = None
        return [dict(d) for d in self._dets[self._i]]

    def core_mask(self):
        if self._core is None and self._sat is not None:
            self._core = fast_core_mask(self._sat)
        return self._core, PHOTO_S

    def sat_mask(self):
        return self._sat, PHOTO_S
