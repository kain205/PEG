#!/bin/bash
# Local side of the YOLOX lane: every few minutes pull the run log, the train log and each new epoch checkpoint off
# the Colab VM, so a lost VM costs at most one epoch (resume: upload the newest full ckpt to
# /content/resume_ckpt.pth.tar and relaunch colab_all.sh). Every epoch is kept as a model-only fp16 copy (~200 MB);
# only the newest full checkpoint (with optimizer, ~800 MB, needed to resume) is kept.
# Usage: bash configs/yolox/pull_ckpts.sh [session] [out_dir]    (stops when the VM reports HOLDING, after the last pull)
SESS=${1:-peg}
OUT=${2:-results/yolox_glaremot2_half}
P=$HOME/Projects/gemma4ever/.local/colab-profiles/${COLAB_PROFILE:-peg3}
C="env HOME=$P SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt $HOME/Projects/gemma4ever/.venv/bin/colab --auth=oauth2"
REMOTE=/content/ByteTrack/YOLOX_outputs/yolox_x_glaremot2_half
mkdir -p $OUT/ckpt
while true; do
  $C download -s $SESS /content/yx_run.log $OUT/yx_run.log >/dev/null 2>&1 || echo "$(date +%T) run log not reachable"
  $C download -s $SESS $REMOTE/train_log.txt $OUT/train_log.txt >/dev/null 2>&1
  for ck in $($C ls -s $SESS $REMOTE 2>/dev/null | grep -o 'epoch_[0-9]*_ckpt.pth.tar' | sort -V); do
    n=${ck#epoch_}; n=${n%%_*}
    [ -s $OUT/ckpt/epoch_${n}_fp16.pth ] && continue
    # the trainer writes epoch N's file right after epoch N; skip it until it stops growing (next listing)
    if $C download -s $SESS $REMOTE/$ck $OUT/ckpt/$ck.part >/dev/null 2>&1 \
       && .venv/bin/python -c "import sys,torch; sd=torch.load(sys.argv[1],map_location='cpu',weights_only=True)['model']; torch.save({'model':{k:v.half() for k,v in sd.items()}}, sys.argv[2])" $OUT/ckpt/$ck.part $OUT/ckpt/epoch_${n}_fp16.pth; then
      mv $OUT/ckpt/$ck.part $OUT/ckpt/latest_full_ckpt.pth.tar
      echo "$(date +%T) pulled epoch $n"
    else
      rm -f $OUT/ckpt/$ck.part $OUT/ckpt/epoch_${n}_fp16.pth
    fi
  done
  grep -q HOLDING $OUT/yx_run.log 2>/dev/null && { echo "$(date +%T) VM holding: final pull done"; break; }
  sleep 300
done
