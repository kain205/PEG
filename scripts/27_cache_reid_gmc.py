"""ReID embeddings + camera-motion (GMC) + depth per frame for the Table I baselines, on the scripts/26 detection cache (Colab).

For every row of <dets>/<split>/<seq>/det/det_nms0.95.txt (all boxes with score >= 0.1; the stricter NMS levels the
trackers use are subsets of these rows) it stores one FastReID embedding, and for every frame of the cached range one
2x3 GMC matrix. The images are streamed from the GlareMOT2 Drive zip with the same code and label-fix overlay as
scripts/26 (only the frames of the wanted split), used once, then deleted.
  ReID: FastReID SBS-S50, MOT20 weights (BoT-SORT release), run exactly as TrackTrack's/Deep-OC-SORT's embedder:
        box rounded and clipped to the image, BGR->RGB crop, resize to 128x384, fp16 model, L2-normalised.
        (BoT-SORT truncates instead of rounding; < 1 px difference.)
  GMC:  BoT-SORT tracker/gmc.py, method sparseOptFlow, downscale 2 (its default). H_t only depends on frames t-1 and t,
        so each seq is cut into chunks that run in parallel, each starting one frame early: identical to a sequential
        run. The first cached frame gets the identity (as the first frame of a BoT-SORT run).
  Depth (DIP only, --megadepth): MegaDepth best_generalization_net_G at 384x512 as in DIP's tools/demo_images.py,
        disparity = 1/exp(log-depth) divided by its per-frame max, area-downsampled to 96x128, stored as uint8.
Output: <out>/<split>/<seq>/
  emb.npy        float16 [N95 + E, 2048]: rows of det_nms0.95.txt in file order, then the E det_nms0.8 rows that have
                 no identical 0.95 row (rare)
  emb08_idx.npy  int64 [rows of det_nms0.8.txt]: row of emb.npy for each 0.8 row (TrackTrack uses both sets)
  gmc.npy        float32 [last-first+1, 2, 3];  disp.npy uint8 [last-first+1, 96, 128] (older runs: disp.npz);  DONE

  python3 scripts/27_cache_reid_gmc.py --dets /content/dets --out /content/feats --overlay /content/overlay \\
      --reid_root "/content/TrackTrack/2. FastReID" --reid_weights /content/mot20_sbs_S50.pth --botsort /content/BoT-SORT
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
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":       # spawned GMC workers re-import this file: keep them light
    c26 = _load("c26", os.path.join(ROOT, "scripts", "26_cache_yolox_dets.py"))
    fetch = c26.fetch


def gmc_chunk(args):
    """GMC matrices of frames lo..hi-1; `paths` starts one frame early (at lo-1, unless lo == 0) so H of frame lo is
    the same as in a sequential run. Runs in a spawned worker: everything it needs comes in `args`."""
    gmc_path, paths, lo, hi = args
    gmc = _load("botsort_gmc", gmc_path)
    g = gmc.GMC(method="sparseOptFlow", downscale=2)
    out = np.zeros((hi - lo, 2, 3), np.float32)
    for j, p in enumerate(paths):
        H = g.apply(cv2.imread(p))
        i = (lo - 1 if lo else 0) + j
        if i >= lo:
            out[i - lo] = H if i > 0 else np.eye(2, 3)
    return lo, out


class Crops(torch.utils.data.Dataset):
    """One item per frame: the 128x384 RGB crops of its boxes (as TrackTrack's EmbeddingComputer makes them) and,
    with depth on, the frame resized to 512x384 RGB in [0, 1] for MegaDepth (DIP's tools/demo_images.py)."""

    def __init__(self, paths, boxes, depth):
        self.paths, self.boxes, self.depth = paths, boxes, depth   # boxes[i]: [n, 4] x1, y1, x2, y2 (may be empty)

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, i):
        b = self.boxes[i]
        if not len(b) and not self.depth:
            return torch.zeros((0, 3, 384, 128)), None, i
        img = cv2.imread(self.paths[i])
        h, w = img.shape[:2]
        bc = np.round(b).astype(np.int32)
        bc[:, [0, 2]] = bc[:, [0, 2]].clip(0, w)
        bc[:, [1, 3]] = bc[:, [1, 3]].clip(0, h)
        crops = []
        for x1, y1, x2, y2 in bc:
            x2, y2 = max(x2, min(x1 + 1, w)), max(y2, min(y1 + 1, h))     # never an empty crop
            x1, y1 = min(x1, x2 - 1), min(y1, y2 - 1)
            c = cv2.cvtColor(img[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
            c = cv2.resize(c, (128, 384), interpolation=cv2.INTER_LINEAR).astype(np.float32)
            crops.append(torch.from_numpy(c.transpose(2, 0, 1).copy()))
        crops = torch.stack(crops) if crops else torch.zeros((0, 3, 384, 128))
        dimg = None
        if self.depth:   # skimage resize(order=1) downsamples with anti-aliasing; INTER_AREA is the cv2 equivalent
            d = cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2RGB), (512, 384), interpolation=cv2.INTER_AREA)
            dimg = torch.from_numpy(d.transpose(2, 0, 1).astype(np.float32) / 255.0)
        return crops, dimg, i


def read_dets(path):
    a = np.loadtxt(path, delimiter=",", ndmin=2, dtype=np.float64)
    return a if a.size else np.zeros((0, 10))


def match_rows(r08, r95):
    """Index of the identical det_nms0.95 row for every det_nms0.8 row (same frame, box, score), -1 if none.
    Both files come from the same raw detections, so NMS 0.8 keeps a subset of NMS 0.95's boxes except in rare
    chains (a box suppressed at 0.95 by a box that 0.8 itself suppressed)."""
    key = lambda r: (int(r[0]), round(r[2], 1), round(r[3], 1), round(r[4], 1), round(r[5], 1), round(r[6], 4))
    at = {key(r): k for k, r in enumerate(r95)}
    return np.array([at.get(key(r), -1) for r in r08], np.int64)


@torch.no_grad()
def embed(model, depth_net, paths, rows, first, workers):
    """emb [len(rows), 2048] float16 (rows in the given order) and, with depth_net, per-frame disparity
    [len(paths), 96, 128] uint8 = round(255 * (1/exp(MegaDepth log-depth)) / its max) at 384x512, area-downsampled.
    paths[i] is MOT frame first + i."""
    by_frame = [[] for _ in paths]
    for k, f in enumerate(rows[:, 0].astype(int)):
        by_frame[f - first].append(k)
    boxes = [np.c_[rows[ix, 2], rows[ix, 3], rows[ix, 2] + rows[ix, 4], rows[ix, 3] + rows[ix, 5]] if ix
             else np.zeros((0, 4)) for ix in by_frame]
    emb = np.zeros((len(rows), 2048), np.float16)
    disp = np.zeros((len(paths), 96, 128), np.uint8) if depth_net is not None else None
    dl = torch.utils.data.DataLoader(Crops(paths, boxes, depth_net is not None), batch_size=16, num_workers=workers,
                                     collate_fn=lambda b: b, pin_memory=False, prefetch_factor=2)
    for batch in dl:
        crops = [c for c, _, _ in batch if len(c)]
        if crops:
            x = torch.cat(crops).cuda(non_blocking=True)
            e = torch.cat([model(x[j:j + 1024]) for j in range(0, len(x), 1024)])
            e = torch.nn.functional.normalize(e.float(), dim=-1).cpu().numpy().astype(np.float16)
            k = 0
            for c, _, i in batch:
                n = len(c)
                if n:
                    emb[by_frame[i]] = e[k:k + n]
                    k += n
        if disp is not None:
            x = torch.stack([d for _, d, _ in batch]).cuda(non_blocking=True)
            inv = 1.0 / torch.exp(depth_net(x).squeeze(1))                    # [B, 384, 512] disparity
            inv = inv / inv.flatten(1).amax(1).view(-1, 1, 1)
            inv = torch.nn.functional.interpolate(inv[:, None], size=(96, 128), mode="area")[:, 0]
            q = (inv * 255).round().clamp(0, 255).byte().cpu().numpy()
            for j, (_, _, i) in enumerate(batch):
                disp[i] = q[j]
    return emb, disp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dets", required=True, help="scripts/26 output (splits.json, <split>/<seq>/det)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tmp", default="/content/stream")
    ap.add_argument("--overlay")
    ap.add_argument("--splits", default="test,val_half")
    ap.add_argument("--reid_root", required=True, help="dir that holds the `fastreid` package + configs/")
    ap.add_argument("--reid_cfg", default="configs/MOT20/sbs_S50.yml")
    ap.add_argument("--reid_weights", required=True)
    ap.add_argument("--botsort", required=True, help="BoT-SORT clone (tracker/gmc.py)")
    ap.add_argument("--megadepth", help="MegaDepth clone (pytorch_DIW_scratch.py); with --megadepth_weights: DIP depth")
    ap.add_argument("--megadepth_weights")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--gmc_procs", type=int, default=6)
    ap.add_argument("--fetch_workers", type=int, default=16)
    ap.add_argument("--chunk", type=int, default=4000, help="frames per download window (disk use ~2 windows)")
    ap.add_argument("--seqs", help="comma list (smoke test)")
    ap.add_argument("--url")
    args = ap.parse_args()
    gmc_path = os.path.join(args.botsort, "tracker", "gmc.py")

    sys.path.insert(0, args.reid_root)
    from fastreid.fastreid_adaptor import FastReID
    model = FastReID(os.path.join(args.reid_root, args.reid_cfg), args.reid_weights)
    depth_net = None
    if args.megadepth:
        sys.path.insert(0, args.megadepth)
        import pytorch_DIW_scratch
        depth_net = pytorch_DIW_scratch.pytorch_DIW_scratch
        sd = torch.load(args.megadepth_weights, map_location="cpu")
        depth_net.load_state_dict({k.replace("module.", "", 1): v for k, v in sd.items()})
        depth_net = depth_net.cuda().eval()

    ranges = json.load(open(os.path.join(args.dets, "splits.json")))
    want = args.splits.split(",")
    todo = []
    for sp in want:
        for seq in sorted(ranges[sp]):
            if args.seqs and seq not in args.seqs.split(","):
                continue
            if not os.path.isfile(os.path.join(args.out, sp, seq, "DONE")):
                todo.append((sp, seq))
    file_id = fetch.ZIPS["v2"][0]
    url = args.url or fetch.drive_url(file_id)
    ix = fetch.load_index(url, os.path.join(ROOT, "cache", f"zipindex_{file_id}.json"))
    zsplit = lambda sp: "test" if sp == "test" else "train"
    print(f"[feats] {len(todo)} seqs to do ({args.splits})", flush=True)

    # Work in windows of --chunk frames (a whole seq when it is shorter): download window k+1 while window k runs,
    # delete each window's images once used (the last one stays for the next window's GMC), so the disk only holds
    # ~2 windows (e.g. 401_sequence_nga3 = 75k frames ~ 64 GB would not fit on a small local disk).
    wins = []
    for sp, seq in todo:
        first, last = ranges[sp][seq]
        lo0, hi0 = first - 1, last                        # 0-based image indices of the cached frame range
        o = os.path.join(args.out, sp, seq)
        start = lo0                                       # resume after the last finished window, if any
        if os.path.isfile(os.path.join(o, "progress.json")) and \
                all(os.path.isfile(os.path.join(o, f + ".part")) for f in ("emb.npy", "gmc.npy")):
            start = json.load(open(os.path.join(o, "progress.json")))["done_until"]
            print(f"[feats] {sp}/{seq}: resuming at frame {start + 1}", flush=True)
        for lo in range(start, hi0, args.chunk):
            hi = min(lo + args.chunk, hi0)
            # (split, seq, lo, hi, seq_start, is_last, init): init = first window of this seq in this run
            wins.append((sp, seq, lo, hi, lo == lo0, hi == hi0, lo == start))

    def fetch_window(w):
        sp, seq, lo, hi, seq_start, _, init = w
        zs = zsplit(sp)
        base = dict(zip="v2", out=os.path.join(args.tmp, zs), split=zs, old_split=None, seqs=seq)
        if init:
            c26.apply_overlay(args.overlay, zs, seq, args.tmp)
        if init and not seq_start:
            lo -= 1                                       # resumed: the GMC of frame lo needs frame lo-1
        ov = os.path.join(args.overlay or "", zs, seq, "images")
        fixed = set(os.listdir(ov)) if args.overlay and os.path.isdir(ov) else set()
        members, ends = fetch.select(ix, argparse.Namespace(**base, parts="images"))
        idx = lambda m: int(os.path.basename(m[4])[6:12])            # frame_000123.jpg
        members = [m for m in members if lo <= idx(m) < hi and os.path.basename(m[4]) not in fixed]
        missing = c26.fetch_members(url, members, ends, args.fetch_workers)
        if missing:
            raise IOError(f"{seq}: {len(missing)} images missing after fetch")

    pending = {}

    def prefetch(k):
        try:
            fetch_window(wins[k])
            pending[k] = True
        except Exception as e:                       # noqa: BLE001 - re-raised by the consumer
            pending[k] = e

    th = None
    if wins:
        th = threading.Thread(target=prefetch, args=(0,))
        th.start()
    pool = mp.get_context("spawn").Pool(args.gmc_procs)
    st = {}                                          # per-seq accumulators
    nseq = 0
    for k, w in enumerate(wins):
        sp, seq, lo, hi, seq_start, is_last, init = w
        th.join()
        res = pending.pop(k)
        if isinstance(res, Exception):
            raise res
        if k + 1 < len(wins):
            th = threading.Thread(target=prefetch, args=(k + 1,))
            th.start()
        first, last = ranges[sp][seq]
        zs = zsplit(sp)
        d = os.path.join(args.tmp, zs, seq)
        if init:
            rows = read_dets(os.path.join(args.dets, zs, seq, "det", "det_nms0.95.txt"))
            assert not len(rows) or (rows[:, 0].min() >= first and rows[:, 0].max() <= last), f"{seq}: det frames out of range"
            r08 = read_dets(os.path.join(args.dets, zs, seq, "det", "det_nms0.8.txt"))
            idx08 = match_rows(r08, rows)
            extra = np.flatnonzero(idx08 < 0)
            idx08[extra] = len(rows) + np.arange(len(extra))      # their own embeddings, stored after the 0.95 rows
            allrows = np.concatenate([rows, r08[extra]]) if len(extra) else rows
            n = last - first + 1
            o = os.path.join(args.out, sp, seq)
            os.makedirs(o, exist_ok=True)
            # big outputs live in .npy memmaps on disk, not in RAM (401_sequence_nga3: disp 0.9 GB, emb ~0.4 GB)
            mode = "w+" if seq_start else "r+"            # r+: resumed, earlier windows are already on disk
            mm = lambda name, dt, shape: np.lib.format.open_memmap(os.path.join(o, name + ".part"), mode=mode,
                                                                   dtype=dt, shape=shape)
            st = dict(t0=time.time(), rows=rows, extra=extra, idx08=idx08, allrows=allrows,
                      emb=mm("emb.npy", np.float16, (len(allrows), 2048)), gmc=mm("gmc.npy", np.float32, (n, 2, 3)),
                      disp=mm("disp.npy", np.uint8, (n, 96, 128)) if depth_net is not None else None, tdet=0.0)
        paths = [os.path.join(d, "images", f"frame_{i:06d}.jpg") for i in range(lo, hi)]
        absent = [p for p in paths if not os.path.isfile(p)]
        if absent:
            raise IOError(f"{seq}: {len(absent)} of {len(paths)} frames absent, e.g. {absent[:2]}")
        # GMC of this window's frames; frame i's matrix needs frame i-1 (kept from the previous window)
        o0 = lo - (first - 1)                           # offset of this window in the seq arrays
        prev = os.path.join(d, "images", f"frame_{lo - 1:06d}.jpg")
        gpaths = ([prev] if not seq_start else []) + paths
        n_w = hi - lo
        step = max(200, -(-n_w // (args.gmc_procs * 4)))
        off = 0 if seq_start else 1                     # gpaths[off + j] is window frame j
        jobs = [(gmc_path, gpaths[max(a_ + off - 1, 0):min(a_ + step, n_w) + off], a_ + off, min(a_ + step, n_w) + off)
                for a_ in range(0, n_w, step)]
        gres = pool.map_async(gmc_chunk, jobs)
        sel = (st["allrows"][:, 0] >= lo + 1) & (st["allrows"][:, 0] <= hi)
        ridx = np.flatnonzero(sel)
        t1 = time.time()
        e_w, d_w = embed(model, depth_net, paths, st["allrows"][ridx], lo + 1, args.workers)
        st["tdet"] += time.time() - t1
        st["emb"][ridx] = e_w
        if d_w is not None:
            st["disp"][o0:o0 + n_w] = d_w
        for a_, (_, part) in zip(range(0, n_w, step), gres.get()):
            st["gmc"][o0 + a_:o0 + a_ + len(part)] = part
        for p in ([prev] if not seq_start else []) + paths[:-1]:
            if os.path.isfile(p):
                os.remove(p)
        o = os.path.join(args.out, sp, seq)
        for name in ("emb", "gmc", "disp"):
            if st[name] is not None:
                st[name].flush()
        json.dump({"done_until": hi}, open(os.path.join(o, "progress.json"), "w"))
        if is_last:
            nseq += 1
            n = last - first + 1
            o = os.path.join(args.out, sp, seq)
            moved = float(np.abs(st["gmc"][:, :, 2]).mean())
            for name in ("emb", "gmc", "disp"):
                if st[name] is not None:
                    del st[name]
                    os.replace(os.path.join(o, f"{name}.npy.part"), os.path.join(o, f"{name}.npy"))
            st["emb"] = st["gmc"] = st["disp"] = None
            os.remove(os.path.join(o, "progress.json"))
            np.save(os.path.join(o, "emb08_idx.npy"), st["idx08"])
            open(os.path.join(o, "DONE"), "w").write(
                f"{len(st['rows'])} + {len(st['extra'])} embeddings (0.95 rows + 0.8-only rows), {n} gmc"
                f"{' + depth' if depth_net is not None else ''} frames {first}..{last}\n")
            shutil.rmtree(d, ignore_errors=True)
            print(f"[{nseq}/{len(todo)}] {sp}/{seq}: {n} frames, {len(st['rows'])}+{len(st['extra'])} embs "
                  f"({n / max(st['tdet'], 1e-6):.0f} fps), gmc mean |t| {moved:.2f} px, "
                  f"total {(time.time() - st['t0']) / 60:.1f} min", flush=True)
        else:
            print(f"    {sp}/{seq}: frames {lo + 1}..{hi} done", flush=True)
    pool.close()
    print("FEATS_DONE", flush=True)


if __name__ == "__main__":
    main()
