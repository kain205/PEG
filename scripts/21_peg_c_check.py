"""PEG-C check 1 (docs/PEG_C_PROTOCOL.md, "Checks before tuning"): the oracle policy b40 / b20 of
results/research/oracle_t3_vest.py recomputed with the tracker's OWN velocity function
(glaremot.tracking.tracker.ols_velocity, t=0) on the 43 tracked burn episodes.
Expected (ORACLE_T3.md, Follow-up 3): b40 = 88.5 test / 86.6 val / 87.8 pooled; b20 = 87.9 / 81.6 / 85.5 (+-1).
Only the already-published points (K = 20 / 40, t = 0) are computed.
Run: .venv/Scripts/python.exe scripts/21_peg_c_check.py  -> results/peg_c/check21.txt"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "results", "research"))
sys.path.insert(0, ROOT)
from oracle_t3 import RCV, RUNS, SYNTH, burn_index, coast_flags, cx, load_mot, load_raw, mk, rate, _iou  # noqa: E402,F401
from glaremot.eval.eval_recovery import BURN_THR  # noqa: E402
from glaremot.tracking.tracker import ols_velocity  # noqa: E402

os.chdir(ROOT)
J = json.load(open("results/research/oracle_t3.json"))
rows = J["episodes"]
published = J["vest"]["per_episode"]   # same order as the tracked episodes
out_lines = []


def P(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    out_lines.append(s)


per = []
for r in rows:
    if r["status"] != "tracked":
        continue
    seq, tid = r["seq"], r["tid"]
    runs = RUNS[r["split"]]
    gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
    bi = burn_index(seq, SYNTH)
    gtb = lambda f, t: next(((q[1], q[2], q[3], q[4]) for q in gt.get(f, []) if q[0] == t), None)
    ep = [f for f in range(r["start"], r["end"] + 1) if gtb(f, tid) and bi.get((tid, f), 1.0) < BURN_THR]
    rawp = load_raw(os.path.join(RCV, runs["PEG+"], "data", f"{seq}.txt"))
    fa = r["anchor_frame"]
    tr = None
    for t, rr in rawp.items():
        if fa in rr and not coast_flags(rr)[fa] and _iou(gtb(fa, tid), rr[fa][:4]) > 0.5:
            tr = rr
            break
    fl = coast_flags(tr)
    det = [f for f in sorted(tr) if f <= fa and not fl[f]]
    ab = tr[fa][:4]
    c0 = cx(ab)
    w0, h0 = ab[2], ab[3]
    cxs = np.array([cx(tr[f][:4]) for f in det])
    e = dict(split=r["split"], seq=seq, tid=tid, start=r["start"], n=r["n"])
    for K in (20, 40):
        v = ols_velocity(det, cxs[:, 0], cxs[:, 1], K, 0.0)
        c = c0.copy()
        cov = 0
        for f in range(fa + 1, ep[-1] + 1):
            c = c + v
            if f in ep:
                cov += _iou(gtb(f, tid), mk(c, w0, h0)) > 0.5
        e[f"cov_b{K}"] = int(cov)
        e[f"v_b{K}"] = v.tolist()
    per.append(e)

P(f"episodes: {len(per)} tracked (expected 43)")
for K in (20, 40):
    k = f"cov_b{K}"
    res = {}
    for name, sel in (("test", lambda e: e["split"] == "test"), ("val", lambda e: e["split"] == "val"), ("pooled", lambda e: True)):
        T = [e for e in per if sel(e)]
        res[name] = rate(T, k)
    P(f"b{K}: test {res['test']:.1f}  val {res['val']:.1f}  pooled {res['pooled']:.1f}")
P("")
P("per episode covered burn frames (this run | published json cov_b40 / cov_b20 | n):")
nd = 0
for e, pub in zip(per, published):
    assert (pub["seq"], pub["tid"], pub["n"]) == (e["seq"], e["tid"], e["n"])
    pb40 = pub["cov_b40"] if pub else None
    pb20 = pub["cov_b20"] if pub else None
    flag = "" if (pb40 == e["cov_b40"] and pb20 == e["cov_b20"]) else "  <-- differs"
    nd += bool(flag)
    P(f"  {e['split']:4s} {e['seq']} g{e['tid']} {e['start']} n{e['n']}: b40 {e['cov_b40']} | {pb40}   b20 {e['cov_b20']} | {pb20}"
      f"   v40 ({e['v_b40'][0]:+.2f},{e['v_b40'][1]:+.2f}){flag}")
P(f"episodes differing from the published json: {nd}")
os.makedirs("results/peg_c", exist_ok=True)
open("results/peg_c/check21.txt", "w", encoding="utf-8").write("\n".join(out_lines) + "\n")
