#!/bin/bash
# ExSORT output-policy matrix on the shared YOLOX fix2 cache (docs/EXSORT_FINDINGS.md). Usage: bash run_exsort_matrix.sh val_half|test
# Needs: results/baselines_t1/repos/exsort (0c25ef3) and results/baselines_t1/repos/exsort_b2bca1b
#   (git clone https://github.com/minhdq245/exsort <dir> && git -C <dir> checkout b2bca1b).
cd "$(dirname "$0")/../.."
R=results/baselines_t1/repos/exsort_b2bca1b
SPLIT=${1:-val_half}
run() { name=$1; shift; echo "== $name"; env "$@" .venv/bin/python scripts/28_run_baselines.py --tracker exsort --split $SPLIT --name $name 2>&1 | grep -E "COMBINED|Error|Traceback"; }
run ex_old    X=1 &                       # 0c25ef3, COAST_MODE=budget (coast up to MAX_AGE when glare explains)
run ex_minh   EXSORT_ROOT=$R &            # b2bca1b, COAST_MODE=fps_budget (1 s / 2 s)
run ex_none   EXSORT_COAST=none &         # no blind coast: emit only tracks matched this frame (= baselines' rule)
wait
for k in 3 6 12 25; do run ex_tau$k EXSORT_TAU=$k & done   # emit iff frames since last high-score match <= k
wait
echo MATRIX_DONE $SPLIT
