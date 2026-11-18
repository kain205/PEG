---
name: exsort-emission-finding
description: 2026-11-18 ExSORT FP come from emitting coast boxes; tau<=3 emission clock (val-chosen) beats 3/11 and Minh's 1/2 s on test
metadata:
  type: project
---
ExSORT's 13k test FP come from *emitting* Kalman coast boxes (precision 17.6%), not from keeping identity. Output-only
rules (tracker state untouched) on the YOLOX fix2 cache, adapter env vars EXSORT_ROOT / EXSORT_COAST / EXSORT_TAU in
glaremot/baselines/t_exsort.py, run names ex_* under results/baselines_t1/runs/{val_half,test}:
- val_half (selection, pre-set rule: HOTA >= base-0.1, IDSW <= base, max MOTA): picked tau3 (emit iff frames since last
  high-score match <= 3). Val HOTA/MOTA/FP: old 53.61/74.76/14339 · Minh fps_budget 53.68/74.69/15728 · none 53.83/76.14/10385 · tau3 53.80/76.26/9891.
- test 48 seqs: old (0c25ef3 budget) 61.39 / IDF1 79.69 / MOTA 72.50 / IDSW 31 / FP 13041 · Minh b2bca1b fps_budget
  61.54 / 79.88 / 72.95 / 31 / 13102 (NOT his reported 59.50 or README 56.43) · none 62.30 / 81.50 / 77.07 / 33 / 6435 ·
  **tau3 62.49 / 81.75 / 77.70 / 32 / 5603**. Without 401 all ~63.9 HOTA.
Disclosure: Fable previewed none/tau3/tau12 on test before the val run (K grid + rule were fixed from val curves).
Break-even: a coast box helps DetA only if P(TP) > DetA/(1+DetA) ~ 0.37, MOTA only if > 0.5.
Next ideas not run: low-score match must not reset `unexplained` (kills phantom tracks, 60% of FP); existence log-odds/SPRT.
Diagnostics: scratchpad diag/ (lost after session). Related: [[exsort-is-team-method]]
