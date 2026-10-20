#!/bin/bash
cd /d/PROJECT/PEG
PY=.venv/Scripts/python.exe
T=results/thach_v2
mkdir -p $T/tune_C_lag $T/tune_C_all $T/tune_C_lag_all
s=$(date +%s)
$PY $T/tune_val.py --peg_c --lag > $T/tune_C_lag/search.log 2>&1 || { echo "lag failed" > $T/stages.fail; exit 1; }
echo "lag $(( $(date +%s) - s ))s" >> $T/stages.times; s=$(date +%s)
$PY $T/tune_val.py --peg_c --all > $T/tune_C_all/search.log 2>&1 || { echo "all failed" > $T/stages.fail; exit 1; }
echo "all $(( $(date +%s) - s ))s" >> $T/stages.times; s=$(date +%s)
k1=$($PY -c "import json;print(json.load(open('$T/tune_C/final.json'))['key'])")
k2=$($PY -c "import json;print(json.load(open('$T/tune_C_lag/final.json'))['key'])")
if [ "$k1" != "$k2" ]; then
  $PY $T/tune_val.py --peg_c --lag --all > $T/tune_C_lag_all/search.log 2>&1 || { echo "lag_all failed" > $T/stages.fail; exit 1; }
  echo "lag_all $(( $(date +%s) - s ))s" >> $T/stages.times
else
  echo "= tune_C_all (lag stage accepted nothing)" > $T/tune_C_lag_all/SKIPPED.txt
  echo "lag_all skipped" >> $T/stages.times
fi
echo done > $T/stages.done
