"""Explanatory figures for the Thach-v2 deck (M6 tone map, M1 cone, M3 dynamic h). CPU only."""
import os, sys, json, glob, time
os.environ["CUDA_VISIBLE_DEVICES"] = ""
sys.path.insert(0, r"D:/PROJECT/PEG/dataset/thach_v2/PEG-main")   # read-only import of friend's module
import numpy as np
import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, Rectangle, Patch
from matplotlib.lines import Line2D
from multiprocessing import Pool

cv2.setNumThreads(1)
ROOT = r"D:/PROJECT/PEG/datasets/real"
SPLITS = r"D:/PROJECT/PEG/glaremot/data/splits.json"
OUT = r"D:/PROJECT/PEG/results/thach_v2/figures"
STATS = r"D:/PROJECT/PEG/results/thach_v2/figure_stats.json"
# chosen M6 frame (found by scanning every 10th frame of the 20 test seqs for a high saturated
# fraction + a GT box inside/next to the halo; picked visually among the top candidates).
SEQ, IDX, TID = "320_sequence_116q_new", 2070, 5     # IDX = jpg index; MOT gt frame = IDX + 1
CROP = (940, 350, 1360, 770)                          # x0,y0,x1,y1 in square (1536) input coords

BG, FG, MUTED = "#15171B", "#F2F2F2", "#A3A8B0"
AMBER, BLUE, GREEN, PURPLE, RED = "#F2A900", "#3987E5", "#19A35F", "#9B6EE8", "#E66767"
plt.rcParams.update({
    "font.family": ["Arial", "DejaVu Sans"], "font.size": 16,
    "figure.facecolor": BG, "axes.facecolor": BG, "savefig.facecolor": BG,
    "text.color": FG, "axes.labelcolor": FG, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": MUTED, "legend.facecolor": BG, "legend.edgecolor": MUTED,
})


def square_sat(path):
    """Replicates Perception.__call__: square input sq (S=1536) and 512x512 saturation map."""
    from glaremot.tracking import tracker as T
    im = cv2.imread(path)
    S = 1536
    sq = im if im.shape[:2] == (S, S) else cv2.resize(im, (S, S), interpolation=cv2.INTER_AREA)
    small = cv2.resize(sq, (T.PHOTO_S, T.PHOTO_S), interpolation=cv2.INTER_AREA)
    return sq, T.fast_saturation_map(small)


def seq_sat_means(seq):
    d = os.path.join(ROOT, seq)
    return [float(square_sat(f)[1].mean()) for f in sorted(glob.glob(d + "/images/*.jpg"))]


def fig_m6():
    from glaremot.tracking import tracker as T
    path = f"{ROOT}/{SEQ}/images/frame_{IDX:06d}.jpg"
    sq, sat = square_sat(path)
    out = T.local_tone_map(sq, sat)
    gt = np.loadtxt(f"{ROOT}/{SEQ}/mot/gt/gt.txt", delimiter=",", ndmin=2)
    g = gt[(gt[:, 0] == IDX + 1) & (gt[:, 1] == TID)][0]
    bx, by, bw, bh = g[2:6]

    ch = np.any(out != sq, axis=2)
    ya = cv2.cvtColor(sq, cv2.COLOR_BGR2GRAY).astype(np.float32)
    yb = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY).astype(np.float32)
    dy = np.abs(yb - ya)
    st = dict(changed_frac=float(ch.mean()), max=float(dy[ch].max()), mean=float(dy[ch].mean()),
              sat_frac=float(sat.mean()))
    print(f"M6 frame: {SEQ} jpg idx {IDX} (gt frame {IDX+1}); sat.mean={st['sat_frac']:.5f}")
    print(f"  pixels changed (full frame): {100*st['changed_frac']:.2f}%")
    print(f"  luminance change inside halo (changed px): max={st['max']:.1f}  mean={st['mean']:.2f}  (0-255)")

    x0, y0, x1, y1 = CROP
    sl = (slice(y0, y1), slice(x0, x1))
    rgb = lambda a: cv2.cvtColor(a[sl], cv2.COLOR_BGR2RGB)
    d = dy[sl].copy()
    vmax = max(1.0, float(np.percentile(dy[ch], 99.5)))
    cm = plt.get_cmap("magma")
    heat = cm(np.clip(d / vmax, 0, 1))[..., :3]
    heat[~ch[sl]] = 0.0

    fig, axs = plt.subplots(1, 3, figsize=(17, 6.4), dpi=110)
    titles = ["Ảnh gốc", "Sau tone-mapping (M6)", "Chỗ bị đổi"]
    imgs = [rgb(sq), rgb(out), heat]
    for k, (ax, t, im) in enumerate(zip(axs, titles, imgs)):
        ax.imshow(im)
        ax.set_xticks([]); ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(t, color=FG, fontsize=18, pad=10)
        if k < 2:
            ax.add_patch(Rectangle((bx - x0, by - y0), bw, bh, fill=False, ec=AMBER, lw=2.5))
    sm = matplotlib.cm.ScalarMappable(norm=matplotlib.colors.Normalize(0, vmax), cmap=cm)
    fig.subplots_adjust(left=0.005, right=0.925, top=0.9, bottom=0.1, wspace=0.04)
    pos = axs[2].get_position()
    cax = fig.add_axes([0.937, pos.y0 + 0.02, 0.01, pos.height - 0.04])
    cb = fig.colorbar(sm, cax=cax)
    cb.set_label("Δ độ sáng (thang 0–255)", color=FG, fontsize=14)
    cb.ax.tick_params(colors=MUTED, labelsize=13)
    cb.outline.set_edgecolor(MUTED)
    fig.text(0.5, 0.035, f"{SEQ}  ·  frame {IDX}  ·  khung vàng = box GT của người", ha="center",
             color=MUTED, fontsize=14)
    fig.savefig(f"{OUT}/m6_tonemap.png")
    plt.close(fig)
    return st


def fig_m1():
    h = 1.0
    v = 0.15 * h                      # schematic velocity (h per frame)
    base, q = 0.1 * h, 0.03 * h
    sig = lambda n: np.sqrt(base ** 2 + n * q ** 2)
    rad = lambda n: np.sqrt(9.21) * sig(n)   # chi2(2) 99% gate radius, as in the code (CONE_CHI2)
    fig, ax = plt.subplots(figsize=(16, 6), dpi=110)
    ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Rectangle((-0.2, -0.5), 0.4, 1.0, fill=False, ec=FG, lw=2.5))
    ax.plot(0, 0, "o", color=FG, ms=11, zorder=5)
    ax.annotate("", xy=(3.45, 0), xytext=(0.12, 0),
                arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=2.5, mutation_scale=22))
    for n in [2, 5, 10, 20]:
        cx = n * v
        r = rad(n)
        ax.add_patch(Ellipse((cx, 0), 2 * r, 2 * r, fill=True, fc=GREEN, alpha=0.18, ec="none"))
        ax.add_patch(Ellipse((cx, 0), 2 * r, 2 * r, fill=False, ec=GREEN, lw=2.2))
        ax.plot(cx, 0, "o", color=BLUE, ms=9, zorder=5)
        ax.text(cx, -0.62, f"gap = {n}", ha="center", va="top", color=FG, fontsize=16)
    r_st = rad(10)
    ax.add_patch(Ellipse((0, 0), 2 * r_st, 2 * r_st, fill=False, ec=PURPLE, lw=2.4, ls="--"))
    ax.plot(10 * v + 0.10, 0.12, "o", color=GREEN, ms=14, mec=FG, zorder=6)
    ax.annotate("detection: khớp lại ID cũ", xy=(10 * v + 0.10, 0.12), xytext=(1.05, 0.92),
                color=GREEN, fontsize=16, ha="center",
                arrowprops=dict(arrowstyle="-", color=GREEN, lw=1.6))
    ax.plot(2.35, -0.85, "x", color=RED, ms=16, mew=4, zorder=6)
    ax.text(2.35, -1.0, "ngoài vùng: không khớp", color=RED, fontsize=16, ha="center", va="top")
    hs = [Line2D([0], [0], marker="o", color="none", mfc=FG, ms=11),
          Line2D([0], [0], marker="o", color=BLUE, mfc=BLUE, ms=9, lw=2.5),
          Line2D([0], [0], color=PURPLE, lw=2.4, ls="--"),
          Patch(fc=GREEN, ec=GREEN, alpha=0.5)]
    ax.legend(hs, ["vị trí thấy lần cuối", "dự đoán vận tốc không đổi", "giả thuyết 'đứng lại'",
                   "vùng chấp nhận (99%)"], loc="upper right", fontsize=15, frameon=True,
              bbox_to_anchor=(1.0, 1.0))
    ax.set_xlim(-0.6, 3.7); ax.set_ylim(-1.35, 1.15)
    fig.tight_layout()
    fig.savefig(f"{OUT}/m1_cone.png")
    plt.close(fig)


def fig_m3():
    fig, axs = plt.subplots(1, 2, figsize=(16, 6), dpi=110)
    ax = axs[0]
    gap = np.arange(0, 21)
    eff = np.where(gap <= 3, 0.40, np.minimum(0.65, 0.40 * (1 + 0.06 * (gap - 3))))
    ax.plot(gap, eff, "-o", color=AMBER, lw=3, ms=7)
    ax.axhline(0.40, color=MUTED, ls="--", lw=2)
    ax.text(20, 0.385, "PEG gốc", color=MUTED, fontsize=15, ha="right", va="top")
    ax.set_xlabel("số frame mất detection", fontsize=16)
    ax.set_ylabel("ngưỡng h", fontsize=16)
    ax.set_ylim(0.3, 0.7); ax.set_xlim(-0.5, 20.5)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax = axs[1]
    phi = np.linspace(0, 1, 1001)
    effh = 0.40
    ttl = np.maximum(1, np.round(5 * np.clip(phi / max(0.5, effh), 0.4, 1.0)))
    ok = phi >= effh                  # the gate only confirms a burn when phi >= h
    ax.axvspan(0, effh, color="#2A2D33", alpha=0.9, lw=0)
    ax.text(effh / 2, 2.5, "φ < h:\nchưa xác nhận chói\n→ không giữ box", color=MUTED, fontsize=14, ha="center", va="center")
    ax.step(phi[ok], ttl[ok], where="post", color=AMBER, lw=3)
    ax.axhline(5, color=MUTED, ls="--", lw=2)
    ax.text(0.0, 5.12, "PEG gốc", color=MUTED, fontsize=15, ha="left", va="bottom")
    ax.set_xlabel("φ (tỉ lệ box bị cháy trắng)", fontsize=16)
    ax.set_ylabel("số frame được giữ box", fontsize=16)
    ax.set_ylim(0, 5.8); ax.set_xlim(0, 1)
    ax.set_yticks(range(0, 6))
    for a in axs:
        a.grid(color="#2A2D33", lw=1)
        a.tick_params(labelsize=15)
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    fig.tight_layout(w_pad=3)
    fig.savefig(f"{OUT}/m3_dynamic_h.png")
    plt.close(fig)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    from glaremot.tracking import tracker as T
    thr = T.DEGLARE_MIN_SAT
    st = fig_m6()
    fig_m1()
    fig_m3()
    seqs = json.load(open(SPLITS))["test"]
    t0 = time.time()
    with Pool(8) as p:
        means = p.map(seq_sat_means, seqs, chunksize=1)
    m = np.array([x for s in means for x in s])
    frac = float((m > thr).mean())
    print(f"M6 applied (sat.mean > {thr}): {100*frac:.2f}% of {len(m)} frames "
          f"(every frame, 20 test seqs, {time.time()-t0:.0f}s); min sat.mean={m.min():.5f}, "
          f"median={np.median(m):.5f}")
    extra = {f"frac_sat_mean_gt_{t}": float((m > t).mean()) for t in (0.001, 0.002, 0.005)}
    print("  stricter thresholds:", extra)
    json.dump({
        "m6_frac_applied": frac, "m6_frac_note": "every frame",
        "m6_frames_total": int(len(m)), "m6_threshold": thr,
        "m6_sat_mean_min": float(m.min()), "m6_sat_mean_median": float(np.median(m)),
        "m6_frac_stricter_thresholds": extra,
        "m6_frame": {"seq": SEQ, "frame": IDX},
        "m6_changed_frac_full_frame": st["changed_frac"],
        "m6_halo_max_lum_change": st["max"], "m6_halo_mean_lum_change": st["mean"],
    }, open(STATS, "w"), indent=2, ensure_ascii=False)
