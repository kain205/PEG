# Thach v2 (M1-M6): all three tables, test + val

Protocol: `docs/THACH_V2_PROTOCOL.md`. Guard on (his setting). PEG = ours, guard on.

## test

| config | T1 HOTA | T1 IDF1 | T1 IDSW | T2 HOTA | T2 MOTA | T3 Rcv@.5 | T3 total | T3 ID-off |
|---|---|---|---|---|---|---|---|---|
| PEG | 68.34 | 82.68 | 15 | 61.41 | 73.48 | 76.2 | 77.1 | 18.5 |
| base | 68.84 | 84.73 | 38 | 62.18 | 72.93 | 76.2 | 77.1 | 18.5 |
| base+M1 | 69.24 | 86.19 | 42 | 62.13 | 72.85 | 70.1 | 73.8 | 6.6 |
| base+M2 | 69.08 | 84.52 | 36 | 62.42 | 73.43 | 76.2 | 77.1 | 18.5 |
| base+M3 | 68.99 | 84.96 | 38 | 62.49 | 73.92 | 76.2 | 77.1 | 18.5 |
| base+M4 | 69.08 | 84.55 | 35 | 62.47 | 73.46 | 76.2 | 77.1 | 18.5 |
| base+M5 | 68.72 | 84.48 | 38 | 62.38 | 72.00 | 76.2 | 77.1 | 15.5 |
| base+M6 | 69.88 | 86.37 | 27 | 63.49 | 73.44 | 77.3 | 78.9 | 18.5 |
| full | 69.54 | 85.87 | 38 | 57.24 | 70.28 | 55.6 | 56.5 | 6.6 |
| full-M1 | 69.17 | 84.61 | 35 | 62.98 | 73.58 | 76.2 | 77.1 | 15.5 |
| full-M2 | 69.14 | 86.00 | 42 | 57.56 | 69.57 | 55.2 | 55.6 | 6.6 |
| full-M3 | 69.30 | 85.67 | 38 | 57.07 | 68.63 | 55.6 | 56.5 | 6.6 |
| full-M4 | 69.54 | 85.87 | 39 | 57.23 | 70.27 | 55.6 | 56.5 | 6.6 |
| full-M5 | 69.73 | 86.21 | 38 | 61.64 | 74.12 | 70.4 | 73.8 | 6.6 |
| full+M6 | 70.03 | 87.03 | 29 | 61.21 | 69.48 | 53.6 | 55.4 | 10.5 |

## val

| config | T1 HOTA | T1 IDF1 | T1 IDSW | T2 HOTA | T2 MOTA | T3 Rcv@.5 | T3 total | T3 ID-off |
|---|---|---|---|---|---|---|---|---|
| PEG | 70.24 | 86.35 | 15 | 76.25 | 89.73 | 67.6 | 67.4 | 10.0 |
| base | 69.98 | 85.76 | 28 | 76.25 | 89.73 | 67.6 | 67.4 | 10.0 |
| base+M1 | 70.23 | 85.88 | 29 | 76.92 | 90.20 | 69.4 | 68.8 | 10.0 |
| base+M2 | 70.15 | 86.11 | 32 | 76.25 | 89.73 | 67.6 | 67.4 | 10.0 |
| base+M3 | 70.02 | 85.86 | 28 | 76.25 | 89.76 | 67.6 | 67.4 | 10.0 |
| base+M4 | 70.15 | 86.11 | 32 | 76.25 | 89.73 | 67.6 | 67.4 | 10.0 |
| base+M5 | 69.98 | 85.75 | 28 | 74.96 | 89.11 | 63.4 | 63.8 | 21.9 |
| base+M6 | 69.88 | 85.24 | 31 | 75.52 | 89.72 | 66.9 | 64.2 | 10.0 |
| full | 70.51 | 86.60 | 33 | 73.70 | 86.55 | 37.7 | 33.3 | 21.9 |
| full-M1 | 70.20 | 86.20 | 32 | 74.96 | 89.13 | 63.4 | 63.8 | 21.9 |
| full-M2 | 70.34 | 86.04 | 29 | 74.84 | 86.69 | 37.7 | 33.3 | 10.0 |
| full-M3 | 70.36 | 86.41 | 33 | 73.68 | 86.52 | 37.7 | 33.3 | 21.9 |
| full-M4 | 70.51 | 86.60 | 33 | 73.70 | 86.55 | 37.7 | 33.3 | 21.9 |
| full-M5 | 70.51 | 86.63 | 33 | 76.92 | 90.21 | 69.4 | 68.8 | 10.0 |
| full+M6 | 69.85 | 85.37 | 48 | 73.16 | 86.62 | 37.1 | 32.6 | 21.9 |

## Val rule (deltas vs his base)

| config | ΔT1 HOTA | ΔT2 HOTA | ΔT3 Rcv | score | admissible |
|---|---|---|---|---|---|
| base+M1 | +0.25 | +0.67 | +1.8 | +2.72 | yes |
| base+M2 | +0.17 | +0.00 | +0.0 | +0.17 | yes |
| base+M3 | +0.04 | +0.00 | +0.0 | +0.04 | yes |
| base+M4 | +0.17 | +0.00 | +0.0 | +0.17 | yes |
| base+M5 | +0.00 | -1.29 | -4.2 | -5.49 | no |
| base+M6 | -0.10 | -0.73 | -0.7 | -1.53 | no |
| full | +0.53 | -2.55 | -29.9 | -31.92 | no |
| full-M1 | +0.22 | -1.29 | -4.2 | -5.27 | no |
| full-M2 | +0.36 | -1.41 | -29.9 | -30.95 | no |
| full-M3 | +0.38 | -2.57 | -29.9 | -32.09 | no |
| full-M4 | +0.53 | -2.55 | -29.9 | -31.92 | no |
| full-M5 | +0.53 | +0.67 | +1.8 | +3.00 | yes |
| full+M6 | -0.13 | -3.09 | -30.5 | -33.72 | no |

Single-event checks (in rank order):

- full-M5: drop 156_sequence_38k (T1 +0.03), 147_sequence_3q (T2 -0.74), episode 332_sequence_99q|1030|209 (T3 +0.00) -> score -0.71 fail
- base+M1: drop 156_sequence_38k (T1 -0.15), 147_sequence_3q (T2 -0.74), episode 332_sequence_99q|1030|209 (T3 +0.00) -> score -0.89 fail

**Selected: base**

## Table III per episode (bootstrap 95% CI)

| split | config | vs | ΔRcv | CI95 | better/worse | frames |
|---|---|---|---|---|---|---|
| test | base+M1 | base | -6.1 | [-11.6, -1.1] | 2/8 | -52 |
| test | base+M6 | base | +1.1 | [-2.2, +5.3] | 2/3 | +9 |
| test | full | base | -20.6 | [-32.6, -7.4] | 3/21 | -175 |
| test | full+M6 | base | -22.6 | [-34.2, -9.4] | 3/23 | -192 |
| test | base | PEG | +0.0 | [+0.0, +0.0] | 0/0 | +0 |
| test | base+M1 | PEG | -6.1 | [-11.6, -1.1] | 2/8 | -52 |
| test | base+M6 | PEG | +1.1 | [-2.2, +5.3] | 2/3 | +9 |
| test | full | PEG | -20.6 | [-32.6, -7.4] | 3/21 | -175 |
| test | full+M6 | PEG | -22.6 | [-34.2, -9.4] | 3/23 | -192 |
| val | base+M1 | base | +1.8 | [+0.0, +5.6] | 1/0 | +10 |
| val | base+M6 | base | -0.7 | [-4.1, +2.4] | 4/4 | -4 |
| val | full | base | -29.9 | [-42.2, -17.0] | 1/15 | -171 |
| val | full+M6 | base | -30.5 | [-42.8, -17.5] | 1/15 | -174 |
| val | base | PEG | +0.0 | [+0.0, +0.0] | 0/0 | +0 |
| val | base+M1 | PEG | +1.8 | [+0.0, +5.6] | 1/0 | +10 |
| val | base+M6 | PEG | -0.7 | [-4.1, +2.4] | 4/4 | -4 |
| val | full | PEG | -29.9 | [-42.2, -17.0] | 1/15 | -171 |
| val | full+M6 | PEG | -30.5 | [-42.8, -17.5] | 1/15 | -174 |
| pooled | base+M1 | base | -3.0 | [-6.7, +0.5] | 3/8 | -42 |
| pooled | base+M6 | base | +0.4 | [-2.0, +3.2] | 6/7 | +5 |
| pooled | full | base | -24.3 | [-33.4, -15.0] | 4/36 | -346 |
| pooled | full+M6 | base | -25.8 | [-34.6, -16.5] | 4/38 | -366 |
| pooled | base | PEG | +0.0 | [+0.0, +0.0] | 0/0 | +0 |
| pooled | base+M1 | PEG | -3.0 | [-6.7, +0.5] | 3/8 | -42 |
| pooled | base+M6 | PEG | +0.4 | [-2.0, +3.2] | 6/7 | +5 |
| pooled | full | PEG | -24.3 | [-33.4, -15.0] | 4/36 | -346 |
| pooled | full+M6 | PEG | -25.8 | [-34.6, -16.5] | 4/38 | -366 |

## Firing counters (Table I, summed over sequences)

- test|base: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- val|base: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|base+M1: {'cone_matches(M1)': 10, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- val|base+M1: {'cone_matches(M1)': 6, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|base+M2: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- val|base+M2: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|base+M3: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- val|base+M3: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|base+M4: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 1, 'deglared_frames(M6)': 0}
- val|base+M4: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|base+M5: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- val|base+M5: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|base+M6: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 16709}
- val|base+M6: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 23129}
- test|full: {'cone_matches(M1)': 6, 'dormant_revivals(M4)': 1, 'deglared_frames(M6)': 0}
- val|full: {'cone_matches(M1)': 6, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|full-M1: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 1, 'deglared_frames(M6)': 0}
- val|full-M1: {'cone_matches(M1)': 0, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|full-M2: {'cone_matches(M1)': 10, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- val|full-M2: {'cone_matches(M1)': 6, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|full-M3: {'cone_matches(M1)': 5, 'dormant_revivals(M4)': 1, 'deglared_frames(M6)': 0}
- val|full-M3: {'cone_matches(M1)': 6, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|full-M4: {'cone_matches(M1)': 6, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- val|full-M4: {'cone_matches(M1)': 6, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|full-M5: {'cone_matches(M1)': 6, 'dormant_revivals(M4)': 1, 'deglared_frames(M6)': 0}
- val|full-M5: {'cone_matches(M1)': 6, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 0}
- test|full+M6: {'cone_matches(M1)': 10, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 16709}
- val|full+M6: {'cone_matches(M1)': 8, 'dormant_revivals(M4)': 0, 'deglared_frames(M6)': 23129}
