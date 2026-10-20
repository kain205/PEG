#!/bin/bash
cd /d/PROJECT/PEG
PY=.venv/Scripts/python.exe
T=results/thach_v2
mkdir -p $T/tune_C_lagP $T/tune_C_lagP_strong
s=$(date +%s)
$PY $T/tune_val.py --peg_c --lag_base > $T/tune_C_lagP/search.log 2>&1 || { echo failed1 > $T/lagP.fail; exit 1; }
echo "strict $(( $(date +%s) - s ))s" >> $T/lagP.times; s=$(date +%s)
$PY $T/tune_val.py --peg_c --lag_base --strong > $T/tune_C_lagP_strong/search.log 2>&1 || { echo failed2 > $T/lagP.fail; exit 1; }
echo "strong $(( $(date +%s) - s ))s" >> $T/lagP.times
echo done > $T/lagP.done
