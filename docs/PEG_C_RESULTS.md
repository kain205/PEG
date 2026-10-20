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

## Stage 2b (Addendum 2, committed a43ae88 before any run): B on PEG+ without V
The staged protocol only tried B after V, where the gate already emits on every gap frame, so B could not be judged on
its own. Re-run on PEG+ alone (P, no V, no S), same grid and strict rule. **Val accepted B L 90 mode all**: T1 +0.04,
T2 HOTA +0.78, T3 Rcv@.5 +3.8 (67.3 → 71.1), single-event check +1.74; BB still never fires; strongest = same final.
**Test once:** Thach harness (guard on) T1 68.50 · T2 62.74 · T3 86.5 (PEG+ 68.41 · 62.33 · 82.2). Ours, guard off:

| vs PEG+ (guard off) | T1 HOTA | IDF1 | MOTA | IDSW | FP | FN | T2 HOTA | MOTA | FP | FN | T3 Rcv@.5 | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PEG+ | 68.23 | 82.24 | 80.52 | 17 | 1440 | 2618 | 62.54 | 73.37 | 2113 | 2268 | 82.2 | 85.1 |
| PEG-C fixed-lag 90 (B all on PEG+) | 68.31 | 82.37 | 80.72 | 15 | 1435 | 2583 | 62.93 | 74.06 | 2108 | 2158 | 86.5 | 86.2 |

Per burn episode vs PEG+: test +4.2 [+1.0, +8.3] (6 better / 0 worse), val +3.9 [−2.2, +12.1] (4 / 3: 178 g206 2→0,
332 g1030 6→0, 210 g317 16→15 — wrong re-acquisition endpoints), pooled +4.1 [+0.9, +8.0]. These equal the literature
check's numbers to the frame. It is the first held-box change after PEG+ that test confirms on all three tables with
FP flat or down — but it is **fixed-lag** (output up to 90 frames late), never an online number.

**Conclusion.** Online: PEG+ stays the recommended held-box fix; PEG-C's V is a val win that test does not confirm
on T3 (its one test gain, T1 IDF1 +1.0 / +1.6, is −1.1 on val). Fixed-lag (when a ≤ 90-frame output delay is
acceptable): PEG+ + burn-gated backfill (B, L 90, all), test T3 82.2 → 86.5, T2 FN −110, T1 FN −35, FP −5/−5.
Still open: a velocity estimator that detects pace changes; B together with S (stitch) for the burn-exit new-id cases.
