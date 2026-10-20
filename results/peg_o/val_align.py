"""D3: sat-mask alignment on val. phi of the GT box (burning track) per MOT frame f using cache row f-1 vs f-2 vs f,
against the T3 burn frames (burn_index < BURN_THR). Also: Thach val cache == results/percep_cache val cache?"""
import glob, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); os.chdir(ROOT); sys.path.insert(0, ROOT)
import cv2
from glaremot.eval.eval_recovery import BURN_THR, burn_index, load_events, load_mot
SYNTH = "datasets/synth"; S = 512
for seq, tid in (("187_sequence_66q_new", 247), ("203_sequence_80q_new", 299)):
    th = np.load(glob.glob(f"results/thach_v2/cache_synth/dets/{seq}__dg0_*.npz")[0])["sat"]
    ours = np.load(f"results/percep_cache/synth/{seq}.npz")["sat"]
    print(seq, "thach cache == percep_cache sat:", bool((th == ours).all()), th.shape)
    H, W = cv2.imread(glob.glob(f"{SYNTH}/{seq}/images/*.jpg")[0]).shape[:2]; sx, sy = S / W, S / H
    gt = load_mot(f"{SYNTH}/{seq}/mot/gt/gt.txt"); bi = burn_index(seq, SYNTH)
    ev = [e for e in load_events(seq, SYNTH) if e[0] == tid]
    def phi(f, row):
        if row < 0 or row >= len(th): return np.nan
        m = np.unpackbits(th[row], count=S * S).reshape(S, S)
        g = [r for r in gt.get(f, []) if r[0] == tid]
        if not g: return np.nan
        _, x, y, w, h = g[0]; b = m[int(y * sy):int((y + h) * sy), int(x * sx):int((x + w) * sx)]
        return float(b.mean()) if b.size else np.nan
    for t, s0, dur in ev:
        fr = [f for f in range(s0 - 6, s0 + dur + 7) if any(r[0] == tid for r in gt.get(f, []))]
        burn = {f for f in range(s0 + 1, s0 + dur + 1) if bi.get((tid, f), 1.0) < BURN_THR}
        print(f" event start {s0} dur {dur}: burn frames {min(burn) if burn else None}-{max(burn) if burn else None}")
        for name, off in (("row f-1", 1), ("row f-2", 2), ("row f", 0)):
            p = np.array([phi(f, f - off) for f in fr]); isb = np.array([f in burn for f in fr])
            hi = p >= 0.4
            print(f"   {name}: phi>=.4 on {int((hi & isb).sum())}/{int(isb.sum())} burn frames; phi>=.4 outside burn {int((hi & ~isb).sum())}/{int((~isb).sum())}; "
                  f"mean phi burn {np.nanmean(p[isb]):.2f} outside {np.nanmean(p[~isb]):.2f}")
