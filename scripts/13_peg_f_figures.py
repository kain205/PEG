"""Figures for the PEG-F deck (results/peg_f/PEG_F.pptx) -> results/peg_f/figures/*.png

    .venv/Scripts/python.exe scripts/13_peg_f_figures.py            # all
    .venv/Scripts/python.exe scripts/13_peg_f_figures.py perseq ablation combo damp swap

All numbers are read from results/peg_f/numbers.json (tracker-only replays, see results/peg_f/RESULTS.md) or from the
MOT outputs of the runs named in results/peg_f/run_matrix.sh. Also writes results/peg_f/figure_stats.json (numbers
computed here for the deck: M1-damp episode coverage, burn frames covered in total).
"""
import itertools
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
import numpy as np                                     # noqa: E402
from matplotlib import rcParams                        # noqa: E402
from matplotlib.patches import Rectangle               # noqa: E402
from PIL import Image, ImageDraw, ImageFont            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import (BURN_THR, burn_index, load_events, load_mot,  # noqa: E402
                                         match_frame)

PF = os.path.join(ROOT, "results", "peg_f")
OUT = os.path.join(PF, "figures")
N = json.load(open(os.path.join(PF, "numbers.json"), encoding="utf-8"))
V = N["variants"]

# ---- palette (validated with dataviz validate_palette.js, dark surface; deck-consistent) ----
BG, CARD, TEXT, MUTED, GRID = "#15171B", "#22252B", "#F2F2F2", "#A3A8B0", "#33373E"
C_PEG, C_PLUS, C_F, C_FA, C_SEL = "#3987E5", "#19A35F", "#9B6EE8", "#CF8000", "#1B9AA6"
GOOD, BAD, NEUT = "#19A35F", "#E66767", "#2B2F36"

rcParams.update({
    "font.family": "Arial", "font.size": 12, "text.color": TEXT, "axes.labelcolor": MUTED,
    "axes.edgecolor": GRID, "xtick.color": MUTED, "ytick.color": MUTED, "figure.facecolor": BG,
    "axes.facecolor": BG, "savefig.facecolor": BG, "axes.spines.top": False, "axes.spines.right": False,
    "hatch.linewidth": 1.6,
})


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, name)
    fig.savefig(p, dpi=200)
    plt.close(fig)
    print("->", p)


def blend(c1, c2, a):
    """colour c2 over c1 with alpha a (hex strings)"""
    f = lambda c: np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], float)  # noqa: E731
    r = f(c1) * (1 - a) + f(c2) * a
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in r)


def t1(v, k): return V[v]["table1"]["combined"][k]
def t2(v, k): return V[v]["table2"]["combined"][k]
def t3(v, k="Rcv@.5"): return V[v]["table3"]["all_burn"][k]


# ═══════════════ 1. per-sequence ΔHOTA (guard on = the friend's own setting) ═══════════════
def fig_perseq():
    pa, pb = N["table1_per_seq"]["peg_g"], N["table1_per_seq"]["F_g"]
    rows = sorted(((s.replace("_sequence_", "_").replace("_complete", "").replace("_new", ""), pb[s]["HOTA"] - pa[s]["HOTA"], pb[s]["IDSW"] - pa[s]["IDSW"], s)
                   for s in pa), key=lambda r: -r[1])
    fig, ax = plt.subplots(figsize=(7.6, 5.3))
    ys = np.arange(len(rows))[::-1]
    for y, (name, d, _, s) in zip(ys, rows):
        col = MUTED if abs(d) < 0.5 else (GOOD if d > 0 else BAD)
        ax.barh(y, d, height=0.7, color=col, zorder=3)
        ax.text(d + (0.5 if d >= 0 else -0.5), y, ("0.0" if round(d, 1) == 0 else f"{d:+.1f}".replace("-", "−")), va="center",
                ha="left" if d >= 0 else "right", fontsize=11.5, color=TEXT if abs(d) >= 0.5 else MUTED)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=12)
    ax.axvline(0, color=MUTED, lw=1, zorder=4)
    ax.set_xlim(-26, 33)
    ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_xlabel("ΔHOTA trên từng video (PEG-F − PEG, guard bật)", fontsize=12, labelpad=8)
    top, bot = rows[0], rows[-1]
    ax.text(-1.0, ys[0], f"{top[1]:+.1f}: 1 lần đổi ID được sửa", ha="right", va="center", fontsize=12.5, color=GOOD, fontweight="bold")
    ax.text(1.2, ys[-1], f"−{abs(bot[1]):.1f}: 1 lần đổi ID mới", ha="left", va="center", fontsize=12.5, color=BAD, fontweight="bold")
    fig.tight_layout()
    save(fig, "perseq_delta.png")


# ═══════════════ 2. single-add ablation grid ═══════════════
def fig_grid():
    cols = [("T1 HOTA", lambda v: t1(v, "HOTA"), 2, 1.0, +1), ("T1 IDF1", lambda v: t1(v, "IDF1"), 2, 3.0, +1),
            ("T1 IDSW", lambda v: t1(v, "IDSW"), 0, 15.0, -1), ("T2 MOTA", lambda v: t2(v, "MOTA"), 2, 3.0, +1),
            ("T3 Rcv@.5", lambda v: t3(v), 1, 10.0, +1)]
    rows = [("P+M1damp", "M1-damp", "hãm vận tốc khi 2 người gần", C_F), ("P+M1swap", "M1-swap", "thêm test đổi ID", C_F),
            ("P+M2", "M2", "Re-ID màu HSV", C_F), ("P+M3", "M3", "ngưỡng h động + TTL", C_F),
            ("P+M4", "M4", "pool track ngủ", C_F), ("P+M5", "M5", "neo vào đèn mũ", C_F),
            ("A", "PEG+ (A)", "khóa kích thước (của mình)", C_PLUS)]
    fig, ax = plt.subplots(figsize=(12.1, 5.2))
    ax.set_xlim(0, 12.1)
    ax.set_ylim(0, 8.55)
    ax.axis("off")
    ax.invert_yaxis()
    x0, cw, rh = 3.6, 1.7, 0.92
    ax.text(0.05, 0.62, "thêm vào PEG", fontsize=12, color=MUTED, va="center")
    for j, (cn, f, dec, sc, sg) in enumerate(cols):
        ax.text(x0 + j * cw + cw / 2, 0.40, cn, ha="center", va="center", fontsize=13.5, fontweight="bold")
        b = f("peg")
        ax.text(x0 + j * cw + cw / 2, 0.86, f"PEG = {b:.{dec}f}", ha="center", va="center", fontsize=10.5, color=MUTED)
    for i, (key, nm, sub, col) in enumerate(rows):
        y = 1.25 + i * rh + (0.25 if key == "A" else 0)
        ax.add_patch(Rectangle((0.0, y + 0.04), 0.09, rh - 0.12, color=col, lw=0))
        ax.text(0.25, y + rh * 0.36, nm, fontsize=13.5, fontweight="bold", va="center")
        ax.text(0.25, y + rh * 0.74, sub, fontsize=10.5, color=MUTED, va="center")
        for j, (cn, f, dec, sc, sg) in enumerate(cols):
            d = f(key) - f("peg")
            shown = round(d, dec)
            if shown == 0:
                fc = CARD
            else:
                good = (shown * sg) > 0
                fc = blend(CARD, GOOD if good else BAD, 0.25 + 0.65 * min(1.0, abs(d) / sc))
            ax.add_patch(Rectangle((x0 + j * cw + 0.04, y + 0.04), cw - 0.08, rh - 0.1, color=fc, lw=0))
            dtxt = (f"{shown:+.{dec}f}" if shown != 0 else f"{0:.{dec}f}").replace("-", "−")
            ax.text(x0 + j * cw + cw / 2, y + rh * 0.38, dtxt, ha="center", va="center", fontsize=16, fontweight="bold")
            ax.text(x0 + j * cw + cw / 2, y + rh * 0.76, f"{f(key):.{dec}f}", ha="center", va="center", fontsize=10, color="#D5D8DD")
    ax.text(x0, 8.45, "số to = thay đổi so với PEG · số nhỏ = giá trị mới · xanh = tốt hơn, đỏ = tệ hơn (IDSW: ít hơn là tốt) · xám = như cũ",
            fontsize=10.5, color=MUTED, va="center")
    fig.subplots_adjust(0.005, 0.01, 0.995, 0.995)
    save(fig, "ablation_grid.png")


# ═══════════════ 3. main combination ═══════════════
def fig_combo():
    series = [("PEG", "peg", C_PEG, None), ("PEG+", "A", C_PLUS, None), ("PEG-F", "F", C_F, None),
              ("PEG-F + PEG+", "FA", C_FA, None), ("PEG+ + M1-swap + M3 (chọn trên test)", "A+M1swap+M3", C_SEL, "///")]
    panels = [("T1 HOTA", lambda v: t1(v, "HOTA"), (66.5, 71.0), 2), ("T1 IDF1", lambda v: t1(v, "IDF1"), (80.0, 88.0), 2),
              ("T2 MOTA", lambda v: t2(v, "MOTA"), (69.0, 75.0), 2), ("T3 Rcv@.5", lambda v: t3(v), (60.0, 86.0), 1)]
    fig, axs = plt.subplots(1, 4, figsize=(12.1, 4.5))
    for ax, (pn, f, (lo, hi), dec) in zip(axs, panels):
        for k, (lab, key, col, hatch) in enumerate(series):
            v = f(key)
            ax.bar(k, v - lo, bottom=lo, width=0.78, color=col if not hatch else BG, edgecolor=col, lw=1.8 if hatch else 0,
                   hatch=hatch, zorder=3)
            ax.text(k, v + (hi - lo) * 0.015, f"{v:.{dec}f}", ha="center", va="bottom", fontsize=10.5, fontweight="bold")
        ax.set_ylim(lo, hi + (hi - lo) * 0.09)
        ax.set_xlim(-0.6, len(series) - 0.4)
        ax.set_xticks([])
        ax.set_title(pn, fontsize=14, fontweight="bold", pad=8)
        ax.yaxis.grid(True, color=GRID, lw=0.8, zorder=0)
        ax.set_axisbelow(True)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color(GRID)
        ax.tick_params(axis="y", length=0, labelsize=10)
        ax.set_xlabel("trục y cắt (không từ 0)", fontsize=9, color=MUTED, labelpad=6)
    handles = [Rectangle((0, 0), 1, 1, facecolor=(c if not h else BG), edgecolor=c, lw=1.6, hatch=h) for _, _, c, h in series]
    fig.legend(handles, [s[0] for s in series], loc="upper center", ncol=5, frameon=False, fontsize=11, labelcolor=TEXT,
               handlelength=1.4, columnspacing=1.6, bbox_to_anchor=(0.5, 1.0))
    fig.subplots_adjust(left=0.04, right=0.995, top=0.80, bottom=0.10, wspace=0.28)
    save(fig, "main_combo.png")


# ═══════════════ image figures ═══════════════
def fnt(sz, bold=False):
    return ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf", sz)


def hx(c): return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def xyxy(r): return (r[1], r[2], r[1] + r[3], r[2] + r[4])


def iou(a, b):
    ix, iy = max(0, min(a[2], b[2]) - max(a[0], b[0])), max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9)


def frame_path(seq_dir, f):
    return os.path.join(seq_dir, "images", f"frame_{f - 1:06d}.jpg")      # MOT frames are 1-based


def box(d, b, col, w=4, halo=True):
    if halo:
        d.rectangle(b, outline=(0, 0, 0), width=w + 3)
    d.rectangle(b, outline=col, width=w)


def tag(d, xy, text, col, sz=22, anchor="la"):
    f = fnt(sz, True)
    bb = d.textbbox(xy, text, font=f, anchor=anchor)
    d.rectangle((bb[0] - 4, bb[1] - 2, bb[2] + 4, bb[3] + 2), fill=(0, 0, 0))
    d.text(xy, text, font=f, fill=col, anchor=anchor)


def sheet(rows, frames, crop, seq_dir, draw_fn, caps_fn, legend, tile_h=370, lab_w=250, out="x.png"):
    """rows: [(name, colour)]; draw_fn(d, ri, f, tf)->None draws on a cropped+scaled tile (tf maps xyxy -> tile px);
    caps_fn(ri, f) -> (line1, line2)."""
    c0 = crop(frames[0]) if callable(crop) else crop
    s = tile_h / (c0[3] - c0[1])
    tw = int((c0[2] - c0[0]) * s)
    gap, cap_h, leg_h = 8, 84, 60
    W = lab_w + len(frames) * (tw + gap) - gap
    H = leg_h + len(rows) * (tile_h + cap_h + gap) - gap
    im = Image.new("RGB", (W, H), hx(BG))
    d = ImageDraw.Draw(im)
    x = 12
    for text, col in legend:
        d.rectangle((x, 14, x + 38, 44), outline=col, width=5)
        d.text((x + 50, 29), text, font=fnt(30), fill=hx(TEXT), anchor="lm")
        x += 50 + int(d.textlength(text, font=fnt(30))) + 50
    for ri, (name, col) in enumerate(rows):
        y0 = leg_h + ri * (tile_h + cap_h + gap)
        for k, line in enumerate(name.split("\n")):
            d.text((12, y0 + tile_h // 2 - 24 + k * 46 - (len(name.split("\n")) - 1) * 23), line, font=fnt(40, True), fill=col)
        for fi, f in enumerate(frames):
            cx1, cy1, cx2, cy2 = crop(f) if callable(crop) else crop
            tile = Image.open(frame_path(seq_dir, f)).convert("RGB").crop((cx1, cy1, cx2, cy2)).resize((tw, tile_h), Image.LANCZOS)
            td = ImageDraw.Draw(tile)
            def tf(b):
                return ((b[0] - cx1) * s, (b[1] - cy1) * s, (b[2] - cx1) * s, (b[3] - cy1) * s)
            draw_fn(td, ri, f, tf)
            xx = lab_w + fi * (tw + gap)
            im.paste(tile, (xx, y0))
            l1, l2 = caps_fn(ri, f)
            for txt_, bold, base_sz, yy, col_ in ((l1, True, 30, 6, hx(TEXT)), (l2, False, 26, 44, hx(MUTED))):
                sz = base_sz
                while sz > 14 and d.textlength(txt_, font=fnt(sz, bold)) > tw - 8:
                    sz -= 1
                d.text((xx + 6, y0 + tile_h + yy), txt_, font=fnt(sz, bold), fill=col_)
    p = os.path.join(OUT, out)
    os.makedirs(OUT, exist_ok=True)
    im.save(p)
    print("->", p, im.size)


# ═══════════════ 4. M1-damp episode (Table III synth twin) ═══════════════
SYNTH = os.path.join(ROOT, "datasets", "synth")
RCV = os.path.join(ROOT, "results", "eval_recovery", "trackers")


def episode_stats(peg, other):
    """covered burn frames (IoU>=.5 match) per episode and in total, PEG vs `other`, over every Table III seq."""
    tot = {"peg": 0, "other": 0, "burn": 0}
    per = {}
    for fn in sorted(os.listdir(os.path.join(RCV, peg, "data"))):
        seq = fn[:-4]
        gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
        bi = burn_index(seq, SYNTH)
        runs = {"peg": load_mot(os.path.join(RCV, peg, "data", fn)), "other": load_mot(os.path.join(RCV, other, "data", fn))}
        for tid, s0, dur in load_events(seq, SYNTH):
            ep = [f for f in range(s0 + 1, s0 + dur + 1)
                  if any(r[0] == tid for r in gt.get(f, [])) and bi.get((tid, f), 1.0) < BURN_THR]
            if not ep:
                continue
            c = {k: sum(1 for f in ep if match_frame(gt.get(f, []), r.get(f, []), 0.5).get(tid)) for k, r in runs.items()}
            per[(seq, tid)] = (len(ep), c["peg"], c["other"])
            tot["burn"] += len(ep)
            tot["peg"] += c["peg"]
            tot["other"] += c["other"]
    return tot, per


def fig_damp():
    seq, gid = "183_sequence_62q_new", 240
    peg_run, dmp_run = "pf_peg_rcv", "pf_P+M1damp_rcv"
    tot, per = episode_stats(peg_run, dmp_run)
    n_ep, cov_peg, cov_dmp = per[(seq, gid)]
    stats = {"seq": seq, "gt_id": gid, "episode_burn_frames": n_ep, "episode_cov_peg": cov_peg, "episode_cov_damp": cov_dmp,
             "total_burn_frames": tot["burn"], "total_cov_peg": tot["peg"], "total_cov_damp": tot["other"]}
    sp = os.path.join(PF, "figure_stats.json")
    old = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    old["damp"] = stats
    json.dump(old, open(sp, "w", encoding="utf-8"), indent=1)
    print("damp stats", stats)

    sdir = os.path.join(SYNTH, seq)
    gt = load_mot(os.path.join(sdir, "mot", "gt", "gt.txt"))
    bi = burn_index(seq, SYNTH)
    runs = [load_mot(os.path.join(RCV, r, "data", f"{seq}.txt")) for r in (peg_run, dmp_run)]
    frames = [448, 456, 464, 472, 482]
    stats["frames"] = frames
    # track id that follows GT before the burn (frame 440)
    fid = []
    for r in runs:
        g = [x for x in gt[440] if x[0] == gid][0]
        fid.append(max(r[440], key=lambda t: iou(xyxy(g), xyxy(t)))[0])
    gtb = lambda f: xyxy([x for x in gt[f] if x[0] == gid][0])  # noqa: E731
    for k, r in (("peg", runs[0]), ("damp", runs[1])):
        tid = fid[0 if k == "peg" else 1]
        for lab, f in (("first", frames[0]), ("last", frames[-1])):
            stats[f"iou_{k}_{lab}"] = round(iou(gtb(f), xyxy([x for x in r[f] if x[0] == tid][0])), 2)
    old["damp"] = stats
    json.dump(old, open(sp, "w", encoding="utf-8"), indent=1)
    cols = [hx(C_PEG), hx("#E66767")]
    GTC = hx("#3DDC84")
    cx, cy, w, h = 1215, 885, 300, 380
    crop = (cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2)

    def draw(td, ri, f, tf):
        g = [x for x in gt[f] if x[0] == gid][0]
        for t in runs[ri].get(f, []):
            if t[0] == fid[ri]:
                box(td, tf(xyxy(t)), cols[ri], 5)
        box(td, tf(xyxy(g)), GTC, 3, halo=True)

    def caps(ri, f):
        g = [x for x in gt[f] if x[0] == gid][0]
        t = [x for x in runs[ri].get(f, []) if x[0] == fid[ri]]
        v = iou(xyxy(g), xyxy(t[0])) if t else 0.0
        m = bi.get((gid, f), 1.0)
        return f"frame {f}   IoU {v:.2f}", ("đang bị chói" if m < 0.5 else "chói yếu dần")
    sheet([("PEG", cols[0]), ("PEG +\nM1-damp", cols[1])], frames, crop, sdir, draw, caps,
          [("Người thật (GT)", GTC), ("PEG", cols[0]), ("PEG + M1-damp", cols[1])], tile_h=360, out="damp_episode.png")


# ═══════════════ 5. 129: ID swap ═══════════════
def fig_swap():
    seq = "129_sequence_13q_complete"
    sdir = os.path.join(ROOT, "datasets", "real", seq)
    gt = load_mot(os.path.join(sdir, "mot", "gt", "gt.txt"))
    R = os.path.join(ROOT, "results", "eval", "trackers")
    runs = [load_mot(os.path.join(R, f"pf_{r}", "data", f"{seq}.txt")) for r in ("peg", "F")]
    frames = [330, 338, 342, 420, 560]
    sp = os.path.join(PF, "figure_stats.json")
    old = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
    old["swap"] = {"seq": seq, "frames": frames}
    json.dump(old, open(sp, "w", encoding="utf-8"), indent=1)
    idcol = {1: hx("#F2A900"), 2: hx("#34C6E8")}
    GTC = (235, 235, 235)
    names = {12: "A", 1034: "B"}

    def crop(f):
        g = gt[f]
        cx = sum(x[1] + x[3] / 2 for x in g) / len(g)
        cy = sum(x[2] + x[4] / 2 for x in g) / len(g)
        return (int(cx - 90), int(cy - 90), int(cx + 90), int(cy + 90))

    def who(ri, f):
        gs, ts = gt.get(f, []), runs[ri].get(f, [])
        best = (-1, ())
        for perm in itertools.permutations(range(len(ts)), min(len(gs), len(ts))):
            sc = sum(iou(xyxy(gs[i]), xyxy(ts[p])) for i, p in enumerate(perm))
            if sc > best[0]:
                best = (sc, perm)
        out = {g[0]: None for g in gs}
        for i, p in enumerate(best[1]):
            if iou(xyxy(gs[i]), xyxy(ts[p])) >= 0.3:
                out[gs[i][0]] = ts[p][0]
        return out

    def draw(td, ri, f, tf):
        for g in gt.get(f, []):
            b = tf(xyxy(g))
            td.rectangle(b, outline=GTC, width=2)
            td.text((b[0] + 3, b[3] - 2), names.get(g[0], "?"), font=fnt(30, True), fill=GTC, anchor="lb")
        for t in runs[ri].get(f, []):
            b = tf(xyxy(t))
            box(td, b, idcol.get(t[0], (255, 255, 255)), 4, halo=False)
            if t[0] == 1:
                tag(td, (b[2] - 2, b[1] - 4), f"id{t[0]}", idcol[t[0]], 26, "rb")
            else:
                tag(td, (b[2] - 2, b[3] + 4), f"id{t[0]}", idcol[t[0]], 26, "ra")

    def caps(ri, f):
        w = who(ri, f)
        fmt = lambda v: f"id{v}" if v else "—"  # noqa: E731
        return f"frame {f}", f"A = {fmt(w.get(12))}   B = {fmt(w.get(1034))}"
    sheet([("PEG", hx(C_PEG)), ("PEG-F", hx(C_F))], frames, crop, sdir, draw, caps,
          [("Người thật A, B (GT)", GTC), ("id1", idcol[1]), ("id2", idcol[2])], tile_h=360, out="swap_129.png")


ALL = {"perseq": fig_perseq, "ablation": fig_grid, "combo": fig_combo, "damp": fig_damp, "swap": fig_swap}

if __name__ == "__main__":
    which = sys.argv[1:] or list(ALL)
    for k in which:
        ALL[k]()
