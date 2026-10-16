"""Turn matched GT/prediction sequences into typed failure events.

One extractor per metric family (see the table in the skill file):
  FN_RUN / FP_RUN / LOC_PAIR / IDSW / ID_FRAG / ID_MERGE / LOW_IOU_RUN  (full-scene MOT)
  BURN_EP                                                             (Table III, synth)
All matching comes from ``matching.py`` (TrackEval-exact), so event counts reconcile with
the benchmark txt. Tags are added afterwards by ``tags.annotate``.
"""
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field

import numpy as np

from .matching import evaluate
from ..eval.eval_recovery import (BURN_THR, CLEAR_THR, burn_index, load_events,
                                  match_frame)

PHANTOM_FRAC = 0.10     # FP_RUN 'phantom': pred id matched in <= this share of its frames
LOC_LO, LOC_HI = 0.2, 0.5   # LOC_PAIR: FP+FN at same frame with IoU in [LO, HI)
LOC_MIN = 3             # min frames for a LOC_PAIR
LOW_IOU, LOW_IOU_MIN = 0.75, 5   # LOW_IOU_RUN: matched but IoU < 0.75 for >= 5 frames
SWAP_WIN = 30           # IDSW 'swap': new id was on another GT within this many frames
FRAG_MIN = 3            # ID_FRAG / ID_MERGE: an id must cover >= this many frames to count


@dataclass
class FailureEvent:
    event_id: str
    seq: str
    dataset: str
    type: str
    subtype: str
    frame_start: int
    frame_end: int
    key_frame: int
    gt_ids: list
    pred_ids: list
    severity: float
    iou_stats: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
    diag: dict = None
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


def short(seq):
    from .io import short_name
    return short_name(seq)


def runs(frames):
    """Group sorted ints into [(start, end)] consecutive runs."""
    out, frames = [], sorted(frames)
    if not frames:
        return out
    s = p = frames[0]
    for f in frames[1:]:
        if f != p + 1:
            out.append((s, p))
            s = f
        p = f
    out.append((s, p))
    return out


def _stats(vals):
    v = [x for x in vals if x is not None]
    return {"min": round(float(min(v)), 3), "mean": round(float(np.mean(v)), 3)} if v else {}


class _Index:
    """Per-sequence lookup tables built once from the ClearResult."""

    def __init__(self, R):
        self.R = R
        self.gt_frames = defaultdict(list)      # gt -> frames present
        self.trk_frames = defaultdict(list)
        self.g_match = defaultdict(dict)        # gt -> {f: (trk, iou)}
        self.t_match = defaultdict(dict)        # trk -> {f: (gt, iou)}
        for f in range(1, R.T + 1):
            for g in R.gt_ids.get(f, []):
                self.gt_frames[g].append(f)
            for t in R.trk_ids.get(f, []):
                self.trk_frames[t].append(f)
            for g, t, i in R.matches.get(f, []):
                self.g_match[g][f] = (t, i)
                self.t_match[t][f] = (g, i)

    def best_gt_iou(self, f, g):
        """Best IoU of GT g with any prediction at frame f (0 if none)."""
        R = self.R
        if f not in R.sim:
            return 0.0
        return float(R.sim[f][R.gt_ids[f].index(g)].max())

    def best_trk_iou(self, f, t):
        R = self.R
        if f not in R.sim:
            return 0.0
        return float(R.sim[f][:, R.trk_ids[f].index(t)].max())


def _mk(sd_seq, dataset, typ, sub, s, e, key, gts, prs, sev, iou, ident, **extra):
    return FailureEvent(
        event_id=f"{short(sd_seq)}/{typ}/{ident}/f{s:04d}", seq=sd_seq, dataset=dataset,
        type=typ, subtype=sub, frame_start=s, frame_end=e, key_frame=key,
        gt_ids=list(gts), pred_ids=list(prs), severity=float(sev), iou_stats=iou, extra=extra)


def _fn_runs(seq, ds, ix):
    R, out = ix.R, []
    for g, frs in ix.gt_frames.items():
        un = [f for f in frs if g not in ix.g_match or f not in ix.g_match[g]]
        never = not ix.g_match[g]
        for s, e in runs(un):
            if never:
                sub = "never_tracked"
            elif s == frs[0]:
                sub = "late_start"
            elif e == frs[-1]:
                sub = "early_end"
            else:
                sub = "gap"
            iou = _stats([ix.best_gt_iou(f, g) for f in range(s, e + 1)])
            out.append(_mk(seq, ds, "FN_RUN", sub, s, e, (s + e) // 2, [g], [], e - s + 1, iou, f"g{g}"))
    return out


def _fp_runs(seq, ds, ix, gt):
    R, out = ix.R, []
    for t, frs in ix.trk_frames.items():
        frac = len(ix.t_match[t]) / len(frs)
        un = [f for f in frs if f not in ix.t_match[t]]
        for s, e in runs(un):
            span = range(s, e + 1)
            dup = 0
            for f in span:            # IoU >= .5 with a GT that is matched to another id
                if f in R.sim:
                    col = R.trk_ids[f].index(t)
                    for gi in np.nonzero(R.sim[f][:, col] >= 0.5)[0]:
                        g = R.gt_ids[f][gi]
                        if g in ix.g_match and f in ix.g_match[g] and ix.g_match[g][f][0] != t:
                            dup += 1
                            break
            prev = [f for f in ix.t_match[t] if f < s]
            last_g = ix.t_match[t][max(prev)][0] if prev else None
            gone = sum(1 for f in span if last_g is not None and last_g not in R.gt_ids.get(f, []))
            n = e - s + 1
            if dup * 2 >= n:
                sub = "duplicate"
            elif frac <= PHANTOM_FRAC:
                sub = "phantom"
            elif last_g is not None and gone * 2 >= n:
                sub = "overhang"
            else:
                sub = "stray"
            iou = _stats([ix.best_trk_iou(f, t) for f in span])
            out.append(_mk(seq, ds, "FP_RUN", sub, s, e, (s + e) // 2, [], [t], n, iou, f"t{t}",
                           matched_frac=round(frac, 3)))
    return out


def _loc_pairs(seq, ds, ix, fns, fps):
    R, pairs = ix.R, defaultdict(list)
    for f, sim in R.sim.items():
        ug = [R.gt_ids[f].index(g) for g in R.un_gt[f]]
        ut = [R.trk_ids[f].index(t) for t in R.un_trk[f]]
        if not ug or not ut:
            continue
        cand = sorted(((sim[i, j], i, j) for i in ug for j in ut if LOC_LO <= sim[i, j] < LOC_HI),
                      reverse=True)
        used_i, used_j = set(), set()
        for v, i, j in cand:
            if i in used_i or j in used_j:
                continue
            used_i.add(i)
            used_j.add(j)
            pairs[(R.gt_ids[f][i], R.trk_ids[f][j])].append((f, float(v)))
    out = []
    for (g, t), fv in pairs.items():
        vmap = dict(fv)
        for s, e in runs([f for f, _ in fv]):
            if e - s + 1 < LOC_MIN:
                continue
            ev = _mk(seq, ds, "LOC_PAIR", "loose", s, e, (s + e) // 2, [g], [t], e - s + 1,
                     _stats([vmap[f] for f in range(s, e + 1)]), f"g{g}t{t}")
            for o in fns:
                if o.gt_ids == [g] and o.frame_start <= e and o.frame_end >= s:
                    ev.links.append(o.event_id)
                    o.links.append(ev.event_id)
            for o in fps:
                if o.pred_ids == [t] and o.frame_start <= e and o.frame_end >= s:
                    ev.links.append(o.event_id)
                    o.links.append(ev.event_id)
            out.append(ev)
    return out


def _idsw(seq, ds, ix):
    R, out = ix.R, []
    for f, g, pt, nt in R.idsw:
        prevs = [(pf, v[0]) for pf, v in ix.t_match[nt].items() if pf < f]
        lf, lg = max(prevs) if prevs else (None, None)
        gm = ix.g_match[g]
        pm = max(x for x in gm if x < f)
        gap = f - pm - 1
        if lg is not None and lg != g and f - lf <= SWAP_WIN:
            sub = "swap"
        elif lg is None:
            sub = "reinit"
        else:
            sub = "transfer"
        e = f
        while e + 1 in gm and gm[e + 1][0] == nt:
            e += 1
        out.append(_mk(seq, ds, "IDSW", sub, f, e, f, [g], [pt, nt], e - f + 1,
                       _stats([gm[k][1] for k in range(f, e + 1)]), f"g{g}",
                       prev_id=pt, new_id=nt, gap=gap, other_gt=lg if sub == "swap" else None))
    return out


def _id_events(seq, ds, ix, I):
    R, out = ix.R, []
    for g, m in ix.g_match.items():
        cnt = Counter(t for t, _ in m.values())
        ids = [t for t, n in cnt.items() if n >= FRAG_MIN]
        if len(ids) < 2:
            continue
        main = I.gt2trk.get(g) or cnt.most_common(1)[0][0]
        other = sorted(f for f, (t, _) in m.items() if t != main and cnt[t] >= FRAG_MIN)
        sev = I.gt_count[g] - I.pot.get((g, main), 0)
        s, e = other[0], other[-1]
        out.append(_mk(seq, ds, "ID_FRAG", "multi_id", s, e, other[len(other) // 2], [g], ids, sev,
                       _stats([m[f][1] for f in other]), f"g{g}", main_id=main, n_ids=len(ids)))
    for t, m in ix.t_match.items():
        cnt = Counter(g for g, _ in m.values())
        ids = [g for g, n in cnt.items() if n >= FRAG_MIN]
        if len(ids) < 2:
            continue
        inv = {v: k for k, v in I.gt2trk.items()}
        main = inv.get(t) or cnt.most_common(1)[0][0]
        other = sorted(f for f, (g, _) in m.items() if g != main and cnt[g] >= FRAG_MIN)
        sev = I.trk_count[t] - I.pot.get((main, t), 0)
        s, e = other[0], other[-1]
        out.append(_mk(seq, ds, "ID_MERGE", "multi_gt", s, e, other[len(other) // 2], ids, [t], sev,
                       _stats([m[f][1] for f in other]), f"t{t}", main_gt=main, n_gts=len(ids)))
    return out


def _low_iou(seq, ds, ix):
    out = []
    for g, m in ix.g_match.items():
        low = [f for f, (_, i) in m.items() if i < LOW_IOU]
        for s, e in runs(low):
            if e - s + 1 >= LOW_IOU_MIN:
                out.append(_mk(seq, ds, "LOW_IOU_RUN", "loose", s, e, (s + e) // 2, [g],
                               sorted({m[f][0] for f in range(s, e + 1)}), e - s + 1,
                               _stats([m[f][1] for f in range(s, e + 1)]), f"g{g}"))
    return out


def extract_sequence(seq, gt, trk, T, dataset="real"):
    """All non-burn events for one sequence + the matching results (for tagging/reconcile)."""
    R, I = evaluate(gt, trk, T)
    ix = _Index(R)
    fns, fps = _fn_runs(seq, dataset, ix), _fp_runs(seq, dataset, ix, gt)
    evs = fns + fps + _loc_pairs(seq, dataset, ix, fns, fps) + _idsw(seq, dataset, ix) \
        + _id_events(seq, dataset, ix, I) + _low_iou(seq, dataset, ix)
    return evs, R, I


# --------------------------------------------------------------------------- #
# Table III family: one BURN_EP per glare event (mirrors eval_recovery.recovery_seq)
# --------------------------------------------------------------------------- #
def extract_burn_episodes(seq, gt_mot, trk_mot, glare_root, iou_thr=0.5):
    """Returns (events, counters). ``counters`` = {idsw, frag, id_off, n_ep, n_surv} summed
    over the sequence's episodes, to be compared with ``recovery_seq``. ``gt_mot`` /
    ``trk_mot`` come from ``eval_recovery.load_mot`` (same loader as the benchmark)."""
    bi = burn_index(seq, glare_root)
    cnt = dict(idsw=0, frag=0, id_off=0, n_ep=0, n_surv=0)
    if not bi:
        return [], cnt
    burn_tids = {tid for (tid, _f) in bi}
    frames = sorted(gt_mot)
    match = {f: match_frame(gt_mot[f], trk_mot.get(f, []), iou_thr) for f in frames}
    trk_ids = {f: {r[0] for r in trk_mot.get(f, [])} for f in frames}
    entering = {}
    for tid in burn_tids:
        c = Counter()
        for f in frames:
            if bi.get((tid, f), 1.0) >= CLEAR_THR and tid in match[f]:
                c[match[f][tid][0]] += 1
        entering[tid] = c.most_common(1)[0][0] if c else None
    gt_at = {f: {r[0] for r in gt_mot[f]} for f in frames}
    out = []
    for tid, s0, dur in load_events(seq, glare_root):
        eid = entering.get(tid)
        ep = [F for F in range(s0 + 1, s0 + dur + 1)
              if F in gt_at and tid in gt_at[F] and bi.get((tid, F), 1.0) < BURN_THR]
        if not ep:
            continue
        idsw = frag = id_off = 0
        prev_cov, prev_id = True, eid
        for F in ep:
            pair = match[F].get(tid)
            cov = pair is not None
            cur = pair[0] if cov else None
            frag += int(prev_cov and not cov)
            idsw += int(cov and prev_id is not None and cur != prev_id)
            id_off += int(eid is not None and eid not in trk_ids[F])
            if cov:
                prev_id = cur
            prev_cov = cov
        last = match[ep[-1]].get(tid)
        surv = int(eid is not None and last is not None and last[0] == eid)
        cnt["n_ep"] += 1
        cnt["idsw"] += idsw
        cnt["frag"] += frag
        cnt["id_off"] += id_off
        cnt["n_surv"] += surv
        if surv and not (idsw or frag or id_off):
            continue                                    # clean episode: not a failure
        on_eid = [F for F in ep if (match[F].get(tid) or (None,))[0] == eid and eid is not None]
        failed = len(ep) - len(on_eid)
        if eid is None:
            sub = "no_entering_id"
        elif surv:
            sub = "ok"
        elif last is not None:                          # covered at the end, by another id
            sub = "reborn" if eid not in trk_ids[ep[-1]] else "id_swapped"
        else:
            sub = "dropped" if eid not in trk_ids[ep[-1]] else "drift"
        ms = {F: bi.get((tid, F), 1.0) for F in ep}
        key = min(ms, key=ms.get)
        seen = sorted({match[F][tid][0] for F in ep if tid in match[F]} | ({eid} if eid else set()))
        out.append(_mk(seq, "synth", "BURN_EP", sub, ep[0], ep[-1], key, [tid], seen, failed,
                       _stats([match[F][tid][1] for F in ep if tid in match[F]]), f"g{tid}",
                       idsw=idsw, frag=frag, id_off=id_off, survived=surv, entering_id=eid,
                       min_m=round(min(ms.values()), 3), burn_frames=len(ep)))
    return out, cnt
