"""Table I baselines on the shared YOLOX detection cache (GlareMOT2, both label fixes), scored like scripts/06.

Detections come from scripts/26 (det_nms0.95 = every box with score >= 0.1 after NMS 0.95). Each method gets its
own detection NMS by re-running NMS on those rows (results/baselines_t1/RUNS.md explains why that matches running
it on the raw detector output); score thresholds are the trackers' own. ReID / GMC inputs come from scripts/27
(<feats>/<split>/<seq>/{emb.npy, gmc.npy}), aligned with the det_nms0.95 rows and frames.
Splits (frames as cached): val_half = official train seqs, frames n//2+1..n (sanity runs / any tuning),
test = official test seqs, all frames (Table I, run once per method).
Output: <out>/<split>/<name>/data/<seq>.txt (frames renumbered from 1), summary.txt (per seq + COMBINED, and
COMBINED without --drop seqs).

  .venv/bin/python scripts/28_run_baselines.py --tracker bytetrack --split val_half
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import trackeval  # noqa: F401  (before any repo goes on sys.path)
import torch
import torchvision

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from glaremot.baselines.adapters import LAZY, TRACKERS, get_tracker  # noqa: E402
from glaremot.eval.eval_mot import print_table, run_trackeval  # noqa: E402

B = os.path.join(ROOT, "results", "baselines_t1")


def load_rows(path):
    a = np.loadtxt(path, delimiter=",", ndmin=2, dtype=np.float64)
    return a if a.size else np.zeros((0, 10))


def per_frame(rows, nms):
    """{frame: (idx into rows, [N,5] x1,y1,x2,y2,score)} after NMS at `nms` (None: as cached)."""
    out = {}
    if not len(rows):
        return out
    order = np.argsort(rows[:, 0], kind="stable")
    frames = rows[order, 0].astype(int)
    cuts = np.flatnonzero(np.diff(frames)) + 1
    for idx in np.split(order, cuts):
        r = rows[idx]
        d = np.c_[r[:, 2], r[:, 3], r[:, 2] + r[:, 4], r[:, 3] + r[:, 5], r[:, 6]]
        if nms is not None and nms < 0.95 and len(d) > 1:
            k = torchvision.ops.nms(torch.from_numpy(d[:, :4]), torch.from_numpy(d[:, 4]), nms).numpy()
            idx, d = idx[k], d[k]
        out[int(r[0, 0])] = (idx, d)
    return out


class SatWindows:
    """Lazy reader of scripts/29's sat_<lo>.npz windows: get(i) = bool 512x512 map of 0-based image index i."""

    def __init__(self, d):
        self.d = d
        self.los = sorted(int(f[4:-4]) for f in os.listdir(d) if f.startswith("sat_") and f.endswith(".npz"))
        self.lo, self.arr = None, None

    def get(self, i):
        lo = max(v for v in self.los if v <= i)
        if lo != self.lo:
            self.lo, self.arr = lo, np.load(os.path.join(self.d, f"sat_{lo}.npz"))["sat"]
        from glaremot.tracking.tracker import PHOTO_S
        return np.unpackbits(self.arr[i - lo], count=PHOTO_S * PHOTO_S).reshape(PHOTO_S, PHOTO_S).astype(bool)


def run_seq(cls, split_dir, feats_dir, seq, first, last, out_txt):
    meta = json.load(open(os.path.join(split_dir, seq, "meta", "DONE.json")))
    fps = int(meta.get("output_integer_fps") or round(meta.get("source_video_fps", 25)))
    hw = (int(meta["video_height"]), int(meta["video_width"]))
    trk = cls(fps, hw, seq)
    rows = load_rows(os.path.join(split_dir, seq, "det", "det_nms0.95.txt"))
    frames = per_frame(rows, cls.nms)
    extra_src = {}
    fd = os.path.join(feats_dir, seq)
    if "emb" in cls.needs:       # rows of det_nms0.95.txt first, then the 0.8-only rows (scripts/27)
        extra_src["emb"] = np.load(os.path.join(fd, "emb.npy"), mmap_mode="r")
        assert len(extra_src["emb"]) >= len(rows), f"{seq}: emb rows {len(extra_src['emb'])} < dets {len(rows)}"
    if "gmc" in cls.needs:
        extra_src["gmc"] = np.load(os.path.join(fd, "gmc.npy"))                 # [last-first+1, 2, 3]
    if "disp" in cls.needs:
        dp = os.path.join(fd, "disp.npy")                                   # [last-first+1, 96, 128] uint8
        extra_src["disp"] = np.load(dp, mmap_mode="r") if os.path.isfile(dp) else \
            np.load(os.path.join(fd, "disp.npz"))["disp"]
    if "pegsat" in cls.needs:     # scripts/29: m_glare per det_nms0.95 row + packed 512x512 saturation maps
        pd = os.path.join(os.path.dirname(os.path.dirname(feats_dir)), "pegsat",
                          os.path.basename(feats_dir), seq)
        extra_src["mg"] = np.load(os.path.join(pd, "mg.npy"))
        assert len(extra_src["mg"]) == len(rows), f"{seq}: mg rows != dets"
        extra_src["satwin"] = SatWindows(pd)
    if "exsat" in cls.needs:      # scripts/29 --kind exsort: ExSORT's own 512x512 saturation masks
        extra_src["satwin"] = SatWindows(os.path.join(os.path.dirname(os.path.dirname(feats_dir)), "exsat",
                                                      os.path.basename(feats_dir), seq))
    if "dets08" in cls.needs:
        extra_src["dets08"] = per_frame(load_rows(os.path.join(split_dir, seq, "det", "det_nms0.8.txt")), None)
        extra_src["idx08"] = np.load(os.path.join(fd, "emb08_idx.npy")) if "emb" in cls.needs else None
    empty = (np.zeros(0, int), np.zeros((0, 5)))
    lines = []
    for f in range(first, last + 1):
        idx, d = frames.get(f, empty)
        extra = {"frame": f - first + 1, "hw": hw}
        if "emb" in extra_src:
            extra["emb"] = np.asarray(extra_src["emb"][idx], dtype=np.float32)
        if "gmc" in extra_src:
            extra["gmc"] = extra_src["gmc"][f - first]
        if "disp" in extra_src:
            extra["disp"] = extra_src["disp"][f - first]
        if "mg" in extra_src:
            extra["mg"] = extra_src["mg"][idx]
        if "satwin" in extra_src:
            extra["sat"] = extra_src["satwin"].get(f - 1)
        if "dets08" in extra_src:
            i08, d08 = extra_src["dets08"].get(f, empty)
            extra["dets08"] = d08
            if extra_src["idx08"] is not None:
                extra["emb08"] = np.asarray(extra_src["emb"][extra_src["idx08"][i08]], dtype=np.float32)
        for tid, x, y, w, h in trk.step(d, extra):
            lines.append(f"{f - first + 1},{int(tid)},{x:.2f},{y:.2f},{w:.2f},{h:.2f},1,-1,-1,-1\n")
    with open(out_txt, "w") as fh:
        fh.writelines(lines)
    return last - first + 1


def gt_workspace(split_dir, seqs, ranges, gt_root):
    """GT rows of the scored frames only, renumbered like the tracker output."""
    lengths = {}
    for s in seqs:
        a, b = ranges[s]
        os.makedirs(os.path.join(gt_root, s, "gt"), exist_ok=True)
        with open(os.path.join(split_dir, s, "gt", "gt.txt")) as fi, \
                open(os.path.join(gt_root, s, "gt", "gt.txt"), "w") as fo:
            for ln in fi:
                p = ln.strip().split(",")
                if len(p) > 1 and a <= int(float(p[0])) <= b:
                    p[0] = str(int(float(p[0])) - a + 1)
                    fo.write(",".join(p) + "\n")
        lengths[s] = b - a + 1
    return lengths


def print_rows(split_root):
    """Markdown Table I (all seqs, then without the --drop seqs) from <split_root>/<name>/summary.txt."""
    order = ["bytetrack", "ocsort", "deepocsort", "diffmot", "botsort", "hybridsort", "tracktrack", "dip"]
    names = [n for n in order if os.path.isfile(os.path.join(split_root, n, "summary.txt"))]
    names += sorted(n for n in os.listdir(split_root) if n not in names and not n.startswith(("_", "smoke"))
                    and os.path.isfile(os.path.join(split_root, n, "summary.txt")))
    cols = "HOTA DetA AssA IDF1 MOTA IDSW Rcll Prcn FP FN".split()
    for k, label in ((0, "all seqs"), (1, "without 401")):
        print(f"\n{label}\n| method | " + " | ".join(cols) + " |\n|---|" + "---|" * len(cols))
        for n in names:
            rows = [ln.split()[1:] for ln in open(os.path.join(split_root, n, "summary.txt")) if ln.startswith("COMBINED")]
            if len(rows) > k:
                print(f"| {n} | " + " | ".join(rows[k]) + " |")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tracker", choices=sorted(TRACKERS) + list(LAZY))
    ap.add_argument("--table", action="store_true", help="print the Table I rows of every finished run of --split")
    ap.add_argument("--split", default="val_half", choices=["val_half", "test"])
    ap.add_argument("--name", help="run name (default: the tracker key)")
    ap.add_argument("--dets", default=os.path.join(B, "dets"))
    ap.add_argument("--feats", default=os.path.join(B, "feats"))
    ap.add_argument("--out", default=os.path.join(B, "runs"))
    ap.add_argument("--seqs", help="comma list (smoke test)")
    ap.add_argument("--drop", default="401_", help="also report COMBINED without seqs starting with this")
    ap.add_argument("--skip_track", action="store_true", help="re-score existing txt")
    args = ap.parse_args()
    if args.table:
        return print_rows(os.path.join(args.out, args.split))
    assert args.tracker, "--tracker is required"

    ranges = json.load(open(os.path.join(args.dets, "splits.json")))[args.split]
    seqs = sorted(ranges) if not args.seqs else [s for s in args.seqs.split(",") if s in ranges]
    split_dir = os.path.join(args.dets, "test" if args.split == "test" else "train")
    feats_dir = os.path.join(args.feats, args.split)
    name = args.name or args.tracker
    run_dir = os.path.join(args.out, args.split, name)
    data_dir = os.path.join(run_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    cls = get_tracker(args.tracker)
    t0, nf = time.time(), 0
    if not args.skip_track:
        for i, s in enumerate(seqs):
            a, b = ranges[s]
            t1 = time.time()
            n = run_seq(cls, split_dir, os.path.join(feats_dir), s, a, b, os.path.join(data_dir, f"{s}.txt"))
            nf += n
            print(f"[{i + 1}/{len(seqs)}] {s}: {n} frames, {n / max(time.time() - t1, 1e-6):.0f} fps", flush=True)
    gt_root = os.path.join(args.out, args.split, "_gt")
    lengths = gt_workspace(split_dir, seqs, ranges, gt_root)
    res = run_trackeval(gt_root, os.path.join(args.out, args.split), name, lengths, run_dir)
    hdr = (f"{name} on {args.split} ({len(seqs)} seqs, YOLOX-X fix2 cache, det NMS {cls.nms}); "
           f"tracking {nf} frames in {time.time() - t0:.0f} s")
    text = print_table(hdr, res)
    keep = [s for s in seqs if not s.startswith(args.drop)] if args.drop else seqs
    if len(keep) < len(seqs):
        sub = run_trackeval(gt_root, os.path.join(args.out, args.split), name,
                            {s: lengths[s] for s in keep}, run_dir)
        text += print_table(f"{name} on {args.split} without {args.drop}* ({len(keep)} seqs)",
                            {"COMBINED_SEQ": sub["COMBINED_SEQ"]})
    with open(os.path.join(run_dir, "summary.txt"), "w") as fh:
        fh.write(text + "\n")


if __name__ == "__main__":
    main()
