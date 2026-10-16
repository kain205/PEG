"""Presentation evidence figures for the failure analysis (filmstrips + charts).

Each filmstrip is a row (or two rows, PEG vs backbone) of crops at chosen frames with
GT and prediction boxes; hidden (alive but not emitted) tracks are drawn dashed from the
diag dump. Charts summarise PEG vs backbone and the reviewed causes.

    .venv/Scripts/python.exe scripts/09_presentation_figures.py
Output: results/failure_analysis/figures/*.png
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from glaremot.analysis import io as aio                       # noqa: E402
from glaremot.analysis.matching import clear_match_sequence     # noqa: E402
from glaremot.eval.eval_recovery import burn_index             # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "failure_analysis", "figures")
FONT = "C:/Windows/Fonts/arial.ttf"
FONT_B = "C:/Windows/Fonts/arialbd.ttf"

GT_COL = (40, 200, 90)          # GT person
MISS_COL = (232, 60, 170)       # GT person nobody is tracking
PEG_COL = (42, 120, 214)        # PEG box
BB_COL = (235, 104, 52)         # backbone box
FP_COL = (227, 60, 60)          # box on no person
TILE_H = 380
CAP_H = 58


def font(sz, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, sz)


def iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def xyxy(r):
    _, x, y, w, h = r
    return (x, y, x + w, y + h)


def load_diag(run, seq):
    p = os.path.join(aio.fa_root(), "diag", run, f"{seq}.jsonl")
    if not os.path.exists(p):
        return {}
    out = {}
    with open(p, encoding="utf-8") as f:
        for ln in f:
            r = json.loads(ln)
            out[r["f"]] = {t["id"]: t for t in r["tracks"]}
    return out


def dashed_rect(d, b, col, w=3, dash=12):
    x1, y1, x2, y2 = b
    for (ax, ay, bx, by) in ((x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)):
        L = max(abs(bx - ax), abs(by - ay))
        n = max(1, int(L // dash))
        for k in range(0, n, 2):
            t0, t1 = k / n, min(1.0, (k + 1) / n)
            d.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)],
                   fill=col, width=w)


def label(d, xy, text, col, sz=22):
    f = font(sz, True)
    x, y = xy
    bb = d.textbbox((x, y), text, font=f)
    d.rectangle([bb[0] - 3, bb[1] - 2, bb[2] + 3, bb[3] + 2], fill=(0, 0, 0))
    d.text((x, y), text, font=f, fill=col)


class Track:
    """One tracker run on one sequence: MOT boxes (+ optional diag for hidden tracks)."""

    def __init__(self, name, col, results_subdir, tracker_name, seq, diag_run=None):
        self.name, self.col = name, col
        self.mot = aio.load_mot(os.path.join(aio.tracker_dir(results_subdir, tracker_name), f"{seq}.txt"))
        self.diag = load_diag(diag_run, seq) if diag_run else {}


def crop_rect(boxes, W, H, pad=0.6, min_side=260, aspect=0.85):
    x1 = min(b[0] for b in boxes); y1 = min(b[1] for b in boxes)
    x2 = max(b[2] for b in boxes); y2 = max(b[3] for b in boxes)
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    w, h = (x2 - x1) * (1 + pad), (y2 - y1) * (1 + pad)
    h = max(h, min_side, w / aspect)
    w = max(w, h * aspect)
    x1, y1 = max(0, cx - w / 2), max(0, cy - h / 2)
    x2, y2 = min(W, x1 + w), min(H, y1 + h)
    x1, y1 = max(0, x2 - w), max(0, y2 - h)
    return int(x1), int(y1), int(x2), int(y2)


def filmstrip(name, seq, data_root, frames, gt_ids, rows, pred_ids, captions=None, crop=None,
              burn_root=None, show_all_gt=False):
    """rows: [Track]; pred_ids: {track.name: [ids]} focus predictions per row (drawn + labelled).
    captions: optional fn(row_name, f) -> extra text line."""
    sdir = os.path.join(data_root, seq)
    paths = aio.list_frames(sdir)
    gt = aio.load_mot(os.path.join(sdir, "mot", "gt", "gt.txt"), is_gt=True)
    W, H = Image.open(paths[0]).size
    bi = burn_index(seq, burn_root) if burn_root else {}
    if crop is None:
        bs = []
        for f in frames:
            bs += [xyxy(r) for r in gt.get(f, []) if r[0] in gt_ids]
            for tr in rows:
                bs += [xyxy(r) for r in tr.mot.get(f, []) if r[0] in pred_ids.get(tr.name, [])]
                bs += [tuple(tr.diag[f][t]["box"]) for t in pred_ids.get(tr.name, [])
                       if f in tr.diag and t in tr.diag[f]]
        crop = crop_rect(bs, W, H)
    cx1, cy1, cx2, cy2 = crop
    s = TILE_H / (cy2 - cy1)
    tw = int((cx2 - cx1) * s)
    gap, lab_w = 8, (190 if len(rows) > 1 else 0)
    sheet = Image.new("RGB", (lab_w + len(frames) * (tw + gap) - gap, len(rows) * (TILE_H + CAP_H + gap) - gap),
                      (18, 18, 18))
    for ri, tr in enumerate(rows):
        y0 = ri * (TILE_H + CAP_H + gap)
        R = clear_match_sequence(gt, tr.mot, len(paths))        # same matching as TrackEval
        if lab_w:
            d = ImageDraw.Draw(sheet)
            d.text((12, y0 + TILE_H // 2 - 16), tr.name, font=font(30, True), fill=tr.col)
        for fi, f in enumerate(frames):
            im = Image.open(paths[f - 1]).convert("RGB").crop(crop).resize((tw, TILE_H))
            d = ImageDraw.Draw(im)
            T = lambda b: tuple(((b[0] - cx1) * s, (b[1] - cy1) * s, (b[2] - cx1) * s, (b[3] - cy1) * s))  # noqa
            G = [(r[0], xyxy(r)) for r in gt.get(f, []) if show_all_gt or r[0] in gt_ids]
            P = [(r[0], xyxy(r)) for r in tr.mot.get(f, [])]
            focus = pred_ids.get(tr.name, [])
            m = R.match_of(f)
            matched_t = {t for t, _ in m.values()}
            best = None
            for g, gb in G:
                col = GT_COL if g in m else MISS_COL
                d.rectangle(T(gb), outline=col, width=3 if g in gt_ids else 2)
                if g in gt_ids:
                    best = m[g][1] if g in m else 0.0
            for t, pb in P:
                if t not in focus:
                    continue
                col = tr.col if t in matched_t else FP_COL
                d.rectangle(T(pb), outline=col, width=5)
                tb = T(pb)
                label(d, (tb[0] + 2, min(TILE_H - 28, tb[3] + 4)), f"{tr.name.split()[0]} id{t}", col, 20)
            for t in focus:                                     # hidden (alive, not in output) from diag
                if f in tr.diag and t in tr.diag[f] and not tr.diag[f][t]["emit"]:
                    tb = T(tr.diag[f][t]["box"])
                    dashed_rect(d, tb, (200, 200, 200), 3)
                    label(d, (tb[0] + 2, max(0, tb[1] - 26)), f"id{t} hidden", (220, 220, 220), 18)
            sheet.paste(im, (lab_w + fi * (tw + gap), y0))
            d = ImageDraw.Draw(sheet)
            x = lab_w + fi * (tw + gap)
            line1 = f"frame {f}"
            if gt_ids and best is not None:
                line1 += f"   IoU {best:.2f}" if best > 0 else "   MISSED"
            d.text((x + 6, y0 + TILE_H + 4), line1, font=font(22, True), fill=(235, 235, 235))
            extra = []
            if bi and gt_ids:
                m = min(bi.get((g, f), 1.0) for g in gt_ids)
                if m < 0.95:
                    extra.append(f"glare m={m:.2f}")
            if captions:
                c = captions(tr.name, f)
                if c:
                    extra.append(c)
            if extra:
                d.text((x + 6, y0 + TILE_H + 31), "  ".join(extra), font=font(19), fill=(190, 190, 190))
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, f"{name}.png")
    sheet.save(p)
    print("->", p, sheet.size)
    return p


def mode_cap(tr, tid):
    def cap(_row, f):
        d = tr.diag.get(f, {}).get(tid)
        if not d:
            return ""
        s = d["mode"] if d["emit"] else "hidden"
        if d["tsu"] >= 1 and d.get("phi") is not None:
            s += f"  phi={d['phi']:.2f}"
        return s
    return cap


def box_cap(tr, tid):
    def cap(_row, f):
        r = [r for r in tr.mot.get(f, []) if r[0] == tid]
        return f"box {r[0][3]:.0f}x{r[0][4]:.0f}px" if r else "no box"
    return cap


def main():
    real, synth = os.path.join(ROOT, "datasets", "real"), os.path.join(ROOT, "datasets", "synth")

    # 1. gate fires correctly, frozen coast box drifts off a walking worker (Table III)
    s = "204_sequence_81q_complete"
    t = Track("PEG", PEG_COL, "eval_recovery", "peg_rcv", s, "eval_recovery__peg_rcv")
    filmstrip("01_gate_ok_box_drifts", s, synth, [336, 348, 358, 366, 376], [300], [t], {"PEG": [2]},
              captions=mode_cap(t, 2), burn_root=synth)

    # 2. coasting box collapses (area velocity not damped) (Table III)
    s = "320_sequence_116q_new"
    t = Track("PEG", PEG_COL, "eval_recovery", "peg_rcv", s)
    filmstrip("02_box_collapse", s, synth, [224, 236, 244, 250, 256], [1], [t], {"PEG": [1]},
              captions=box_cap(t, 1), burn_root=synth)

    # 3. gate emits a phantom on a lamp bloom (real)
    s = "136_sequence_2q_new"
    t = Track("PEG", PEG_COL, "eval", "peg", s, "eval__peg")
    filmstrip("03_gate_phantom_bloom", s, real, [494, 505, 520, 537, 552], [], [t], {"PEG": [3]},
              captions=mode_cap(t, 3), show_all_gt=True)

    # 4. gate miss: worker burnt but phi measured on a stale box (real)
    s = "136_sequence_2q_new"
    t = Track("PEG", PEG_COL, "eval", "peg", s, "eval__peg")
    filmstrip("04_gate_miss_stale_box", s, real, [120, 150, 168, 185, 200], [3], [t], {"PEG": [3]},
              captions=mode_cap(t, 3))

    # 5. PEG vs backbone: lost re-association (real 325_92q)
    s = "325_sequence_92q_new"
    tp = Track("PEG", PEG_COL, "eval", "peg", s, "eval__peg")
    tb = Track("Backbone", BB_COL, "eval", "backbone", s, "eval__backbone")
    filmstrip("05_peg_vs_backbone_reassoc", s, real, [300, 340, 380, 392, 396], [3], [tp, tb],
              {"PEG": [3, 7], "Backbone": [3]})

    # 6. partial box on an unusual pose (real)
    s = "316_sequence_112q_new"
    t = Track("PEG", PEG_COL, "eval", "peg", s, "eval__peg")
    filmstrip("06_partial_box_pose", s, real, [700, 762, 768, 774, 780], [1], [t], {"PEG": [2]})

    # 7. GT stops while the person is still there (real)
    s = "176_sequence_56q_new"
    t = Track("PEG", PEG_COL, "eval", "peg", s, "eval__peg")
    filmstrip("07_gt_truncated", s, real, [645, 652, 660, 670, 680], [], [t], {"PEG": [2]}, show_all_gt=True)

    # 8. Table III counts a worker that was never tracked before the burn (synth)
    s = "312_sequence_108q_new"
    t = Track("PEG", PEG_COL, "eval_recovery", "peg_rcv", s)
    filmstrip("08_never_tracked_before_burn", s, synth, [20, 40, 60, 80, 92], [861], [t], {"PEG": [1]},
              burn_root=synth)

    # single tiles for the "how tracking is scored" slides
    s = "204_sequence_81q_complete"
    t = Track("PEG", PEG_COL, "eval_recovery", "peg_rcv", s, "eval_recovery__peg_rcv")
    filmstrip("t_match", s, synth, [358], [300], [t], {"PEG": [2]}, burn_root=synth)
    filmstrip("t_nomatch", s, synth, [376], [300], [t], {"PEG": [2]}, burn_root=synth)
    s = "136_sequence_2q_new"
    t = Track("PEG", PEG_COL, "eval", "peg", s, "eval__peg")
    filmstrip("t_fn", s, real, [185], [3], [t], {"PEG": [3]})
    filmstrip("t_fp", s, real, [505], [], [t], {"PEG": [3]}, show_all_gt=True)
    s = "325_sequence_92q_new"
    t = Track("PEG", PEG_COL, "eval", "peg", s, "eval__peg")
    filmstrip("t_id_before", s, real, [300], [3], [t], {"PEG": [3]})
    filmstrip("t_id_after", s, real, [396], [3], [t], {"PEG": [7]})


if __name__ == "__main__":
    main()
