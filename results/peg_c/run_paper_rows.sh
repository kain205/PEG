#!/bin/bash
# PEG-C paper-setting rows (our repo, guard OFF, cached replays). Run once after val selection (online final: P + V K40 t2).
#   online rows     : pegc_test / pegc_fs / pegc_rcv / v_pegc_rcv
#   fixed-lag rows  : + GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=hidden : pegcl_test / pegcl_fs / pegcl_rcv / v_pegcl_rcv
cd /d/PROJECT/PEG
PY=.venv/Scripts/python.exe
for v in $(env | grep -o '^\(GPEG\|GBEACON\)_[A-Z_0-9]*'); do unset $v; done
unset GMOT_AM_DAMP GMOT_AM_SWAP GMOT_ADAPTIVE_MOTION GMOT_REID GMOT_DORMANT
export GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_VEL_K=40 GPEG_VEL_T=2
rows() { # prefix, extra env...
  local p=$1; shift
  env "$@" $PY scripts/06_eval_mot.py --split test --percep_cache results/percep_cache/real --tracker_name ${p}_test
  env "$@" $PY scripts/06_eval_mot.py --split test --data_root datasets/synth --results_subdir eval_synthfs --percep_cache results/percep_cache/synth --tracker_name ${p}_fs
  env "$@" $PY scripts/07_eval_recovery.py --split test --percep_cache results/percep_cache/synth --tracker_name ${p}_rcv
  env "$@" $PY scripts/07_eval_recovery.py --split val --percep_cache results/percep_cache/synth --tracker_name v_${p}_rcv
}
rows pegc GPEG_X=0
rows pegcl GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=hidden
echo ROWS_DONE
# --- Stage 2b (Addendum 2): B on PEG+ without V (val-chosen B[3] = L90, mode all). Label: fixed-lag 90 (B on PEG+). ---
rows_bl() {
  env GPEG_SIZE_LOCK=1 GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=all GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 \
    $PY scripts/06_eval_mot.py --split test --percep_cache results/percep_cache/real --tracker_name pegcbl_test
  env GPEG_SIZE_LOCK=1 GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=all GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 \
    $PY scripts/06_eval_mot.py --split test --data_root datasets/synth --results_subdir eval_synthfs --percep_cache results/percep_cache/synth --tracker_name pegcbl_fs
  env GPEG_SIZE_LOCK=1 GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=all GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 \
    $PY scripts/07_eval_recovery.py --split test --percep_cache results/percep_cache/synth --tracker_name pegcbl_rcv
  env GPEG_SIZE_LOCK=1 GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=all GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 \
    $PY scripts/07_eval_recovery.py --split val --percep_cache results/percep_cache/synth --tracker_name v_pegcbl_rcv
}
# rows_bl   # (run once; commented so re-sourcing the file does not re-run)
