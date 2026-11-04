# AGENTS.md

Map of the repo for coding agents. Keep it short; details live in `README.md` and the code.

## Project goal (student project — keep scope light)
Reproduce the PEG paper (*"Burnt, Not Gone: A Photometric Emission Gate…"*), then maybe:
improve it, make it more robust, or just find failure cases and write analysis.
1. **Now: reproduce** Tables I–IV with the shipped weights. Don't retrain unless asked.
2. Later: ablations / failure analysis / robustness. Prefer small, explainable experiments.

## Working agreement
- **The user does not run commands. The agent runs everything** (setup, eval, analysis)
  and reports the numbers. Don't hand back "run this command" instructions.
- Report results against the paper numbers (see "Reference numbers" below), with the
  exact command + env vars used, so the run can be repeated.
- Long runs (full eval ≈ 17k frames; ≈ 40 min on the old GTX 1650): run in the background,
  use `--resume` so an interrupted run picks up where it stopped.
- Commit/push only when asked. `origin` = `kain205/PEG` (private, ours);
  `upstream` = `minhdq245/PEG` (original, read-only — never push there).

## Environment rules
- Machine (since 2026-10-26): WSL2 Ubuntu on Windows, **RTX 5060 Ti (16 GB, sm_120)**, repo at
  `/home/thanh1402/Projects/PEG`. **Disk: WSL's ext4.vhdx lives on Windows D:, so the real free space is D:'s (48 GB on 2026-11-03), not what `df /` shows (591 GB); D: full = WSL crashes. Never pull big data locally.** (Old machine: Windows 11, GTX 1650, `.venv/Scripts/python.exe`.)
- venv: `.venv/` (Python 3.10) managed by **uv** (`~/.local/bin/uv`). Don't use system Python (3.14) or conda.
- Always call the venv interpreter directly: `.venv/bin/python …` (no activate needed).
- Installed: torch 2.11.0+cu128, torchvision 0.26.0+cu128 (cu128 has sm_120 kernels), pinned `requirements.txt`, TrackEval.
- Add packages with `uv pip install --python .venv <pkg>`. Torch must come from
  `--index-url https://download.pytorch.org/whl/cu128`.
- Measured 2026-10-26 on the 5060 Ti: full pipeline ≈ 19.5 fps (~2 GB VRAM), full Table I ≈ 15 min; percep-cache replay 13 s.
  Sanity on v1 data matched the paper: T1 68.19/82.30/80.62/17, T2 MOTA 73.24 FP 2024 Rcll 85.61 IDF1 75.29, T3 Rcv 76.5 total 77.6 ID-off 18.5.
  (GTX 1650: detector ≈ 7.4 fps; fp16 gave no speedup there.)
- TrackEval uses `np.float`/`np.int`; `glaremot/eval/eval_mot.py` already shims them for numpy 2.
- Env vars in Bash: `GMOT_TRACKER=beacon …`.

## Colab (training lane; retrain only when asked)
- Account **martha** (one session is ours for PEG training). Use the official `colab` CLI that lives in the
  gemma4ever venv with martha's profile as HOME (OAuth token already there; re-auth: `~/Projects/gemma4ever/scripts/colab/remote_auth.sh`):
  `HOME=~/Projects/gemma4ever/.local/colab-profiles/martha SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt ~/Projects/gemma4ever/.venv/bin/colab --auth=oauth2 <new|exec|upload|download|stop|sessions|usage>`.
  `colab exec` exits 0 even when the code raises: print one result line and check it. Always `stop` the session after use.
- Data: do NOT mount Drive (drivemount needs a human browser grant per VM). `scripts/24_fetch_glaremot.py` streams
  only the wanted members from the public Drive zip by HTTP Range (no zip copy on disk). Probed 2026-10-26 on a CPU VM:
  206 GB free disk, ~41 MB/s per stream, ~64 MB/s with 8 streams (train 115 GB ≈ 30 min).
- **Quota way out (2026-11-03): read the zip through the Drive API as a user.** Own Desktop OAuth client of the user
  (project cool-subset-513601-n3, test user = tyler), token via `configs/yolox/drive_auth.py` (secrets in
  ~/.config/peg_drive, never in git); `configs/yolox/push_token.sh` pushes a <=1 h access token to the VM every 2 min;
  scripts/24 uses it when `GDRIVE_TOKEN_FILE` is set. rclone's built-in client shares a global per-minute quota (403s);
  the Cloud-SDK client is blocked by Google for Drive scopes ("This app is blocked").
- The GlareMOT2 Drive zip has a per-file anonymous download quota: after ~150 GB of range reads in a day it
  answers HTTP 200 "Quota exceeded" (HTML) to every client. Fetch only what you need, once.
- Checkpoints: pull them to this machine with `colab download` (VM disk is lost on disconnect).
- **2026-11-02, account peg3: a blocking cell no longer keeps the VM alive** (reclaimed ~30 min after launch, twice;
  downloads do not count either). Liveness follows kernel EXEC activity: launch the job detached on the VM
  (`nohup setsid bash ... &` inside an exec) and run `configs/yolox/keepalive.sh` locally, detached with setsid; it
  execs a tiny cell every 4 min (as LifeMate's tools/colab.py does). Older note, kept for history:
- Long jobs: run them as a BLOCKING kernel cell (`subprocess.run(...)` piped to `colab exec --timeout 20`): the CLI
  returns, the kernel stays BUSY and the runtime stays alive. A `nohup ... &` job with an idle kernel was reclaimed
  after ~40 min (2026-10-26, VM disk lost). Watch with `colab download <log>` / `colab status` (both work while busy).
  Martha: H100 rejected, A100 80GB ok (6.8 CU/h). An IDLE kernel after the job ends is reclaimed too (2026-10-27: a
  finished 20-epoch run, ALL_EXIT 0, lost with every checkpoint). colab_all.sh now packs /content/yx_out and holds
  the kernel busy until /content/PULLED exists. Local background shells get reaped when this machine is low on RAM
  (another project's vLLM uses it), so do not rely on a local watcher; check in by hand.
  2026-10-27 22:30: this machine rebooted and the A100 VM was gone too, mid-run. Now `configs/yolox/pull_ckpts.sh`
  pulls every epoch's checkpoint (fp16 copy + newest full one) to `results/yolox_glaremot2_half/`; to resume, upload
  `latest_full_ckpt.pth.tar` to `/content/resume_ckpt.pth.tar` (ssh) and relaunch colab_all.sh (colab_run.sh resumes).
  `colab download` ~10 MB/s; `colab upload` fails over ~300 MB (use ssh: `ssh -o ProxyCommand="... colab ssh
  --proxy-mode -s peg" root@colab`, ~2.5 MB/s up).
- **YOLOX-X detector lane (team task from Minh, 2026-10-26)**: `configs/yolox/README.md` (recipe + decisions),
  data `scripts/25_build_yolox_glaremot.py`. GlareMOT2 train split, 2.5 fps, halves, glare filter >25 % sat ->
  train 6818 / val 6972 imgs; `400_sequence_morongmo` (73k frames) is ~half of both, 78 % of val boxes, so AP is
  also scored on `val_half_nomrm`. Init TrackTrack mot17 YOLOX-X: val AP50 .434 / AP50:95 .169 (nomrm .424/.169).
  2026-10-28: labels of 400 (MoRongMo) and 401 (nga3) fixed by Minh (old labels drifted up to 98 frames behind the
  video); init switched to TrackTrack **MOT20** (Minh). MOT20 init on fixed val: AP50 .641 / .295, nomrm .366 / .153.
  Then `configs/yolox/colab_cache.sh` (armed on the VM) caches detections of the best epoch (val_half_nomrm AP50) on
  every frame of every seq -> /content/dets; `configs/yolox/pull_cache.sh` pulls it to results/yolox_dets_cache/.
  2026-11-02: fix 2 = 23 cam-5 seqs re-boxed (whole person); both fixes = `configs/yolox/make_overlay.sh` (`--overlay` in
  scripts 25/26). Run 3 on Colab profile **peg3** (tyler.ramirez, PEG-only; acc2 belongs to LifeMate, do not use):
  colab_all.sh now does overlay, train+test build, train, best epoch, test AP once, cache `--splits val_half,test`.

## Data (not in git)
- `datasets/` is gitignored and access-controlled — never commit it.
- Source: `GlareMOT_full.zip` (85 GB, see below), extracted with dirs renamed to the
  `splits.json` names (zip drops `_complete`/`_new`/`_in_progress` suffixes).
- `configs/paths.yaml`: `datasets/real` (real test seqs, Table I), `datasets/synth`
  (synthetic-burn twins, Tables II–IV). Layout: `<seq>/images/*.jpg`, `<seq>/mot/gt/gt.txt`.
- Split is frozen: `glaremot/data/splits.json` (train 80 / val 17 / test 20).
- **GlareMOT2 full.zip** (Drive id `1kUTdfRNbZzbwyl94JE--Vz8C5YVkzgms`, public link, 217.8 GB, stored/uncompressed):
  119 seqs = the old 117 + `400_sequence_morongmo` (train) + `401_sequence_nga3` (test), names without suffixes.
  Its own "official v1" split (seed 20261024): **train 71 / test 48, no val**. It is NOT our frozen split: of our 20
  test seqs, 10 are in its train; of our 80 train + 17 val, 37 are in its test → the shipped weights are not clean
  on its test. Ask the user before adopting it. Per seq: `images/ labels/ labels_all/ meta/ mot/gt/`.
  Zip byte layout: test 0–102.4 GB, train 102.4–217.7 GB. No synthetic twins inside.
  **GlareMOT2 frames differ from v1**: v1 frames are 1536×1536 letterboxes of the video (black pad, e.g. 333 px
  top/bottom); GlareMOT2 frames are the native video (2688×1520, 320: 2944×1656), re-timed to integer fps, GT in
  native pixels (= v1 GT ×1.75 minus pad); seqs 305/312/316/320/325 relabelled. `Perception` stretched any non-square
  frame to S×S (`square_frame`) → HOTA 47.90 (boxes ~1.3× too wide). Fixed 2026-10-26: `eval_mot.track_sequence`
  letterboxes non-square frames (`letterbox_params/letterbox_frame/unletterbox_row` in tracker.py) and maps rows
  back; square frames are untouched (v1 output byte-identical). PEG on GlareMOT2 frames of our 20 test seqs:
  HOTA 68.11 · IDF1 82.66 · MOTA 80.93 · IDSW 18 (`results/eval_v2/trackers/peg_v2_lb`, data `datasets_v2/real_oldtest`).
  Other `square_frame` users (scripts/05 video, 03, 12, h_psi training) still stretch: fix before using them on 16:9.
- Old zip **GlareMOT_full.zip** (Drive id `1LEHAvE7r85UsUUdZcDeRONabZSUwxIt-`, public, 85.7 GB): `GlareMOT/<seq>` (real)
  and `GlareMOT-Synth/<seq>` (twins). This machine's `datasets/real` + `datasets/synth` (test split) come from it:
  `24_fetch_glaremot.py --zip v1 --out datasets/real --old_split test --parts images,mot,meta` and
  `--zip v1synth --out datasets/synth --old_split test`.

## Repo map
```
glaremot/
  tracking/beacon_tracker.py  PEG: photometric emission gate + evidence-gated coast (the contribution)
  tracking/tracker.py         OC-SORT backbone + Perception (YOLO11m + h_psi head)
  tracking/occlusion_graph.py occlusion handling
  perception/h_psi.py         learned visibility head (+ Stage1HeadLoss)
  perception/analytic.py      analytic m_glare target
  perception/synth_glare.py   synthetic burn generator (makes the twins)
  photometric.py              saturation / photometric features
  eval/eval_mot.py            full-scene MOT eval (Tables I, II, IV)
  eval/eval_recovery.py       burnt-target recovery eval (Table III)
  eval/percep_cache.py        record/replay detector outputs for fast tracker-only ablations
  external/ocsort/            vendored OC-SORT
  config.py, data/            path config, datasets, splits
  analysis/                   failure-analysis harness (events, sheets, casebook); skill: .claude/skills/failure-analysis
scripts/  01-04 optional retraining | 05 run tracker | 06 eval MOT | 07 eval recovery | 08 failure analysis | 09 presentation figures | 10 Table II vs I glare delta | 11 PEG vs PEG+ figures | 12 appearance sidecar for percep cache | 13 PEG-F figures
          | 19 PEG-O estimator check | 20 PEG-O figures | 21 PEG-C velocity check (oracle b40) | 22 PEG-C figures
          | 24 stream GlareMOT2 seqs from the Drive zip (no full download) | 25 YOLOX COCO set from GlareMOT2 train
          | 26 full-frame YOLOX det cache for all 119 seqs (train_half / val_half / test, native fps; Colab)
          | 14-17 MoRongMo labeling for FastLabeler (14 record dets+track, 15 MOT->project.json, 16 QA sheets, 17 app-timeline frames); see results/label_MoRongMo/NOTES.md
weights/  detector/best.pt, hpsi/h_psi_head.pt (shipped)
results/  outputs (gitignored), except results/paper_logs/ (reference logs, tracked)
```

## How to run (agent runs these)
```bash
PY=.venv/bin/python
# GMOT_BIRTH_SIZE_GUARD=0 is REQUIRED to match the paper (all tables; verified).
# Table I — real test (20 seqs)
GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 $PY scripts/06_eval_mot.py --split test --tracker_name peg --resume
# Tables II & IV — full-scene on synthetic twins
GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 $PY scripts/06_eval_mot.py --split test --data_root datasets/synth \
    --results_subdir eval_synthfs --tracker_name peg_fs_noguard --resume
# Table III — recovery on burnt targets (sets emit cap 90 internally)
GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 $PY scripts/07_eval_recovery.py --split test --tracker_name peg_rcv_noguard --resume
# Qualitative video
GMOT_TRACKER=beacon $PY scripts/05_run_tracker.py --video clip.mp4 --mot_out out.txt
# Failure analysis (offline, seconds; reads existing results): extract -> show/render -> review -> report
$PY scripts/08_failure_analysis.py extract --results_subdir eval --tracker_name peg   # then see .claude/skills/failure-analysis
```
- Omit `GMOT_TRACKER=beacon` for the bare backbone baseline (no gate).
- `--skip_track` re-scores existing MOT txt without re-running the tracker.
- `--max_frames N` for quick smoke tests before a full run.
- `--percep_cache results/percep_cache/{real,synth}` (06 and 07): replays cached detector + saturation outputs
  (byte-identical MOT txt), so a tracker-only run takes ~11 s instead of ~40 min. Built 2026-10-07 for the test
  split; a missing seq is recorded on first run. Use it for every ablation; `synth` serves Tables II-IV.
- PEG+ ablation matrix: `bash results/peg_plus/run_ablation.sh real|synth`.
- PEG-F matrix (friend's methods, all 3 tables): `bash results/peg_f/run_matrix.sh real|synth`; M2/M4 need the
  `<seq>.app.npz` sidecars (`scripts/12_cache_appearance.py`, already built for real+synth test).
- Outputs: `results/<results_subdir>/` (default `results/eval`), `results/eval_recovery/`.

## Knobs for ablations / failure analysis (env vars)
- `GBEACON_CUSUM_H` gate threshold h (default 0.40) · `GBEACON_COAST_FLOOR` δ (default 3)
- `GBEACON_MF_CONFIRM`, `GBEACON_CUSUM`, `GBEACON_NIS` — refinements the paper says don't help
- `GMOT_BIRTH_SIZE_GUARD` anti glare-bloom phantom-birth guard (runtime default on)
- `GPEG_SIZE_LOCK=1` **PEG+** (ours): zero Kalman area velocity while coasting · `GPEG_LAMP_FOLLOW=1` lamp-follow
  (tried, hurts every table — keep off). Both default off = paper PEG.
- `GPEG_ODO=1` **PEG-O** (ours, failed — keep off): burn-disc odometry moves the held box; `GPEG_ODO_TAU` (0.06),
  `GPEG_ODO_GAMMA` (1) · `GPEG_ARMED_SURVIVE=1` armed track not deleted by allowed_gap (never fires on val). Default off = PEG/PEG+.
- **PEG-C** (ours, docs/PEG_C_PROTOCOL.md; all default off = PEG/PEG+): online `GPEG_VEL_K`/`GPEG_VEL_T` (V: coast-entry velocity =
  OLS slope of the last K detection centres, axis zeroed if |v| <= t*SE), `GPEG_CAP` (C: gate arms only while gap <= N),
  `GPEG_STITCH_K` (S: burn-exit stitch); FIXED-LAG (rewrite MOT rows up to L frames back, report separately)
  `GPEG_BACKFILL_L`/`GPEG_BACKFILL_MODE` hidden|all (B), `GPEG_BACKBIRTH=1` (BB). `GPEG_F_STATS=1` prints pegc_* counters.
- `GPEG_F=1` **PEG-F** (friend's fork, default off): master switch for M1 `GMOT_ADAPTIVE_MOTION` (= `GMOT_AM_DAMP` +
  `GMOT_AM_SWAP`), M2 `GMOT_REID`, M3 `GBEACON_DYNAMIC_H`/`GBEACON_ADAPTIVE_TTL`, M4 `GMOT_DORMANT`, M5 `GBEACON_ANCHOR`;
  each env var overrides the master. `GPEG_F_STATS=1` prints per-seq firing counters.
- Full list: `grep -rn os.environ glaremot scripts`

## Reference numbers
- Table I, PEG, COMBINED: HOTA 68.20 · DetA 65.89 · AssA 71.62 · IDF1 82.30 · MOTA 80.62 · IDSW 17
  (full per-seq log: `results/paper_logs/table1_real_test_peg.txt`).
- Weakest seqs there (good starting points for failure analysis): 129_13q, 136_2q,
  312_108q, 320_116q, 325_92q.
- Paper Table II/IV PEG (h=0.4): MOTA 73.24 · FP 2024 · Rcll 85.61 · IDF1 75.29.
  Paper Table III PEG: clear 93.0 · Rcv 76.5 · heavy 74.1 · total 77.6 · ID-off 18.5.
- Our reproduction (2026-09-29) + status: `results/REPRODUCTION.md` (gitignored dir).
- Bare backbone (no gate), real test, guard off: HOTA 68.05 · IDF1 82.72 · MOTA 79.31 · IDSW 15 · FP 1816 · FN 2496
  (`results/eval/trackers/backbone`, run name `backbone`).
- **PEG+ (size lock), guard off:** Table III Rcv@.5 82.2 (PEG 76.6) · total 85.1 · ID-off 15.5;
  Table II MOTA 73.37 · IDF1 77.95; Table I HOTA 68.23 · MOTA 80.52 (≈ PEG). Details + deck: `results/peg_plus/RESULTS.md`.
- Our PEG Table III guard off (`peg_rcv_ng`): clear 93.0 · Rcv 76.6 · heavy 74.1 · total 77.8 · ID-off 18.5.
- **PEG-F** (friend, guard on, their setting): Table I HOTA 68.82 · IDF1 84.42 · IDSW 27 — reproduced exactly (re-score,
  live run of their code @4.3 fps, cached port byte-identical). Fair baseline = PEG guard on 68.33/82.68/15. Guard off:
  F T2 MOTA 70.91 · T3 Rcv 66.2 (M1-damp hurts burns); M2/M4 never fire. Details + deck: `results/peg_f/RESULTS.md`.
- **Val selection (2026-10-17)**, pre-registered (`docs/VAL_SELECTION_PROTOCOL.md`) → `docs/VAL_SELECTION_RESULTS.md`:
  greedy on val picked PEG+M1damp (one episode), which loses to PEG on every test table. Test-selected A+M1swap+M3
  ≈ PEG on val. PEG+ T3: test +5.6, val −0.4, pooled 48 ep +3.2 [CI +0.1, +7.3]. Val caches built for real+synth
  (`results/percep_cache/*`, + `.app.npz`); runner `results/val_selection/run_selection.py`. Deck slides 16–21.
- **Thach v2 (M1-M6, 2026-10-19)**, pre-registered (`docs/THACH_V2_PROTOCOL.md`) → `docs/THACH_V2_RESULTS.md`: his T1
  reproduces 14/14 but was tuned/chosen on test (0 val runs). Val rule selects base (no method). M1 (adaptive Q) × M5
  (anchor) collapses T3: full+M6 Rcv 76.2 → 53.6 test, 67.6 → 37.1 val. Tuning from scratch on val
  (`docs/THACH_V2_TUNE_PROTOCOL.md`, `results/thach_v2/tune_val.py`) also ends at PEG. Best overall (test once):
  PEG+ by design + M1 cone (val-chosen) T1 68.44 · T2 63.14 · T3 83.1. Full metrics: `results/thach_v2/full_metrics.md`. Deck 20-35.
- **PEG-O (photometric odometry, 2026-10-20)**, pre-registered (`docs/PEG_O_PROTOCOL.md`) → `docs/PEG_O_RESULTS.md`: val rejects
  every (τ, γ) (T3 −13.5…−41 vs PEG+) → keep PEG+. Test once at the best val point (τ .08 γ 4, guard off): T1 68.15 ·
  T2 MOTA 73.06 · T3 Rcv 73.6 (PEG+ 82.2); pooled 48 ep. −10.6 [−19.5, −2.7]. The burn disc is not rigid. `results/peg_o/`, deck 36-38.
- **PEG-C (the coast designed, 2026-10-20)**, pre-registered (`docs/PEG_C_PROTOCOL.md`) → `docs/PEG_C_RESULTS.md`: val picks
  P + V (K 40, t 2): val T3 67.3 → 75.8, but test once (guard off) T1 68.49 / IDF1 83.24 · T2 HOTA 61.15 · T3 Rcv 80.5 (PEG+ 82.2);
  per episode test −1.8 [−7.7, +3.6], val +8.6, pooled +2.4 [−2.1, +6.8]. Long-baseline velocity is stale when walkers change
  pace; error floor ≈ 0.3 px/f is the CV model, not noise. C, S, B-after-V, BB not accepted (S = one-seq T2 gain). Online: PEG+ stays best.
  Details + deck slides 39–41: `results/peg_c/RESULTS.md`.
  **Stage 2b, FIXED-LAG (not online): PEG+ + B (`GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=all`, no V)** val-chosen, test once
  guard off: T1 68.31 / FP 1435 / FN 2583 · T2 HOTA 62.93 / FN 2158 · T3 Rcv 86.5 (PEG+ 82.2); per episode test +4.2
  [+1.0, +8.3] 6/0, pooled +4.1 [+0.9, +8.0]. Run names `pegcbl_*`. Report it only as a fixed-lag row.
- Failure analysis, first pass: `results/failure_analysis/REPORT.md` (findings + next experiments).
