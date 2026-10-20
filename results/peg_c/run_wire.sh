#!/bin/bash
# WP1b wiring runs (no metrics read). counters -> results/peg_c/wire/<name>.jsonl, stdout -> <name>.log
cd /d/PROJECT/PEG
PY=.venv/Scripts/python.exe
export GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_VEL_K=40 GPEG_F_STATS=1
SEQS="187_sequence_66q_new 133_sequence_17q_new 147_sequence_3q_new 178_sequence_58q_new"
ALL="GPEG_CAP=48 GPEG_STITCH_K=1.5 GPEG_BACKFILL_L=90 GPEG_BACKBIRTH=1"
rm -f results/peg_c/wire/*.jsonl
t3() { n=$1; shift; env "$@" GPEG_F_STATS_OUT=results/peg_c/wire/$n.jsonl $PY scripts/07_eval_recovery.py --split val --percep_cache results/percep_cache/synth --seqs $SEQS --tracker_name $n > results/peg_c/wire/$n.log 2>&1; }
t1() { n=$1; shift; env "$@" GPEG_F_STATS_OUT=results/peg_c/wire/$n.jsonl $PY scripts/06_eval_mot.py --split val --percep_cache results/percep_cache/real --tracker_name $n > results/peg_c/wire/$n.log 2>&1; }
t3 wire_online GPEG_CAP=48 GPEG_STITCH_K=1.5
t3 wire_pegc_all $ALL GPEG_BACKFILL_MODE=all
t3 wire_pegc_hid $ALL GPEG_BACKFILL_MODE=hidden
t1 wire_online_t1 GPEG_CAP=48 GPEG_STITCH_K=1.5
t1 wire_pegc_all_t1 $ALL GPEG_BACKFILL_MODE=all
t1 wire_pegc_hid_t1 $ALL GPEG_BACKFILL_MODE=hidden
echo finished > results/peg_c/wire/DONE
