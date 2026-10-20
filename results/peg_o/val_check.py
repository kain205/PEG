"""D1: offline PEG-O estimator (scripts/19_peg_o_check.py run(): GT-anchored, direct replacement, window follows the
estimate) on the val T3 burn episodes where O[8] (tau .08 gamma 4) loses >= 5 covered frames vs S0+P in the Thach
harness. Burn window = the T3 episode frames (as analyze.episodes). Cache = Thach val synth cache (dg0), 'sat'
row f-1 = MOT frame f. Run: .venv/Scripts/python.exe results/peg_o/val_check.py"""
import glob, importlib.util, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "results", "thach_v2"))
from glaremot.eval.eval_recovery import BURN_THR, burn_index, load_events, load_mot
spec = importlib.util.spec_from_file_location("chk19", "scripts/19_peg_o_check.py"); chk = importlib.util.module_from_spec(spec); spec.loader.exec_module(chk)
spec = importlib.util.spec_from_file_location("an", "results/thach_v2/analyze.py"); an = importlib.util.module_from_spec(spec); spec.loader.exec_module(an)
SYNTH = "datasets/synth"
BASE, O8 = "tv51d09158", "tv6fa5af52"
ea, eb = an.episodes(BASE, "val"), an.episodes(O8, "val")
bad = [k for k in ea if ea[k][1] - eb[k][1] >= 5]
print("episodes with O[8] loss >= 5 frames:", [(k, ea[k], eb[k]) for k in bad])
for key in bad:
    short, tid, start = key.split("|"); tid = int(tid); start = int(start)
    seq = [d for d in os.listdir(SYNTH) if d.startswith(short + "_")][0]
    gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt")); bi = burn_index(seq, SYNTH)
    ep = None
    for t, s0, dur in load_events(seq, SYNTH):
        e = [f for f in range(s0 + 1, s0 + dur + 1) if any(r[0] == tid for r in gt.get(f, [])) and bi.get((t, f), 1.0) < BURN_THR]
        if t == tid and e and e[0] == start:
            ep = e
    cache = glob.glob(f"results/thach_v2/cache_synth/dets/{seq}__dg0_*.npz")[0]
    for tau in (0.06, 0.08):
        chk.run(seq, tid, ep[0], ep[-1], f"{key} tau{tau}", tau=tau, frames=ep, cache=cache)
