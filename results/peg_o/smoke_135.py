"""PEG-O smoke on 135_19q only (test): per-episode coverage at IoU .5 (same logic as
results/val_selection/episodes.py) for PEG, PEG+, and the smoke run, plus the per-frame centre
error of the emitted box vs GT for the g53 409-451 episode.
Prereq: tracker dirs peg_rcv_ng, pegplus_A_rcv, smoke_pego_135 under results/eval_recovery/trackers
(smoke: GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_ODO=1 scripts/07_eval_recovery.py
 --split test --percep_cache results/percep_cache/synth --tracker_name smoke_pego_135 --seqs 135_sequence_19q_new)
Run: .venv/Scripts/python.exe results/peg_o/smoke_135.py [tracker_name ...]"""
import os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import BURN_THR, _iou, burn_index, load_events, load_mot, match_frame  # noqa: E402

SEQ = "135_sequence_19q_new"
SYNTH = os.path.join(ROOT, "datasets", "synth")
RCV = os.path.join(ROOT, "results", "eval_recovery", "trackers")
RUNS = {"PEG": "peg_rcv_ng", "PEG+": "pegplus_A_rcv", "PEG-O": "smoke_pego_135"}
if len(sys.argv) > 1:          # optional: name of the PEG-O tracker dir (default smoke_pego_135)
    RUNS["PEG-O"] = sys.argv[1]
gt = load_mot(os.path.join(SYNTH, SEQ, "mot", "gt", "gt.txt"))
bi = burn_index(SEQ, SYNTH)
trk = {k: load_mot(os.path.join(RCV, n, "data", f"{SEQ}.txt")) for k, n in RUNS.items()}


for tid, s0, dur in load_events(SEQ, SYNTH):
    ep = [f for f in range(s0 + 1, s0 + dur + 1)
          if any(r[0] == tid for r in gt.get(f, [])) and bi.get((tid, f), 1.0) < BURN_THR]
    if not ep:
        continue
    cov = {k: sum(1 for f in ep if match_frame(gt.get(f, []), t.get(f, []), 0.5).get(tid)) for k, t in trk.items()}
    print(f"g{tid} frames {ep[0]}-{ep[-1]} n={len(ep)} coverage " +
          "  ".join(f"{k} {cov[k]}/{len(ep)}={cov[k]/len(ep):.2f}" for k in RUNS))
    if tid == 53 and ep[0] == 409:
        for k in ("PEG+", "PEG-O"):
            # nearest emitted box (any id) to GT centre, per frame; missing frames counted separately
            errs, miss = [], 0
            for f in ep:
                g = [r for r in gt[f] if r[0] == tid][0]
                gc = np.array([g[1] + g[3] / 2, g[2] + g[4] / 2])
                tr = trk[k].get(f, [])
                if not tr:
                    miss += 1
                    continue
                cs = [np.array([r[1] + r[3] / 2, r[2] + r[4] / 2]) for r in tr]
                errs.append(min(np.linalg.norm(c - gc) for c in cs))
            if k == "PEG+":   # oracle-centred PEG+: its own w x h, centre = GT centre
                hit = 0
                for f in ep:
                    g = [r for r in gt[f] if r[0] == tid][0]
                    gc = np.array([g[1] + g[3] / 2, g[2] + g[4] / 2])
                    tr = trk[k].get(f, [])
                    if not tr:
                        continue
                    r = min(tr, key=lambda r: np.linalg.norm(np.array([r[1] + r[3] / 2, r[2] + r[4] / 2]) - gc))
                    ob = (gc[0] - r[3] / 2, gc[1] - r[4] / 2, r[3], r[4])
                    hit += _iou(g[1:], ob) > 0.5
                print(f"   oracle-centred PEG+ (own w x h, GT centre): coverage {hit}/{len(ep)} = {hit/len(ep):.2f}")
            e = np.array(errs)
            print(f"   centre err {k}: mean {e.mean():.1f} max {e.max():.1f} (frames with an emitted box {len(e)}/{len(ep)})")
