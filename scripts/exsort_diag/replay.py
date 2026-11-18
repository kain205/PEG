# ExSORT FP diagnostics (2026-11-18), kept as run; paths are hard-coded to this machine's results/baselines_t1 layout.
"""Instrumented ExSORT (0c25ef3) replay: one row per emitted box with coast/glare features + GT match."""
import json, os, sys
import numpy as np, torch, torchvision
from multiprocessing import Pool
from scipy.optimize import linear_sum_assignment
ROOT = "/home/thanh1402/Projects/PEG"; B = ROOT + "/results/baselines_t1"
EX = B + "/repos/exsort"; sys.path.insert(0, EX)
OUT = sys.argv[2]; SPLIT = sys.argv[1]
SD = B + "/dets/" + ("test" if SPLIT == "test" else "train")

def load_rows(p):
    a = np.loadtxt(p, delimiter=",", ndmin=2, dtype=np.float64)
    return a if a.size else np.zeros((0, 10))

def per_frame(rows, nms):
    out = {}
    if not len(rows): return out
    order = np.argsort(rows[:, 0], kind="stable"); frames = rows[order, 0].astype(int)
    for idx in np.split(order, np.flatnonzero(np.diff(frames)) + 1):
        r = rows[idx]; d = np.c_[r[:, 2], r[:, 3], r[:, 2] + r[:, 4], r[:, 3] + r[:, 5], r[:, 6]]
        if len(d) > 1:
            k = torchvision.ops.nms(torch.from_numpy(d[:, :4]), torch.from_numpy(d[:, 4]), nms).numpy(); d = d[k]
        out[int(r[0, 0])] = d
    return out

class Sat:
    def __init__(s, d):
        s.d = d; s.los = sorted(int(f[4:-4]) for f in os.listdir(d) if f.startswith("sat_")); s.lo = None
    def get(s, i):
        lo = max(v for v in s.los if v <= i)
        if lo != s.lo: s.lo, s.arr = lo, np.load(f"{s.d}/sat_{lo}.npz")["sat"]
        return np.unpackbits(s.arr[i - lo], count=512 * 512).reshape(512, 512).astype(bool)

def iou(a, b):
    a = a[:, None]; b = b[None]
    iw = np.clip(np.minimum(a[..., 2], b[..., 2]) - np.maximum(a[..., 0], b[..., 0]), 0, None)
    ih = np.clip(np.minimum(a[..., 3], b[..., 3]) - np.maximum(a[..., 1], b[..., 1]), 0, None)
    i = iw * ih
    return i / ((a[..., 2] - a[..., 0]) * (a[..., 3] - a[..., 1]) + (b[..., 2] - b[..., 0]) * (b[..., 3] - b[..., 1]) - i + 1e-9)

def run(args):
    seq, first, last = args
    torch.set_num_threads(1)
    from exsort.api import create_tracker
    from exsort.geometry import norm_box_to_xyxy
    cfg = json.load(open(EX + "/configs/selected.json")); HF = cfg["params"]["HEAD_FRACTION"]
    floor = min(cfg["params"]["DET"], cfg["params"]["LOW"]); trk = create_tracker(cfg)
    meta = json.load(open(f"{SD}/{seq}/meta/DONE.json")); H, W = int(meta["video_height"]), int(meta["video_width"])
    fps = int(meta.get("output_integer_fps") or 25)
    frames = per_frame(load_rows(f"{SD}/{seq}/det/det_nms0.95.txt"), 0.65)
    sat = Sat(f"{B}/exsat/{SPLIT}/{seq}")
    g = load_rows(f"{SD}/{seq}/gt/gt.txt"); g = g[(g[:, 6] != 0)]
    gord = np.argsort(g[:, 0], kind="stable"); g = g[gord]; gf = g[:, 0].astype(int)
    gt = {int(f): g[a:b] for f, a, b in zip(*(lambda u, s, c: (u, s, s + c))(*np.unique(gf, return_index=True, return_counts=True)))}
    RL = np.zeros((512, 512), np.int32)   # per-pixel run length of saturation (frames)
    st = {}; rows = []; lines = []
    sx, sy = 512 / W, 512 / H
    def band(b, m):
        x1, y1, x2, y2 = b; h = y2 - y1
        a, c = int(max(0, x1 * sx)), int(min(512, np.ceil(x2 * sx)))
        d, e = int(max(0, y1 * sy)), int(min(512, np.ceil((y1 + HF * h) * sy)))
        if c <= a or e <= d: return None
        return m[d:e, a:c]
    for f in range(first, last + 1):
        k = f - first + 1
        d = frames.get(f, np.zeros((0, 5)))
        d = d[np.argsort(-d[:, 4], kind="stable")[:100]] if len(d) else d
        dr = [dict(box=np.array([(x1 + x2) / 2 / W, (y1 + y2) / 2 / H, (x2 - x1) / W, (y2 - y1) / H], np.float32), conf=float(sc))
              for x1, y1, x2, y2, sc in d if sc >= floor]
        m = sat.get(f - 1); RL = np.where(m, RL + 1, 0)
        out = trk.step(dr, W, H, k, sat=m)
        obx = []; feats = []
        for t in out:
            x1, y1, x2, y2 = norm_box_to_xyxy(t.out_box(), W, H)
            bx = (max(0., x1), max(0., y1), max(1., x2 - x1), max(1., y2 - y1))
            lines.append(f"{k},{int(t.id)},{bx[0]:.2f},{bx[1]:.2f},{bx[2]:.2f},{bx[3]:.2f},1,-1,-1,-1\n")
            b = np.array([bx[0], bx[1], bx[0] + bx[2], bx[1] + bx[3]])
            s = st.setdefault(id(t), dict(bf0=0., n0=0, born=k, c0=None, pmax=0))
            tsu = t.kf.time_since_update
            pb = t.pred() if tsu else t.box
            bm = band(pb, m); br = band(pb, RL)
            n = int(bm.sum()) if bm is not None else 0
            bf = n / bm.size if bm is not None and bm.size else 0.
            rl = int(br.max()) if br is not None and br.size else 0
            full = m[int(max(0, pb[1] * sy)):int(min(512, np.ceil(pb[3] * sy))), int(max(0, pb[0] * sx)):int(min(512, np.ceil(pb[2] * sx)))]
            ff = float(full.mean()) if full.size else 0.
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; hh = b[3] - b[1]
            if tsu == 0:
                s.update(bf0=bf, n0=n, rl0=rl, lastc=(cx, cy), lasth=hh)
                if s["c0"] is None: s["c0"] = (cx, cy)
            s["pmax"] = max(s["pmax"], np.hypot(cx - s["c0"][0], cy - s["c0"][1]) / max(hh, 1))
            v = t.kf.kf.x[4:6, 0]
            edge = min(b[0], b[1], W - b[2], H - b[3])
            feats.append([k, t.id, tsu, int(t.now), float(t.kf.last_observation[4]), t.unexplained, t.kf.hits, t.high_hits,
                          k - s["born"], bf, n, s["bf0"], s["n0"], rl, s.get("rl0", 0), ff, float(np.hypot(*v)) / max(hh, 1) * fps,
                          s["pmax"], edge, hh, b[2] - b[0], cx, cy, fps, t.since_high])
            obx.append(b)
        gg = gt.get(k if SPLIT == "test" else f, np.zeros((0, 9)))
        if SPLIT != "test": pass
        gb = np.c_[gg[:, 2], gg[:, 3], gg[:, 2] + gg[:, 4], gg[:, 3] + gg[:, 5]]
        nm = 0
        if obx:
            ob = np.asarray(obx); I = iou(ob, gb) if len(gb) else np.zeros((len(ob), 0))
            mid = -np.ones(len(ob)); best = I.max(1) if I.shape[1] else np.zeros(len(ob))
            if I.size:
                r, c = linear_sum_assignment(-(I * (I >= .5)))
                for i, j in zip(r, c):
                    if I[i, j] >= .5: mid[i] = gg[j, 1]; nm += 1
            for i, ft in enumerate(feats): rows.append(ft + [mid[i], best[i], len(gb)])
    np.save(f"{OUT}/{seq}.npy", np.asarray(rows, np.float64).reshape(-1, 28))
    open(f"{OUT}/{seq}.txt", "w").writelines(lines)
    ngt = sum(len(v) for kk, v in gt.items() if (1 <= kk <= last - first + 1 if SPLIT == "test" else first <= kk <= last))
    return seq, len(rows), ngt

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    sp = json.load(open(B + "/dets/splits.json"))[SPLIT]
    jobs = sorted([(s, a, b) for s, (a, b) in sp.items()], key=lambda j: -(j[2] - j[1]))
    with Pool(8) as p:
        for r in p.imap_unordered(run, jobs, chunksize=1): print(r, flush=True)
