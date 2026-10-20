#!/bin/bash
cd /d/PROJECT/PEG
PY=.venv/Scripts/python.exe
T=results/thach_v2
$PY $T/tune_val.py --peg_c --test > $T/tune_C/test.log 2>&1 || { echo "C failed" > $T/tests.fail; exit 1; }
$PY $T/tune_val.py --peg_c --strong --test > $T/tune_C_strong/test.log 2>&1 || { echo "strong failed" > $T/tests.fail; exit 1; }
$PY $T/tune_val.py --peg_c --all --test > $T/tune_C_all/test.log 2>&1 || { echo "all failed" > $T/tests.fail; exit 1; }
echo done > $T/tests.done
