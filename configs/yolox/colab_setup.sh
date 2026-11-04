#!/bin/bash
# Colab VM setup for the YOLOX fine-tune (see configs/yolox/README.md). Idempotent.
set -e
cd /content
[ -d ByteTrack ] || git clone -q https://github.com/ifzhang/ByteTrack.git
cd ByteTrack && git checkout -q d1bf0191adff59bc8fcfeaa0b33d3d1642552a99
pip install -q loguru thop tabulate pycocotools ninja lap
# detector-only use: the MOT evaluator needs cython_bbox (tracking), which we do not train/eval with
sed -i 's/^from .mot_evaluator import MOTEvaluator/# &  (disabled: needs cython_bbox)/' yolox/evaluators/__init__.py
# keep every epoch's checkpoint (EMA weights) so each can be scored on more than one val set afterwards
grep -q 'ckpt_name="epoch_' yolox/core/trainer.py || sed -i 's/^\(        \)self.save_ckpt(ckpt_name="latest")$/&\n\1self.save_ckpt(ckpt_name="epoch_{}".format(self.epoch + 1))/' yolox/core/trainer.py
# COCOeval_opt needs the compiled yolox._C; use pycocotools' COCOeval (same AP numbers)
sed -i 's/^            from yolox.layers import COCOeval_opt as COCOeval$/            from pycocotools.cocoeval import COCOeval/' yolox/evaluators/coco_evaluator.py
mkdir -p pretrained
# TrackTrack (CVPR 2025) YOLOX-X detector for MOT17 test: COCO -> MOT17 + CrowdHuman + WiderPerson, 80 epochs
[ -s pretrained/tracktrack_mot17.pth.tar ] || curl -sSL -o pretrained/tracktrack_mot17.pth.tar \
  "https://drive.usercontent.google.com/download?id=1MAb-Bhikx-fWe0VlJON_VMrYIyyyrt-F&export=download&confirm=t"
# TrackTrack YOLOX-X detector for MOT20 test (MOT20 + CrowdHuman): the init Minh asked for (crowded scenes)
[ -s pretrained/tracktrack_mot20.pth.tar ] || curl -sSL -o pretrained/tracktrack_mot20.pth.tar \
  "https://drive.usercontent.google.com/download?id=1FunATdHrWfK95RiiEIw2GJ-gXB-tXMPB&export=download&confirm=t"
echo SETUP_DONE
