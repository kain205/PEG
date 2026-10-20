---
name: peg-o-photometric-odometry
description: PEG-O (2026-10-20) — burn-disc odometry for the held box; FAILED on val (T3 −13.5…−41) and test (−8.6 vs PEG+): the saturated disc is not rigid. Do not retry without a stability test.
metadata:
  type: project
---

PEG-O = PEG+ (size lock) + a centre measurement during the burn: disc matched filter on the saturated component
under the prediction, peak curvature k = confidence (τ), z = anchor + displacement of the peak since the first sharp
armed frame. Code `glaremot/tracking/beacon_tracker.py` (`GPEG_ODO`, `GPEG_ODO_TAU`, `GPEG_ODO_GAMMA`, `GPEG_ARMED_SURVIVE`),
default off = byte-identical PEG/PEG+. Protocol docs/PEG_O_PROTOCOL.md (+ addendum), results results/peg_o/RESULTS.md,
docs/PEG_O_RESULTS.md, deck slides 36–38 of results/peg_f/PEG_F.pptx.

**Outcome:** the plan's absolute R ≈ (0.08h)² gave Kalman gain ≈ 0.01 (OC-SORT position P is only ~10 px²) → changed to
relative R = γ(τ/k)P before val (disclosed). Then 135_19q g53 went 4/43 → 41/43. But val rejected every (τ, γ) point
(T3 Rcv@.5 −13.5 … −41.2 vs PEG+); test at the best val point (τ .08 γ 4, guard off): T3 82.2 → 73.6, pooled 48 ep.
−10.6 [−19.5, −2.7]. Mechanism: the saturated component changes shape as the burn ramps/fades or merges, so the
matched-filter peak moves 10–20 px with a still body; on 30–40 px wide workers that kills IoU, and the injected
velocity keeps the box drifting. The offline GT-anchored estimator fails on those val episodes too (not a code bug).
S (armed survival) never fires on val.

**Why it matters:** every attempt to move the held box (B lamp-follow, M5, M1 damp, PEG-O) has now failed; size lock
(PEG+) is the only held-box fix that survives. **How to apply:** before another "measure the burn" idea, require a
measurement whose noise is small relative to the narrow val boxes (e.g. only after the disc is stable, only for large
boxes), and check it offline on val episodes first. Related: [[tune-on-val-from-scratch]], [[delegate-easy-tasks-to-sonnet]].
