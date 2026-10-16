"""Per-track diagnostics: re-run the tracker on ONE sequence with a state dump.

Writes ``results/failure_analysis/diag/<run>/<seq>.jsonl``
(<run> = <results_subdir>__<tracker_name> of the stored run it is checked against, so real and
synth twins with the same sequence name do not overwrite each other) (one line per frame with all
tracks: id, emitted?, state, mode, time_since_update, allowed_gap, m, m_glare, present,
vis_geom, box, PEG's cusum / burn flag / emit-until / phi) plus the run's MOT txt, then
checks that this txt equals the stored one (determinism). ``render`` picks the dump up
automatically (extra timeline rows, mode in tile captions). ~2-4 min per sequence on the GTX 1650.
"""
import json
import os

from ..config import load_config, weight_path
from ..data.splits import make_splits
from . import io as aio


def resolve_seq(name):
    """Full split name from a full or short ('312_108q') name."""
    sp = make_splits()
    allseq = sp["train"] + sp["val"] + sp["test"]
    hits = [s for s in allseq if s == name or aio.short_name(s) == name]
    if len(hits) != 1:
        raise SystemExit(f"cannot resolve sequence '{name}' (matches: {hits})")
    return hits[0]


def _f(v, nd=4):
    return None if v is None else round(float(v), nd)


def make_dump(fh, W, H, norm_box_to_xyxy):
    """Callable for ``track_sequence(diag_out=...)`` writing one jsonl line per frame."""
    def dump(fi, tracker, emitted):
        em = {id(t) for t in emitted}
        rows = []
        for t in tracker.tracks:
            try:
                gap = t.allowed_gap()
            except Exception:
                gap = None
            x1, y1, x2, y2 = norm_box_to_xyxy(t.out_box(), W, H)
            rows.append(dict(
                id=int(t.id), emit=id(t) in em, state=t.state, mode=t.mode,
                tsu=int(t.kf.time_since_update), gap=None if gap is None else int(gap),
                m=_f(t.m), m_glare=_f(t.m_glare), present=_f(t.present), vis_geom=_f(t.vis_geom),
                box=[round(float(v), 1) for v in (x1, y1, x2, y2)],
                cusum=_f(getattr(t, "_cusum_g", None)), burn=bool(getattr(t, "_burn", False)),
                lamp=int(getattr(t, "_lamp_emit_until", -1)), phi=_f(getattr(t, "_phi", None))))
        fh.write(json.dumps(dict(f=fi, tracks=rows)) + "\n")
    return dump


def run_diag(seq, data_root=None, results_subdir="eval", stored_name="peg", tracker="beacon"):
    """Re-run `seq` with the state dump; compare its MOT txt with the stored one."""
    os.environ["GMOT_TRACKER"] = tracker
    os.environ.setdefault("GMOT_BIRTH_SIZE_GUARD", "0")      # required to match the paper
    import cv2
    import torch
    from ..eval.eval_mot import track_sequence
    from ..tracking.tracker import Perception, norm_box_to_xyxy

    seq = resolve_seq(seq)
    cfg = load_config()
    root = aio.resolve(data_root) if data_root else aio.cfg_data_root("real")
    sdir = os.path.join(root, seq)
    H, W = cv2.imread(aio.list_frames(sdir)[0]).shape[:2]
    out_dir = os.path.join(aio.fa_root(), "diag", f"{results_subdir}__{stored_name}")
    os.makedirs(out_dir, exist_ok=True)
    out_txt = os.path.join(out_dir, f"{seq}.txt")
    out_jsonl = os.path.join(out_dir, f"{seq}.jsonl")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    percep = Perception(weight_path(cfg, "detector"), weight_path(cfg, "hpsi"), device, 0.25)
    with open(out_jsonl, "w", encoding="utf-8") as fh:
        n, fps = track_sequence(sdir, percep, out_txt, diag_out=make_dump(fh, W, H, norm_box_to_xyxy))
    print(f"diag: {n} frames @ {fps:.1f} FPS -> {out_jsonl}")

    stored = os.path.join(aio.tracker_dir(results_subdir, stored_name), f"{seq}.txt")
    if not os.path.exists(stored):
        print(f"WARNING: no stored MOT txt at {stored}; determinism not checked")
        return None
    a = open(out_txt, encoding="utf-8").read().splitlines()
    b = open(stored, encoding="utf-8").read().splitlines()
    n_diff = sum(1 for x, y in zip(a, b) if x != y) + abs(len(a) - len(b))
    if n_diff == 0:
        print(f"determinism OK: diag MOT txt is identical to {stored} ({len(a)} rows)")
    else:
        print(f"WARNING: diag MOT txt differs from stored one: {n_diff} of {max(len(a), len(b))} rows "
              f"differ (diag {len(a)} rows, stored {len(b)} rows)")
    return n_diff
