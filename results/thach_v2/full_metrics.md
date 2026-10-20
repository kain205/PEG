### val

| config | T1 HOTA | T1 IDF1 | T1 MOTA | T1 IDSW | T2 HOTA | T2 IDF1 | T2 MOTA | T3 Rcv@.5 | T3 total | T3 ID-off | where the change vs PEG sits |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PEG | 70.24 | 86.35 | 82.06 | 15 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | **10.0** |  |
| PEG+ (ours) | 70.11 | 86.06 | 82.20 | 17 | 76.30 | 89.24 | 89.80 | 67.3 | 66.3 | **10.0** |  |
| PEG + M1 cone [M1c[0]] | **70.66** | **86.93** | 82.03 | 16 | 77.56 | 91.20 | 89.76 | 67.6 | 67.4 | **10.0** | T1 +0.42: top 156 +3.7, without it -0.01; T2 +1.31: top 147 +10.0, without it +0.00 |
| PEG + M1 damping [M1d[0]] | 70.24 | 86.29 | 82.17 | **13** | 75.77 | 88.72 | 89.88 | 69.4 | 68.8 | **10.0** | T2 -0.48: top 332 +0.7, without it -0.55; T3 +1.8: 1 ep. better / 0 worse, without top (332) +0.00 |
| PEG + M3 dyn-h/TTL [M3[0]] | 70.28 | 86.45 | 82.28 | 15 | 76.25 | 89.20 | 89.76 | 67.6 | 67.4 | **10.0** |  |
| PEG + M1 adaptive Q [M1q[0]] | 70.24 | 86.35 | 82.06 | 15 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | **10.0** |  |
| PEG + M2 Re-ID [M2[0]] | 70.24 | 86.35 | 82.06 | 15 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | **10.0** |  |
| PEG + M4 dormant [M4[0]] | 70.24 | 86.35 | 82.06 | 15 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | **10.0** |  |
| PEG + M5 anchor [M5[2]] | 70.26 | 86.41 | 82.17 | 15 | 76.18 | 89.16 | 89.66 | 67.4 | 67.4 | **10.0** |  |
| PEG + his ID-resolver rewrite [R[0]] | 69.98 | 85.76 | 82.00 | 28 | 76.25 | 89.19 | 89.73 | 67.6 | 67.4 | **10.0** |  |
| PEG + M6 tone-map [M6[0]] | 70.14 | 85.82 | 81.60 | 18 | 75.52 | 87.92 | 89.72 | 66.9 | 64.2 | **10.0** | T2 -0.73: top 315 +0.4, without it -0.73; T3 -0.7: 4 ep. better / 4 worse, without top (178) -1.68 |
| Thach full+M6 (his params, tuned on test) | 69.85 | 85.37 | 81.75 | 48 | 73.16 | 85.30 | 86.62 | 37.1 | 32.6 | 21.9 |  |
| STRONGEST (val, no single-event check): M1c[0] + M1d[0] | 70.63 | 86.87 | 82.14 | 14 | 77.09 | 90.71 | 89.94 | 69.4 | 68.8 | **10.0** | T1 +0.39: top 156 +3.3, without it +0.04; T2 +0.84: top 147 +6.2, without it +0.05; T3 +1.8: 1 ep. better / 0 worse, without top (332) +0.00 |
| STRONGEST with PEG+ by design: M1c[0] + P[0] | 70.54 | 86.64 | 82.16 | 18 | **77.63** | **91.24** | 89.84 | 67.3 | 66.3 | **10.0** | T1 +0.30: top 156 +3.9, without it -0.20; T2 +1.38: top 147 +10.6, without it -0.01 |
| PEG-O (P+O, best val point τ .08 γ 4; rejected by val) | 70.11 | 86.06 | 82.20 | 17 | 74.75 | 87.11 | 88.02 | 53.8 | 46.5 | 34.2 | T2 -1.50: top 147 +6.1, without it -2.65; T3 -13.8: 4 ep. better / 5 worse, without top (147) -16.35 |
| PEG-C online (P + V K40 t2; val-chosen) | 69.67 | 84.96 | 82.78 | 16 | 76.20 | 88.63 | 91.27 | **75.8** | **74.1** | **10.0** | T1 -0.57: top 195 +0.1, without it -0.72; T3 +8.2: 9 ep. better / 1 worse, without top (187) +6.90 |
| PEG-C fixed-lag 90 (B hidden; rejected by val) | 69.70 | 85.00 | **82.85** | 16 | 76.20 | 88.63 | 91.27 | **75.8** | **74.1** | **10.0** | T1 -0.54: top 195 +0.2, without it -0.72; T3 +8.2: 9 ep. better / 1 worse, without top (187) +6.90 |
| PEG-C strongest (+ S stitch k 1.0) | 69.67 | 84.96 | 82.78 | 16 | 77.50 | 90.24 | 91.36 | **75.8** | **74.1** | **10.0** | T1 -0.57: top 195 +0.1, without it -0.72; T2 +1.25: top 147 +11.4, without it -0.29; T3 +8.2: 9 ep. better / 1 worse, without top (187) +6.90 |
| ALL = PEG-C + Thach greedy (M1 cone) | 70.09 | 85.55 | 82.75 | 17 | 77.49 | 90.25 | **91.38** | **75.8** | **74.1** | **10.0** | T2 +1.24: top 147 +11.3, without it -0.29; T3 +8.2: 9 ep. better / 1 worse, without top (187) +6.90 |
| PEG-C fixed-lag 90 (B all on PEG+; val-chosen) | 70.15 | 86.20 | 82.46 | 17 | 77.08 | 89.66 | 90.62 | 71.1 | 70.6 | **10.0** | T2 +0.83: top 141 +3.9, without it +0.69; T3 +3.5: 4 ep. better / 3 worse, without top (141) +1.46 |

S (armed survival): byte-identical to PEG+ on val, never fires. ALL (Stage B: PEG-O's Stage-A final + Thach greedy) = Stage-A final is PEG+, so ALL = 'STRONGEST with PEG+ by design' above. PEG-C: lag stage (B, BB) on top of V accepted nothing (B hidden ±0.03, B all T3 −2.1; BB never fires); C (cap) ≤ +0.09; tune_C_lag_all = tune_C_all. Stage 2b (B on PEG+, no V): B[3] (L90, all) accepted on val (fixed-lag; test run once in this harness).

Best overall (chosen on val by ΣΔ T1 HOTA + T2 HOTA + T3 Rcv@.5 vs PEG): ALL = PEG-C + Thach greedy (M1 cone) — val ΣΔ +9.29; test: T1 HOTA 68.78, T2 HOTA 61.35, T3 Rcv@.5 81.20

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
| PEG + M6 tone-map [M6[0]] | 69.39 | 85.00 | 80.56 | **13** | 62.84 | 77.49 | 73.34 | 77.3 | 78.9 | 18.5 | T1 +1.05: top 129 +23.5, without it +0.06; T2 +1.43: top 129 +23.5, without it +0.12; T3 +1.1: 2 ep. better / 3 worse, without top (316) -0.49 |
| Thach full+M6 (his params, tuned on test) | **70.03** | **87.03** | 80.43 | 29 | 61.21 | 77.56 | 69.48 | 53.6 | 55.4 | **10.5** |  |
| STRONGEST (val, no single-event check): M1c[0] + M1d[0] | 68.46 | 82.94 | 80.91 | 16 | 60.41 | 73.28 | 73.20 | 70.0 | 73.8 | 15.5 | T2 -1.00: top 204 +9.4, without it -1.66; T3 -6.2: 2 ep. better / 8 worse, without top (204) -7.34 |
| STRONGEST with PEG+ by design: M1c[0] + P[0] | 68.44 | 82.71 | 80.88 | 15 | **63.14** | **78.50** | 75.05 | 83.1 | 85.1 | 11.6 | T2 +1.73: top 204 +11.5, without it +1.13; T3 +6.9: 6 ep. better / 2 worse, without top (325) +4.65 |
| PEG-O (P+O, best val point τ .08 γ 4; rejected by val) | – | – | – | – | – | – | – | – | – | – | not run on test: rejected on val |
| PEG-C online (P + V K40 t2; val-chosen) | 68.80 | 84.26 | 80.98 | 15 | 60.89 | 74.61 | 74.55 | 80.4 | 81.8 | 18.5 | T1 +0.46: top 320 +2.9, without it +0.26; T2 -0.52: top 320 +4.6, without it -1.27; T3 +4.2: 6 ep. better / 6 worse, without top (325) +1.84 |
| PEG-C fixed-lag 90 (B hidden; rejected by val) | – | – | – | – | – | – | – | – | – | – | not run in this harness: rejected on val; paper-setting row in results/peg_c |
| PEG-C strongest (+ S stitch k 1.0) | 68.86 | 84.34 | **81.16** | 14 | 62.67 | 78.29 | **75.55** | 81.2 | 81.8 | **10.5** | T1 +0.52: top 320 +2.9, without it +0.34; T2 +1.26: top 135 +20.1, without it +0.20; T3 +5.0: 6 ep. better / 6 worse, without top (325) +2.69 |
| ALL = PEG-C + Thach greedy (M1 cone) | 68.78 | 84.24 | 80.95 | 15 | 61.35 | 75.45 | 75.13 | 81.2 | 81.8 | 11.6 | T1 +0.44: top 320 +2.9, without it +0.25; T3 +5.0: 6 ep. better / 6 worse, without top (325) +2.69 |
| PEG-C fixed-lag 90 (B all on PEG+; val-chosen) | 68.50 | 82.82 | 81.01 | 15 | 62.74 | 77.90 | 74.72 | **86.5** | **86.2** | 15.5 | T2 +1.33: top 176 +8.3, without it +0.71; T3 +10.3: 8 ep. better / 0 worse, without top (325) +8.20 |

S (armed survival): byte-identical to PEG+ on val, never fires. ALL (Stage B: PEG-O's Stage-A final + Thach greedy) = Stage-A final is PEG+, so ALL = 'STRONGEST with PEG+ by design' above. PEG-C: lag stage (B, BB) on top of V accepted nothing (B hidden ±0.03, B all T3 −2.1; BB never fires); C (cap) ≤ +0.09; tune_C_lag_all = tune_C_all. Stage 2b (B on PEG+, no V): B[3] (L90, all) accepted on val (fixed-lag; test run once in this harness).

Best overall (chosen on val by ΣΔ T1 HOTA + T2 HOTA + T3 Rcv@.5 vs PEG): ALL = PEG-C + Thach greedy (M1 cone) — val ΣΔ +9.29; test: T1 HOTA 68.78, T2 HOTA 61.35, T3 Rcv@.5 81.20
