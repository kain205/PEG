"""Step 12 -- PEG-F appearance sidecar for the perception caches (CPU only, no detector).

GMOT_REID / GMOT_DORMANT need an HSV appearance per detection, which needs pixels; the
perception cache replays detections without images. This script decodes each cached
sequence's frames (same sorted order as eval_mot), rebuilds the square detector input exactly
as ``Perception.__call__`` does (``square_frame``) and computes ``extract_appearance`` on every
cached det's ``xyxy_s`` (float32, the same values the live path passes), in recorded order.
Writes ``<cache_dir>/<seq>.app.npz`` (app[N,48] float32, NaN rows where None; valid[N]).

  python scripts/12_cache_appearance.py --cache_dir results/percep_cache/real --data_root datasets/real
  python scripts/12_cache_appearance.py --cache_dir results/percep_cache/synth --data_root datasets/synth
"""
import argparse
import glob
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import numpy as np
import torch

from glaremot.config import load_config, weight_path
from glaremot.data.splits import make_splits
from glaremot.eval.percep_cache import app_path, save_appearance
from glaremot.tracking.tracker import extract_appearance, square_frame


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache_dir", required=True)
    ap.add_argument("--data_root", required=True)
    ap.add_argument("--split", default="test", choices=["train", "val", "test", "all"],
                    help="only sequences of this split (that have a cache file)")
    ap.add_argument("--config", default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    S = int(torch.load(weight_path(cfg, "hpsi"), map_location="cpu", weights_only=False)["meta"]["imgsz"])
    sp = make_splits()
    want = set(sp["train"] + sp["val"] + sp["test"]) if args.split == "all" else set(sp[args.split])
    seqs = sorted(os.path.basename(p)[:-len(".npz")]
                  for p in glob.glob(os.path.join(args.cache_dir, "*.npz"))
                  if not p.endswith((".app.npz", ".tmp.npz")))
    seqs = [s for s in seqs if s in want]
    print(f"{len(seqs)} cached sequences | S={S} | data_root={args.data_root}", flush=True)

    for i, seq in enumerate(seqs, 1):
        path = os.path.join(args.cache_dir, f"{seq}.npz")
        out = app_path(path)
        if os.path.exists(out) and not args.overwrite:
            print(f"[{i}/{len(seqs)}] {seq}: exists, skip", flush=True)
            continue
        t0 = time.time()
        z = np.load(path)
        n_frames, df, xyxy = int(z["n_frames"]), z["det_frame"], z["xyxy"]
        img_paths = sorted(glob.glob(os.path.join(args.data_root, seq, "images", "*.jpg")))
        if len(img_paths) != n_frames:
            raise ValueError(f"{seq}: cache has {n_frames} frames, {len(img_paths)} images on disk")
        # dets of frame f are the contiguous rows df == f (recorded in frame order)
        starts = np.searchsorted(df, np.arange(n_frames + 1))
        apps = [None] * len(df)
        with ThreadPoolExecutor(4) as ex:
            for f, frame in enumerate(ex.map(cv2.imread, img_paths)):
                a, b = starts[f], starts[f + 1]
                if a == b:
                    continue
                sq = square_frame(frame, S)
                for k in range(a, b):
                    apps[k] = extract_appearance(sq, tuple(xyxy[k]))
        save_appearance(out, apps)
        n_ok = sum(a is not None for a in apps)
        print(f"[{i}/{len(seqs)}] {seq}: {n_frames} frames, {len(apps)} dets "
              f"({n_ok} with appearance) {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
