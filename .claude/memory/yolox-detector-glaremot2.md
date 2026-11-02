---
name: yolox-detector-glaremot2
description: "2026-10-26 team task (Minh): retrain detector as YOLOX-X on GlareMOT2 from TrackTrack weights; recipe, decisions, MoRongMo imbalance"
metadata:
  node_type: memory
  type: project
  originSessionId: ba71c7ef-b148-49b3-b0cd-856ddb377306
  modified: 2026-10-26T16:41:57.854Z
---

GlareMOT2 (219 GB Drive zip, official train 71 / test 48, no val) is the team's new dataset. Minh asked for the
detector to be retrained as YOLOX-X, fine-tuned from TrackTrack (CVPR 2025) weights. His rules: sample 2-3 fps, drop
frames where a GT box has >25 % saturated pixels (people only; glare is the tracker's job), train on the first half
of each train seq and validate on the second half. Minh's own try had its best epoch at 4 of 20 and looked bad.

The user said to answer obvious questions myself and ask only when it is really needed.
I decided: use the ByteTrack YOLOX fork (the weight's preprocessing), lr 0.001/64 (YOLOX's default is 10x that), drop
whole frames, and use the repo's `saturation_map`. Recipe: `configs/yolox/README.md`.

**Why it matters:** `400_sequence_morongmo` is ~half the sampled frames and 78 % of val boxes, so AP on plain val
mostly measures one video. Also score `val_half_nomrm`.

**How to apply:** compare to the init-weight AP (val AP50 .434). Swapping the detector also breaks h_psi, which taps
YOLO11m P3 features. Either retrain h_psi on YOLOX features or keep YOLO11m for h_psi. Related: [[morongmo-labeling-task]].

2026-10-28 run (fixed 400/401 labels from Minh; the old labels drifted up to 98 frames; MOT20 init per Minh):
val AP50 .641 -> .888 at epoch 15, the first epoch without mosaic. On val_half_nomrm: .366 -> .946 / AP50:95 .526.
The old-label MOT17 run peaked at ~.70 val AP50. Best checkpoint: results/yolox_glaremot2_half_fixed/ckpt/epoch_15_fp16.pth.
Next: full-frame det cache of all 119 seqs (scripts/26, configs/yolox/colab_cache.sh) for train_half/val_half/test.

2026-11-02 (Minh): labels fixed twice. Fix 1 = 400/401 timing; fix 2 = 23 cam-5 seqs (in both train and test) re-boxed
as whole person (`configs/yolox/make_overlay.sh`). Retrain on both fixes, then cache only val_half + test on the
unfiltered full-frame data. Colab: PEG has its own account, profile `peg3` (tyler.ramirez). acc2/douglas belongs to
LifeMate; the user set this split on 2026-11-02, so never run PEG jobs there. Run 3 pulls: results/yolox_glaremot2_half_fix2/.
