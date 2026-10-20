# PEG-C (the coast, designed): results (2026-10-20)

Protocol: `docs/PEG_C_PROTOCOL.md` (committed 0f92215 before any run; code + Addendum 1 committed 134d947 before the
val search). Full tables, search traces, per-episode lists and commands: `results/peg_c/RESULTS.md` (Vietnamese),
numbers `results/peg_c/numbers.json`, orchestration log `results/peg_c/ORCHESTRATOR_LOG.md`. Deck slides 39–41.

## Idea
PEG decides *whether* to coast (φ ≥ h). PEG-C designs *how*: one constant-velocity model, used as a filter online
(V = coast-entry velocity from the OLS slope of the last K detection centres, C = causal cap on gate arming,
S = burn-exit stitch) and as a fixed-lag smoother (B = straight line between the two detections around a burn-armed
gap, BB = backward birth). One knob each; size lock (PEG+) on by design. All flags off = byte-identical PEG / PEG+.

Caveats stated up front: the components came from oracle analyses that pooled val and test episodes; synthetic burns
are centred on the GT box, so anything reading the disc geometry leaks GT on T2/T3 — PEG-C reads only the existence
gate (φ ≥ h) and the track's own detections; fixed-lag rows are not online and are always labelled "fixed-lag L".

## What happened
1. Checks: the tracker's `ols_velocity` reproduces the oracle b40 exactly (87.8 pooled, 43/43 episodes);
   flags off byte-identical (6 run pairs, 3 tables, also in Thach's fork); port = ours byte-for-byte.
2. **Val (pre-registered, Thach harness, guard on):** online strict final = **P + V (K 40, t 2)**: T3 Rcv@.5 67.3 → 75.8,
   T1 HOTA −0.44, T2 −0.10. S gains T2 +1.30 but only through one sequence (fails the single-event check; the
   "strongest" variant keeps it). C never moves anything (≤ +0.09). Fixed-lag stage: nothing accepted (B hidden
   fills no frame because the gate already emits almost every gap frame; B all costs T3 −2.1 in two episodes; BB never
   fires). ALL (+ Thach's components): + M1 cone (T1 +0.42, T2 +1.29).
3. **Test once** (T1 HOTA / IDF1 · T2 HOTA · T3 Rcv@.5):

| | Thach harness, guard on | ours, guard off (paper setting) |
|---|---|---|
| PEG+ | 68.41 / 82.68 · 62.33 · 82.2 | 68.23 / 82.24 · 62.54 · 82.2 |
| PEG-C online (P + V) | 68.80 / 84.26 · 60.89 · 80.4 | 68.49 / 83.24 · 61.15 · 80.5 |
| PEG-C fixed-lag 90 (B hidden; not selected by val) | – | 68.48 / 83.23 · 61.04 · 80.5 |
| PEG-C strongest (+ S) | 68.86 / 84.34 · 62.67 · 81.2 | – |
| ALL (PEG-C + M1 cone) | 68.78 / 84.24 · 61.35 · 81.2 | – |
| Thach best (PEG+ + M1 cone) | 68.44 / 82.71 · 63.14 · 83.1 | – |

   Per burn episode, PEG-C vs PEG+ (bootstrap 95% CI): test −1.8 [−7.7, +3.6] (4 better / 5 worse), val +8.6
   [+3.0, +15.7] (9 / 1), pooled 48 episodes +2.4 [−2.1, +6.8]. Guard off, T2 AssA −2.8 and IDSW 16 → 20.

## Why (post-test analysis, not used for selection)
On the test losses (211 g320 25 → 13, 176 g204 25 → 10) PEG+ and PEG-C differ only in the entry velocity, and PEG+'s own
Kalman velocity was closer to the true burn velocity than the 40-frame OLS: the long baseline is stale when the walker
changes pace, or when the 40 detections straddle an earlier gap (211). The slope-noise check explains why no K fixes
this: σ = 2.2 px gives a white-noise floor σ√(12/K³) of 0.03 px/f at K = 40, but the measured error stays at
0.28–0.33 px/f, as large as the model-error-only fit on GT (0.30) — about 54–63 % of the median walking speed (0.52).
The limit is the constant-velocity model, not noise. The val gain was real on val (9 of 10 changed episodes better)
and is what the oracle had already flagged: its gain was val-driven (all-episode test +0.5, val +7.3).

**Conclusion: PEG+ stays the recommended held-box fix.** PEG-C's V is a val win that test does not confirm on T3; its
one test gain is T1 IDF1 (+1.0 guard off, +1.6 guard on), which is −1.1 on val. Not tested by the protocol: B on top
of PEG+ without V (the literature check measured +4.3/+3.8 T3 there); a velocity estimator that detects pace changes.
