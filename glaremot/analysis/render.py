"""Images an agent can look at: contact sheet + timeline (+ optional mp4 for humans).

Draw convention (fixed; the skill file repeats it):
  GT matched      green, thin            GT MISSED   magenta, THICK
  pred matched    per-id colour          pred FP     RED
  focus ids       labelled g<id> (GT) / t<id> (pred) in large text; other boxes dimmed
  yellow rectangle on the full-frame tile = the crop used for the other tiles
"""
import json
import os

import cv2
import numpy as np

from .io import fa_root, frame_image, load_run_meta, load_seq, run_dir
from .matching import clear_match_sequence
from ..photometric import mask_area_inside, saturation_map

TILE_H = 320
FULL_W = 640
MAX_W = 1800
GREEN, MAGENTA, RED, YELLOW = (0, 200, 0), (255, 0, 255), (0, 0, 255), (0, 255, 255)
_FALLBACK_PALETTE = [(80, 220, 80), (60, 200, 255), (255, 120, 60), (200, 80, 255), (60, 255, 255),
                     (255, 200, 40), (40, 120, 255), (180, 255, 120), (255, 80, 200), (120, 220, 255)]


_IC = []


def id_color(tid):
    """Per-id colour, shared with the tracker's own visualisation when importable."""
    if not _IC:
        try:
            from ..tracking.tracker import id_color as ic
        except Exception:      # torch/ultralytics missing: same-style fallback palette
            ic = lambda t: _FALLBACK_PALETTE[int(t) % len(_FALLBACK_PALETTE)]
        _IC.append(ic)
    return _IC[0](tid)


def case_dir(run, event_id):
    d = os.path.join(run_dir(run), "cases", event_id.replace("/", "__"))
    os.makedirs(d, exist_ok=True)
    return d


# --------------------------------------------------------------------------- #
# diag rows (written by diag.py)
# --------------------------------------------------------------------------- #
GATE_H = float(os.environ.get("GBEACON_CUSUM_H", "0.40"))   # PEG gate threshold h (beacon_tracker default)


def load_diag(run, seq):
    """{frame: {track_id: dict}} from results/failure_analysis/diag/<run>/<seq>.jsonl or None."""
    p = os.path.join(fa_root(), "diag", run, f"{seq}.jsonl")
    if not os.path.exists(p):
        return None
    out = {}
    with open(p, encoding="utf-8") as f:
        for ln in f:
            r = json.loads(ln)
            out[r["f"]] = {t["id"]: t for t in r["tracks"]}
    return out


# --------------------------------------------------------------------------- #
# per-frame drawing
# --------------------------------------------------------------------------- #
def _text(img, s, org, scale=0.5, col=(255, 255, 255), th=1):
    (w, h), b = cv2.getTextSize(s, cv2.FONT_HERSHEY_SIMPLEX, scale, th)
    x, y = int(org[0]), int(org[1])
    cv2.rectangle(img, (x, y - h - 3), (x + w + 4, y + b), (25, 25, 25), -1)
    cv2.putText(img, s, (x + 2, y), cv2.FONT_HERSHEY_SIMPLEX, scale, col, th, cv2.LINE_AA)
    return w + 4


def _boxes(sd, R, ev, f):
    """[(kind, id, matched, focus, (x,y,w,h))] for GT and pred boxes at frame f."""
    m = R.match_of(f)
    matched_t = {t for t, _ in m.values()}
    with_gt = {m[g][0] for g in ev["gt_ids"] if g in m}       # preds that carry a focus GT
    if f in R.sim:                                            # + preds loosely overlapping one (IoU >= .2)
        for g in ev["gt_ids"]:
            if g in R.gt_ids[f]:
                row = R.sim[f][R.gt_ids[f].index(g)]
                with_gt |= {R.trk_ids[f][j] for j in np.nonzero(row >= 0.2)[0]}
    near_gt = set()                                           # GTs loosely overlapping a focus pred (IoU >= .1)
    if f in R.sim and ev["pred_ids"]:
        for t in ev["pred_ids"]:
            if t in R.trk_ids[f]:
                col = R.sim[f][:, R.trk_ids[f].index(t)]
                near_gt |= {R.gt_ids[f][i] for i in np.nonzero(col >= 0.1)[0]}
    out = []
    for g, *b in sd.gt.get(f, []):
        out.append(("gt", g, g in m, g in ev["gt_ids"] or g in near_gt, b))
    for t, *b in sd.trk.get(f, []):
        out.append(("pred", t, t in matched_t, t in ev["pred_ids"] or t in with_gt, b))
    return out


def _draw(img, boxes, s, ox, oy, labels, thick_scale=1.0):
    """Draw boxes on img (already the resized crop). Dim non-focus first, focus on top."""
    base = img.copy()
    for focus_pass in (False, True):
        canvas = img if focus_pass else base
        for kind, i, matched, focus, (x, y, w, h) in boxes:
            if focus != focus_pass:
                continue
            p1 = (int(round((x - ox) * s)), int(round((y - oy) * s)))
            p2 = (int(round((x + w - ox) * s)), int(round((y + h - oy) * s)))
            if kind == "gt":
                col, th = (GREEN, 1) if matched else (MAGENTA, 3)
            else:
                col, th = (id_color(i), 2) if matched else (RED, 2)
            if not focus and not focus_pass:
                th = 1
            cv2.rectangle(canvas, p1, p2, col, max(1, int(th * thick_scale)))
            if focus and labels:
                lab = f"{'g' if kind == 'gt' else 't'}{i}"
                _text(canvas, lab, (p1[0], p1[1] - 6 if kind == "gt" else p2[1] + 18), 0.55, col, 2)
        if not focus_pass:
            img[:] = cv2.addWeighted(base, 0.7, img, 0.3, 0)
    return img


def _crop_rect(sd, R, ev, frames):
    """Union of focus boxes over `frames`, padded 50 %, min 256 px, aspect in [0.7, 1.5]."""
    xs1, ys1, xs2, ys2 = [], [], [], []
    for f in frames:
        for kind, i, _, focus, (x, y, w, h) in _boxes(sd, R, ev, f):
            if focus:
                xs1.append(x), ys1.append(y), xs2.append(x + w), ys2.append(y + h)
    if not xs1:
        return 0, 0, sd.W, sd.H
    x1, y1, x2, y2 = min(xs1), min(ys1), max(xs2), max(ys2)
    w, h = max(x2 - x1, 1), max(y2 - y1, 1)
    w, h = max(w * 2.0, 256), max(h * 2.0, 256)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    if w / h > 1.5:
        h = w / 1.5
    elif w / h < 0.7:
        w = h * 0.7
    w, h = min(w, sd.W), min(h, sd.H)
    x0 = min(max(cx - w / 2, 0), sd.W - w)
    y0 = min(max(cy - h / 2, 0), sd.H - h)
    return int(x0), int(y0), int(x0 + w), int(y0 + h)


def _tile_frames(ev, T):
    s, e = ev["frame_start"], ev["frame_end"]
    fr = [s - 5, s] + [int(round(v)) for v in np.linspace(s, e, 5)[1:-1]] + [e, e + 5]
    out = []
    for f in fr:
        f = min(max(f, 1), T)
        if f not in out:
            out.append(f)
    return out


def _caption(sd, ev, R, f, img, diag, mg):
    """Two short lines: [frame, IoU/matched id] and [m_glare, saturation, tracker mode]."""
    parts = [f"f{f}"]
    if ev["gt_ids"]:
        pair = R.match_of(f).get(ev["gt_ids"][0])
        present = any(b[0] == ev["gt_ids"][0] for b in sd.gt.get(f, []))
        parts.append(f"IoU {pair[1]:.2f}" if pair else ("miss" if present else "no-gt"))
        if pair:
            parts[-1] += f" t{pair[0]}"
    n1 = len(parts)
    if mg is not None:
        v = mg.get((ev["gt_ids"][0], f - 1), 1.0) if ev["gt_ids"] else None
        if v is not None:
            parts.append(f"m {v:.2f}")
    sat = _sat_frac(sd, ev, f, img)
    if sat is not None:
        parts.append(f"sat {sat:.2f}")
    if diag and f in diag:
        ids = [t for t in ev["pred_ids"] if t in diag[f]] or \
              ([R.match_of(f)[ev["gt_ids"][0]][0]] if ev["gt_ids"] and ev["gt_ids"][0] in R.match_of(f) else [])
        for t in ids[:2]:
            parts.append(f"t{t}:{diag[f][t]['mode']}")
    return " ".join(parts[:n1]), " ".join(parts[n1:])


def _sat_frac(sd, ev, f, img):
    for kind, ids in (("gt", ev["gt_ids"]), ("pred", ev["pred_ids"])):
        rows = sd.gt.get(f, []) if kind == "gt" else sd.trk.get(f, [])
        for r in rows:
            if r[0] in ids:
                x, y, w, h = r[1:]
                x1, y1, x2, y2 = int(max(x, 0)), int(max(y, 0)), int(x + w), int(y + h)
                sub = img[y1:y2, x1:x2]
                if sub.size == 0:
                    return None
                return float(saturation_map(sub).mean())
    return None


def _mg(sd):
    if sd.dataset != "synth":
        return None
    from ..data.glare_m import glare_m_map
    return glare_m_map(sd.seq, glare_root=os.path.dirname(sd.seq_dir))


def contact_sheet(ev, sd, R, diag=None, mg=None):
    frames = _tile_frames(ev, sd.T)
    crop = _crop_rect(sd, R, ev, sorted(set(frames + [ev["key_frame"]])))
    x0, y0, x1, y1 = crop
    tiles = []
    kf = ev["key_frame"]
    im = frame_image(sd.seq_dir, kf, sd.img_paths)
    s = FULL_W / sd.W
    full = cv2.resize(im, (FULL_W, int(sd.H * s)), interpolation=cv2.INTER_AREA)
    _draw(full, _boxes(sd, R, ev, kf), s, 0, 0, labels=False)
    cv2.rectangle(full, (int(x0 * s), int(y0 * s)), (int(x1 * s), int(y1 * s)), YELLOW, 2)
    _text(full, f"full frame f{kf} (key)  yellow = crop", (4, 18), 0.5)
    tiles.append(full)
    for f in frames:
        im = frame_image(sd.seq_dir, f, sd.img_paths)
        crop_im = im[y0:y1, x0:x1]
        sc = TILE_H / crop_im.shape[0]
        t = cv2.resize(crop_im, (max(1, int(crop_im.shape[1] * sc)), TILE_H), interpolation=cv2.INTER_CUBIC)
        _draw(t, _boxes(sd, R, ev, f), sc, x0, y0, labels=True)
        l1, l2 = _caption(sd, ev, R, f, im, diag, mg)
        col = YELLOW if f in (ev["frame_start"], ev["frame_end"]) else (255, 255, 255)
        _text(t, l1, (4, 18), 0.5, col)
        if l2:
            _text(t, l2, (4, 40), 0.5, col)
        tiles.append(t)
    # layout: full-frame tile on the left, crop tiles flow into rows on its right
    right_w = MAX_W - FULL_W - 4
    rows, cur, w = [], [], 0
    for t in tiles[1:]:
        if cur and w + t.shape[1] + 4 > right_w:
            rows.append(cur)
            cur, w = [], 0
        cur.append(t)
        w += t.shape[1] + 4
    rows.append(cur)
    rw = max(sum(t.shape[1] + 4 for t in r) for r in rows)
    rh = sum(max(t.shape[0] for t in r) + 4 for r in rows)
    sheet_w, body_h = FULL_W + 4 + rw, max(rh, full.shape[0])
    body = np.full((body_h, sheet_w, 3), 40, np.uint8)
    body[:full.shape[0], :FULL_W] = full
    y = 0
    for r in rows:
        x = FULL_W + 4
        for t in r:
            body[y:y + t.shape[0], x:x + t.shape[1]] = t
            x += t.shape[1] + 4
        y += max(t.shape[0] for t in r) + 4
    head = np.full((62, sheet_w, 3), 25, np.uint8)
    tg = " ".join(f"{k}={v}" if not isinstance(v, bool) else k for k, v in ev["tags"].items()
                  if v not in (False, None))
    cv2.putText(head, f"{ev['event_id']}  {ev['type']}/{ev['subtype']}  frames {ev['frame_start']}-"
                f"{ev['frame_end']}  severity {ev['severity']:.0f}  gt={ev['gt_ids']} pred={ev['pred_ids']}",
                (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(head, tg[:230], (6, 48), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)
    head = head[:, :sheet_w] if head.shape[1] >= sheet_w else head
    return np.vstack([head, body])


# --------------------------------------------------------------------------- #
# timeline
# --------------------------------------------------------------------------- #
def timeline(ev, sd, R, path, diag=None, mg=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    lo, hi = max(1, ev["frame_start"] - 30), min(sd.T, ev["frame_end"] + 30)
    fr = list(range(lo, hi + 1))
    g = ev["gt_ids"][0] if ev["gt_ids"] else None
    ids = list(ev["pred_ids"])
    rgb = lambda t: tuple(c / 255 for c in id_color(t)[::-1])
    nrow = 3 + (3 if diag else 0)
    fig, ax = plt.subplots(nrow, 1, figsize=(11, 1.9 * nrow + 0.6), sharex=True)
    for a in ax:
        a.axvspan(ev["frame_start"], ev["frame_end"], color="orange", alpha=0.18)
        a.axvline(ev["key_frame"], color="k", lw=0.6, ls=":")
        a.grid(alpha=0.25)

    # row 1: IoU of the focus GT (or best IoU of the focus pred)
    a = ax[0]
    xs, ys, cs = [], [], []
    for f in fr:
        if g is not None:
            if any(b[0] == g for b in sd.gt.get(f, [])):
                pair = R.match_of(f).get(g)
                xs.append(f)
                ys.append(pair[1] if pair else 0.0)
                cs.append("tab:green" if pair else "m")
        elif ids:
            for t in ids:
                if any(b[0] == t for b in sd.trk.get(f, [])):
                    pair = [(gg, i) for gg, tt, i in R.matches.get(f, []) if tt == t]
                    xs.append(f)
                    ys.append(pair[0][1] if pair else 0.0)
                    cs.append("tab:green" if pair else "r")
    a.scatter(xs, ys, c=cs, s=10)
    a.axhline(0.5, color="gray", lw=0.6, ls="--")
    a.set_ylim(-0.05, 1.05)
    a.set_ylabel(f"IoU of {'g' + str(g) if g is not None else 't' + str(ids[:1])}\n(magenta/red = missed)", fontsize=8)

    # row 2: which pred id carries the GT / where the focus pred ids exist
    a = ax[1]
    if g is not None:
        for f in fr:
            pair = R.match_of(f).get(g)
            if pair:
                a.scatter(f, pair[0], color=rgb(pair[0]), s=14)
    for t in ids:
        pf = [f for f in fr if any(b[0] == t for b in sd.trk.get(f, []))]
        mt = {f for f in pf if any(tt == t for _, tt, _ in R.matches.get(f, []))}
        a.scatter([f for f in pf if f in mt], [t] * sum(f in mt for f in pf), marker="|", s=60, color=rgb(t))
        a.scatter([f for f in pf if f not in mt], [t] * sum(f not in mt for f in pf), marker="|", s=60, color="r")
    a.set_ylabel("pred id (colour = id,\nred | = FP frame)", fontsize=8)

    # row 3: glare signal
    a = ax[2]
    if g is not None and mg:
        a.plot(fr, [mg.get((g, f - 1), 1.0) for f in fr], color="tab:blue", label="m_glare (schedule)")
    step = max(1, len(fr) // 60)
    sf, sv = [], []
    for f in fr[::step]:
        rows = [b for b in sd.gt.get(f, []) if b[0] == g] if g is not None else \
               [b for b in sd.trk.get(f, []) if b[0] in ids]
        im = frame_image(sd.seq_dir, f, sd.img_paths)
        if rows and im is not None:
            _, x, y, w, h = rows[0]
            sub = im[int(max(y, 0)):int(y + h), int(max(x, 0)):int(x + w)]
            if sub.size:
                sf.append(f)
                sv.append(float(saturation_map(sub).mean()))
    a.plot(sf, sv, color="tab:red", marker=".", ms=3, label="saturated fraction in box")
    a.set_ylim(-0.05, 1.05)
    a.legend(fontsize=7, loc="upper right")
    a.set_ylabel("glare signal", fontsize=8)

    if diag:
        focus = set(ids)
        if g is not None:
            focus |= {R.match_of(f)[g][0] for f in fr if g in R.match_of(f)}
        focus = sorted(focus)[:4]
        modes = sorted({diag[f][t]["mode"] for f in fr if f in diag for t in focus if t in diag[f]})
        a = ax[3]
        for t in focus:                                   # dot = emitted, x = alive but NOT emitted
            pts = [(f, modes.index(diag[f][t]["mode"]), diag[f][t].get("emit", True))
                   for f in fr if f in diag and t in diag[f]]
            on = [p for p in pts if p[2]]
            off = [p for p in pts if not p[2]]
            a.scatter([p[0] for p in on], [p[1] for p in on], s=12, color=rgb(t), label=f"t{t}")
            a.scatter([p[0] for p in off], [p[1] for p in off], s=14, color=rgb(t), marker="x", lw=0.8)
        a.set_yticks(range(len(modes)))
        a.set_yticklabels(modes, fontsize=7)
        a.legend(fontsize=7, ncol=4, loc="upper right")
        a.set_ylabel("tracker mode\n(dot=emitted, x=hidden)", fontsize=7)
        a = ax[4]
        for t in focus:
            pts = [(f, diag[f][t]["tsu"], diag[f][t]["gap"]) for f in fr if f in diag and t in diag[f]]
            a.plot([p[0] for p in pts], [p[1] for p in pts], color=rgb(t), lw=1.2)
            a.plot([p[0] for p in pts], [p[2] for p in pts], color=rgb(t), lw=0.8, ls="--")
        a.set_ylabel("time_since_update (solid)\nallowed_gap (dashed)", fontsize=7)
        a = ax[5]
        # PEG gate (default GBEACON_CUSUM=0): fires when phi >= h on a missed frame and arms
        # emission until _lamp_emit_until. phi is only evaluated while the track is missed.
        for t in focus:
            pts = [(f, diag[f][t]) for f in fr if f in diag and t in diag[f]]
            a.plot([f for f, d in pts], [d["phi"] if d["tsu"] >= 1 and d.get("phi") is not None else np.nan
                                         for f, d in pts], color=rgb(t), lw=1.2, marker=".", ms=3)
            a.plot([f for f, d in pts], [1.1 if f <= d.get("lamp", -1) else np.nan for f, d in pts],
                   color=rgb(t), lw=4, alpha=0.7)
        a.axhline(GATE_H, color="k", lw=0.8, ls="--")
        a.set_ylim(-0.05, 1.2)
        a.set_ylabel(f"gate: phi on missed frames\nh={GATE_H} dashed, armed = bar", fontsize=7)
    ax[-1].set_xlabel("MOT frame")
    fig.suptitle(f"{ev['event_id']}  {ev['type']}/{ev['subtype']}  (orange = event span, dotted = key frame)",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def clip(ev, sd, R, path, max_frames=400):
    lo, hi = max(1, ev["frame_start"] - 15), min(sd.T, ev["frame_end"] + 15)
    hi = min(hi, lo + max_frames - 1)
    s = 960 / sd.W
    out = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 22, (960, int(sd.H * s)))
    for f in range(lo, hi + 1):
        im = cv2.resize(frame_image(sd.seq_dir, f, sd.img_paths), (960, int(sd.H * s)))
        _draw(im, _boxes(sd, R, ev, f), s, 0, 0, labels=True)
        _text(im, f"f{f}  {ev['event_id']}", (4, 18), 0.6)
        out.write(im)
    out.release()


def render_events(run, events, mp4=False):
    """Render sheet.png + timeline.png (+ clip.mp4) per event dict. Returns sheet paths."""
    meta = load_run_meta(run)
    by_seq = {}
    for ev in events:
        by_seq.setdefault(ev["seq"], []).append(ev)
    paths = []
    for seq, evs in by_seq.items():
        sd = load_seq(seq, meta["data_root"], meta["results_subdir"], meta["tracker_name"], meta["dataset"])
        R = clear_match_sequence(sd.gt, sd.trk, sd.T)
        diag, mg = load_diag(run, seq), _mg(sd)
        for ev in evs:
            d = case_dir(run, ev["event_id"])
            sheet = contact_sheet(ev, sd, R, diag, mg)
            cv2.imwrite(os.path.join(d, "sheet.png"), sheet)
            timeline(ev, sd, R, os.path.join(d, "timeline.png"), diag, mg)
            if mp4:
                clip(ev, sd, R, os.path.join(d, "clip.mp4"))
            paths.append(os.path.join(d, "sheet.png"))
    return paths
