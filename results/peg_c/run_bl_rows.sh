#!/bin/bash
cd /d/PROJECT/PEG
PY=.venv/Scripts/python.exe
for v in $(env | grep -o '^\(GPEG\|GBEACON\)_[A-Z_0-9]*'); do unset $v; done
unset GMOT_AM_DAMP GMOT_AM_SWAP GMOT_ADAPTIVE_MOTION GMOT_REID GMOT_DORMANT
E="GPEG_SIZE_LOCK=1 GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=all GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0"
$PY results/thach_v2/tune_val.py --peg_c --lag_base --test > results/thach_v2/tune_C_lagP/test.log 2>&1 || { echo failedH > results/peg_c/bl.fail; exit 1; }
env $E $PY scripts/06_eval_mot.py --split test --percep_cache results/percep_cache/real --tracker_name pegcbl_test
env $E $PY scripts/06_eval_mot.py --split test --data_root datasets/synth --results_subdir eval_synthfs --percep_cache results/percep_cache/synth --tracker_name pegcbl_fs
env $E $PY scripts/07_eval_recovery.py --split test --percep_cache results/percep_cache/synth --tracker_name pegcbl_rcv
env $E $PY scripts/07_eval_recovery.py --split val --percep_cache results/percep_cache/synth --tracker_name v_pegcbl_rcv
echo done > results/peg_c/bl.done
