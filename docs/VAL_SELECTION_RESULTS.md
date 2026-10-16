# Val selection: results (2026-10-17)

Protocol: `docs/VAL_SELECTION_PROTOCOL.md`, committed before any val number existed (commit `e259c12`). It was
followed exactly. Nothing below changes the selection after seeing test.

Setup: shipped weights, `GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0`, tracker-only replay from val perception
caches recorded with the live detector (4.3 FPS; replay byte-identical to the live run on 17/17 real val seqs).
Val = 17 real seqs (Table I), 9 synthetic twins (Table II/IV), 18 burn episodes / 571 burn frames (Table III).

## Round 1 (val, from PEG)
| candidate | T1 HOTA | T2 HOTA | T3 Rcv@.5 | score | admissible | T1 IDSW |
|---|---|---|---|---|---|---|
| PEG | 70.27 | 76.25 | 67.6 | – | – | 15 |
| A (PEG+) | −0.14 | +0.06 | −0.3 | −0.38 | yes | 17 |
| B lamp follow | −0.02 | −2.24 | −11.6 | −13.86 | no | 15 |
| **M1damp** | +0.00 | −0.44 | **+1.4** | **+0.96** | yes | 13 |
| M1swap | −0.04 | +0.00 | +0.0 | −0.04 | yes | 22 |
| M2 | 0 | 0 | 0 | 0 | yes | 15 |
| M3 | +0.04 | +0.00 | +0.0 | +0.04 | yes | 15 |
| M4 | 0 | 0 | 0 | 0 | yes | 15 |
| M5 | −0.01 | −1.29 | −4.2 | −5.50 | no | 15 |

Round 2 (from PEG+M1damp): no candidate scores > +0.5 (best: M3, +0.07). **Selected: PEG + M1damp.**
Full tables: `results/val_selection/SELECTION.md`.

## Test, scored once
| config | T1 HOTA | T1 IDF1 | T1 IDSW | T2 HOTA | T2 MOTA | T3 Rcv@.5 | T3 total |
|---|---|---|---|---|---|---|---|
| PEG | 68.19 | 82.30 | 17 | 61.70 | 73.26 | 76.6 | 77.8 |
| **val-selected: PEG + M1damp** | 67.38 | 80.79 | 19 | 57.84 | 70.28 | 66.4 | 69.7 |
| PEG+ (A) | 68.23 | 82.24 | 17 | 62.54 | 73.37 | 82.2 | 85.1 |
| A+M1swap+M3 (test-selected earlier) | 68.81 | 84.56 | 36 | 63.17 | 73.90 | 82.2 | 85.1 |

The same A+M1swap+M3 on **val**: T1 HOTA 70.16 (−0.11), T2 HOTA 76.31 (+0.06), T3 Rcv@.5 67.3 (−0.3), i.e. PEG.

The val-selected config is worse than PEG on every table of test. (Its test runs are the `pf_P+M1damp*` runs from
the earlier matrix: same env, and the replay is deterministic.)

## Why: Table III per burn episode (bootstrap over episodes, 10k resamples)
| | test (30 ep, 850 fr) | val (18 ep, 571 fr) | pooled (48 ep) |
|---|---|---|---|
| PEG Rcv@.5 | 76.6 | 67.6 | 73.0 |
| A − PEG | **+5.6** [+0.7, +12.1], 6 better / 2 worse | −0.4 [−3.2, +2.1], 2 / 2 | +3.2 [+0.1, +7.3] |
| M1damp − PEG | **−10.2** [−17.7, −3.8], 2 / 9 | +1.4 [−1.0, +5.5], 1 / 1 | −5.6 [−10.6, −1.2] |
| M1swap, M3 − PEG | 0 (no episode changes) | 0 | 0 |

- **M1damp was picked because of one episode.** On val it changes 2 of 18 episodes: 332_99q tid1030 goes 3 → 13
  covered frames, and 147_3q goes 38 → 36. +8 frames of 571 = +1.4 points, which is enough to pass the +0.5 bar.
  On test it loses 87 frames across 9 episodes. The mechanism is known: damping freezes a coasting box while the
  worker keeps walking (`results/peg_f/RESULTS.md`).
- **PEG+ has little to fix on val.** It changes 4 of 18 val episodes, net −2 frames. Val's PEG failures are mostly
  targets that are never tracked at all (315_111q 0/14 and 0/43, 178_58q 2/43). Size lock can't help those. Test
  has more episodes where the coast box collapses (320_116q 17 → 31, 325_92q 10 → 30), which is exactly what PEG+
  fixes. Pooled over 48 episodes the gain is +3.2, with a CI that barely clears 0.
- **The Table I gain of M1swap does not transfer.** Test +0.50 HOTA came from one sequence (129_13q, one identity
  swap). On val: −0.04 HOTA, IDSW 15 → 22.

## What this means
1. The friend's concern was right. The test-selected A+M1swap+M3 gain (+0.62 T1 HOTA, +1.47 T2 HOTA, +5.6 T3) does
   not reproduce on val (−0.11, +0.06, −0.3).
2. Selecting on this val is not reliable either. It is small (18 burn episodes), and one episode can move T3 by
   more than the +0.5 acceptance bar. Our pre-registered bar was too low for this noise level. That was a protocol
   mistake. We report it as it is and do not re-select.
3. No component is robustly better than PEG on all three tables. PEG+ is the only one with a positive pooled
   Table III estimate (+3.2, CI [+0.1, +7.3]), and it works only where the coast box collapses. M1damp is harmful
   overall. M1swap, M2, M3 and M4 have no measurable effect outside single events.
4. A better protocol next time: accept a component only if its bootstrap CI on the pooled episode deltas excludes 0
   (or use cross-validation over val+test sequences), and report the per-episode count of changed outcomes.

Reproduce:
```bash
bash results/val_selection/build_val_cache.sh          # ~2 h live detector, val caches + appearance sidecars
.venv/Scripts/python.exe results/val_selection/run_selection.py   # greedy selection (~10 min)
.venv/Scripts/python.exe results/val_selection/episodes.py        # per-episode + bootstrap CIs
.venv/Scripts/python.exe results/val_selection/collect_val.py     # numbers_val.json (deck input)
```
