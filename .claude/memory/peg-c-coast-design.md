---
name: peg-c-coast-design
description: PEG-C (2026-10-20) — designed coast. Online V (long-baseline velocity) won val but lost test T3 (−1.8); fixed-lag B (burn-gated backfill, L90 all) on PEG+ won val AND test (T3 82.2→86.5). Online best = PEG+; fixed-lag best = PEG+ + B.
metadata:
  type: project
---

PEG-C = PEG+ + one constant-velocity model: V = coast-entry velocity from the OLS slope of the last K raw detection
centres (`GPEG_VEL_K`, `GPEG_VEL_T`), C = gate arms only while gap ≤ N (`GPEG_CAP`), S = burn-exit stitch
(`GPEG_STITCH_K`), fixed-lag B = straight-line backfill of burn-armed gaps (`GPEG_BACKFILL_L`, `_MODE`), BB = backward
birth (`GPEG_BACKBIRTH`). All default off = byte-identical PEG/PEG+. Protocol docs/PEG_C_PROTOCOL.md (0f92215),
code 134d947, results docs/PEG_C_RESULTS.md + results/peg_c/RESULTS.md, deck slides 39–41.

**Outcome:** val (Thach harness, guard on) picked P + V (K 40, t 2): T3 67.3 → 75.8. S only via one seq (strongest
keeps it), C ≤ +0.09, B hidden fills nothing (gate already emits the gap), B all −2.1 T3, BB never fires. Test once,
guard off: T1 68.49 / IDF1 83.24 (PEG+ 68.23 / 82.24), T2 HOTA 61.15 (62.54), T3 80.5 (82.2); per episode test −1.8
[−7.7, +3.6], val +8.6 [+3.0, +15.7], pooled +2.4 [−2.1, +6.8]. On the test losses (176 g204, 211 g320) PEG+'s own
Kalman velocity was closer to the truth than the 40-frame OLS (walker changes pace; history straddles a gap).
Slope noise σ√(12/K³) (σ 2.2 px) is tiny at K 40, but measured |v_est − v_true| plateaus at ≈ 0.3 px/f = the GT-fit
model error: the CV model, not noise, is the limit.

**Stage 2b (Addendum 2, a43ae88):** B on PEG+ without V — val accepted L 90 mode all (T3 +3.8, T2 +0.78); test once
guard off T1 FN 2618→2583, T2 FN 2268→2158, FP −5/−5, T3 82.2→86.5; per episode test +4.2 [+1.0, +8.3] 6/0, pooled
+4.1 [+0.9, +8.0]. Fixed-lag only (≤ 90 frames late), names `pegcbl_*`. Lesson: test each component on its own
mechanism — the staged protocol had judged B after V, where V already emits on every gap frame.

**Why it matters:** the oracle had warned the b40 gain was val-driven (all-episode test +0.5, val +7.3) and that is
exactly what happened; an oracle gain that comes from one split stays in that split. **How to apply:** don't push
pre-burn velocity further; report PEG+ + B as the fixed-lag row; leftovers: pace-change-aware estimator, B + S. Related:
[[coast-design-research]], [[peg-o-photometric-odometry]], [[tune-on-val-from-scratch]].
