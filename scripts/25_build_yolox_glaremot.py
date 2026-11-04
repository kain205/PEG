"""Build a YOLOX (ByteTrack-style COCO) detector set from the GlareMOT2 official train split, streamed from Drive.

Recipe (team decision, 2026-10-26):
  * `--split train` (71 seqs) -> train_half.json / val_half.json (below); `--split test` (48 seqs) -> test.json with every
    sampled frame of each seq, same sampling and filter (a shared cache for the team; score on it once, never tune);
  * per seq, frames sampled at ~--target_fps (2-3 fps; adjacent frames are near-duplicates -> overfit);
  * first half of each seq (by frame index) -> train_half.json, second half -> val_half.json
    (the MOT17 "half" protocol of ByteTrack / TrackTrack);
  * a frame is dropped if any GT box has > --sat_max of its pixels saturated
    (glaremot.photometric.saturation_map: HSV V >= 0.92 and S <= 0.35). The detector should learn visible people
    only; burnt-out people are the tracker's job (PEG). Frames listed in meta/uncertain_frames.csv are dropped too;
  * boxes: GT rows with visibility > 0, clipped to the image.

Only the sampled JPEGs are fetched (one ranged GET each), so the 115 GB split costs ~1/9 of that.
Output (= YOLOX data_dir): <out>/annotations/{train_half,val_half}.json, <out>/train/<seq>/images/*.jpg,
<out>/build_stats.json (per-seq counts, saturation fractions).

  python scripts/25_build_yolox_glaremot.py --out /content/yx --workers 16
"""
import argparse
import csv
import importlib.util
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from glaremot.photometric import saturation_map  # noqa: E402

_spec = importlib.util.spec_from_file_location("fetch", os.path.join(ROOT, "scripts", "24_fetch_glaremot.py"))
fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch)


def run_fetch(url, members, ends, workers, label):
    members = [m + (ends[m[2]],) for m in members]
    todo = [m for m in members if not fetch.done_already(m)]
    print(f"[{label}] {len(members)} files, {sum(m[1] for m in todo) / 1e9:.2f} GB to go", flush=True)
    gs = [g for g in fetch.groups(members, 512 << 20) if any(not fetch.done_already(m) for m in g)]
    stats, lock, t0 = {"bytes": 0, "files": 0}, threading.Lock(), time.time()
    with ThreadPoolExecutor(workers) as ex:
        futs = [ex.submit(fetch.fetch_group, url, g, stats, lock) for g in gs]
        for k, f in enumerate(as_completed(futs), 1):
            f.result()
            if k % 500 == 0 or k == len(gs):
                dt = time.time() - t0
                print(f"[{label} {k}/{len(gs)}] {stats['bytes'] / 1e9:.1f} GB, {stats['bytes'] / 1e6 / dt:.0f} MB/s",
                      flush=True)
    missing = [m[4] for m in members if not fetch.done_already(m)]
    if missing:
        sys.exit(f"{len(missing)} files missing, e.g. {missing[:3]}")


def apply_overlay(overlay, split, raw):
    """Copy <overlay>/<split>/<seq>/** over <raw>/<seq>/; returns the set of written paths."""
    import shutil
    src, done = os.path.join(overlay, split), set()
    if not os.path.isdir(src):
        return done
    for root, _, files in os.walk(src):
        dst = os.path.join(raw, os.path.relpath(root, src))
        os.makedirs(dst, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(dst, f))
            done.add(os.path.join(dst, f))
    seqs = sorted({os.path.relpath(p, raw).split(os.sep)[0] for p in done})
    print(f"[overlay] {len(done)} files over {len(seqs)} seqs: {','.join(s.split('_')[0] for s in seqs)}", flush=True)
    return done


def uncertain(seq_dir):
    p = os.path.join(seq_dir, "meta", "uncertain_frames.csv")
    if not os.path.isfile(p):
        return set()
    with open(p) as f:
        return {int(r["target_frame"]) for r in csv.DictReader(f)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--split", default="train", choices=["train", "test"], help="official split to build from")
    ap.add_argument("--target_fps", type=float, default=2.5)
    ap.add_argument("--sat_max", type=float, default=0.25)
    ap.add_argument("--seqs", help="comma list of seq names/ids (smoke tests)")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--index", help="central-directory cache; default cache/zipindex_<id>.json")
    ap.add_argument("--url", help="zip URL override (see 24_fetch_glaremot.py --url)")
    ap.add_argument("--overlay", help="dir with <split>/<seq>/... label fixes released after the zip (mot/, meta/, extra "
                    "images); copied over each seq after its GT is fetched, and its images are never re-fetched")
    ap.add_argument("--no_fetch", action="store_true",
                    help="use only files already under --out (Drive per-file quota exceeded); absent frames are skipped")
    args = ap.parse_args()

    file_id, prefix, _ = fetch.ZIPS["v2"]
    url = args.url or fetch.drive_url(file_id)
    ix = fetch.load_index(url, args.index or os.path.join(ROOT, "cache", f"zipindex_{file_id}.json"))
    raw = os.path.join(args.out, args.split)
    sel = argparse.Namespace(zip="v2", out=raw, split=args.split, old_split=None, seqs=args.seqs, parts="meta,mot")
    members, ends = fetch.select(ix, sel)
    if not args.no_fetch:
        run_fetch(url, members, ends, args.workers, "meta+gt")
    from_overlay = apply_overlay(args.overlay, args.split, raw) if args.overlay else set()

    # pick frames per seq
    sel.parts = "images"
    imgs, ends = fetch.select(ix, sel)
    by_path = {m[4]: m for m in imgs}
    seqs = sorted({os.path.relpath(m[4], raw).split(os.sep)[0] for m in members})
    plan = {}
    for seq in seqs:
        d = os.path.join(raw, seq)
        meta = json.load(open(os.path.join(d, "meta", "DONE.json")))
        n, fps = int(meta["written_images"]), float(meta["output_integer_fps"])
        stride = max(1, round(fps / args.target_fps))
        plan[seq] = dict(n=n, fps=fps, stride=stride, half=n // 2, frames=list(range(0, n, stride)))
    paths = [os.path.join(raw, s, "images", f"frame_{i:06d}.jpg") for s in seqs for i in plan[s]["frames"]]
    want = [by_path[p] for p in paths if p in by_path and p not in from_overlay]
    # frames that are not in the zip: a label fix released after the zip (e.g. 400_sequence_morongmo_fixed.zip,
    # meta/mot + extra images copied over the seq dir) can make a seq longer; those images must already be on disk
    extra = [p for p in paths if p not in by_path and not os.path.isfile(p)]
    if extra and not args.no_fetch:
        sys.exit(f"{len(extra)} sampled frames are neither in the zip nor on disk, e.g. {extra[:3]}")
    if not args.no_fetch:
        run_fetch(url, want, ends, args.workers, "images")

    out = {k: {"images": [], "annotations": [], "categories": [{"id": 1, "name": "person"}],
               "videos": []} for k in (("train_half", "val_half") if args.split == "train" else ("test",))}
    img_id = ann_id = 0
    stats = {"args": vars(args), "seqs": {}}
    for vid, seq in enumerate(seqs, 1):
        d, p = os.path.join(raw, seq), plan[seq]
        gt = np.loadtxt(os.path.join(d, "mot", "gt", "gt.txt"), delimiter=",", ndmin=2)
        unc = uncertain(d)
        st = dict(fps=p["fps"], stride=p["stride"], n=p["n"], sampled=0, absent=0, drop_sat=0, drop_uncertain=0,
                  kept={k: 0 for k in out}, boxes={k: 0 for k in out}, sat_fracs=[])
        for k in out:
            out[k]["videos"].append({"id": vid, "file_name": seq})
        for i in p["frames"]:
            st["sampled"] += 1
            part = "test" if args.split == "test" else ("train_half" if i < p["half"] else "val_half")
            if i in unc or i + 1 in unc:              # target_frame base is not documented: drop both readings
                st["drop_uncertain"] += 1
                continue
            rel = os.path.join(args.split, seq, "images", f"frame_{i:06d}.jpg")
            if not os.path.isfile(os.path.join(args.out, rel)):
                st["absent"] += 1                     # only with --no_fetch
                continue
            im = cv2.imread(os.path.join(args.out, rel))
            H, W = im.shape[:2]
            sat = saturation_map(im)
            rows = gt[gt[:, 0] == i + 1]
            boxes, worst = [], 0.0
            for r in rows:
                x1, y1 = max(0.0, r[2]), max(0.0, r[3])
                x2, y2 = min(float(W), r[2] + r[4]), min(float(H), r[3] + r[5])
                if x2 - x1 < 1 or y2 - y1 < 1:
                    continue
                f = float(sat[int(y1):int(np.ceil(y2)), int(x1):int(np.ceil(x2))].mean())
                worst = max(worst, f)
                if r[8] > 0:
                    boxes.append((x1, y1, x2 - x1, y2 - y1, int(r[1])))
            st["sat_fracs"].append(round(worst, 4))
            if worst > args.sat_max:
                st["drop_sat"] += 1
                continue
            img_id += 1
            out[part]["images"].append({"id": img_id, "file_name": rel, "width": W, "height": H,
                                        "frame_id": i + 1, "video_id": vid})
            for x, y, w, h, tid in boxes:
                ann_id += 1
                out[part]["annotations"].append({"id": ann_id, "image_id": img_id, "category_id": 1,
                                                 "bbox": [round(x, 2), round(y, 2), round(w, 2), round(h, 2)],
                                                 "area": round(w * h, 2), "iscrowd": 0, "track_id": tid})
            st["kept"][part] += 1
            st["boxes"][part] += len(boxes)
        stats["seqs"][seq] = st
        print(f"{seq:32s} fps {p['fps']:.0f} stride {p['stride']:2d} sampled {st['sampled']:4d} "
              f"absent {st['absent']:4d} drop sat {st['drop_sat']:3d} unc {st['drop_uncertain']:3d} kept {st['kept']}", flush=True)
    os.makedirs(os.path.join(args.out, "annotations"), exist_ok=True)
    for k, v in out.items():
        json.dump(v, open(os.path.join(args.out, "annotations", f"{k}.json"), "w"))
    tot = {k: (len(v["images"]), len(v["annotations"])) for k, v in out.items()}
    stats["total"] = tot
    json.dump(stats, open(os.path.join(args.out, f"build_stats_{args.split}.json"), "w"))
    print(f"[done] seqs {len(seqs)} | (images, boxes) {tot} | dropped sat "
          f"{sum(s['drop_sat'] for s in stats['seqs'].values())} uncertain "
          f"{sum(s['drop_uncertain'] for s in stats['seqs'].values())}", flush=True)


if __name__ == "__main__":
    main()
