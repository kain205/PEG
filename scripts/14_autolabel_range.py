"""Step 14 -- Auto-label a frame folder for the FastLabeler handoff (MoRongMo).

Runs a detector ONCE at a low confidence (``--record_conf``) and records the perception
outputs into chunked caches (``<cache_dir>/chunk_<start>.npz``, resumable), then replays
them through a tracker to produce a MOT txt whose frame column is the *display* frame
number of the original video (``--start_display`` + local index).

Detector (``--detector``): ``peg`` = shipped YOLO11m@1536 + h_psi head (GlareMOT domain;
useless on bright close-up footage such as MoRongMo), ``coco`` = a COCO-pretrained
ultralytics model (``--weights``, class person only, ``--imgsz``) with dummy h_psi scalars.
Tracker (``--tracker``): ``peg`` = GMOT_TRACKER-selected PEG/backbone (needs the peg
detector's scalars), ``bytetrack`` = ultralytics ByteTrack fed from the cache; on observed
frames the raw detection box is written (matched to the track by IoU), never a smoothed one.

Stages (``--stage``): ``record`` (GPU, ~7 fps), ``track`` (cache replay, seconds), ``all``.

Outputs
  --mot_out   MOT txt: display_frame,id,x,y,w,h,m,1,1   (tight boxes, like eval_mot)
  --dets_out  CSV of every recorded detection >= record_conf (for the miss sheets):
              display_frame,x,y,w,h,conf,m_glare,present,core_frac

Example
  GMOT_TRACKER=beacon $PY scripts/14_autolabel_range.py \
      --images dataset/MoRongMo/seq_35068_56611/images --start_display 35068 \
      --cache_dir cache/label_MoRongMo --mot_out results/label_MoRongMo/raw_peg.txt \
      --dets_out results/label_MoRongMo/dets_conf010.csv
"""
import argparse
import glob
import os
import queue
import sys
import threading
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from glaremot.config import load_config, weight_path  # noqa: E402
from glaremot.eval.eval_mot import make_tracker  # noqa: E402
from glaremot.eval.percep_cache import CachedPerception, RecordingPerception  # noqa: E402
from glaremot.tracking.tracker import (PHOTO_S, Perception, fast_core_mask,  # noqa: E402
                                       fast_saturation_map, norm_box_to_xyxy)


def chunk_path(cache_dir, start):
    return os.path.join(cache_dir, f"chunk_{start:06d}.npz")


class CocoPerception:
    """Same interface as ``Perception`` (dets + sat/core masks) from a COCO-pretrained
    ultralytics model, person class only. Boxes are normalised cx,cy,w,h in [0,1] of the
    full frame (what ``norm_box_to_xyxy`` expects); h_psi scalars are dummies."""
    needs_frame = True

    def __init__(self, weights, device, conf, imgsz):
        from ultralytics import YOLO
        self.model, self.device, self.conf, self.imgsz = YOLO(weights), device, conf, imgsz
        self._sat = self._core = None

    def core_mask(self):
        if self._core is None and self._sat is not None:
            self._core = fast_core_mask(self._sat)
        return self._core, PHOTO_S

    def sat_mask(self):
        return self._sat, PHOTO_S

    def __call__(self, frame):
        H, W = frame.shape[:2]
        small = cv2.resize(frame, (PHOTO_S, PHOTO_S), interpolation=cv2.INTER_AREA)
        self._sat = fast_saturation_map(small)
        self._core = None
        r = self.model.predict(frame, imgsz=self.imgsz, conf=self.conf, classes=[0],
                               verbose=False, device=self.device)[0]
        dets = []
        if r.boxes is None or not len(r.boxes):
            return dets
        for (x1, y1, x2, y2), c in zip(r.boxes.xyxy.cpu().numpy(), r.boxes.conf.cpu().numpy()):
            dets.append({
                "box": np.array([(x1 + x2) * 0.5 / W, (y1 + y2) * 0.5 / H,
                                 max(1.0, x2 - x1) / W, max(1.0, y2 - y1) / H], np.float32),
                "xyxy_s": np.array([x1, y1, x2, y2], np.float32),
                "conf": float(c), "m_glare": 1.0, "present": 1.0, "core_frac": 0.0,
                "appearance": None})
        return dets


def make_percep(args, device, cfg):
    if args.detector == "peg":
        return Perception(weight_path(cfg, "detector"), weight_path(cfg, "hpsi"), device, args.record_conf)
    return CocoPerception(args.weights, device, args.record_conf, args.imgsz)


def record(img_paths, cache_dir, record_conf, chunk, device, cfg, args):
    """Record perception for every frame not yet covered by a chunk file."""
    n = len(img_paths)
    starts = list(range(0, n, chunk))
    todo = [s for s in starts if not os.path.exists(chunk_path(cache_dir, s))]
    print(f"record: {n} frames, {len(starts)} chunks, {len(todo)} to do", flush=True)
    if not todo:
        return
    percep = make_percep(args, device, cfg)
    t0, done = time.time(), 0
    for s in todo:
        paths = img_paths[s:s + chunk]
        rec = RecordingPerception(percep)
        rq: "queue.Queue" = queue.Queue(maxsize=8)

        def _reader(paths=paths):
            for p in paths:
                rq.put(cv2.imread(p))
            rq.put(None)

        threading.Thread(target=_reader, daemon=True).start()
        while True:
            frame = rq.get()
            if frame is None:
                break
            rec(frame)
            done += 1
            if done % 100 == 0:
                el = time.time() - t0
                print(f"  {done} frames  {done / el:.2f} fps  chunk {s}", flush=True)
        rec.save(chunk_path(cache_dir, s), record_conf)
        print(f"  saved chunk {s} ({len(paths)} frames)", flush=True)


class ChunkedReplay:
    """Serves the chunk caches in order, filtering detections to conf >= ``conf``.
    Same interface as CachedPerception (needs_frame False, sat_mask/core_mask of the
    current frame)."""
    needs_frame = False

    def __init__(self, cache_dir, n_frames, chunk, conf):
        self.starts = list(range(0, n_frames, chunk))
        for s in self.starts:
            if not os.path.exists(chunk_path(cache_dir, s)):
                raise FileNotFoundError(chunk_path(cache_dir, s))
        self.cache_dir, self.conf, self.n_frames = cache_dir, conf, n_frames
        self._ci, self._cur, self._served = -1, None, 0
        self.raw = []          # (local_frame, det) for every det >= record conf

    def _next_chunk(self):
        self._ci += 1
        self._cur = CachedPerception(chunk_path(self.cache_dir, self.starts[self._ci]))

    def __call__(self, frame=None):
        if self._cur is None or self._cur._i + 1 >= self._cur.n_frames:
            self._next_chunk()
        dets = self._cur()
        for d in dets:
            self.raw.append((self._served, d))
        self._served += 1
        return [d for d in dets if d["conf"] >= self.conf]

    def core_mask(self):
        return self._cur.core_mask()

    def sat_mask(self):
        return self._cur.sat_mask()


class _Dets:
    """Minimal stand-in for ultralytics Boxes: .conf/.xywh/.cls + boolean-mask indexing."""

    def __init__(self, xywh, conf, cls=None):
        self.xywh = np.asarray(xywh, np.float32).reshape(-1, 4)
        self.conf = np.asarray(conf, np.float32)
        self.cls = np.zeros(len(self.conf), np.float32) if cls is None else cls

    def __len__(self):
        return len(self.conf)

    def __getitem__(self, m):
        return _Dets(self.xywh[m], self.conf[m], self.cls[m])


def _iou_xyxy(a, b):
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    return inter / max(1e-6, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def make_bytetrack(args):
    from types import SimpleNamespace
    from ultralytics.trackers.byte_tracker import BYTETracker
    cfg = SimpleNamespace(track_high_thresh=args.bt_high, track_low_thresh=args.bt_low,
                          new_track_thresh=args.bt_new, track_buffer=args.bt_buffer,
                          match_thresh=args.bt_match, fuse_score=True)
    return BYTETracker(cfg)


def track(img_paths, cache_dir, chunk, conf, start_display, mot_out, dets_out, args):
    H, W = cv2.imread(img_paths[0]).shape[:2]
    use_bt = args.tracker == "bytetrack"
    # ByteTrack does its own two-stage thresholding (bt_low/bt_high): give it every cached det
    percep = ChunkedReplay(cache_dir, len(img_paths), chunk, args.bt_low if use_bt else conf)
    tracker = make_bytetrack(args) if use_bt else make_tracker()
    if hasattr(tracker, "attach_perception"):
        tracker.attach_perception(percep)
    rows = []
    t0 = time.time()
    for fi in range(1, len(img_paths) + 1):
        dets = percep()
        F = start_display + fi - 1
        if use_bt:
            xyxy = [norm_box_to_xyxy(d["box"], W, H) for d in dets]
            xywh = [[(b[0] + b[2]) / 2, (b[1] + b[3]) / 2, b[2] - b[0], b[3] - b[1]] for b in xyxy]
            out = tracker.update(_Dets(xywh, [d["conf"] for d in dets]))
            for r in out:
                tb = r[:4]
                j = max(range(len(xyxy)), key=lambda k: _iou_xyxy(xyxy[k], tb), default=None)
                if j is None or _iou_xyxy(xyxy[j], tb) < 0.3:
                    continue
                x1, y1, x2, y2 = xyxy[j]
                rows.append(f"{F},{int(r[4])},{max(0.0, x1):.2f},{max(0.0, y1):.2f},"
                            f"{max(1.0, x2 - x1):.2f},{max(1.0, y2 - y1):.2f},{dets[j]['conf']:.4f},1,1")
            continue
        tracks = tracker.step(dets, W, H, fi, core_fn=percep.core_mask)
        for t in tracks:
            x1, y1, x2, y2 = norm_box_to_xyxy(t.out_box(), W, H)
            rows.append(f"{F},{t.id},{max(0.0, x1):.2f},{max(0.0, y1):.2f},"
                        f"{max(1.0, x2 - x1):.2f},{max(1.0, y2 - y1):.2f},"
                        f"{max(t.m, 0.001):.4f},1,1")
    print(f"track: {len(img_paths)} frames in {time.time() - t0:.1f}s, {len(rows)} rows, "
          f"{len({r.split(',')[1] for r in rows})} ids", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(mot_out)), exist_ok=True)
    with open(mot_out, "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + ("\n" if rows else ""))
    if dets_out:
        with open(dets_out, "w", encoding="utf-8") as f:
            f.write("frame,x,y,w,h,conf,m_glare,present,core_frac\n")
            for li, d in percep.raw:
                x1, y1, x2, y2 = norm_box_to_xyxy(d["box"], W, H)
                f.write(f"{start_display + li},{max(0.0, x1):.2f},{max(0.0, y1):.2f},"
                        f"{max(1.0, x2 - x1):.2f},{max(1.0, y2 - y1):.2f},{d['conf']:.4f},"
                        f"{d['m_glare']:.4f},{d['present']:.4f},{d['core_frac']:.4f}\n")
        print(f"dets: {len(percep.raw)} rows -> {dets_out}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="folder of frame_*.jpg (sorted order)")
    ap.add_argument("--start_display", type=int, required=True,
                    help="display (1-based) frame number of the first jpg")
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--mot_out", default=None)
    ap.add_argument("--dets_out", default=None)
    ap.add_argument("--conf", type=float, default=0.25, help="tracker detection conf")
    ap.add_argument("--record_conf", type=float, default=0.10, help="detector conf when recording")
    ap.add_argument("--chunk", type=int, default=2000)
    ap.add_argument("--max_frames", type=int, default=0, help="smoke test (use a separate cache_dir)")
    ap.add_argument("--offset", type=int, default=0, help="smoke test: skip the first N frames")
    ap.add_argument("--stage", choices=["record", "track", "all"], default="all")
    ap.add_argument("--detector", choices=["peg", "coco"], default="coco")
    ap.add_argument("--weights", default="weights/pretrained/yolo11l.pt")
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--tracker", choices=["peg", "bytetrack"], default="bytetrack")
    ap.add_argument("--bt_high", type=float, default=0.30)
    ap.add_argument("--bt_low", type=float, default=0.10)
    ap.add_argument("--bt_new", type=float, default=0.40)
    ap.add_argument("--bt_buffer", type=int, default=50)
    ap.add_argument("--bt_match", type=float, default=0.8)
    ap.add_argument("--config", default=None)
    args = ap.parse_args()

    img_paths = sorted(glob.glob(os.path.join(args.images, "*.jpg")))
    if args.offset:
        img_paths = img_paths[args.offset:]
        args.start_display += args.offset
    if args.max_frames:
        img_paths = img_paths[:args.max_frames]
    if not img_paths:
        raise FileNotFoundError(args.images)
    os.makedirs(args.cache_dir, exist_ok=True)
    cfg = load_config(args.config)
    if args.stage in ("record", "all"):
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"device={device} detector={args.detector} weights={args.weights} imgsz={args.imgsz} "
              f"record_conf={args.record_conf} frames={len(img_paths)}", flush=True)
        record(img_paths, args.cache_dir, args.record_conf, args.chunk, device, cfg, args)
    if args.stage in ("track", "all"):
        if not args.mot_out:
            ap.error("--mot_out required for tracking")
        print(f"tracker={args.tracker} (GMOT_TRACKER={os.environ.get('GMOT_TRACKER', 'base')}) "
              f"conf={args.conf} bt=({args.bt_high},{args.bt_low},{args.bt_new},{args.bt_buffer})", flush=True)
        track(img_paths, args.cache_dir, args.chunk, args.conf, args.start_display,
              args.mot_out, args.dets_out, args)


if __name__ == "__main__":
    main()
