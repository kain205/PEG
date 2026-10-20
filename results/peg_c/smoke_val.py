"""PEG-C check 3 (wiring smoke, VAL): per T3 burn episode of two val sequences, covered frames @IoU .5 and mean
centre error (px) of the emitted box nearest the GT on burn frames, PEG+ (v_A_rcv) vs a smoke run.
Episode definition = results/peg_o/episodes.py. Oracle b40 reference: 187 g247 n33: 33 (PEG+ 33), n35: 35 (PEG+ 19);
133 g117 n36: 34 (PEG+ 36), n37: 26 (PEG+ 17).
Run: .venv/Scripts/python.exe results/peg_c/smoke_val.py [smoke_run_name] -> results/peg_c/smoke_val.txt"""
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import BURN_THR, burn_index, load_events, load_mot, match_frame  # noqa: E402

SYNTH = os.path.join(ROOT, "datasets", "synth")
RCV = os.path.join(ROOT, "results", "eval_recovery", "trackers")
SMOKE = sys.argv[1] if len(sys.argv) > 1 else "smoke_pegc_v40"
SEQS = ["187_sequence_66q_new", "133_sequence_17q_new"]
REF = {("187_sequence_66q_new", 247, 33): 33, ("187_sequence_66q_new", 247, 35): 35,
       ("133_sequence_17q_new", 117, 36): 34, ("133_sequence_17q_new", 117, 37): 26}


def cerr(gt, trk, ep, tid):
    errs = []
    for f in ep:
        g = [r for r in gt.get(f, []) if r[0] == tid]
        if not g or not trk.get(f):
            continue
        gc = np.array([g[0][1] + g[0][3] / 2, g[0][2] + g[0][4] / 2])
        errs.append(min(np.linalg.norm(np.array([r[1] + r[3] / 2, r[2] + r[4] / 2]) - gc) for r in trk[f]))
    return float(np.mean(errs)) if errs else float("nan")


lines = [f"smoke run: {SMOKE} vs PEG+ v_A_rcv (val, T3, guard off, cached)",
         "seq tid burn_frames n | covered PEG+ -> smoke | oracle b40 | centre err px PEG+ -> smoke"]
tot = {"PEG+": 0, "smoke": 0, "n": 0}
for seq in SEQS:
    gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
    bi = burn_index(seq, SYNTH)
    trk = {"PEG+": load_mot(os.path.join(RCV, "v_A_rcv", "data", f"{seq}.txt")),
           "smoke": load_mot(os.path.join(RCV, SMOKE, "data", f"{seq}.txt"))}
    for tid, s0, dur in load_events(seq, SYNTH):
        ep = [f for f in range(s0 + 1, s0 + dur + 1)
              if any(r[0] == tid for r in gt.get(f, [])) and bi.get((tid, f), 1.0) < BURN_THR]
        if not ep:
            continue
        cov = {k: sum(1 for f in ep if match_frame(gt.get(f, []), t.get(f, []), 0.5).get(tid)) for k, t in trk.items()}
        ce = {k: cerr(gt, t, ep, tid) for k, t in trk.items()}
        ref = REF.get((seq, tid, len(ep)))
        tot["PEG+"] += cov["PEG+"]; tot["smoke"] += cov["smoke"]; tot["n"] += len(ep)
        lines.append(f"{seq} g{tid} {ep[0]}-{ep[-1]} n{len(ep)} | {cov['PEG+']} -> {cov['smoke']} | "
                     f"{'-' if ref is None else ref} | {ce['PEG+']:.1f} -> {ce['smoke']:.1f}")
lines.append(f"TOTAL over listed episodes: PEG+ {tot['PEG+']} -> smoke {tot['smoke']} of {tot['n']} burn frames")
txt = "\n".join(lines)
print(txt)
open(os.path.join(ROOT, "results", "peg_c", "smoke_val.txt"), "w", encoding="utf-8").write(txt + "\n")
