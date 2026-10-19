"""During burn frames (Table III, test+val), where is the box of the burnt target's track?
Matches the track to the GT box at the burn start (IoU>.5) and follows that track id.
Reports per config: frames with the box present, median centre error (dx/w, dy/h), median h ratio, IoU>.5 share."""
import os, sys, statistics as st
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import BURN_THR, burn_index, load_events, load_mot  # noqa
import importlib.util
spec = importlib.util.spec_from_file_location("an", os.path.join(HERE, "analyze.py")); an = importlib.util.module_from_spec(spec); spec.loader.exec_module(an)

def iou(a, b):
    ax2, ay2, bx2, by2 = a[0] + a[2], a[1] + a[3], b[0] + b[2], b[1] + b[3]
    iw, ih = max(0, min(ax2, bx2) - max(a[0], b[0])), max(0, min(ay2, by2) - max(a[1], b[1]))
    i = iw * ih
    return i / (a[2] * a[3] + b[2] * b[3] - i + 1e-9)

def run(cfg, split):
    d = an.paths(cfg, split)[3]
    dx, dy, hr, n, pres, hit = [], [], [], 0, 0, 0
    for f in sorted(os.listdir(d)):
        seq = f[:-4]
        if an.short(seq) not in an.SPLITS[split]:
            continue
        gt, trk, bi = load_mot(os.path.join(an.SYNTH, seq, "mot", "gt", "gt.txt")), load_mot(os.path.join(d, f)), burn_index(seq, an.SYNTH)
        for tid, s0, dur in load_events(seq, an.SYNTH):
            g0 = [r for r in gt.get(s0, []) if r[0] == tid]
            if not g0:
                continue
            cand = [(iou(r[1:5], g0[0][1:5]), r[0]) for r in trk.get(s0, [])]
            cand = [c for c in cand if c[0] > 0.5]
            k = max(cand)[1] if cand else None
            for x in range(s0 + 1, s0 + dur + 1):
                g = [r for r in gt.get(x, []) if r[0] == tid]
                if not g or bi.get((tid, x), 1.0) >= BURN_THR:
                    continue
                n += 1
                t = [r for r in trk.get(x, []) if r[0] == k] if k is not None else []
                if not t:
                    continue
                pres += 1
                gb, tb = g[0][1:5], t[0][1:5]
                hit += iou(gb, tb) > 0.5
                dx.append(((tb[0] + tb[2] / 2) - (gb[0] + gb[2] / 2)) / gb[2])
                dy.append(((tb[1] + tb[3] / 2) - (gb[1] + gb[3] / 2)) / gb[3])
                hr.append(tb[3] / gb[3])
    med = lambda v: st.median(v) if v else float("nan")
    mabs = lambda v: st.median([abs(a) for a in v]) if v else float("nan")
    return n, pres, hit, med(dx), med(dy), mabs(dy), med(hr)

if __name__ == "__main__" and "--dump" not in sys.argv:
    sys.stdout.reconfigure(encoding="utf-8")
    print("split cfg | burn frames | same-id box present | IoU>.5 | med dx/w | med dy/h | med|dy|/h | med h ratio")
    for split in ("test", "val"):
        for c in ("PEG", "base", "base+M1", "base+M5", "full-M5", "full-M1", "full"):
            n, p, h, dx, dy, ady, hr = run(c, split)
            print(f"{split} {c:8s} | {n} | {p} ({100*p/n:.0f}%) | {h} ({100*h/n:.0f}%) | {dx:+.3f} | {dy:+.3f} | {ady:.3f} | {hr:.2f}")


def dump():
    """-> drift.json: drift numbers + T3 Rcv of the diagnostic configs (diag_m1m5.py)."""
    import json, re
    out = {}
    for split in ("test", "val"):
        for c in ("base", "base+M1", "base+M5", "full", "dxbase+M5+Q", "dxfull-Q", "dxfull-cone", "dxfull-damp"):
            n, p, h, dx, dy, ady, hr = run(c, split)
            rep = an.run.report(c, "t3", split, False)
            rcv = float(re.search(r"^all-burn\s+\S+\s+\d+\s+([\d.]+)%", open(rep, encoding="utf-8").read(), re.M)[1])
            out[f"{split}|{c}"] = {"burn_frames": n, "present": p, "iou50": h, "dx_w": dx, "dy_h": dy, "abs_dy_h": ady, "h_ratio": hr, "rcv": rcv}
    json.dump(out, open(os.path.join(HERE, "drift.json"), "w"), indent=1)
    for k, v in out.items():
        print(k, round(v["dx_w"], 3), v["rcv"])


if __name__ == "__main__" and "--dump" in sys.argv:
    dump()
