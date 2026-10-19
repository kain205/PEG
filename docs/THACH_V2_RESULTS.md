# Thach v2 (M1-M6): results (2026-10-19)

Protocol: `docs/THACH_V2_PROTOCOL.md` (committed e4467a3, before any val number). Full tables:
`results/thach_v2/THACH_V2.md`, numbers `results/thach_v2/numbers_thach.json`. Deck slides 20-32.

## 1. Reproduction
- His Table I (test) reproduces exactly for all 14 configs from his caches, and the caches match a live run on our
  GPU (base 68.84, full+M6 70.03, `results/thach_v2/out_live/eval/`).
- His results folder holds 56 Table I runs on test, 0 runs on val, 0 runs of Table II/III. His script says
  "choose / calibrate on VAL, report TEST once", but the configs and parameters were chosen on Table I test
  (M1 alone: dx_qonly / dx_qcone / dx_damp 66.44-68.84, fix1 69.09, fix2 = final 69.24).
- His `base` is not PEG: the old M1-swap identity logic is always on. Test 129: +23.5 HOTA, test 320: IDSW 4 -> 25.

## 2. All three tables (guard on = his setting; PEG = ours, guard on)

| split | config | T1 HOTA | T1 IDSW | T2 HOTA | T2 MOTA | T3 Rcv@.5 | ID kept to burn end |
|---|---|---|---|---|---|---|---|
| test | PEG | 68.34 | 15 | 61.41 | 73.48 | 76.2 | 19/30 |
| test | base | 68.84 | 38 | 62.18 | 72.93 | 76.2 | 19/30 |
| test | base+M6 | 69.88 | 27 | 63.49 | 73.44 | 77.3 | 18/30 |
| test | full (M1-M5) | 69.54 | 38 | 57.24 | 70.28 | 55.6 | 5/30 |
| test | full+M6 | 70.03 | 29 | 61.21 | 69.48 | 53.6 | 4/30 |
| val | PEG | 70.24 | 15 | 76.25 | 89.73 | 67.6 | 7/18 |
| val | base | 69.98 | 28 | 76.25 | 89.73 | 67.6 | 7/18 |
| val | base+M6 | 69.88 | 31 | 75.52 | 89.72 | 66.9 | 8/18 |
| val | full (M1-M5) | 70.51 | 33 | 73.70 | 86.55 | 37.7 | 0/18 |
| val | full+M6 | 69.85 | 48 | 73.16 | 86.62 | 37.1 | 0/18 |

## 3. Pre-registered val rule
Admissible and score > 0.5: full-M5 (+3.00) and base+M1 (+2.72). Both fail the single-event check: their gain
comes from one T2 sequence (147_sequence_3q) and one T3 burn episode (332_sequence_99q); without them the score
is -0.71 / -0.89. Every config with both M1 and M5 is out at step 1 (T3 about -30). M6 is out (all three tables
down on val). **Selected: base** = no method is supported by val. Test once: base T1 68.84 / T2 62.18 / T3 76.2
(PEG 68.34 / 61.41 / 76.2). On val base is ≈ PEG (T1 -0.26, IDSW 28 vs 15, T2/T3 equal), so in practice: keep PEG.

## 4. Why Table III collapses: M1 x M5 (diagnostic only, not used for selection)
M1's adaptive Q inflates the Kalman position covariance every frame without a detection. M5's headlamp anchor is a
"weak" centre update with a fixed measurement noise, so with a large covariance the gain approaches 1 and the weak
nudge becomes a full pull. During burn frames the box stays present at the right height but slides sideways
(median centre offset in person widths; `results/thach_v2/burn_drift.py`, `drift.json`):

| config | T3 test | T3 val | dx/w test | dx/w val |
|---|---|---|---|---|
| base | 76.2 | 67.6 | +0.02 | -0.02 |
| base+M1 | 70.1 | 69.4 | +0.01 | -0.02 |
| base+M5 | 76.2 | 63.4 | -0.01 | -0.05 |
| base+M5 + only M1's Q inflation | 53.6 | 35.9 | -0.14 | -0.39 |
| full (M1-M5) | 55.6 | 37.7 | -0.10 | -0.39 |
| full with `GMOT_ADAPTIVE_Q=0` | 69.5 | 65.1 | -0.00 | -0.05 |
| full with `GMOT_CONE=0` | 54.7 | 37.7 | -0.11 | -0.39 |
| full with `GMOT_INTERACT_DAMP=0` | 54.9 | 35.9 | -0.13 | -0.39 |

## 5. Commands
Harness: his code unchanged except `eval_recovery.py --det_cache` (`results/thach_v2/eval_recovery_det_cache.patch`);
config files with our paths in `results/thach_v2/configs/` (copied into his `configs/`).
```bash
PY=.venv/Scripts/python.exe
bash results/thach_v2/build_caches.sh                 # perception caches (GPU, ~9 h) + live T1 check
$PY results/thach_v2/run.py --split test              # 14 configs x 3 tables (cached, ~30 s each)
$PY results/thach_v2/run.py --split val
$PY results/thach_v2/analyze.py                       # val rule, per-episode bootstrap -> THACH_V2.md
$PY results/thach_v2/diag_m1m5.py                     # M1 sub-switch diagnostic (T3)
$PY results/thach_v2/burn_drift.py --dump             # box drift during burn -> drift.json
```

## 6. Tuning from scratch on val (`docs/THACH_V2_TUNE_PROTOCOL.md`, committed 0ff194f before any run)
Start S0 = his code with every switch off and the original PEG resolver = our PEG (val 70.24 / 76.25 / 67.6).
Round 1 tried 26 parameter points (9 components); best point per component, Δ vs S0 on val:

| component | best point | ΔT1 HOTA | ΔT2 HOTA | ΔT3 Rcv | score | without most favourable unit |
|---|---|---|---|---|---|---|
| M1 cone | χ² 5.99, speed 0.04h | +0.42 | +1.31 | 0.0 | +1.73 | −0.01 (156 in T1, 147 in T2) |
| M1 damping ×0.88 | on | 0.00 | −0.48 | +1.8 | +1.32 | −0.60 (332 in T2 and its burn episode) |
| M3 | decay 0.03, TTL off | +0.04 | 0 | 0 | +0.04 | – |
| M1 adaptive Q / M2 / M4 | any value | 0 | 0 | 0 | 0 | – |
| M5 | weak-R ×96 | +0.02 | −0.07 | −0.2 | −0.25 | – |
| R (his resolver rewrite) | on | −0.26 | 0 | 0 | −0.26 | – |
| M6 | on | −0.10 | −0.73 | −0.7 | −1.53 | – |

No point passes → final = S0 = PEG. Test once (`results/thach_v2/tune/test.json`): 68.34 / 61.41 / 76.2 = PEG.
Trace: `results/thach_v2/tune/trace.json`, all evaluations: `tune/ledger.json`. Deck slide 33.
```bash
.venv/Scripts/python.exe results/thach_v2/tune_val.py          # val search (~15 min)
.venv/Scripts/python.exe results/thach_v2/tune_val.py --test   # test once, final config only
```

### Test, for comparison only (run after the decision was committed; `tune/test_diagnostic.json`)
Sum of Δ (T1 HOTA + T2 HOTA + T3 Rcv) on test for each component's best val point, vs PEG:
cone +2.53 (T2 from 204 +12.1 and 176 +6.5, T3 one episode of 204; without 204 ≈ +0.6) · damping −8.52 (T3 −6.7) ·
M6 +3.58 and resolver rewrite +1.27, both almost only from the single ID switch fixed in 129 (+23.5 HOTA on that
sequence; without 129: M6 ≈ −0.3, resolver ≈ −1.1) · M3 +0.46 · M5 +0.38 · M4 +0.05 · adaptive Q, M2 0.
M6 and the resolver rewrite were tuned by Thach on test, so their test numbers are optimistic.

## 7. Full metrics and the "strongest" versions (Addenda 1-2 of the tune protocol)

Strongest (val greedy without the single-event check): M1 cone + M1 damping. With PEG+ in by design: PEG+ + M1 cone.
Test once each. Full table (val + test, every component's best val point, notes = video the gain rests on):

### val

| config | T1 HOTA | T1 IDF1 | T1 MOTA | T1 IDSW | T2 HOTA | T2 IDF1 | T2 MOTA | T3 Rcv@.5 | T3 total | T3 ID-off | where the change vs PEG sits |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PEG | 70.24 | 86.35 | 82.06 | 15 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | 10.0 |  |
| PEG+ (ours) | 70.11 | 86.06 | 82.20 | 17 | 76.30 | 89.24 | 89.80 | 67.3 | 66.3 | 10.0 |  |
| PEG + M1 cone [M1c[0]] | 70.66 | 86.93 | 82.03 | 16 | 77.56 | 91.20 | 89.76 | 67.6 | 67.4 | 10.0 | T1 +0.42: top 156 +3.7, without it -0.01; T2 +1.31: top 147 +10.0, without it +0.00 |
| PEG + M1 damping [M1d[0]] | 70.24 | 86.29 | 82.17 | 13 | 75.77 | 88.72 | 89.88 | 69.4 | 68.8 | 10.0 | T2 -0.48: top 332 +0.7, without it -0.55; T3 +1.8: 1 ep. better / 0 worse, without top (332) +0.00 |
| PEG + M3 dyn-h/TTL [M3[0]] | 70.28 | 86.45 | 82.28 | 15 | 76.25 | 89.20 | 89.76 | 67.6 | 67.4 | 10.0 |  |
| PEG + M1 adaptive Q [M1q[0]] | 70.24 | 86.35 | 82.06 | 15 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | 10.0 |  |
| PEG + M2 Re-ID [M2[0]] | 70.24 | 86.35 | 82.06 | 15 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | 10.0 |  |
| PEG + M4 dormant [M4[0]] | 70.24 | 86.35 | 82.06 | 15 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | 10.0 |  |
| PEG + M5 anchor [M5[2]] | 70.26 | 86.41 | 82.17 | 15 | 76.18 | 89.16 | 89.66 | 67.4 | 67.4 | 10.0 |  |
| PEG + his ID-resolver rewrite [R[0]] | 69.98 | 85.76 | 82.00 | 28 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | 10.0 |  |
| PEG + M6 tone-map [M6[0]] | 70.14 | 85.82 | 81.60 | 18 | 75.52 | 87.92 | 89.72 | 66.9 | 64.2 | 10.0 | T2 -0.73: top 315 +0.4, without it -0.73; T3 -0.7: 4 ep. better / 4 worse, without top (178) -1.68 |
| Thach full+M6 (his params, tuned on test) | 69.85 | 85.37 | 81.75 | 48 | 73.16 | 85.30 | 86.62 | 37.1 | 32.6 | 21.9 |  |
| STRONGEST (val, no single-event check): M1c[0] + M1d[0] | 70.63 | 86.87 | 82.14 | 14 | 77.09 | 90.71 | 89.94 | 69.4 | 68.8 | 10.0 | T1 +0.39: top 156 +3.3, without it +0.04; T2 +0.84: top 147 +6.2, without it +0.05; T3 +1.8: 1 ep. better / 0 worse, without top (332) +0.00 |
| STRONGEST with PEG+ by design: M1c[0] + P[0] | 70.54 | 86.64 | 82.16 | 18 | 77.63 | 91.24 | 89.84 | 67.3 | 66.3 | 10.0 | T1 +0.30: top 156 +3.9, without it -0.20; T2 +1.38: top 147 +10.6, without it -0.01 |

### test

| config | T1 HOTA | T1 IDF1 | T1 MOTA | T1 IDSW | T2 HOTA | T2 IDF1 | T2 MOTA | T3 Rcv@.5 | T3 total | T3 ID-off | where the change vs PEG sits |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PEG | 68.34 | 82.68 | 80.59 | 15 | 61.41 | 74.61 | 73.48 | 76.2 | 77.1 | 18.5 |  |
| PEG+ (ours) | 68.41 | 82.68 | 80.77 | 15 | 62.33 | 77.52 | 73.99 | 82.2 | 85.1 | 15.5 | T2 +0.92: top 176 +6.6, without it +0.41; T3 +6.0: 6 ep. better / 2 worse, without top (325) +3.79 |
| PEG + M1 cone [M1c[0]] | 68.38 | 82.66 | 81.00 | 15 | 62.70 | 76.61 | 74.64 | 77.4 | 77.6 | 11.6 | T2 +1.29: top 204 +12.1, without it +0.62; T3 +1.2: 1 ep. better / 0 worse, without top (204) +0.00 |
| PEG + M1 damping [M1d[0]] | 68.45 | 83.08 | 80.77 | 16 | 59.48 | 71.56 | 72.00 | 69.5 | 73.8 | 18.5 | T2 -1.93: top 136 +0.7, without it -2.15; T3 -6.7: 2 ep. better / 8 worse, without top (325) -7.34 |
| PEG + M3 dyn-h/TTL [M3[0]] | 68.49 | 82.89 | 81.10 | 15 | 61.72 | 74.98 | 74.46 | 76.2 | 77.1 | 18.5 | T2 +0.31: top 305 +3.4, without it +0.23 |
| PEG + M1 adaptive Q [M1q[0]] | 68.34 | 82.68 | 80.59 | 15 | 61.41 | 74.61 | 73.48 | 76.2 | 77.1 | 18.5 |  |
| PEG + M2 Re-ID [M2[0]] | 68.34 | 82.68 | 80.59 | 15 | 61.41 | 74.61 | 73.48 | 76.2 | 77.1 | 18.5 |  |
| PEG + M4 dormant [M4[0]] | 68.34 | 82.70 | 80.60 | 14 | 61.46 | 74.64 | 73.51 | 76.2 | 77.1 | 18.5 |  |
| PEG + M5 anchor [M5[2]] | 68.33 | 82.68 | 80.60 | 15 | 61.40 | 74.60 | 73.40 | 76.6 | 77.8 | 18.5 |  |
| PEG + his ID-resolver rewrite [R[0]] | 68.84 | 84.73 | 80.00 | 38 | 62.18 | 77.42 | 72.93 | 76.2 | 77.1 | 18.5 | T1 +0.50: top 129 +23.5, without it -0.52; T2 +0.77: top 129 +23.4, without it -0.59 |
| PEG + M6 tone-map [M6[0]] | 69.39 | 85.00 | 80.56 | 13 | 62.84 | 77.49 | 73.34 | 77.3 | 78.9 | 18.5 | T1 +1.05: top 129 +23.5, without it +0.06; T2 +1.43: top 129 +23.5, without it +0.12; T3 +1.1: 2 ep. better / 3 worse, without top (316) -0.49 |
| Thach full+M6 (his params, tuned on test) | 70.03 | 87.03 | 80.43 | 29 | 61.21 | 77.56 | 69.48 | 53.6 | 55.4 | 10.5 |  |
| STRONGEST (val, no single-event check): M1c[0] + M1d[0] | 68.46 | 82.94 | 80.91 | 16 | 60.41 | 73.28 | 73.20 | 70.0 | 73.8 | 15.5 | T2 -1.00: top 204 +9.4, without it -1.66; T3 -6.2: 2 ep. better / 8 worse, without top (204) -7.34 |
| STRONGEST with PEG+ by design: M1c[0] + P[0] | 68.44 | 82.71 | 80.88 | 15 | 63.14 | 78.50 | 75.05 | 83.1 | 85.1 | 11.6 | T2 +1.73: top 204 +11.5, without it +1.13; T3 +6.9: 6 ep. better / 2 worse, without top (325) +4.65 |
