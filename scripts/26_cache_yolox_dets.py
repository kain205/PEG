"""Full-frame YOLOX detection cache for the GlareMOT2 sequences (team task, 2026-10-28; val+test only since 2026-11-02).

The dataset is kept as it is: every frame at the sequence's own fps, no glare filter. The splits are:
  train_half = official train seqs, frames 1 .. n//2      (the detector was fine-tuned on 2.5 fps samples of these)
  val_half   = official train seqs, frames n//2+1 .. n    (tune trackers here)
  test       = official test seqs, all frames             (score once)
`--splits` picks which ones to cache (Minh, 2026-11-02: val_half,test). Each seq is streamed from the Drive zip
(scripts/24): GT + meta first, then the label fixes released after the zip are copied over it (--overlay, e.g.
400/401 *_fixed.zip and the 2026-11-01 cam-5 fix), then only the images of the wanted frames. Every one of those
frames goes through the detector, the results are written, and the images are deleted. The next seq downloads while
the current one is running.

Output (<out>/):
  splits.json                          frame ranges of the cached splits + detector / settings / ckpt md5
  <split>/<seq>/det/det_nms{0.8,0.95}.txt   MOT det rows: frame,-1,x,y,w,h,score,-1,-1,-1 (native pixels, score >= --conf);
                                       frame numbers are those of the full seq (a val_half file starts at n//2+1)
  <split>/<seq>/gt/gt.txt, meta/       GT and meta as released (or as fixed by the overlay), whole seq
Two NMS levels as in TrackTrack (0.8 for matching, 0.95 for its "deleted" low-confidence set).

Run inside the ByteTrack repo (its YOLOX fork):
  PYTHONPATH=/content/ByteTrack python3 scripts/26_cache_yolox_dets.py --exp configs/yolox/yolox_x_glaremot2_half.py \\
      --ckpt best.pth --out /content/dets --overlay /content/overlay --splits val_half,test
"""
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import threading
import time

import cv2
import numpy as np
import torch
import torchvision

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("fetch", os.path.join(ROOT, "scripts", "24_fetch_glaremot.py"))
fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch)

MEAN, STD = np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225])
SPLITS = ("train_half", "val_half", "test")


def preproc(img, size):
    """ByteTrack's preproc (the weights were trained with it): resize keeping ratio, pad 114, BGR->RGB, mean/std."""
    r = min(size[0] / img.shape[0], size[1] / img.shape[1])
    out = np.full((size[0], size[1], 3), 114.0, np.float32)
    h, w = int(img.shape[0] * r), int(img.shape[1] * r)
    out[:h, :w] = cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    out = (out[:, :, ::-1] / 255.0 - MEAN) / STD
    return np.ascontiguousarray(out.transpose(2, 0, 1), dtype=np.float32), r


class Frames(torch.utils.data.Dataset):
    def __init__(self, paths, size):
        self.paths, self.size = paths, size

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        img = cv2.imread(self.paths[i])
        x, r = preproc(img, self.size)
        return torch.from_numpy(x), r, i


def frame_range(split, n, want):
    """0-based image indices [a, b) of one seq covered by the wanted splits (a == b: nothing to do)."""
    if split == "test":
        return (0, n) if "test" in want else (0, 0)
    a = 0 if "train_half" in want else n // 2
    b = n if "val_half" in want else n // 2
    return (a, b) if a < b else (0, 0)


def apply_overlay(overlay, split, seq, dest):
    """Copy <overlay>/<split>/<seq>/** over the streamed seq; returns the set of written paths (empty: no fix)."""
    src = os.path.join(overlay, split, seq) if overlay else None
    done = set()
    if not src or not os.path.isdir(src):
        return done
    for root, _, files in os.walk(src):
        dst = os.path.join(dest, split, seq, os.path.relpath(root, src))
        os.makedirs(dst, exist_ok=True)
        for f in files:
            shutil.copy2(os.path.join(root, f), os.path.join(dst, f))
            done.add(os.path.join(dst, f))
    return done


def fetch_members(url, members, ends, workers):
    """Fetch zip members (skipping files already complete on disk); returns the paths still missing."""
    members = [m + (ends[m[2]],) for m in members]
    gs = [g for g in fetch.groups(members, 512 << 20) if any(not fetch.done_already(m) for m in g)]
    stats, lock = {"bytes": 0, "files": 0}, threading.Lock()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(workers) as ex:
        for f in [ex.submit(fetch.fetch_group, url, g, stats, lock) for g in gs]:
            f.result()
    return [m[4] for m in members if not fetch.done_already(m)]


def download(url, ix, split, seq, dest, workers, overlay, want):
    """GT + meta, then the label fix, then only the images of the wanted frames. Returns the overlay's paths."""
    base = dict(zip="v2", out=os.path.join(dest, split), split=split, old_split=None, seqs=seq)
    members, ends = fetch.select(ix, argparse.Namespace(**base, parts="mot,meta"))
    missing = fetch_members(url, members, ends, workers)
    if missing:
        raise IOError(f"{seq}: {len(missing)} gt/meta files missing after fetch")
    fixed = apply_overlay(overlay, split, seq, dest)
    n = int(json.load(open(os.path.join(dest, split, seq, "meta", "DONE.json")))["written_images"])
    a, b = frame_range(split, n, want)
    members, ends = fetch.select(ix, argparse.Namespace(**base, parts="images"))
    idx = lambda m: int(os.path.basename(m[4])[6:12])            # frame_000123.jpg
    members = [m for m in members if a <= idx(m) < b and m[4] not in fixed]   # images of a fix win over the zip
    missing = fetch_members(url, members, ends, workers)
    if missing:
        raise IOError(f"{seq}: {len(missing)} images missing after fetch")
    return fixed


@torch.no_grad()
def detect(model, paths, size, conf, nms_levels, batch, workers, frame0=0):
    """MOT det rows per NMS level; paths[i] is MOT frame frame0 + i + 1."""
    dl = torch.utils.data.DataLoader(Frames(paths, size), batch_size=batch, num_workers=workers, pin_memory=True)
    rows = {n: [] for n in nms_levels}
    for x, r, idx in dl:
        out = model(x.cuda(non_blocking=True).half()).float()        # [B, A, 5 + C]: cx, cy, w, h, obj, cls
        boxes = torch.cat([out[..., :2] - out[..., 2:4] / 2, out[..., :2] + out[..., 2:4] / 2], -1)
        score = out[..., 4] * out[..., 5]
        for b in range(out.shape[0]):
            keep = score[b] >= conf
            bb, ss = boxes[b][keep], score[b][keep]
            frame = frame0 + int(idx[b]) + 1
            for n in nms_levels:
                k = torchvision.ops.nms(bb, ss, n)
                d = (bb[k] / float(r[b])).cpu().numpy()
                s = ss[k].cpu().numpy()
                for (x1, y1, x2, y2), sc in zip(d, s):
                    rows[n].append(f"{frame},-1,{x1:.1f},{y1:.1f},{x2 - x1:.1f},{y2 - y1:.1f},{sc:.4f},-1,-1,-1\n")
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--exp", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tmp", default="/content/stream")
    ap.add_argument("--overlay", help="dir with <split>/<seq>/... label fixes copied over the streamed seq")
    ap.add_argument("--splits", default="train_half,val_half,test", help="comma list of " + ",".join(SPLITS))
    ap.add_argument("--conf", type=float, default=0.1)
    ap.add_argument("--nms", default="0.8,0.95")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--fetch_workers", type=int, default=16)
    ap.add_argument("--seqs", help="comma list (smoke test)")
    ap.add_argument("--url", help="zip URL override (see 24_fetch_glaremot.py --url)")
    args = ap.parse_args()
    want = set(args.splits.split(","))
    assert want and want <= set(SPLITS), f"--splits must be a subset of {SPLITS}"

    from yolox.exp import get_exp
    exp = get_exp(args.exp, None)
    model = exp.get_model().cuda().eval()
    sd = torch.load(args.ckpt, map_location="cpu", weights_only=True)
    model.load_state_dict({k: v.float() for k, v in sd.get("model", sd).items()})
    model.half()
    nms_levels = [float(v) for v in args.nms.split(",")]
    size = tuple(exp.test_size)

    file_id = fetch.ZIPS["v2"][0]
    url = args.url or fetch.drive_url(file_id)
    ix = fetch.load_index(url, os.path.join(ROOT, "cache", f"zipindex_{file_id}.json"))
    # seqs of the official splits the wanted splits come from, in zip order (test first, then train)
    seqs = []
    for split in (["test"] if "test" in want else []) + (["train"] if want & {"train_half", "val_half"} else []):
        sel = argparse.Namespace(zip="v2", out="/", split=split, old_split=None, seqs=args.seqs, parts="meta")
        members, _ = fetch.select(ix, sel)
        first = {}
        for m in members:
            first.setdefault(m[0].split("/")[2], m[2])
        seqs += [(split, s) for s, _ in sorted(first.items(), key=lambda kv: kv[1])]

    os.makedirs(args.out, exist_ok=True)
    md5 = hashlib.md5(open(args.ckpt, "rb").read()).hexdigest()
    splits_path = os.path.join(args.out, "splits.json")
    splits = json.load(open(splits_path)) if os.path.isfile(splits_path) else {
        **{sp: {} for sp in SPLITS if sp in want},
        "note": "MOT frame ranges [first, last], inclusive. train_half/val_half split the official train seqs at n//2. "
                "Det files hold only the frames of the cached splits; gt.txt is the whole seq.",
        "detector": {"exp": os.path.basename(args.exp), "ckpt": os.path.basename(args.ckpt), "ckpt_md5": md5,
                     "test_size": list(size), "conf": args.conf, "nms": nms_levels, "fp16": True,
                     "cached_splits": [sp for sp in SPLITS if sp in want]}}

    pending = {}

    def prefetch(split, seq):
        try:
            pending[(split, seq)] = download(url, ix, split, seq, args.tmp, args.fetch_workers, args.overlay, want)
        except Exception as e:                       # noqa: BLE001 - reported by the consumer
            pending[(split, seq)] = e

    todo = [(sp, s) for sp, s in seqs if not os.path.isfile(os.path.join(args.out, sp, s, "DONE"))]
    print(f"[cache] splits {sorted(want)}: {len(seqs)} seqs, {len(todo)} to do", flush=True)
    th = None
    if todo:
        th = threading.Thread(target=prefetch, args=todo[0]); th.start()
    for k, (split, seq) in enumerate(todo):
        t0 = time.time()
        th.join()
        res = pending.pop((split, seq))
        if isinstance(res, Exception):
            raise res
        fixed = bool(res)
        if k + 1 < len(todo):
            th = threading.Thread(target=prefetch, args=todo[k + 1]); th.start()
        d = os.path.join(args.tmp, split, seq)
        n = int(json.load(open(os.path.join(d, "meta", "DONE.json")))["written_images"])
        a, b = frame_range(split, n, want)
        paths = [os.path.join(d, "images", f"frame_{i:06d}.jpg") for i in range(a, b)]
        absent = [p for p in paths if not os.path.isfile(p)]
        if absent:
            raise IOError(f"{seq}: {len(absent)} of {b - a} frames absent, e.g. {absent[:2]}")
        t1 = time.time()
        rows = detect(model, paths, size, args.conf, nms_levels, args.batch, args.workers, frame0=a)
        o = os.path.join(args.out, split, seq)
        os.makedirs(os.path.join(o, "det"), exist_ok=True)
        for nl, rr in rows.items():
            with open(os.path.join(o, "det", f"det_nms{nl}.txt"), "w") as f:
                f.writelines(rr)
        shutil.copytree(os.path.join(d, "mot", "gt"), os.path.join(o, "gt"), dirs_exist_ok=True)
        shutil.copytree(os.path.join(d, "meta"), os.path.join(o, "meta"), dirs_exist_ok=True)
        if split == "train":
            if "train_half" in want:
                splits["train_half"][seq] = [1, n // 2]
            if "val_half" in want:
                splits["val_half"][seq] = [n // 2 + 1, n]
        else:
            splits["test"][seq] = [1, n]
        json.dump(splits, open(splits_path, "w"), indent=1)
        open(os.path.join(o, "DONE"), "w").write(
            f"{n} frames, detected {a + 1}..{b}{' (label fix applied)' if fixed else ''}\n")
        shutil.rmtree(d)
        print(f"[{k + 1}/{len(todo)}] {split}/{seq}: {n} frames, detected {a + 1}..{b}, "
              f"{len(rows[nms_levels[0]])} dets@nms{nms_levels[0]}, detect {(b - a) / max(1e-6, time.time() - t1):.0f} fps, "
              f"total {(time.time() - t0) / 60:.1f} min{' [label fix]' if fixed else ''}", flush=True)
    print("CACHE_DONE", flush=True)


if __name__ == "__main__":
    main()
