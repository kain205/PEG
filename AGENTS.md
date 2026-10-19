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
- Long runs (full eval ≈ 17k frames ≈ 40 min on the GTX 1650): run in the background,
  use `--resume` so an interrupted run picks up where it stopped.
- Commit/push only when asked. `origin` = `kain205/PEG` (private, ours);
  `upstream` = `minhdq245/PEG` (original, read-only — never push there).

## Environment rules
- Machine: Windows 11, **GTX 1650 (4 GB, sm_75)**. CPU fallback works but is slow.
- venv: `.venv/` (Python 3.10) managed by **uv** (`~/.local/bin/uv.exe`). Don't use
  system Python (3.13) or conda.
- Always call the venv interpreter directly: `.venv/Scripts/python.exe …` (no activate needed).
- Installed: torch 2.11.0+cu128, torchvision 0.26.0+cu128, pinned `requirements.txt`, TrackEval.
- Add packages with `uv pip install --python .venv <pkg>`. Torch must come from
  `--index-url https://download.pytorch.org/whl/cu128` (cu128 still supports sm_75).
- Measured: detector @1536 ≈ 7.4 fps, ~0.6 GB VRAM. fp16 gives no speedup — leave it off.
- TrackEval uses `np.float`/`np.int`; `glaremot/eval/eval_mot.py` already shims them for numpy 2.
- Env vars: in PowerShell use `$env:GMOT_TRACKER="beacon"; …`; in Bash `GMOT_TRACKER=beacon …`.

## Data (not in git)
- `datasets/` is gitignored and access-controlled — never commit it.
- Source: `dataset/GlareMOT_full.zip` (85 GB), extracted with dirs renamed to the
  `splits.json` names (zip drops `_complete`/`_new`/`_in_progress` suffixes).
- `configs/paths.yaml`: `datasets/real` (real test seqs, Table I), `datasets/synth`
  (synthetic-burn twins, Tables II–IV). Layout: `<seq>/images/*.jpg`, `<seq>/mot/gt/gt.txt`.
- Split is frozen: `glaremot/data/splits.json` (train 80 / val 17 / test 20).

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
weights/  detector/best.pt, hpsi/h_psi_head.pt (shipped)
results/  outputs (gitignored), except results/paper_logs/ (reference logs, tracked)
```

## How to run (agent runs these)
```bash
PY=.venv/Scripts/python.exe
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
- Failure analysis, first pass: `results/failure_analysis/REPORT.md` (findings + next experiments).
