"""PEG-O figures for the slides (reuses the filmstrip helper of scripts/09, as scripts/11 does). No tracker runs.

  135_19q_strip.png  test 135_19q g53 409-451 + one pre-burn frame: PEG+ / PEG-O reported (tau .08 gamma 4) / PEG-O smoke (tau .06 gamma 1)
  187_66q_strip.png  val 187_66q g247 141-173 (the failure): PEG+ / PEG-O (O[8])
  scoremap.png       what the estimator sees: sat mask + disc-filter score map over the search window (kappa 2), peak, +-Delta probes,
                     predicted (= PEG-O output) box, GT box; top: 135 f411; bottom: 187 f146 with the peak trail (numbered, f142-150) vs GT centres
GT box = magenta (a GT box nobody matches is yellow). Output: results/peg_o/figures/
    .venv/Scripts/python.exe scripts/20_peg_o_figures.py
"""
import glob
import importlib.util
import os
import sys
from collections import Counter

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import load_mot, match_frame  # noqa: E402
from glaremot.tracking.beacon_tracker import ODO_KAPPA, ODO_RHO_MAX, ODO_RHO_MIN, odo_disc_kernel, odo_measure  # noqa: E402

_spec = importlib.util.spec_from_file_location("figs09", os.path.join(ROOT, "scripts", "09_presentation_figures.py"))
F9 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F9)
OUT = os.path.join(ROOT, "results", "peg_o", "figures")
SYNTH = os.path.join(ROOT, "datasets", "synth")
RCV = os.path.join(ROOT, "results", "eval_recovery", "trackers")
F9.OUT = OUT
F9.GT_COL = (255, 0, 255)
F9.MISS_COL = (255, 255, 0)
PLUS_COL, O_COL, S_COL = (25, 163, 95), (240, 120, 40), (80, 190, 240)
BG = "#15171B"


def focus_ids(seq, run, tid, frames):
    gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
    trk = load_mot(os.path.join(RCV, run, "data", f"{seq}.txt"))
    c = Counter()
    for f in frames:
        m = match_frame(gt.get(f, []), trk.get(f, []), 0.3).get(tid)
        if m:
            c[m[0]] += 1
    return [i for i, _ in c.most_common(2)]


def strip(name, seq, tid, frames, runs):
    """runs: [(label, color, tracker_name)]"""
    win = list(range(max(1, frames[0] - 15), frames[-1] + 1))
    rows = [F9.Track(lab, col, "eval_recovery", trk, seq) for lab, col, trk in runs]
    focus = {lab: focus_ids(seq, trk, tid, win) for lab, _, trk in runs}
    return F9.filmstrip(name, seq, SYNTH, frames, [tid], rows, focus, burn_root=SYNTH)


def _gt_box(seq, tid, f):
    gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
    r = [r for r in gt.get(f, []) if r[0] == tid]
    return r[0][1:5] if r else None


def _trk_box(seq, run, tid, f, win):
    ids = focus_ids(seq, run, tid, win)
    trk = load_mot(os.path.join(RCV, run, "data", f"{seq}.txt"))
    r = [r for r in trk.get(f, []) if r[0] in ids[:1]]
    return r[0][1:5] if r else None


def _peak_at(seq, tid, f, run, win, sat, W, H):
    """odo_measure on frame f with the window centred on the PEG-O tracker box of that frame. Returns (b_px, k, rho, box)."""
    S = 512
    sx, sy = S / W, S / H
    m = np.unpackbits(sat[f - 1], count=S * S).reshape(S, S).astype(np.uint8)
    x, y, w, h = _trk_box(seq, run, tid, f, win)
    c = np.array([x + w / 2, y + h / 2])
    _, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
    b, rho, pk, kx, ky = odo_measure(lab, st, c, w, h, sx, sy, S)
    return m, lab, c, (x, y, w, h), b, rho, pk, kx, ky


def scoremap_panel(axs, seq, tid, f, run, burn_win, title, trail=None):
    """axs = (sat panel, score panel); both square crops of the same grid-px side. trail = frames whose peak is drawn as a numbered
    dot trail (with the GT centres) on the sat panel of frame f."""
    import matplotlib.patches as mp
    S = 512
    sat = np.load(os.path.join(ROOT, "results", "percep_cache", "synth", f"{seq}.npz"))["sat"]
    H, W = cv2.imread(glob.glob(os.path.join(SYNTH, seq, "images", "*.jpg"))[0]).shape[:2]
    sx, sy = S / W, S / H
    m, lab, c, (x, y, w, h), b, rho, pk, kx, ky = _peak_at(seq, tid, f, run, burn_win, sat, W, H)
    gx, gy, gw, gh = _gt_box(seq, tid, f)
    k = lab[int(np.clip(c[1] * sy, 0, S - 1)), int(np.clip(c[0] * sx, 0, S - 1))]
    if k == 0:
        bx = lab[int((c[1] - h / 2) * sy):int((c[1] + h / 2) * sy), int((c[0] - w / 2) * sx):int((c[0] + w / 2) * sx)]
        ids, cnt = np.unique(bx[bx > 0], return_counts=True)
        k = ids[np.argmax(cnt)]
    sc = cv2.filter2D((lab == k).astype(np.float32), -1, odo_disc_kernel(rho), borderType=cv2.BORDER_CONSTANT)
    x0, y0 = max(0, int((c[0] - ODO_KAPPA * w / 2) * sx)), max(0, int((c[1] - ODO_KAPPA * h / 2) * sy))
    x1, y1 = min(S, int((c[0] + ODO_KAPPA * w / 2) * sx)), min(S, int((c[1] + ODO_KAPPA * h / 2) * sy))
    px, py = int(round(b[0] * sx)), int(round(b[1] * sy))
    assert abs(sc[py, px] - pk) < 1e-5, (sc[py, px], pk)
    dl = max(2, int(rho / 4))
    # square crop: side = max(window w, h) + margin, centred on the window, clipped to the grid
    side = int(max(x1 - x0, y1 - y0) * 1.35)
    ccx, ccy = (x0 + x1) / 2, (y0 + y1) / 2
    X0 = int(np.clip(ccx - side / 2, 0, S - side)); Y0 = int(np.clip(ccy - side / 2, 0, S - side)); X1, Y1 = X0 + side, Y0 + side
    pts = []
    if trail:
        for ti, tf in enumerate(trail):
            _, _, tc, _, tb, trho, _, tkx, tky = _peak_at(seq, tid, tf, run, burn_win, sat, W, H)
            g = _gt_box(seq, tid, tf)
            pts.append((tf, tb[0] * sx, tb[1] * sy, (g[0] + g[2] / 2) * sx, (g[1] + g[3] / 2) * sy, min(tkx, tky)))
    for ai, ax in enumerate(axs):
        if ai == 0:
            ax.imshow(m[Y0:Y1, X0:X1], cmap="gray", vmin=0, vmax=1, extent=(X0, X1, Y1, Y0), interpolation="nearest")
            ax.set_title(f"sat mask f{f} (white = saturated)", color="w", fontsize=10)
        else:
            ax.imshow(sc[Y0:Y1, X0:X1], cmap="magma", extent=(X0, X1, Y1, Y0), interpolation="nearest")
            ax.set_title(f"disc-filter score f{f}  (rho = {rho:.0f} px)", color="w", fontsize=10)
        ax.add_patch(mp.Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False, ec="#8888ff", lw=1.2, ls="--"))
        ax.add_patch(mp.Rectangle((x * sx, y * sy), w * sx, h * sy, fill=False, ec="#2de0e0", lw=2))
        ax.add_patch(mp.Rectangle((gx * sx, gy * sy), gw * sx, gh * sy, fill=False, ec="#ff00ff", lw=2))
        if ai == 1:
            ax.plot([px], [py], "+", color="#7CFC00", ms=16, mew=2.5)
            for dx, dy in ((dl, 0), (-dl, 0), (0, dl), (0, -dl)):
                ax.plot([px + dx], [py + dy], "o", color="#7CFC00", ms=5, mfc="none", mew=1.5)
        if ai == 0 and pts:
            ax.plot([p_[1] for p_ in pts], [p_[2] for p_ in pts], "-", color="#7CFC00", lw=0.8, alpha=0.8)
            for p_ in pts:
                ax.plot([p_[3]], [p_[4]], ".", color="#ff00ff", ms=4)
                ax.plot([p_[1]], [p_[2]], "o", color="#7CFC00", ms=4, mfc="#7CFC00" if p_[5] >= 0.06 else "none", mew=1)
            # zoomed inset (numbered peaks vs GT centres)
            ia = ax.inset_axes([0.55, 0.07, 0.42, 0.42]); ia.set_facecolor("#101216")
            xs = [p_[1] for p_ in pts] + [p_[3] for p_ in pts]; ys = [p_[2] for p_ in pts] + [p_[4] for p_ in pts]
            padx, pady = 3, 3
            ia.set_xlim(min(xs) - padx, max(xs) + padx); ia.set_ylim(max(ys) + pady, min(ys) - pady)
            ia.plot([p_[1] for p_ in pts], [p_[2] for p_ in pts], "-", color="#7CFC00", lw=0.8, alpha=0.8)
            for n, p_ in enumerate(pts, 1):
                ia.plot([p_[3]], [p_[4]], "o", color="#ff00ff", ms=4)
                big = p_[5] >= 0.06
                ia.plot([p_[1]], [p_[2]], "o", color="#7CFC00", ms=9, mfc="#7CFC00" if big else "none", mew=1.4)
                ia.text(p_[1], p_[2], str(n), color="k" if big else "w", fontsize=6.5, ha="center", va="center", fontweight="bold")
            ia.tick_params(colors="#aaaaaa", labelsize=6)
            for sp in ia.spines.values():
                sp.set_color("#7CFC00")
        ax.set_xlim(X0, X1); ax.set_ylim(Y1, Y0); ax.set_aspect("equal")
        ax.set_xlabel("sat grid px (512²)", color="#aaaaaa", fontsize=8); ax.set_ylabel("sat grid px (512²)", color="#aaaaaa", fontsize=8)
        ax.set_facecolor(BG); ax.tick_params(colors="#aaaaaa", labelsize=7)
        for sp in ax.spines.values():
            sp.set_color("#555555")
    txt = f"{title}\nf{f}  k = {min(kx, ky):.3f} (kx {kx:.3f}, ky {ky:.3f})\npeak shift vs box centre: ({b[0] - c[0]:+.0f}, {b[1] - c[1]:+.0f}) px"
    if pts:
        txt += f"\nzoom inset: peaks 1..{len(trail)} = f{trail[0]}..f{trail[-1]} (filled: k >= .06) vs GT centre (magenta)"
    axs[0].text(0.01, 0.99, txt, transform=axs[0].transAxes, va="top", ha="left", color="w", fontsize=7.5, bbox=dict(fc=BG, ec="none", alpha=0.8))
    return min(kx, ky), rho


def scoremap():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig, axs = plt.subplots(2, 2, figsize=(11, 10.5), facecolor=BG)
    cases = [("135_sequence_19q_new", 53, 411, "pego_rcv", list(range(394, 452)), "test 135_19q g53 (worker walks 108 px)", None),
             ("187_sequence_66q_new", 247, 146, "v_pego_rcv", list(range(126, 174)), "val 187_66q g247 (worker ~still, burn ramping up)", list(range(142, 151)))]
    info = []
    for ri, (seq, tid, f, run, win, title, trail) in enumerate(cases):
        info.append((seq, f) + scoremap_panel(axs[ri], seq, tid, f, run, win, title, trail))
    leg = [Line2D([0], [0], color="#2de0e0", lw=2, label="predicted box (PEG-O output at this frame)"),
           Line2D([0], [0], color="#ff00ff", lw=2, label="GT box / GT centre (dots)"), Line2D([0], [0], color="#8888ff", lw=1.2, ls="--", label="search window (kappa = 2)"),
           Line2D([0], [0], marker="+", color="#7CFC00", lw=0, ms=12, mew=2, label="matched-filter peak"),
           Line2D([0], [0], marker="o", color="#7CFC00", lw=0, mfc="none", label="+-Delta probes / numbered peak trail")]
    fig.legend(handles=leg, loc="lower center", ncol=3, facecolor=BG, edgecolor="#555555", labelcolor="w", fontsize=9)
    fig.subplots_adjust(left=0.07, right=0.98, top=0.95, bottom=0.09, hspace=0.22, wspace=0.18)
    p = os.path.join(OUT, "scoremap.png")
    fig.savefig(p, dpi=130, facecolor=BG)
    print("->", p, info)


def main():
    os.makedirs(OUT, exist_ok=True)
    strip("135_19q_strip", "135_sequence_19q_new", 53, [401, 409, 424, 438, 451],
          [("PEG+", PLUS_COL, "pegplus_A_rcv"), ("PEG-O\nt.08 g4", O_COL, "pego_rcv"), ("PEG-O\nt.06 g1", S_COL, "smoke_pego2_135")])
    strip("187_66q_strip", "187_sequence_66q_new", 247, [133, 141, 152, 163, 173],
          [("PEG+", PLUS_COL, "v_A_rcv"), ("PEG-O\nt.08 g4", O_COL, "v_pego_rcv")])
    scoremap()


if __name__ == "__main__":
    main()
