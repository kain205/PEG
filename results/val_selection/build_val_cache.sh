#!/usr/bin/env bash
# Build val-split perception caches (live detector, records on first run) + appearance sidecars.
# Also yields the live PEG val baselines (v_peg_live*). Re-runnable: --resume skips finished seqs.
set -u
cd "$(dirname "$0")/../.."
PY=.venv/Scripts/python.exe
L=results/val_selection/logs
export GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0
$PY scripts/06_eval_mot.py --split val --percep_cache results/percep_cache/real --tracker_name v_peg_live --resume > $L/build_t1.log 2>&1; echo "t1 exit $?"
$PY scripts/06_eval_mot.py --split val --data_root datasets/synth --results_subdir eval_synthfs --percep_cache results/percep_cache/synth --tracker_name v_peg_live_fs --resume > $L/build_t2.log 2>&1; echo "t2 exit $?"
$PY scripts/07_eval_recovery.py --split val --percep_cache results/percep_cache/synth --tracker_name v_peg_live_rcv > $L/build_t3.log 2>&1; echo "t3 exit $?"
$PY scripts/12_cache_appearance.py --split val --cache_dir results/percep_cache/real --data_root datasets/real > $L/build_app_real.log 2>&1; echo "app real exit $?"
$PY scripts/12_cache_appearance.py --split val --cache_dir results/percep_cache/synth --data_root datasets/synth > $L/build_app_synth.log 2>&1; echo "app synth exit $?"
echo DONE
