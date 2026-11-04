# YOLOX-X detector on GlareMOT2 (team task, 2026-10-26)

Asked by Minh (team chat): retrain the detector as YOLOX-X, fine-tuned from a crowd-pretrained MOT weight.

## Recipe and the decisions behind it
| Item | Choice | Why |
|---|---|---|
| Init weight | TrackTrack `mot20.pth.tar` (Drive id `1FunATdHrWfK95RiiEIw2GJ-gXB-tXMPB`; MOT20 + CrowdHuman), from 2026-10-28 | Minh: use the MOT20 model (crowded scenes). Runs before that used `mot17.pth.tar` (id `1MAb-Bhikx-fWe0VlJON_VMrYIyyyrt-F`; md5 differs). Paper §4.3: YOLOX-X from COCO, 80 epochs on the target set + CrowdHuman (+ WiderPerson), ByteTrack default config. Both load into YOLOX-X with all keys (99.0 M params). |
| Code | ByteTrack's YOLOX fork @ `d1bf019` | The weight was trained with it (RGB + ImageNet mean/std preprocessing; official YOLOX >= 0.2 does not normalise, so it would mis-read the weight). TrackTrack's repo ships inference only. |
| Data | GlareMOT2 official `train` split (71 seqs); `test` untouched | Minh: only train/test exist. |
| Train/val | per seq, first half of frames -> train, second half -> val | Minh; = ByteTrack's MOT17 "half" protocol. |
| Frame rate | stride = round(fps / 2.5) (every 8-10th frame) | Minh: 2-3 fps against near-duplicate frames. |
| Glare filter | drop a frame if any GT box has > 25 % saturated pixels (`saturation_map`: HSV V >= 0.92, S <= 0.35, the repo's definition) | Minh: detector learns visible people; burns are the tracker's job. Whole frame dropped (not just the box) so a burnt person is never a negative. Same filter on val. |
| Labels | `mot/gt/gt.txt` rows with visibility > 0, clipped | = `labels/` of the release. Frames in `meta/uncertain_frames.csv` dropped. |
| Hyper-params | ByteTrack MOT17 ablation: 800x1440, lr 0.001/64 per image, warmup 1, mosaic+mixup, NMS 0.7 | Fine-tune from a person detector: 20 epochs, last 5 without mosaic, eval every epoch. Note YOLOX's own default lr is 10x higher (0.01/64). |
| Selection | ByteTrack keeps `best_ckpt` by val AP50; both AP50 and AP50:95 logged | Epoch-0 AP of the init weight is measured first as the baseline. |

## Run log
- 2026-10-27 run 1: Drive answered "Quota exceeded" (per-file anonymous download quota of the GlareMOT2 zip, from the
  VM and from this machine) after 11290 / 14642 sampled frames. All 70 other seqs are complete; `400_sequence_morongmo`
  has 3984 / 7336 sampled frames. Built with `--no_fetch` (absent frames skipped) rather than wait for the quota.
  It only thins the over-represented MoRongMo seq.

- 2026-10-28: Minh fixed the MoRongMo (400) and nga3 (401) labels: `400_sequence_morongmo_fixed.zip`
  (Drive `1S64CCoC6sGWohE7IY4B8x2XBMCCrQKDW`) and `401_sequence_nga3_fixed.zip` (`1U7dOMaZxF5NcwPM914iTP3hE3zAG10qo`).
  The old labels put annotation frame k on image k, but the video runs at 25.037 fps. The lag grows to 98-100 frames
  (~4 s) by the end: 99.5 % of frames are shifted, 75 % by >= 1 s. Moving people get boxes at the wrong place.
  Apply a fix by copying its meta/, mot/ and extra images over the seq dir, then build with `--no_fetch`. The old-label
  run stopped at epoch 13 (`results/yolox_glaremot2_half_oldlabels/`, logs only; weights deleted 2026-11-04). The fixed-label run uses the MOT20 init.
- 2026-10-28 fixed-label run (MOT20 init): best epoch 15 (first epoch without mosaic). Val AP50 .888 / AP50:95 .424;
  val_half_nomrm .946 / .526 (init .641/.295 and .366/.153). Checkpoint deleted 2026-11-04 (logs kept in results/yolox_glaremot2_half_fixed/).
  The full-frame cache (scripts/26) stopped after 8/119 seqs (test 127-145): the anonymous Drive quota ran out again.
  Partial: results/yolox_dets_cache/dets_partial.tar. The VM was stopped to save CU. To resume, upload the partial dets
  (DONE seqs are skipped) and rerun once the quota is back, or read the zip with an authenticated account.
- 2026-10-28 TEST, once, epoch 15 (`configs/yolox/eval_split.py`; test.json rebuilt with the fixed nga3 labels:
  11863 imgs / 11208 boxes, `results/yolox_test_eval/`): AP50 .874 / AP50:95 .457; without 401_nga3 (62 % of test
  images) .910 / .537. Weakest: 136_2q .21, 322 .60, 320_116q .69, 318 .78, 401 .82. Local eval reproduces the VM's
  val_nomrm AP (.9445/.5268 vs .9457/.5255).
- 2026-11-02 fix 2 (Minh, `GlareMOT_annotations_updated_20261031-20261101.zip`, Drive `1e-TDdN2nTZ9yBDakUi476HVGrWPNd-sn`):
  23 cam-5 seqs (train 304 305 307 312 313 315 317 319 324 325 326 330 332; test 308 309 310 311 314 323 327 328 329 331)
  re-drawn as whole-person boxes: frame counts and timing unchanged, boxes ~20 % taller (top up 20-45 px, bottom down
  35-85 px), IoU with the old boxes ~0.5-0.75; 317/319 almost unchanged. labels/ = gt.txt; labels_all/ not updated.
  Both fixes now live in one overlay (`make_overlay.sh` -> /content/overlay) that scripts/25 and 26 copy over each seq
  (`--overlay`). Run 3 (account peg3 = tyler.ramirez, A100 80 GB, ~8.9 CU/h): same recipe and MOT20 init, then the
  val-chosen epoch is scored on test once and the full-frame cache is built for val_half + test only
  (`--splits val_half,test`, Minh). Local pulls: results/yolox_glaremot2_half_fix2/.
  A blocking cell did not keep this account's VM alive (lost twice ~30 min in); third try ran detached + keepalive.sh.
  Result: best epoch 15 again (val_half_nomrm AP50 .9465 / AP50:95 .5265; epochs 16-20 .942-.946). TEST once
  (test.json with both fixes, 11862 imgs / 11251 boxes): AP50 .880 / AP50:95 .484; without 401_nga3 .910 / .542
  (run 2 on old cam-5 test labels: .874/.457, .910/.537). nga3 .846/.384 (run 2 .818/.322). Weakest: 136 .24,
  322 .65, 320 .71, 318 .72. Cam-5 test seqs mostly gain AP50:95 (314 .38->.60, 331 .19->.47, 309 .51->.60).
  Log: results/yolox_glaremot2_half_fix2/test_eval.txt.
  Cache (val_half 71 + test 48, all frames, both fixes): anonymous quota blocked after 7 seqs, rclone's client hit its
  shared per-minute quota; done with the user's own OAuth client (drive_auth.py + push_token.sh). 119/119 seqs, checked
  (frame ranges, cam-5 gt sha256). results/yolox_glaremot2_half_fix2/dets.tar; Drive team folder:
  glaremot2_yolox_dets_fix2.zip (1XPU7xqfqqC8zAXhbtyX838_Ndqx77GhZ), weights yolox_x_glaremot2_fix2_best.zip
  (1DExg2ilth5RR4Y1BSA7s4IZu8rL-jbEh). Run 3 cost ~82 CU (500 -> 418).

## Files
- `scripts/25_build_yolox_glaremot.py`: streams only the sampled frames from the Drive zip -> COCO jsons + `build_stats_<split>.json`; `--split test` -> `test.json` (team cache).
- `yolox_x_glaremot2_half.py`: the exp (env `YX_DATA`, `YX_EPOCHS`, `YX_NO_AUG`, `YX_EXP_NAME`).
- `colab_setup.sh`: clone/pin ByteTrack, deps, disable its cython_bbox-only MOT evaluator, fetch the init weight.
- `eval_ckpt.py`: COCO AP of any checkpoint on the val set.
- `colab_run.sh`: baseline AP, train, AP of every epoch on `val_half_nomrm`; `colab_all.sh`: setup + overlay + build (train, test) + run + `colab_cache.sh` (best epoch, test AP once, det cache) + hold.
- `make_overlay.sh`: label fixes released after the zip (400/401 timing, 2026-11-01 cam-5 boxes) as one overlay dir.

## Commands (Colab VM)
All of it: upload a tarball of the needed repo files to `/content/pegcode.tgz`, then run `colab_all.sh` as a blocking
kernel cell (see AGENTS.md, Colab). The steps it runs:
```bash
python3 /content/PEG/scripts/25_build_yolox_glaremot.py --out /content/yx --workers 32
bash /content/PEG/configs/yolox/colab_setup.sh
cd /content/ByteTrack
PYTHONPATH=. python3 /content/PEG/configs/yolox/eval_ckpt.py /content/PEG/configs/yolox/yolox_x_glaremot2_half.py pretrained/tracktrack_mot17.pth.tar
PYTHONPATH=. python3 tools/train.py -f /content/PEG/configs/yolox/yolox_x_glaremot2_half.py -d 1 -b 16 --fp16 -o -c pretrained/tracktrack_mot17.pth.tar
```
