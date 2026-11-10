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
The old-label MOT17 run peaked at ~.70 val AP50. (Run 1/2 weights deleted 2026-11-04, logs kept.)
Next: full-frame det cache of all 119 seqs (scripts/26, configs/yolox/colab_cache.sh) for train_half/val_half/test.

2026-11-02 (Minh): labels fixed twice. Fix 1 = 400/401 timing; fix 2 = 23 cam-5 seqs (in both train and test) re-boxed
as whole person (`configs/yolox/make_overlay.sh`). Retrain on both fixes, then cache only val_half + test on the
unfiltered full-frame data. Colab: PEG has its own account, profile `peg3` (tyler.ramirez). acc2/douglas belongs to
LifeMate; the user set this split on 2026-11-02, so never run PEG jobs there. Run 3 pulls: results/yolox_glaremot2_half_fix2/.
Run 3 done 2026-11-03: best epoch 15, val_half_nomrm .9465/.5265; test (once) AP50 .880 / AP50:95 .484. Kept weight:
results/yolox_glaremot2_half_fix2/yolox_x_glaremot2_half_best_fp16.pth (Drive 1DExg2ilth5RR4Y1BSA7s4IZu8rL-jbEh);
cache zip val_half 71 + test 48 seqs on Drive 1XPU7xqfqqC8zAXhbtyX838_Ndqx77GhZ (team folder). Code in commits 9638d87, 939c1a4.
2026-11-04 owner decision: peg3 is LENT to LifeMate until the 2026-11-16 freeze. Do not stop its lifemate-* sessions;
mention it if peg3 CU drops below ~50. Ask the owner before starting PEG jobs on peg3 in that window.
2026-11-10: Table I baselines (8 methods, official repos via adapters in glaremot/baselines, scripts 27/28,
configs/baselines/README.md) re-run on the fix-2 YOLOX cache, test 48 seqs once: TrackTrack HOTA 58.88 best, DIP 51.28
last; table in configs/baselines/README.md. Lessons: /tmp is a RAM tmpfs on this WSL (never stream data there); peg3
Colab often "Service Unavailable" (capacity) -> home GPU under LifeMate's gpulock + systemd-run MemoryMax scope.
PEG on the same cache (option A, owner's choice 2026-11-10: analytic m_glare, present=1, scripts/29 saturation maps):
HOTA 58.19 all / 61.94 w/o 401 (TrackTrack 58.88 / 61.60); PEG best IDF1/IDSW w/o 401, worse MOTA (FP, esp. on 401).
