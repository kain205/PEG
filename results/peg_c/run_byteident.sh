#!/bin/bash
# PEG-C implementation check 2: flags unset => byte-identical MOT txt vs existing PEG / PEG+ runs (cached, guard off).
cd /d/PROJECT/PEG
PY=.venv/Scripts/python.exe
unset $(env | grep -o '^GPEG_[A-Z_0-9]*' | tr '\n' ' ') 2>/dev/null
export GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0
run() { # label, extra env, cmd...
  local t0=$(date +%s); local label=$1; shift
  env "$@" ; echo "TIME $label $(( $(date +%s) - t0 ))s"
}
run T1_peg   GPEG_X=0 $PY scripts/06_eval_mot.py --split test --percep_cache results/percep_cache/real --tracker_name bic_peg
run T1_pegp  GPEG_SIZE_LOCK=1 $PY scripts/06_eval_mot.py --split test --percep_cache results/percep_cache/real --tracker_name bic_pegplus
run T2_peg   GPEG_X=0 $PY scripts/06_eval_mot.py --split test --data_root datasets/synth --results_subdir eval_synthfs --percep_cache results/percep_cache/synth --tracker_name bic_peg_fs
run T2_pegp  GPEG_SIZE_LOCK=1 $PY scripts/06_eval_mot.py --split test --data_root datasets/synth --results_subdir eval_synthfs --percep_cache results/percep_cache/synth --tracker_name bic_pegplus_fs
run T3_peg   GPEG_X=0 $PY scripts/07_eval_recovery.py --split test --percep_cache results/percep_cache/synth --tracker_name bic_peg_rcv
run T3_pegp  GPEG_SIZE_LOCK=1 $PY scripts/07_eval_recovery.py --split test --percep_cache results/percep_cache/synth --tracker_name bic_pegplus_rcv
echo DONE
