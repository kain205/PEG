"""POST-TEST ANALYSIS, NOT USED FOR SELECTION. Instrumented replay of config pegc (P + V K40 t2), guard off, cached, T3, to explain why the tracker
loses test 176 g204 (331-355) and 211 g320 (436-460) while the oracle b40 policy (results/research/ORACLE_T3.md) covered them (21 / 20 frames),
next to the val episode 187 g247 201-235 (oracle 35).
The wrapper only READS (it recomputes the V pieces from the track's _det_hist); the replay MOT rows must equal pegc_rcv / v_pegc_rcv byte-for-byte.
Run: .venv/Scripts/python.exe results/peg_c/diag_test_losses.py -> results/peg_c/diag_test_losses.txt + .json"""
import json, math, os, re, sys
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT); os.chdir(ROOT)
# same env as the pegc rows + what eval_recovery sets before importing the tracker
os.environ.update(GMOT_TRACKER="beacon", GMOT_BIRTH_SIZE_GUARD="0", GPEG_SIZE_LOCK="1", GPEG_VEL_K="40", GPEG_VEL_T="2",
                  GMOT_OUTPUT_MAX_GAP="90", GMOT_EMIT_CAP="90")
for k in list(os.environ):
    if k.startswith(("GPEG_BACKFILL", "GPEG_CAP", "GPEG_STITCH", "GPEG_BACKBIRTH", "GPEG_F", "GBEACON_", "GMOT_AM_", "GMOT_REID", "GMOT_DORMANT", "GMOT_ADAPTIVE")):
        del os.environ[k]
import numpy as np
from glaremot.eval import eval_mot
from glaremot.eval.eval_recovery import burn_index, load_events, load_mot, match_frame, BURN_THR, _iou
from glaremot.tracking import tracker as T

SYNTH = os.path.join(ROOT, "datasets", "synth")
CASES = [("test", "176_sequence_56q_new", 204, "pegc_rcv", "pegplus_A_rcv"), ("test", "211_sequence_88q_new", 320, "pegc_rcv", "pegplus_A_rcv"),
         ("val", "187_sequence_66q_new", 247, "v_pegc_rcv", "v_A_rcv")]
EPS = {"176_sequence_56q_new": (331, 355), "211_sequence_88q_new": (436, 460), "187_sequence_66q_new": (201, 235)}
ORACLE = {"176_sequence_56q_new": dict(n=25, vt=(-1.24, -0.47), ve=(-1.02, -0.87), cov=21), "211_sequence_88q_new": dict(n=25, vt=(-0.08, 1.96), ve=(0.27, 1.28), cov=20),
          "187_sequence_66q_new": dict(n=35, vt=(0.53, 0.46), ve=(0.33, 0.29), cov=35)}
LOG = []
CUR = {"seq": None}
orig = T.MotionTrack.update_missing


def wrapped(self, W, H, beacon_used=False):
    gap = int(self.kf.time_since_update)
    rec = None
    if gap == 1 and self.good_hits >= T.FC_MIN_GOOD_HITS and T.VEL_K > 0:
        K = T.VEL_K
        dh = list(self._det_hist)
        fr = [h[0] for h in dh]; cx = [h[1] * W for h in dh]; cy = [h[2] * H for h in dh]
        v0 = T.ols_velocity(fr, cx, cy, K, 0.0)
        v2 = T.ols_velocity(fr, cx, cy, K, T.VEL_T)
        f = np.array(fr[-K:], float); n = len(f); se = [None, None]
        if n >= 3 and np.ptp(f) > 0 and np.any(v0 != 0):
            fc = f - f.mean(); sxx = float(np.sum(fc * fc))
            for d, c in enumerate((cx, cy)):
                c = np.array(c[-K:], float); cc = c - c.mean(); sl = float(np.sum(fc * cc) / sxx)
                se[d] = float(np.sqrt(float(np.sum((cc - sl * fc) ** 2)) / (n - 2) / sxx))
        b = self.kf.get_state()[0]
        hbox = float(b[3] - b[1])
        v_g = v2 if float(np.hypot(*v2)) <= 0.1 * hbox else np.zeros(2)
        speed_guard = float(np.hypot(*v2)) > 0.1 * hbox
        vmax = 2.0 * self.median_step_px(W, H)
        ceiling = float(np.hypot(*v_g)) > vmax > 0.0
        in_window = int(np.sum(np.array(fr) > fr[-1] - 2 * K))
        rec = dict(seq=CUR["seq"], tid=int(self.id), frame=int(self.last_frame + 1), n_det_used=n, in_2K_window=in_window, v_ols_t0=[float(v0[0]), float(v0[1])],
                   se=se, v_t2=[float(v2[0]), float(v2[1])], axes_zeroed_by_t2=[bool(v0[d] != 0 and v2[d] == 0) for d in (0, 1)], speed_guard=bool(speed_guard),
                   box_h=round(hbox, 1), vmax=round(vmax, 3), ceiling_hit=bool(ceiling), v_kalman_before=[float(self.kf.kf.x[4, 0]), float(self.kf.kf.x[5, 0])])
    orig(self, W, H, beacon_used)
    if rec is not None:
        rec["v_final"] = [float(self.kf.kf.x[4, 0]), float(self.kf.kf.x[5, 0])]
        LOG.append(rec)


T.MotionTrack.update_missing = wrapped
out_dir = os.path.join(ROOT, "results", "peg_c", "diag_replay")
os.makedirs(out_dir, exist_ok=True)
lines = ["POST-TEST ANALYSIS, NOT USED FOR SELECTION. Instrumented replay of pegc (P + V K40 t2), guard off, cached, T3.", ""]
res = {}
for split, seq, tid, run, ref in CASES:
    CUR["seq"] = seq
    percep, _ = eval_mot.seq_perception(seq, None, os.path.join(ROOT, "results", "percep_cache", "synth"), 0.25)
    out_txt = os.path.join(out_dir, f"{seq}.txt")
    eval_mot.track_sequence(os.path.join(SYNTH, seq), percep, out_txt)
    a = open(out_txt, "rb").read()
    b = open(os.path.join(ROOT, "results", "eval_recovery", "trackers", run, "data", f"{seq}.txt"), "rb").read()
    same = a == b
    lines.append(f"== {split} {seq} g{tid}: replay rows == {run}: {'BYTE-IDENTICAL' if same else 'DIFFERENT'} ({len(a.splitlines())} rows)")
    assert same, "replay differs"
    gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt")); trk = load_mot(out_txt)
    f0, f1 = EPS[seq]
    c = Counter()
    for f in range(f0 - 30, f1 + 1):
        m = match_frame(gt.get(f, []), trk.get(f, []), 0.3).get(tid)
        if m:
            c[m[0]] += 1
    ids = [i for i, _ in c.most_common(2)]
    ev = [r for r in LOG if r["seq"] == seq and r["tid"] in ids and f0 - 60 <= r["frame"] <= f1]
    ev.sort(key=lambda r: r["frame"])
    pk = load_mot(os.path.join(ROOT, "results", "eval_recovery", "trackers", ref, "data", f"{seq}.txt"))
    cov = sum(1 for f in range(f0, f1 + 1) if match_frame(gt.get(f, []), trk.get(f, []), 0.5).get(tid))
    covp = sum(1 for f in range(f0, f1 + 1) if match_frame(gt.get(f, []), pk.get(f, []), 0.5).get(tid))
    o = ORACLE[seq]
    gtc = {f: ([r for r in gt[f] if r[0] == tid][0]) for f in range(f0, f1 + 1) if f in gt and any(r[0] == tid for r in gt[f])}
    ff = sorted(gtc)
    vt = ((gtc[ff[-1]][1] + gtc[ff[-1]][3] / 2) - (gtc[ff[0]][1] + gtc[ff[0]][3] / 2)) / max(1, ff[-1] - ff[0]), ((gtc[ff[-1]][2] + gtc[ff[-1]][4] / 2) - (gtc[ff[0]][2] + gtc[ff[0]][4] / 2)) / max(1, ff[-1] - ff[0])
    lines.append(f"   burn frames {f0}-{f1} (n={o['n']}); tracker ids matched to the target: {ids}; covered@.5: PEG+ {covp} -> pegc {cov}; oracle b40 {o['cov']}")
    lines.append(f"   oracle (ORACLE_T3.md): vt (true mean burn velocity) {o['vt']}  ve (b40 estimate) {o['ve']}  px/frame;  GT mean velocity recomputed here: ({vt[0]:+.2f},{vt[1]:+.2f})")
    n_in = sum(1 for r in ev if f0 <= r["frame"] <= f1)
    lines.append(f"   coast entries (gap==1, mature track) of those ids from f{f0 - 60} to f{f1}: {len(ev)}; inside the burn window: {n_in}")
    for r in ev:
        tag = "IN-BURN " if f0 <= r["frame"] <= f1 else "pre-burn"
        se = ["-" if s is None else f"{s:.3f}" for s in r["se"]]
        lines.append(f"   {tag} f{r['frame']} id{r['tid']}: n_det {r['n_det_used']} (in 2K window {r['in_2K_window']}) | v_ols(t=0) ({r['v_ols_t0'][0]:+.2f},{r['v_ols_t0'][1]:+.2f}) SE ({se[0]},{se[1]}) "
                     f"| t=2 zeroed axes {r['axes_zeroed_by_t2']} -> ({r['v_t2'][0]:+.2f},{r['v_t2'][1]:+.2f}) | speed guard {r['speed_guard']} (h {r['box_h']}) "
                     f"| ceiling vmax {r['vmax']} hit {r['ceiling_hit']} | Kalman v before ({r['v_kalman_before'][0]:+.2f},{r['v_kalman_before'][1]:+.2f}) -> written ({r['v_final'][0]:+.2f},{r['v_final'][1]:+.2f})")
    # arithmetic counterfactuals (NOT tracker runs): move the first coast box of the matched track with v_final, with and without the VEL_DAMP decay (x0.95/frame past gap 10)
    gov = [r for r in ev if r["frame"] <= f0]
    if gov:
        g0 = gov[-1]; fe = g0["frame"]; vf = np.array(g0["v_final"])
        rr = [q for q in trk.get(fe, []) if q[0] == g0["tid"]]
        if rr:
            _, bx, by, bw, bh = rr[0][:5]
            c0 = np.array([bx + bw / 2, by + bh / 2])
            def run_cf(damp):
                cov_cf = 0
                for f in range(f0, f1 + 1):
                    if f not in gtc:
                        continue
                    k = f - fe
                    disp = sum((0.95 ** max(0, j - 10)) if damp else 1.0 for j in range(1, k + 1))
                    c = c0 + vf * disp
                    cov_cf += _iou(gtc[f][1:5], (c[0] - bw / 2, c[1] - bh / 2, bw, bh)) > 0.5
                return cov_cf
            cfu, cfd = run_cf(False), run_cf(True)
            lines.append(f"   counterfactual (arithmetic, same start box {bw:.0f}x{bh:.0f} from the pegc row at f{fe}, v_final): undamped constant velocity covers {cfu}/{o['n']}; "
                         f"with the tracker's VEL_DAMP x0.95/frame past gap 10 it covers {cfd}/{o['n']} (tracker actual {cov})")
    res[seq] = dict(split=split, tid=tid, frames=[f0, f1], ids=ids, covered_pegplus=covp, covered_pegc=cov, oracle=o, gt_mean_v=vt, entries=ev, entries_in_burn=n_in)
    lines.append("")
txt = "\n".join(lines)
print(txt)
open(os.path.join(ROOT, "results", "peg_c", "diag_test_losses.txt"), "w", encoding="utf-8").write(txt + "\n")
json.dump(res, open(os.path.join(ROOT, "results", "peg_c", "diag_test_losses.json"), "w"), indent=1)
