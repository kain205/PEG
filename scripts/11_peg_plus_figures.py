"""PEG vs PEG+ before/after evidence (Table III burn episodes) for the slides.

1. Per burn episode: coverage @IoU .5 and mean IoU of the burnt target, PEG vs PEG+
   (printed + saved as episodes.json, ranked by gain).
2. Two-row filmstrips (PEG top, PEG+ bottom) for the reference failure cases of the
   failure analysis (figures 01/02) and for the most-improved / still-failing episodes.

    .venv/Scripts/python.exe scripts/11_peg_plus_figures.py --plus pegplus_A_rcv
Output: results/peg_plus/figures/*.png, results/peg_plus/episodes.json
"""
import argparse
import importlib.util
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import (BURN_THR, burn_index, load_events,  # noqa: E402
                                         load_mot, match_frame)

_spec = importlib.util.spec_from_file_location("figs09", os.path.join(ROOT, "scripts", "09_presentation_figures.py"))
F9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F9)

OUT = os.path.join(ROOT, "results", "peg_plus", "figures")
SYNTH = os.path.join(ROOT, "datasets", "synth")
RCV = os.path.join(ROOT, "results", "eval_recovery", "trackers")
PEG_COL = (57, 135, 229)       # same blue as the deck / charts
PLUS_COL = (25, 163, 95)       # PEG+ green
F9.OUT = OUT
F9.GT_COL = (242, 169, 0)      # GT amber: visible on burnt-white tiles, never the PEG+ green


def episodes(seq, peg, plus):
    """Per glare event on this seq: burn frames, coverage and mean IoU for both runs."""
    gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
    bi = burn_index(seq, SYNTH)
    runs = {k: load_mot(os.path.join(RCV, name, "data", f"{seq}.txt")) for k, name in
            (("peg", peg), ("plus", plus))}
    out = []
    for tid, s0, dur in load_events(seq, SYNTH):
        ep = [f for f in range(s0 + 1, s0 + dur + 1)
              if any(r[0] == tid for r in gt.get(f, [])) and bi.get((tid, f), 1.0) < BURN_THR]
        if not ep:
            continue
        row = dict(seq=seq, tid=tid, start=ep[0], end=ep[-1], n=len(ep))
        for k, trk in runs.items():
            cov, ious, ids = 0, [], Counter()
            for f in ep:
                m = match_frame(gt.get(f, []), trk.get(f, []), 0.5).get(tid)
                if m:
                    cov += 1
                    ious.append(m[1])
                    ids[m[0]] += 1
            row[f"{k}_cov"] = cov / len(ep)
            row[f"{k}_iou"] = sum(ious) / len(ious) if ious else 0.0
            row[f"{k}_id"] = ids.most_common(1)[0][0] if ids else None
        out.append(row)
    return out


def track_id_near(seq, run, tid, frames):
    """Tracker id matched most often to GT `tid` over `frames` (to pick the focus box)."""
    gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
    trk = load_mot(os.path.join(RCV, run, "data", f"{seq}.txt"))
    c = Counter()
    for f in frames:
        m = match_frame(gt.get(f, []), trk.get(f, []), 0.3).get(tid)
        if m:
            c[m[0]] += 1
    return [i for i, _ in c.most_common(2)]


def strip(name, seq, frames, tid, peg, plus):
    win = list(range(max(1, frames[0] - 15), frames[-1] + 1))
    rows = [F9.Track("PEG", PEG_COL, "eval_recovery", peg, seq),
            F9.Track("PEG+", PLUS_COL, "eval_recovery", plus, seq)]
    focus = {"PEG": track_id_near(seq, peg, tid, win), "PEG+": track_id_near(seq, plus, tid, win)}
    def size_cap(row, f):
        tr = rows[0] if row == "PEG" else rows[1]
        bs = [r for r in tr.mot.get(f, []) if r[0] in focus[row][:1]]
        return f"box {bs[0][3]:.0f}x{bs[0][4]:.0f}px" if bs else ""
    return F9.filmstrip(name, seq, SYNTH, frames, [tid], rows, focus, captions=size_cap,
                        burn_root=SYNTH)


def frames_for(ep, k=5):
    """One frame just before the burn + evenly spaced frames through it."""
    s, e = ep["start"], ep["end"]
    pts = [max(1, s - 8)] + [round(s + (e - s) * i / (k - 2)) for i in range(k - 1)]
    return sorted(set(pts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--peg", default="peg_rcv_ng")
    ap.add_argument("--plus", required=True)
    args = ap.parse_args()
    seqs = sorted(f[:-4] for f in os.listdir(os.path.join(RCV, args.plus, "data")))
    eps = [e for s in seqs for e in episodes(s, args.peg, args.plus)]
    for e in eps:
        e["gain"] = e["plus_cov"] - e["peg_cov"]
    eps.sort(key=lambda e: -e["gain"])
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(os.path.dirname(OUT), "episodes.json"), "w", encoding="utf-8") as f:
        json.dump(eps, f, indent=1)
    print(f"{'seq':<28}{'gt':>5}{'frames':>12}{'PEG cov':>9}{'PEG+ cov':>9}{'PEG iou':>8}{'PEG+ iou':>9}")
    for e in eps:
        print(f"{e['seq']:<28}{e['tid']:>5}{e['start']:>6}-{e['end']:<5}{e['peg_cov']:>9.2f}"
              f"{e['plus_cov']:>9.2f}{e['peg_iou']:>8.2f}{e['plus_iou']:>9.2f}")
    better = sum(e["gain"] > 0.05 for e in eps)
    worse = sum(e["gain"] < -0.05 for e in eps)
    print(f"\nepisodes: {len(eps)} | better {better} | worse {worse} | same {len(eps) - better - worse}")

    # reference cases from the failure analysis (same episodes as figures 01/02)
    strip("cmp_box_collapse", "320_sequence_116q_new", [224, 236, 244, 250, 256], 1, args.peg, args.plus)
    strip("cmp_box_drifts", "204_sequence_81q_complete", [336, 348, 358, 366, 376], 300, args.peg, args.plus)
    # most improved (skip the two reference episodes) + the worst remaining failure
    ref = {("320_sequence_116q_new", 1), ("204_sequence_81q_complete", 300)}
    top = [e for e in eps if (e["seq"], e["tid"]) not in ref and e["gain"] > 0][:2]
    for i, e in enumerate(top, 1):
        strip(f"cmp_best{i}", e["seq"], frames_for(e), e["tid"], args.peg, args.plus)
    # still failing; skip episodes nobody covers at all (target never tracked before the
    # burn -- a Table III scoring quirk, not a coast failure)
    fails = sorted([e for e in eps if e["plus_cov"] < 0.6 and e["peg_cov"] < 0.6
                    and (e["plus_cov"] > 0 or e["peg_cov"] > 0)
                    and (e["seq"], e["tid"]) not in ref], key=lambda e: e["plus_cov"])
    if fails:
        e = fails[0]
        strip("cmp_still_fails", e["seq"], frames_for(e), e["tid"], args.peg, args.plus)


if __name__ == "__main__":
    main()
