"""Frame-level GT<->prediction matching that replicates TrackEval exactly.

``clear_match_sequence`` mirrors ``trackeval/metrics/clear.py:eval_sequence`` (score =
1000*(same id as previous step) + IoU, zeroed below IoU 0.5, Hungarian) and
``identity_assignment`` mirrors ``trackeval/metrics/identity.py`` (global IDF1 Hungarian),
on the data ``MotChallenge2DBox`` would score with ``DO_PREPROC=False`` (GT rows with
flag 0 dropped, ids relabelled to contiguous sorted order, file order kept). Counts
therefore reconcile with ``benchmark_*.txt``.
"""
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

EPS = np.finfo("float").eps
THR = 0.5


def iou_matrix(g, t):
    """TrackEval box IoU (xywh) between arrays g (Nx4) and t (Mx4) -> N x M."""
    g = np.array(g, dtype=float).reshape(-1, 4)
    t = np.array(t, dtype=float).reshape(-1, 4)
    g[:, 2] += g[:, 0]
    g[:, 3] += g[:, 1]
    t[:, 2] += t[:, 0]
    t[:, 3] += t[:, 1]
    mn = np.minimum(g[:, None, :], t[None, :, :])
    mx = np.maximum(g[:, None, :], t[None, :, :])
    inter = np.maximum(mn[..., 2] - mx[..., 0], 0) * np.maximum(mn[..., 3] - mx[..., 1], 0)
    a1 = (g[:, 2] - g[:, 0]) * (g[:, 3] - g[:, 1])
    a2 = (t[:, 2] - t[:, 0]) * (t[:, 3] - t[:, 1])
    union = a1[:, None] + a2[None, :] - inter
    inter[a1 <= EPS, :] = 0
    inter[:, a2 <= EPS] = 0
    inter[union <= EPS] = 0
    union[union <= EPS] = 1
    return inter / union


@dataclass
class ClearResult:
    T: int
    TP: int = 0
    FN: int = 0
    FP: int = 0
    IDSW: int = 0
    gt_ids: dict = field(default_factory=dict)      # f -> [gt id] (file order)
    trk_ids: dict = field(default_factory=dict)     # f -> [trk id]
    sim: dict = field(default_factory=dict)         # f -> G x T IoU matrix (frames with both)
    matches: dict = field(default_factory=dict)     # f -> [(gt, trk, iou)]
    un_gt: dict = field(default_factory=dict)       # f -> [gt id unmatched]
    un_trk: dict = field(default_factory=dict)      # f -> [trk id unmatched]
    idsw: list = field(default_factory=list)        # [(f, gt, prev_trk, new_trk)]

    def match_of(self, f):
        """{gt: (trk, iou)} for frame f."""
        return {g: (t, i) for g, t, i in self.matches.get(f, [])}


def clear_match_sequence(gt, trk, T=None):
    """gt / trk: {frame: [(id,x,y,w,h)]}. Returns ClearResult (see module docstring)."""
    T = T or max(list(gt) + list(trk) + [0])
    g_lab = {g: i for i, g in enumerate(sorted({r[0] for rs in gt.values() for r in rs}))}
    t_lab = {t: i for i, t in enumerate(sorted({r[0] for rs in trk.values() for r in rs}))}
    prev_id = np.full(len(g_lab), np.nan)        # last matched tracker id, any time back
    prev_step = np.full(len(g_lab), np.nan)      # tracker id at the previous timestep
    R = ClearResult(T=T)
    for f in range(1, T + 1):
        grows, trows = gt.get(f, []), trk.get(f, [])
        gids = [r[0] for r in grows]
        tids = [r[0] for r in trows]
        R.gt_ids[f], R.trk_ids[f] = gids, tids
        if not gids:
            R.FP += len(tids)
            R.un_gt[f], R.un_trk[f] = [], list(tids)
            continue
        if not tids:
            R.FN += len(gids)
            R.un_gt[f], R.un_trk[f] = list(gids), []
            continue
        sim = iou_matrix([r[1:] for r in grows], [r[1:] for r in trows])
        gl = np.array([g_lab[g] for g in gids])
        tl = np.array([t_lab[t] for t in tids])
        score = (tl[None, :] == prev_step[gl][:, None]) * 1000.0 + sim
        score[sim < THR - EPS] = 0
        rows, cols = linear_sum_assignment(-score)
        ok = score[rows, cols] > EPS
        rows, cols = rows[ok], cols[ok]
        mg, mt = gl[rows], tl[cols]
        is_sw = ~np.isnan(prev_id[mg]) & (mt != prev_id[mg])
        for k in np.nonzero(is_sw)[0]:
            R.idsw.append((f, gids[rows[k]], _orig(t_lab, prev_id[mg[k]]), tids[cols[k]]))
        R.IDSW += int(is_sw.sum())
        prev_id[mg] = mt
        prev_step[:] = np.nan
        prev_step[mg] = mt
        R.TP += len(rows)
        R.FN += len(gids) - len(rows)
        R.FP += len(tids) - len(rows)
        R.sim[f] = sim
        R.matches[f] = [(gids[i], tids[j], float(sim[i, j])) for i, j in zip(rows, cols)]
        mgs = {gids[i] for i in rows}
        mts = {tids[j] for j in cols}
        R.un_gt[f] = [g for g in gids if g not in mgs]
        R.un_trk[f] = [t for t in tids if t not in mts]
    return R


def _orig(lab, idx):
    inv = {v: k for k, v in lab.items()}
    return inv[int(idx)]


@dataclass
class IdResult:
    IDTP: int
    IDFN: int
    IDFP: int
    gt2trk: dict            # gt id -> trk id assigned by the global IDF1 matching
    pot: dict               # (gt, trk) -> potential-match frames (IoU >= 0.5)
    gt_count: dict
    trk_count: dict

    @property
    def IDF1(self):
        d = 2 * self.IDTP + self.IDFN + self.IDFP
        return 2 * self.IDTP / d if d else 0.0


def identity_assignment(gt, trk, R):
    """Global IDF1 assignment (trackeval identity.py) reusing R.sim for the IoU matrices."""
    g_ids = sorted({r[0] for rs in gt.values() for r in rs})
    t_ids = sorted({r[0] for rs in trk.values() for r in rs})
    G, Tn = len(g_ids), len(t_ids)
    if Tn == 0 or G == 0:
        n_gt = sum(len(v) for v in gt.values())
        n_tr = sum(len(v) for v in trk.values())
        return IdResult(0, n_gt if Tn == 0 else 0, n_tr if G == 0 else 0, {}, {}, {}, {})
    gi, ti = {g: i for i, g in enumerate(g_ids)}, {t: i for i, t in enumerate(t_ids)}
    pot = np.zeros((G, Tn))
    gc, tc = np.zeros(G), np.zeros(Tn)
    for f in range(1, R.T + 1):
        gl = [gi[g] for g in R.gt_ids.get(f, [])]
        tl = [ti[t] for t in R.trk_ids.get(f, [])]
        if f in R.sim:
            a, b = np.nonzero(R.sim[f] >= THR)
            for x, y in zip(a, b):
                pot[gl[x], tl[y]] += 1
        for i in gl:
            gc[i] += 1
        for j in tl:
            tc[j] += 1
    n = G + Tn
    fp_mat, fn_mat = np.zeros((n, n)), np.zeros((n, n))
    fp_mat[G:, :Tn] = 1e10
    fn_mat[:G, Tn:] = 1e10
    for i in range(G):
        fn_mat[i, :Tn] = gc[i]
        fn_mat[i, Tn + i] = gc[i]
    for j in range(Tn):
        fp_mat[:G, j] = tc[j]
        fp_mat[G + j, j] = tc[j]
    fn_mat[:G, :Tn] -= pot
    fp_mat[:G, :Tn] -= pot
    rows, cols = linear_sum_assignment(fn_mat + fp_mat)
    idfn = int(fn_mat[rows, cols].sum())
    idfp = int(fp_mat[rows, cols].sum())
    idtp = int(gc.sum() - idfn)
    g2t = {g_ids[r]: t_ids[c] for r, c in zip(rows, cols)
           if r < G and c < Tn and pot[r, c] > 0}
    potd = {(g_ids[a], t_ids[b]): int(pot[a, b]) for a, b in zip(*np.nonzero(pot))}
    return IdResult(idtp, idfn, idfp, g2t, potd,
                    {g_ids[i]: int(gc[i]) for i in range(G)},
                    {t_ids[j]: int(tc[j]) for j in range(Tn)})


def evaluate(gt, trk, T):
    """Match a sequence; returns (ClearResult, IdResult)."""
    R = clear_match_sequence(gt, trk, T)
    return R, identity_assignment(gt, trk, R)
