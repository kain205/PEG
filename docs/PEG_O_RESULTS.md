# PEG-O (photometric odometry): results (2026-10-20)

Protocol: `docs/PEG_O_PROTOCOL.md` (committed 4b13dc3 before any run; addendum with the fusion change committed
bab4795 with the code, before any val run). Full tables, per-episode lists and commands: `results/peg_o/RESULTS.md`,
numbers `results/peg_o/numbers.json`, orchestration log `results/peg_o/ORCHESTRATOR_LOG.md`. Deck slides 36–38.

## Idea
PEG uses the saturated set to *decide* (φ ≥ h). PEG-O also uses it to *measure*: disc matched filter on the saturated
component under the prediction, peak sharpness k (Laplace curvature) as confidence, measurement = anchor centre +
displacement of the peak since the first sharp armed frame (no lamp→body offset). Centre-only Kalman update with
relative R = γ·(τ/k)·P (centre gain 1/(1+γτ/k)), jump gate 0.5·diag; size locked (PEG+). Default off = byte-identical
PEG / PEG+ (checked on all three test tables, 7 run pairs, and in Thach's fork).

## What happened
1. Plan's fusion (absolute R ≈ (0.08h)²) was a no-op: OC-SORT's position variance is ~10 px², gain ≈ 0.01. Found on the
   one-sequence smoke (test 135_19q, the episode the idea came from); changed to relative R before any val run (disclosed).
   After the change: 135_19q g53 coverage 4/43 → 41/43 (= the oracle bound for PEG+'s box size).
2. **Val (pre-registered, Thach harness, guard on): nothing accepted.** All 9 (τ, γ) points lose T3 Rcv@.5 by 13.5–41.2
   vs PEG+ (67.3) and T2 HOTA by 1.0–4.8; T1 unchanged. S (armed survival) never fires on val. Final = PEG+;
   `tune_O/test.json` = PEG+ (68.41 / 62.33 / 82.2). Stage B not run (it would equal `tune_strong_P`).
3. **Test once at the best val point (τ .08, γ 4; not selected), our repo, guard off (paper setting):**

| | T1 HOTA | T1 IDF1 | T1 MOTA | T2 HOTA | T2 MOTA | T2 IDF1 | T3 Rcv@.5 | T3 total | T3 ID-off |
|---|---|---|---|---|---|---|---|---|---|
| PEG | 68.19 | 82.30 | 80.62 | 61.70 | 73.26 | 75.30 | 76.6 | 77.8 | 18.5 |
| PEG+ | 68.23 | 82.24 | 80.52 | 62.54 | 73.37 | 77.95 | 82.2 | 85.1 | 15.5 |
| PEG-O | 68.15 | 82.15 | 80.36 | 61.73 | 73.06 | 77.26 | 73.6 | 74.5 | 9.5 |

   Per burn episode, PEG-O vs PEG+ (bootstrap 95% CI over episodes): test −8.6 [−19.8, +1.0] (6 better / 5 worse),
   val −13.5 [−29.0, −0.8], pooled 48 episodes −10.6 [−19.5, −2.7].

## Why it fails (val diagnosis; no code bug)
The burn disc is not rigid: as the burn ramps up or fades, or merges with a neighbour or the wall, the matched-filter
peak moves 10–20 px while the body stands still. The anchor is often taken on the ramp. On the val workers (28–41 px
wide) that error exceeds the box tolerance, and the gain ≈ 0.6 plus the velocity injected into the Kalman state keep
the box drifting for 20+ frames. The offline GT-anchored estimator fails on the same episodes (adds 3–9 px of error
to near-static workers), anchors are never stale, and the val sat cache is aligned. On test 135_19q (264 px box, worker
walks ~110 px) the same noise is negligible, which is why the idea looked good there.

Fixed (test, τ .08 γ 4): 135_19q g53 4 → 11/43, 204_81q g300 (400–432) 26 → 30, 316_112q 22 → 28, 145_28q 31 → 36.
Broke: 211_88q g319 35 → 6, 183_62q 35 → 12, 192_70q 39 → 22, 211_88q g320 25 → 9, 176_56q 25 → 11.
Not fixable by any coast: 312_108q g861 and 305_103q g3 (never tracked before the burn). 325_92q (half the frame
saturated): the peak becomes sharp only at the end of the burn (f296+), coverage unchanged = PEG+.

**Conclusion: keep PEG+.** Every attempt to move the held box (B lamp-follow, M5 anchor, M1 damping, PEG-O) has failed;
the size lock is the only held-box fix that holds on test.
