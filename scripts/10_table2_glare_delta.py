"""Table II vs Table I: which errors does the synthetic glare add?

Same 15 sequences, same GT, same frames; only the images differ (synthetic lamp burns
pasted on scheduled targets). Compares, GT-box by GT-box, the real run with the
synthetic-twin run and splits the extra misses / extra false boxes by where they are:
on the burnt person (m < 0.7), near a burn (same person, +-30 frames), or elsewhere.

    .venv/Scripts/python.exe scripts/10_table2_glare_delta.py [--b_real eval/peg --b_synth eval_synthfs/peg_fs_noguard]
Output: results/failure_analysis/table2_glare_delta.json (+ printed table)
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from glaremot.analysis import io as aio                      # noqa: E402
from glaremot.analysis.matching import clear_match_sequence, iou_matrix  # noqa: E402
from glaremot.eval.eval_recovery import burn_index, BURN_THR   # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEAR = 30


def load(subdir, name, seq):
    return aio.load_mot(os.path.join(ROOT, "results", subdir, "trackers", name, "data", seq + ".txt"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--real", default="eval/peg")
    ap.add_argument("--synth", default="eval_synthfs/peg_fs_noguard")
    ap.add_argument("--out", default="table2_glare_delta.json")
    a = ap.parse_args()
    rs, rn = a.real.split("/")
    ss, sn = a.synth.split("/")
    seqs = sorted(f[:-4] for f in os.listdir(os.path.join(ROOT, "results", ss, "trackers", sn, "data")))
    rows, tot = [], {}
    for seq in seqs:
        gt = aio.load_mot(os.path.join(ROOT, "datasets", "synth", seq, "mot", "gt", "gt.txt"), is_gt=True)
        T = len(aio.list_frames(os.path.join(ROOT, "datasets", "synth", seq)))
        R = clear_match_sequence(gt, load(rs, rn, seq), T)
        S = clear_match_sequence(gt, load(ss, sn, seq), T)
        bi = burn_index(seq)                      # {(tid, frame1): m}
        burnt = {}
        for (g, f), m in bi.items():
            if m < BURN_THR:
                burnt.setdefault(g, set()).add(f)
        c = dict(seq=aio.short_name(seq), gt=sum(len(v) for v in gt.values()),
                 FN_real=R.FN, FN_synth=S.FN, FP_real=R.FP, FP_synth=S.FP,
                 IDSW_real=R.IDSW, IDSW_synth=S.IDSW,
                 fn_new_burnt=0, fn_new_near=0, fn_new_else=0, fn_fixed=0,
                 fn_burnt_frames=0, fn_burnt_missed_real=0,
                 fp_on_burnt=0, fp_on_burnt_real=0)
        burnt_set = {(g, f) for g, fs in burnt.items() for f in fs}
        c["burnt_gt_frames"] = len(burnt_set)
        for f in range(1, T + 1):
            ur, us = set(R.un_gt.get(f, [])), set(S.un_gt.get(f, []))
            for g in us - ur:
                if (g, f) in burnt_set:
                    c["fn_new_burnt"] += 1
                elif any(abs(f - h) <= NEAR for h in burnt.get(g, ())):
                    c["fn_new_near"] += 1
                else:
                    c["fn_new_else"] += 1
            c["fn_fixed"] += len(ur - us)
            for g in us:
                if (g, f) in burnt_set:
                    c["fn_burnt_frames"] += 1
            for g in ur:
                if (g, f) in burnt_set:
                    c["fn_burnt_missed_real"] += 1
        for Rr, key in ((S, "fp_on_burnt"), (R, "fp_on_burnt_real")):
            src = load(ss, sn, seq) if Rr is S else load(rs, rn, seq)
            for f, ts in Rr.un_trk.items():
                bg = [r for r in gt.get(f, []) if (r[0], f) in burnt_set]
                if not ts or not bg:
                    continue
                tb = [r for r in src.get(f, []) if r[0] in ts]
                sim = iou_matrix([r[1:] for r in bg], [r[1:] for r in tb])
                c[key] += int((sim.max(axis=0) >= 0.1).sum())
        rows.append(c)
        for k, v in c.items():
            if k != "seq":
                tot[k] = tot.get(k, 0) + v
    tot["seq"] = "TOTAL"
    rows.append(tot)
    out = os.path.join(aio.fa_root(), a.out)
    json.dump(rows, open(out, "w"), indent=1)
    keys = ["seq", "FN_real", "FN_synth", "FP_real", "FP_synth", "IDSW_real", "IDSW_synth", "burnt_gt_frames",
            "fn_burnt_missed_real", "fn_burnt_frames", "fn_new_burnt", "fn_new_near", "fn_new_else", "fn_fixed",
            "fp_on_burnt_real", "fp_on_burnt"]
    print(" ".join(f"{k[:12]:>12}" for k in keys))
    for r in rows:
        print(" ".join(f"{str(r[k])[:12]:>12}" for k in keys))
    print("->", out)


if __name__ == "__main__":
    main()
