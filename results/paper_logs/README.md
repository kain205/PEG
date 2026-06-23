# Paper reproduction logs

Raw eval output backing the numbers reported in the paper. These are committed
verbatim from the eval harness (`scripts/06_eval_mot.py`) so the published figures
can be checked without re-running.

## `table1_real_test_peg.txt` — Table I (PEG row), real held-out test

Produced by:

```bash
GMOT_TRACKER=beacon python scripts/06_eval_mot.py --split test --tracker_name peg
```

The `COMBINED` line reproduces the paper's Table I PEG row exactly:

| HOTA | DetA | AssA | IDF1 | MOTA | IDSW |
|------|------|------|------|------|------|
| 68.20 | 65.89 | 71.62 | 82.30 | 80.62 | 17 |

Run with the deployed default config (`h=0.40`, `δ=3`, grace 5) and the shipped
detector + visibility-head weights. The anti glare-bloom phantom-birth guard is
disabled here (`GMOT_BIRTH_SIZE_GUARD=0`) to match the published numbers; enabling
it (the runtime default) slightly improves them (HOTA 68.34, IDF1 82.68, IDSW 15).
