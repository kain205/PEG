#!/bin/bash
# After training (called by colab_all.sh before it holds the VM): pick the best epoch, score it on test once, then
# build the full-frame detection cache with it (Minh 2026-11-02: val_half + test; the dataset as is, no glare filter).
# Best epoch = highest AP50 on val_half_nomrm (val without MoRongMo; the test seqs have no such scene), AP50:95 breaks ties.
# Logs: /content/test_eval.txt, /content/cache_run.log. Output: /content/dets (+ /content/dets.tar when done).
set -e
cd /content/ByteTrack
export PYTHONPATH=/content/ByteTrack
OUT=YOLOX_outputs/yolox_x_glaremot2_half
BEST=$(python3 - <<'PY'
import re
log = open("/content/yx_run.log").read()
r = re.findall(r"== (epoch_\d+)_ckpt.pth.tar val_half_nomrm\n.*?RESULT AP50_95 ([\d.]+) AP50 ([\d.]+)", log)
best = max(r, key=lambda t: (float(t[2]), float(t[1])))
print(best[0])
PY
)
echo "best epoch by val_half_nomrm AP50: $BEST"
grep -A1 "== ${BEST}_ckpt" /content/yx_run.log | tail -1 || true
python3 -c "import sys,torch; sd=torch.load(sys.argv[1],map_location='cpu',weights_only=True)['model']; torch.save({'model':{k:v.half() for k,v in sd.items()}}, sys.argv[2])" \
  $OUT/${BEST}_ckpt.pth.tar /content/yolox_x_glaremot2_half_best_fp16.pth
echo "$BEST" > /content/best_epoch.txt
if [ -s /content/yx/annotations/test.json ] && [ ! -s /content/test_eval.txt ]; then
  python3 /content/PEG/configs/yolox/eval_split.py --data /content/yx --ann test.json \
    --ckpt /content/yolox_x_glaremot2_half_best_fp16.pth --drop 401_ > /content/test_eval.txt 2>&1 || echo TEST_EVAL_FAILED
  grep RESULT /content/test_eval.txt || true
fi
python3 /content/PEG/scripts/26_cache_yolox_dets.py --exp /content/PEG/configs/yolox/yolox_x_glaremot2_half.py \
  --ckpt /content/yolox_x_glaremot2_half_best_fp16.pth --out /content/dets --overlay /content/overlay \
  --splits ${CACHE_SPLITS:-val_half,test} ${CACHE_ARGS} 2>&1 | tee -a /content/cache_run.log | grep --line-buffered -E '^\[|CACHE_DONE|Error|Traceback'
grep -q CACHE_DONE /content/cache_run.log
tar cf /content/dets.tar -C /content dets
echo CACHE_TAR_DONE
