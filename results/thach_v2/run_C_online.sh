#!/bin/bash
cd /d/PROJECT/PEG
mkdir -p results/thach_v2/tune_C results/thach_v2/tune_C_strong
.venv/Scripts/python.exe results/thach_v2/tune_val.py --peg_c > results/thach_v2/tune_C/search.log 2>&1
.venv/Scripts/python.exe results/thach_v2/tune_val.py --peg_c --strong > results/thach_v2/tune_C_strong/search.log 2>&1
echo done > results/thach_v2/tune_C_online.done
