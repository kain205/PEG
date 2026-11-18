"""Per-frame photometric inputs of PEG (and, with --kind exsort, ExSORT's saturation mask) on the GlareMOT2 frames, for PEG on the shared YOLOX detection cache (CPU).

PEG's tracker consumes, per frame, (a) detection dicts and (b) the frame's saturation map (glaremot/eval/
percep_cache.py). With YOLOX detections instead of YOLO11m + h_psi, this script records what only the image can give:
  sat   the PHOTO_S x PHOTO_S (512) saturation map of the S x S letterbox (S = configs/paths.yaml imgsz, 1536), exactly as
        Perception.__call__ makes it (letterbox_frame -> INTER_AREA to 512 -> fast_saturation_map), bit-packed;
  mg    m_glare_analytic (glaremot/perception/analytic.py: torso-weighted unburnt fraction of the box, the target the
        learned h_psi head regresses to) of every det_nms0.95 row, measured on the letterbox frame, box mapped into it.
Images are streamed from the Drive zip in windows (same code as scripts/27), used once and deleted; nothing goes to /tmp
(a RAM tmpfs on this machine). Resumable per window.
Output: <out>/<split>/<seq>/sat_<lo>.npz (packed bits, frames lo+1..hi of the window, key sat [n, 32768] uint8),
        mg.npy (float32 [rows of det_nms0.95.txt]), DONE.
  GDRIVE_TOKEN_FILE=... .venv/bin/python scripts/29_cache_peg_photometric.py --dets results/baselines_t1/dets \\
      --out results/baselines_t1/pegsat --tmp results/baselines_t1/stream --overlay results/baselines_t1/overlay
"""
import argparse
import importlib.util
import json
import multiprocessing as mp
import os
import shutil
import sys
import threading
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from glaremot.config import load_config  # noqa: E402
from glaremot.perception.analytic import m_glare_analytic  # noqa: E402
from glaremot.tracking.tracker import PHOTO_S, fast_saturation_map, letterbox_frame, letterbox_params  # noqa: E402

S = int(load_config().imgsz)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def exsort_saturation(image):
    """minhdq245/exsort @ 0c25ef3, exsort/cache.py:77-79, verbatim: the ORIGINAL frame stretched to 512x512 (no
    letterbox), V >= 235 and S <= 89."""
    hsv = cv2.cvtColor(cv2.resize(image, (512, 512), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2HSV)
    return np.packbits(((hsv[:, :, 2] >= 235) & (hsv[:, :, 1] <= 89)).reshape(-1))


def frame_job(args):
    """(path, [N,4] native xyxy boxes, kind) -> (packed sat bits, m_glare per box; empty for kind exsort)."""
    path, boxes, kind = args
    img = cv2.imread(path)
    if kind == "exsort":
        return exsort_saturation(img), np.zeros(0, np.float32)
    H, W = img.shape[:2]
    lb = letterbox_params(H, W, S)
    sq = img if lb is None else letterbox_frame(img, S, lb)
    small = cv2.resize(sq, (PHOTO_S, PHOTO_S), interpolation=cv2.INTER_AREA)
    sat = np.packbits(fast_saturation_map(small).astype(bool), axis=None)
    mg = []
    for x1, y1, x2, y2 in boxes:
        if lb is not None:
            s, px, py = lb[:3]
            x1, y1, x2, y2 = x1 * s + px, y1 * s + py, x2 * s + px, y2 * s + py
        mg.append(m_glare_analytic(sq, (x1, y1, x2, y2)))
    return sat, np.asarray(mg, np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dets", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tmp", required=True, help="image stream dir ON DISK (not /tmp)")
    ap.add_argument("--overlay")
    ap.add_argument("--splits", default="test")
    ap.add_argument("--chunk", type=int, default=1000)
    ap.add_argument("--procs", type=int, default=3)
    ap.add_argument("--fetch_workers", type=int, default=8)
    ap.add_argument("--seqs")
    ap.add_argument("--kind", default="peg", choices=["peg", "exsort"],
                    help="peg: PEG letterbox map + m_glare; exsort: ExSORT's stretched 512x512 mask only")
    args = ap.parse_args()
    c26 = _load("c26", os.path.join(ROOT, "scripts", "26_cache_yolox_dets.py"))
    fetch = c26.fetch
    file_id = fetch.ZIPS["v2"][0]
    url = fetch.drive_url(file_id)
    ix = fetch.load_index(url, os.path.join(ROOT, "cache", f"zipindex_{file_id}.json"))
    zsplit = lambda sp: "test" if sp == "test" else "train"
    ranges = json.load(open(os.path.join(args.dets, "splits.json")))

    wins = []
    for sp in args.splits.split(","):
        for seq in sorted(ranges[sp]):
            if args.seqs and seq not in args.seqs.split(","):
                continue
            o = os.path.join(args.out, sp, seq)
            if os.path.isfile(os.path.join(o, "DONE")):
                continue
            first, last = ranges[sp][seq]
            for lo in range(first - 1, last, args.chunk):
                hi = min(lo + args.chunk, last)
                if not os.path.isfile(os.path.join(o, f"sat_{lo}.npz")):      # resume: finished windows stay
                    wins.append((sp, seq, lo, hi))
            if not any(w[1] == seq and w[0] == sp for w in wins):              # all windows there, only DONE missing
                wins.append((sp, seq, None, None))
    print(f"[pegsat] {len(wins)} windows to do", flush=True)

    def fetch_window(w):
        sp, seq, lo, hi = w
        if lo is None:
            return
        zs = zsplit(sp)
        c26.apply_overlay(args.overlay, zs, seq, args.tmp)
        ov = os.path.join(args.overlay or "", zs, seq, "images")
        fixed = set(os.listdir(ov)) if args.overlay and os.path.isdir(ov) else set()
        base = dict(zip="v2", out=os.path.join(args.tmp, zs), split=zs, old_split=None, seqs=seq)
        members, ends = fetch.select(ix, argparse.Namespace(**base, parts="images"))
        idx = lambda m: int(os.path.basename(m[4])[6:12])
        members = [m for m in members if lo <= idx(m) < hi and os.path.basename(m[4]) not in fixed]
        if c26.fetch_members(url, members, ends, args.fetch_workers):
            raise IOError(f"{seq}: images missing after fetch")

    pending = {}

    def prefetch(k):
        try:
            fetch_window(wins[k])
            pending[k] = True
        except Exception as e:                       # noqa: BLE001 - re-raised by the consumer
            pending[k] = e

    pool = mp.get_context("fork").Pool(args.procs)     # before any thread exists
    th = threading.Thread(target=prefetch, args=(0,)) if wins else None
    if th:
        th.start()
    rows_cache = {}
    for k, (sp, seq, lo, hi) in enumerate(wins):
        th.join()
        res = pending.pop(k)
        if isinstance(res, Exception):
            raise res
        if k + 1 < len(wins):
            th = threading.Thread(target=prefetch, args=(k + 1,))
            th.start()
        zs = zsplit(sp)
        o = os.path.join(args.out, sp, seq)
        os.makedirs(o, exist_ok=True)
        if seq not in rows_cache:
            rows_cache.clear()
            r = np.loadtxt(os.path.join(args.dets, zs, seq, "det", "det_nms0.95.txt"), delimiter=",", ndmin=2)
            mgp = os.path.join(o, "mg.npy")
            mg = np.load(mgp) if os.path.isfile(mgp) else np.full(len(r), np.nan, np.float32)
            byf = {}
            for k_, f_ in enumerate(r[:, 0].astype(int) if len(r) else []):
                byf.setdefault(f_, []).append(k_)
            rows_cache[seq] = (r, mg, time.time(), byf)
        r, mg, t0, byf = rows_cache[seq]
        first, last = ranges[sp][seq]
        if lo is not None:
            d = os.path.join(args.tmp, zs, seq, "images")
            jobs, sel = [], []
            for i in range(lo, hi):
                ri = np.asarray(byf.get(i + 1, []), int)
                b = r[ri, 2:6].copy() if len(ri) else np.zeros((0, 4))
                b[:, 2:] += b[:, :2]
                jobs.append((os.path.join(d, f"frame_{i:06d}.jpg"), b, args.kind))
                sel.append(ri)
            out = pool.map(frame_job, jobs, chunksize=8)
            if args.kind == "peg":
                for ri, (_, m) in zip(sel, out):
                    mg[ri] = m
            np.save(os.path.join(o, "mg.npy"), mg)
            tmpf = os.path.join(o, f"sat_{lo}.tmp.npz")
            np.savez_compressed(tmpf, sat=np.stack([s for s, _ in out]))
            os.replace(tmpf, os.path.join(o, f"sat_{lo}.npz"))
            for p, _, _ in jobs:
                if os.path.isfile(p):
                    os.remove(p)
            print(f"    {sp}/{seq}: frames {lo + 1}..{hi} done", flush=True)
        if lo is None or hi == last:
            assert args.kind != "peg" or not np.isnan(mg).any(), f"{seq}: m_glare missing for {int(np.isnan(mg).sum())} rows"
            shutil.rmtree(os.path.join(args.tmp, zs, seq), ignore_errors=True)
            open(os.path.join(o, "DONE"), "w").write(f"{last - first + 1} frames, {len(r)} m_glare rows\n")
            print(f"[done] {sp}/{seq}: {last - first + 1} frames ({(time.time() - t0) / 60:.1f} min)", flush=True)
    pool.close()
    print("PEGSAT_DONE", flush=True)


if __name__ == "__main__":
    main()
