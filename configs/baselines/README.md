# Table I baselines on GlareMOT2 (YOLOX-X cache)

Team task (Minh, 2026-11-09): re-run the 8 baselines of the paper's Table I on the team's YOLOX-X detection cache
(GlareMOT2, both label fixes; `configs/yolox/README.md`). Only Table I (real-data MOT). Every method gets the same
detections and the same ReID model; only the tracker differs.

## Data
- Detections: `results/yolox_glaremot2_half_fix2/dets.tar` (scripts/26): every box with score >= 0.1 after NMS 0.95
  and 0.8, native pixels. Each method's own NMS (0.7 for the YOLOX MOT pipelines) is re-run on the 0.95 rows; greedy
  NMS at t < 0.95 on NMS-0.95 output equals NMS at t on the raw output except in rare suppression chains. Score
  thresholds are the trackers' own (all >= 0.1, so filtering the cache is exact).
- Splits: `test` = the 48 official test seqs, every frame (Table I, each method run once, no tuning);
  `val_half` = second half of the 71 train seqs (sanity runs; any choice would be made here).
- Features (scripts/27, Colab): FastReID SBS-S50 MOT20 weights (BoT-SORT/DiffMOT release) for every cached box,
  cropped exactly like TrackTrack/Deep-OC-SORT (round + clip, RGB, 128x384, fp16, L2); BoT-SORT `sparseOptFlow`
  GMC (downscale 2) per frame; MegaDepth disparity for DIP (384x512 input as in DIP's demo, stored 96x128 uint8).
  The paper's own FastReID was fine-tuned on mine data and is not available; the user chose the public MOT20 model.

## Methods (official repos, cloned to `results/baselines_t1/repos`, unmodified; adapters in `glaremot/baselines`)
| key | repo @ commit | settings (no per-seq hacks, online, no interpolation) |
|---|---|---|
| bytetrack | ifzhang/ByteTrack @ d1bf019 | track 0.6, match 0.9, buffer 30 (frame_rate 30 as its evaluator), min area 100 |
| ocsort | noahcao/OC_SORT @ 8462e7e | det 0.6, iou 0.3, delta_t 3, inertia 0.2, max_age 30, min area 10 |
| deepocsort | GerardMaggiolino/Deep-OC-SORT @ 6bb51d0 | README MOT17: grid off, new KF off, w_emb 0.75, aw 0.5, det 0.6 |
| botsort | NirAharon/BoT-SORT @ 2519854 | --default-parameters --with-reid MOT17: high 0.6, low 0.1, new 0.7, match 0.8, prox 0.5, app 0.25 |
| hybridsort | ymzis69/HybridSORT @ 396f8d3 | MOT17 ReID exp: byte, hmiou 0.25, TCM, EG 1.3/1.2, long-term correction; min area 100 |
| tracktrack | kamkyu94/TrackTrack @ ee7f1c5 | MOT17 default branch: det 0.6, init 0.7, match 0.7, penalties 0.2/0.4, tai 0.55, lost 2*fps |
| diffmot | Kroery/DiffMOT @ eada72e | MOT17 test cfg: high 0.6, low 0.1, w_emb 2.2, aw 1.7; D2MP `MOT_epoch800.pt`, seed 123 |
| dip | tarashakhurana/detecting-invisible-people @ 3b01416 | run_forecast_filtering.sh flags (conf 0.3, occluded 1.06, free-space 1.14, cosine 0.2); released code does not run, reconstructed (t_dip.py). Det NMS 0.7: DIP ran on FRCNN public dets already NMSed by their detector; on the 0.95 rows it starts a track per duplicate box (val smoke HOTA 25 vs 52), decided on val |

Shared deviations: cached sparseOptFlow GMC replaces the "file" GMC of BoT-SORT/Deep-OC-SORT/TrackTrack (files exist
only for MOT17/20) and DIP's ECC (cameras are fixed: mean |t| ~ 0 px); update() runs on every frame (the official
loops skip frames where YOLOX at conf 0.001 returns nothing, which never happens); output filters as each official
evaluator (aspect > 1.6 dropped, min area). Per-method details and file:line sources are in each adapter's docstring.

## Commands
```bash
# features (Colab, peg3): configs/baselines/colab_feats.sh (uploads: pegcode.tgz, dets.tar; token: configs/yolox/push_token.sh)
.venv/bin/python scripts/28_run_baselines.py --tracker <key> --split val_half     # sanity
.venv/bin/python scripts/28_run_baselines.py --tracker <key> --split test         # Table I, once
```
Outputs: `results/baselines_t1/runs/<split>/<key>/{data/<seq>.txt, summary.txt}`; summary has per-seq rows, COMBINED
over all seqs and COMBINED without 401_sequence_nga3 (74.9k of the 118.6k test frames).

## Results (2026-11-10, test = 48 official test seqs, 118.6k frames, each method run once)
Features were computed on the home GPU (peg3 Colab had no capacity: every assign "Service Unavailable"), under
gpulock in a MemoryMax=5G scope; scripts/27 streams 1000-frame windows to disk (not /tmp: it is a RAM tmpfs here)
and keeps its outputs in on-disk memmaps, resumable per window. Full table with Rcll/Prcn/FP/FN:
`results/baselines_t1/TABLE_I.md` (`scripts/28_run_baselines.py --split test --table`).

| method | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | HOTA w/o 401 | IDF1 w/o 401 | MOTA w/o 401 |
|---|---|---|---|---|---|---|---|---|---|
| ExSORT (selected.json, tuned on val by its author) | 61.39 | 58.32 | 65.28 | 79.69 | 72.50 | 31 | 63.92 | 78.61 | 79.11 |
| PEG (YOLOX dets, analytic m, present=1) | 58.19 | 61.25 | 56.14 | 71.70 | 77.41 | 49 | 61.94 | 72.28 | 80.86 |
| TrackTrack | 58.88 | 62.29 | 56.59 | 72.83 | 80.20 | 56 | 61.60 | 71.37 | 81.60 |
| HybridSORT | 57.59 | 61.63 | 54.76 | 70.76 | 79.28 | 87 | 60.60 | 69.39 | 81.21 |
| BoT-SORT | 56.28 | 62.12 | 52.01 | 68.50 | 79.72 | 95 | 61.02 | 70.31 | 81.62 |
| ByteTrack | 56.22 | 61.65 | 52.29 | 68.89 | 79.21 | 72 | 61.02 | 70.70 | 81.37 |
| DiffMOT | 56.01 | 61.97 | 51.64 | 67.97 | 79.53 | 111 | 60.43 | 69.15 | 81.74 |
| Deep-OC-SORT | 53.28 | 59.02 | 49.12 | 65.23 | 75.57 | 89 | 59.10 | 68.27 | 78.86 |
| OC-SORT | 53.27 | 58.93 | 49.17 | 65.50 | 75.55 | 97 | 59.23 | 69.24 | 78.83 |
| DIP | 51.28 | 61.15 | 44.25 | 58.05 | 77.10 | 258 | 57.53 | 63.35 | 80.32 |

401_sequence_nga3 is 63 % of the test frames, so "w/o 401" (47 seqs) is reported too. Same ordering as the paper's
Table I at the ends (TrackTrack best baseline, DIP last).
PEG row: this repo's tracker unchanged (GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0, glaremot/baselines/t_peg.py) on the
same YOLOX rows (conf 0.25, NMS 0.7); its learned h_psi head cannot run on YOLOX boxes, so m_glare = m_glare_analytic
(the head's training target) and present = 1; saturation maps from scripts/29 (CPU pass over the test images).
Without 401 PEG leads HOTA / AssA / IDF1 / IDSW but not MOTA (more FP), the paper's pattern; on 401 (nga3) it
emits ~4.6k extra FP, which puts it second to TrackTrack on all 48 seqs.
ExSORT row (added 2026-11-11, minhdq245/exsort @ 0c25ef3, glaremot/baselines/t_exsort.py): the released tracker and its
frozen configs/selected.json, which its author tuned on val (the other rows use the authors' defaults, no tuning). Fed
by its own protocol: NMS 0.65 re-run on det_nms0.95 rows, top 100, its own 512x512 saturation mask (scripts/29 --kind
exsort). Cross-check: Long's report gives HOTA 61.48 for the same config on its own cache (score floor 0.001); ours is
61.39, so the shared cache reproduces it. ExSORT leads HOTA / AssA / IDF1 / IDSW but has ~13k FP (MOTA 72.50 vs
TrackTrack 80.20): it holds tracks for up to MAX_AGE 160 frames.
Stricter NMS than 0.8 can be rebuilt from det_nms0.95 (as done for 0.7 and 0.65); only the score floor 0.1 is fixed.
