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
