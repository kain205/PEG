# Selecting the PEG+ / PEG-F combination on val (pre-registered)

Written and committed **before** any val number was computed (2026-10-16). The git timestamp of this file is
the proof. Nothing below may be changed after the val runs start; deviations go in a separate "Deviations"
section of the report with the reason.

## Why
The earlier "best" combination (PEG+ + M1-swap + M3) was picked by reading the **test** ablation tables, so its
test numbers are optimistically biased. The fix is the standard one: choose on `val`, then score `test` once.

## Data (frozen split, `glaremot/data/splits.json`, unchanged since the upstream commit)
| table | val data | test data (reported once at the end) |
|---|---|---|
| I  full scene, real | 17 real val seqs (`datasets/real`) | 20 real test seqs |
| II/IV full scene, synthetic twins | 9 val twins (`datasets/synth`) | 15 test twins |
| III recovery on burnt targets | same 9 val twins | same 15 test twins |

Shipped weights, no retraining. `GMOT_TRACKER=beacon`, `GMOT_BIRTH_SIZE_GUARD=0` (paper setting) for every run.
Tracker-only replay from perception caches recorded on val (`--percep_cache`), so only the tracker changes.

## What is selected
Only on/off switches. Every numeric parameter stays at its value in the code (PEG: h=0.40, δ=3; PEG-F: the
friend's constants). No numeric tuning on val or test.

Candidate components (8):
| id | env | what |
|---|---|---|
| A | `GPEG_SIZE_LOCK=1` | PEG+: zero Kalman area velocity while coasting |
| B | `GPEG_LAMP_FOLLOW=1` | PEG+ lamp follow |
| M1damp | `GMOT_AM_DAMP=1` | ×0.88 velocity damping of close pairs |
| M1swap | `GMOT_AM_SWAP=1` | extra swap tests in `_resolve_identity` |
| M2 | `GMOT_REID=1` | HSV appearance votes |
| M3 | `GBEACON_DYNAMIC_H=1 GBEACON_ADAPTIVE_TTL=1` | dynamic h + adaptive emit TTL |
| M4 | `GMOT_DORMANT=1` (+ `GMOT_REID=0` unless M2 is selected) | dormant ID pool |
| M5 | `GBEACON_ANCHOR=1` | headlamp anchor |

## Metrics (val, COMBINED)
Primary, one per table: **T1 HOTA**, **T2 HOTA**, **T3 all-burn Rcv@.5**.

## Rule: greedy forward selection from PEG
1. Current config C = PEG (no component).
2. For every component X not in C, run C+X on all three val tables. Δ = metric(C+X) − metric(C).
3. C+X is *admissible* if each of the three Δ ≥ −0.5 (points).
4. Score(C+X) = ΔT1 HOTA + ΔT2 HOTA + ΔT3 Rcv@.5.
5. If the best admissible score is > +0.5, add that X to C and go to 2. Otherwise stop.
   Ties: the component listed first in the table above wins.
6. The final C is "the val-selected config".

## Reporting
- Val: every round's table (all candidates, all three primary metrics + IDF1, MOTA, IDSW, total, ID-off).
- Test, run **once**: the val-selected config, next to PEG, PEG+ (A), and the earlier test-selected A+M1swap+M3
  (labelled as test-selected). Whatever the test numbers are, they are reported as they are.

## Known limits
- Val is small (17 real, 9 twins), and Table III on val has few burn episodes, so its Rcv@.5 is noisy.
- PEG+'s idea came from failure analysis on test outputs. Val checks whether its effect holds on unseen
  sequences, but it can't undo the fact that the idea came from test.
