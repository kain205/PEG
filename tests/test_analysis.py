"""Toy checks for the failure-analysis harness (hand-built GT/pred with known answers)."""
import numpy as np
import pytest

if not hasattr(np, "float"):
    np.float = float
if not hasattr(np, "int"):
    np.int = int

from glaremot.analysis.events import extract_sequence
from glaremot.analysis.matching import clear_match_sequence, evaluate

T = 20


def box(x, y=100, w=40, h=100):
    return (x, y, w, h)


def build():
    """GT 1: pred 10 misses frames 6-10 (FN gap) and pred 98 duplicates it in 1-5.
    GT 2: pred 20 -> pred 21 at frame 11 (reinit IDSW).  GT 3/4: preds 30/31 swap at 11.
    Pred 99: phantom FP in frames 5-9."""
    gt, trk = {}, {}
    for f in range(1, T + 1):
        gt[f], trk[f] = [], []
        gt[f].append((1, *box(100)))
        gt[f].append((2, *box(300)))
        gt[f].append((3, *box(500)))
        gt[f].append((4, *box(700)))
        if f <= 5 or f > 10:
            trk[f].append((10, *box(100)))
        if f <= 5:
            trk[f].append((98, *box(108)))                        # duplicate of GT 1, IoU ~ .67
        trk[f].append((20 if f <= 10 else 21, *box(300)))
        trk[f].append((30 if f <= 10 else 31, *box(500)))
        trk[f].append((31 if f <= 10 else 30, *box(700)))
        if 5 <= f <= 9:
            trk[f].append((99, *box(900)))
    return gt, trk


def test_event_types():
    gt, trk = build()
    evs, R, I = extract_sequence("toy", gt, trk, T)
    by = {(e.type, e.subtype): e for e in evs}
    fn = [e for e in evs if e.type == "FN_RUN"]
    assert [(e.gt_ids, e.frame_start, e.frame_end, e.subtype) for e in fn] == [([1], 6, 10, "gap")]
    fp = {e.pred_ids[0]: e for e in evs if e.type == "FP_RUN"}
    assert fp[99].subtype == "phantom" and fp[99].severity == 5
    assert fp[98].subtype == "duplicate" and fp[98].severity == 5
    sw = [e for e in evs if e.type == "IDSW"]
    assert sorted((e.gt_ids[0], e.subtype) for e in sw) == [(2, "reinit"), (3, "swap"), (4, "swap")]
    assert R.IDSW == 3 and R.FN == 5 and R.FP == 10
    assert ("FN_RUN", "gap") in by


def test_counts_equal_trackeval():
    from trackeval.datasets import MotChallenge2DBox
    from trackeval.metrics import CLEAR, Identity
    gt, trk = build()
    R, I = evaluate(gt, trk, T)

    def relabel(d):
        ids = sorted({r[0] for rs in d.values() for r in rs})
        return {v: i for i, v in enumerate(ids)}
    gm, tm = relabel(gt), relabel(trk)
    data = dict(num_timesteps=T, num_gt_ids=len(gm), num_tracker_ids=len(tm),
                num_gt_dets=sum(map(len, gt.values())), num_tracker_dets=sum(map(len, trk.values())),
                gt_ids=[], tracker_ids=[], similarity_scores=[])
    for f in range(1, T + 1):
        data["gt_ids"].append(np.array([gm[r[0]] for r in gt[f]], int))
        data["tracker_ids"].append(np.array([tm[r[0]] for r in trk[f]], int))
        data["similarity_scores"].append(MotChallenge2DBox._calculate_box_ious(
            np.array([r[1:] for r in gt[f]], float), np.array([r[1:] for r in trk[f]], float)))
    c = CLEAR({"PRINT_CONFIG": False}).eval_sequence(data)
    i = Identity({"PRINT_CONFIG": False}).eval_sequence(data)
    assert (R.TP, R.FN, R.FP, R.IDSW) == (c["CLR_TP"], c["CLR_FN"], c["CLR_FP"], c["IDSW"])
    assert (I.IDTP, I.IDFN, I.IDFP) == (i["IDTP"], i["IDFN"], i["IDFP"])


def test_empty_frames():
    R = clear_match_sequence({1: [(1, 0, 0, 10, 10)]}, {2: [(5, 0, 0, 10, 10)]}, 3)
    assert (R.FN, R.FP, R.TP, R.IDSW) == (1, 1, 0, 0)
