"""D2 stage 2: anchor hygiene + worst-episode traces from results/peg_o/val_odo_log.json (made by val_odo_log.py, O[4] = tau .06 gamma 1)."""
import json, os, sys, importlib.util
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(ROOT); sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import BURN_THR, _iou, burn_index, load_events, load_mot
spec = importlib.util.spec_from_file_location("an", "results/thach_v2/analyze.py"); an = importlib.util.module_from_spec(spec); spec.loader.exec_module(an)
SYNTH = "datasets/synth"; BASE = "tv51d09158"
tr = json.load(open("results/thach_v2/tune_O/trace.json"))
KEY = [r["key"] for r in tr[1]["rows"] if r["add"].startswith("O[4]")][0]
LOG = json.load(open("results/peg_o/val_odo_log.json"))
gtc, bic = {}, {}
def gt_of(seq):
    if seq not in gtc:
        gtc[seq] = load_mot(f"{SYNTH}/{seq}/mot/gt/gt.txt"); bic[seq] = burn_index(seq, SYNTH)
    return gtc[seq], bic[seq]
def burning_gt(seq, f):
    gt, bi = gt_of(seq)
    return [r for r in gt.get(f, []) if bi.get((r[0], f), 1.0) < BURN_THR]
calls = len(LOG); upd = [e for e in LOG if e["upd"]]
stale_calls = [e for e in LOG if e["had_anchor"] and e["anc_frame"] is not None and e["anc_frame"] < e["loss_start"]]
stale_upd = [e for e in upd if e["anc_frame"] is not None and e["anc_frame"] < e["loss_start"]]
def near_burn(e):
    for r in burning_gt(e["seq"], e["f"]):
        if np.hypot(r[1] + r[3] / 2 - e["cx"], r[2] + r[4] / 2 - e["cy"]) < 0.5 * np.hypot(e["w"], e["h"]):
            return True
    return False
nb = [e for e in upd if not near_burn(e)]
print(f"O[4] key {KEY}: odometry calls {calls}, updates {len(upd)} (tracks {len({(e['seq'], e['tid']) for e in upd})})")
print(f"stale anchor (anchor frame < loss-episode start): calls {len(stale_calls)}, updates {len(stale_upd)}")
print(f"exiting tracks among calls: {sum(e['exiting'] for e in LOG)}; calls with gap<=1: {sum(e['gap'] <= 1 for e in LOG)}")
print(f"updates not near a GT burning target (pre/post-burn glare or wrong target): {len(nb)}")
zc = np.array([e["zc"] for e in upd]); g0 = np.array([e["gain"][0] for e in upd])
print(f"|z-c| px: median {np.median(zc):.1f} mean {zc.mean():.1f} max {zc.max():.1f}; as fraction of box diag: median {np.median([e['zc']/np.hypot(e['w'],e['h']) for e in upd]):.2f}; gain x: median {np.median(g0):.2f} min {g0.min():.2f} max {g0.max():.2f}")
print("box w x h of updating tracks: median", np.median([e["w"] for e in upd]), "x", np.median([e["h"] for e in upd]))
def near_any_burn(e, thr):
    gt, bi = gt_of(e["seq"])
    for r in gt.get(e["f"], []):
        if bi.get((r[0], e["f"]), 1.0) < thr and np.hypot(r[1] + r[3] / 2 - e["cx"], r[2] + r[4] / 2 - e["cy"]) < 0.5 * np.hypot(e["w"], e["h"]):
            return True
    return False
nb2 = [e for e in nb if near_any_burn(e, 0.95)]
print(f"  of those, near a GT target with a partial burn (burn_index < 0.95, ramp/fade): {len(nb2)}; near no burning GT at all: {len(nb) - len(nb2)}")
import collections
print("  no-burn-GT updates by sequence:", dict(collections.Counter(e['seq'] for e in nb if e not in nb2)))
print("  all updates by sequence:", dict(collections.Counter(e['seq'] for e in upd)))
for e in nb[:10]: print("  non-burn update:", {k: (round(v, 1) if isinstance(v, float) else v) for k, v in e.items() if k in ("seq", "f", "tid", "gap", "w", "h", "zc")})
# worst episodes
ea, eb = an.episodes(BASE, "val"), an.episodes(KEY, "val")
worst = sorted(ea, key=lambda k: eb[k][1] - ea[k][1])[:5]
print("\nworst 5 val episodes (n, covered): ", [(k, ea[k], eb[k]) for k in worst])
trk = {}
for key in worst:
    short, tid, start = key.split("|"); tid = int(tid); start = int(start)
    seq = [d for d in os.listdir(SYNTH) if d.startswith(short + "_")][0]
    gt, bi = gt_of(seq)
    ep = None
    for t, s0, dur in load_events(seq, SYNTH):
        e = [f for f in range(s0 + 1, s0 + dur + 1) if any(r[0] == t for r in gt.get(f, [])) and bi.get((t, f), 1.0) < BURN_THR]
        if t == tid and e and e[0] == start: ep = e
    out = load_mot(f"results/thach_v2/out/eval_recovery/trackers/th_{KEY}_rcv/data/{seq}.txt")
    base = load_mot(f"results/thach_v2/out/eval_recovery/trackers/th_{BASE}_rcv/data/{seq}.txt")
    print(f"\n== {key} ({seq}) burn frames {ep[0]}-{ep[-1]}; cols: f k upd | O[4] cx cy iou | P cx cy iou | GT cx cy w h")
    for f in range(ep[0] - 2, ep[-1] + 3):
        g = [r for r in gt.get(f, []) if r[0] == tid]
        if not g: continue
        g = g[0]; gc = (g[1] + g[3] / 2, g[2] + g[4] / 2)
        def best(boxes):
            if not boxes: return "   -     -    -  "
            r = max(boxes, key=lambda r: _iou(g[1:], r[1:]))
            return f"{r[1]+r[3]/2:6.0f} {r[2]+r[4]/2:5.0f} {_iou(g[1:], r[1:]):.2f}"
        ents = [e for e in LOG if e["seq"] == seq and e["f"] == f]
        e = min(ents, key=lambda e: np.hypot(e["cx"] - gc[0], e["cy"] - gc[1])) if ents else None
        ks = f"{e['k']:.3f}" if e and e["k"] is not None else "  -  "
        print(f"f{f} {ks} {'Y' if e and e['upd'] else '.'} | {best(out.get(f, []))} | {best(base.get(f, []))} | {gc[0]:5.0f} {gc[1]:5.0f} {g[3]:3.0f} {g[4]:3.0f}{' *' if f in ep else ''}")
