"""PEG-C figures for the slides -> results/peg_c/figures/. No tracker runs; reads existing outputs + results/peg_c/numbers.json (run results/peg_c/collect.py first).

  187_66q_strip.png   val 187_sequence_66q_new g247 201-235: PEG+ (v_A_rcv) vs PEG-C online (v_pegc_rcv), 4 tiles across the burn   (the win)
  211_88q_strip.png   test 211_sequence_88q_new g320 436-460: PEG+ (pegplus_A_rcv) vs PEG-C (pegc_rcv), 4 tiles                       (the counter-example)
  slope_noise.png     median |v_est - v_true| vs K (log-log): measured (b5..b80), model-error only (g10..g80), the white-noise OLS floor
                      sigma*sqrt(12/K^3) and the median |v_true|
GT box = magenta (a GT box nobody matches is yellow). Run: .venv/Scripts/python.exe scripts/22_peg_c_figures.py"""
import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
_spec = importlib.util.spec_from_file_location("figs20", os.path.join(ROOT, "scripts", "20_peg_o_figures.py"))
F20 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(F20)
F9 = F20.F9
OUT = os.path.join(ROOT, "results", "peg_c", "figures")
F9.OUT = OUT
PLUS_COL, C_COL = (25, 163, 95), (60, 140, 245)


def slope_noise():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = json.load(open(os.path.join(ROOT, "results", "peg_c", "numbers.json"), encoding="utf-8"))
    sn = n["slope_noise"]
    sigma = sn["sigma_px"]
    Kb = [5, 10, 20, 40, 80]; Kg = [10, 20, 40, 80]
    yb = [sn["measured_med_verr_pooled"][f"b{k}"] for k in Kb]
    yg = [sn["model_error_med_verr_pooled"][f"g{k}"] for k in Kg]
    Kc = np.geomspace(5, 80, 100)
    plt.rcParams.update({"font.size": 15, "axes.labelsize": 16, "legend.fontsize": 12.5, "xtick.labelsize": 15, "ytick.labelsize": 15})
    fig, ax = plt.subplots(figsize=(8.2, 5.6))
    BLUE, ORANGE, GRAY = "#1f6fd1", "#e07b00", "#6b6b6b"
    ax.plot(Kc, sigma * np.sqrt(12.0 / Kc ** 3), "--", color=GRAY, lw=2.2,
            label=f"white-noise floor σ·√(12/K³), σ = {sigma:.2f} px")
    ax.plot(Kb, yb, "o-", color=BLUE, lw=2.4, ms=9, label="measured: slope of the past K detections")
    ax.plot(Kg, yg, "s-", color=ORANGE, lw=2.4, ms=9, label="model error only: slope of the GT past")
    ax.axhline(sn["median_vtrue_speed"], color="#222222", lw=1.6, ls=":")
    ax.text(88, sn["median_vtrue_speed"] * 1.07, f"median true speed = {sn['median_vtrue_speed']:.2f} px/frame", fontsize=12.5, va="bottom", ha="right", color="#222222")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xticks(Kb); ax.set_xticklabels([str(k) for k in Kb])
    ax.set_yticks([0.01, 0.03, 0.1, 0.3, 1.0]); ax.set_yticklabels(["0.01", "0.03", "0.1", "0.3", "1"])
    ax.set_xlim(4.5, 90); ax.set_ylim(0.008, 5.0)
    ax.set_xlabel("K  (detection frames in the velocity fit)")
    ax.set_ylabel("median |v_est − v_true|   (px/frame)")
    ax.legend(loc="upper right", frameon=False)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.annotate("noise floor keeps falling,\nbut the error stops at ≈ 0.3:\nthe constant-velocity model, not noise,\nis the limit", xy=(40, 0.29), xytext=(5.3, 0.02),
                fontsize=13, color="#333333", arrowprops=dict(arrowstyle="->", color="#555555"))
    fig.tight_layout()
    p = os.path.join(OUT, "slope_noise.png")
    fig.savefig(p, dpi=150)
    print("->", p)


def main():
    os.makedirs(OUT, exist_ok=True)
    F20.strip("187_66q_strip", "187_sequence_66q_new", 247, [201, 212, 224, 235], [("PEG+", PLUS_COL, "v_A_rcv"), ("PEG-C", C_COL, "v_pegc_rcv")])
    F20.strip("211_88q_strip", "211_sequence_88q_new", 320, [436, 444, 452, 460], [("PEG+", PLUS_COL, "pegplus_A_rcv"), ("PEG-C", C_COL, "pegc_rcv")])
    slope_noise()


if __name__ == "__main__":
    main()
