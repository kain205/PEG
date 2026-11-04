#!/bin/bash
# Baseline AP of the init weight, then the fine-tune, then AP of every epoch on both val sets. Log: /content/yx_run.log
set -e
cd /content/ByteTrack
export PYTHONPATH=/content/ByteTrack
EXP=/content/PEG/configs/yolox/yolox_x_glaremot2_half.py
# init weight: TrackTrack MOT20 YOLOX-X (Minh, 2026-10-28; runs before that used tracktrack_mot17)
INIT=${YX_INIT:-pretrained/tracktrack_mot20.pth.tar}
# val without MoRongMo (one 49-min video = half the sampled frames and 78 % of val boxes)
python3 - <<'PY'
import json
v = json.load(open('/content/yx/annotations/val_half.json'))
keep = {x['id'] for x in v['videos'] if not x['file_name'].startswith('400_')}
ims = [i for i in v['images'] if i['video_id'] in keep]; ids = {i['id'] for i in ims}
v.update(images=ims, annotations=[a for a in v['annotations'] if a['image_id'] in ids])
json.dump(v, open('/content/yx/annotations/val_half_nomrm.json', 'w'))
print('val_half_nomrm', len(ims), 'imgs', len(v['annotations']), 'boxes')
PY
if [ -s /content/resume_ckpt.pth.tar ]; then
  # a lost VM: continue from the last epoch checkpoint pulled to the local machine and uploaded back
  echo "== resume from /content/resume_ckpt.pth.tar"
  python3 tools/train.py -f $EXP -d 1 -b ${YX_BATCH:-16} --fp16 -o --resume -c /content/resume_ckpt.pth.tar
else
  for va in val_half val_half_nomrm; do
    echo "== epoch 0 (init) $va"; YX_VAL_ANN=$va.json python3 /content/PEG/configs/yolox/eval_ckpt.py $EXP $INIT 16 2>&1 | grep -E 'RESULT|Error' || true
  done
  python3 tools/train.py -f $EXP -d 1 -b ${YX_BATCH:-16} --fp16 -o -c $INIT
fi
OUT=YOLOX_outputs/yolox_x_glaremot2_half
for ck in $(ls $OUT/epoch_*_ckpt.pth.tar | sort -V); do
  echo "== $(basename $ck) val_half_nomrm"; YX_VAL_ANN=val_half_nomrm.json python3 /content/PEG/configs/yolox/eval_ckpt.py $EXP $ck 16 2>&1 | grep -E 'RESULT|Error' || true
done
echo RUN_DONE
