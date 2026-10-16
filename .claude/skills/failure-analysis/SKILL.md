---
name: failure-analysis
description: Find and explain where PEG (or the backbone) fails on the GlareMOT sequences. Extracts typed failure events (FN/FP/IDSW/id-frag/burn-recovery) from existing MOT outputs, renders contact sheets + timelines you can look at, records a root-cause verdict per case, and builds a casebook. Use for any "why does PEG fail / find failure cases / analyse errors" task.
---

# Failure analysis for PEG

Offline analysis over existing results (no tracker run needed except `diag`). All commands:
`.venv/Scripts/python.exe scripts/08_failure_analysis.py <cmd> ...` (the agent runs everything).
A **run** is `<results_subdir>__<tracker_name>`, e.g. `eval__peg`; everything for it lives in
`results/failure_analysis/<run>/` (gitignored).

## Procedure
1. **Extract** (seconds). Then read `summary.md` and confirm the RECONCILIATION table says `ALL MATCH`
   (per-seq FP/FN/IDSW equal the benchmark txt, IDF1 within 0.01). If not, stop and fix matching first.
   ```
   extract --results_subdir eval --tracker_name peg                       # real test, Table I
   extract --results_subdir eval_synthfs --tracker_name peg_fs_noguard --data_root datasets/synth   # Tables II/IV
   extract --results_subdir eval_recovery --tracker_name peg_rcv --recovery                          # Table III (BURN_EP)
   ```
   `--no_images` skips the photometric tags (glare_sat / glare_core) for a faster pass.
2. **Triage**: per event type review the top-K by severity **plus** K random ones (stratified, fixed seed)
   so you do not only look at extreme cases. `show --run R --type IDSW --top 20 [--seq 136_2q] [--tag glare] [--unreviewed]`.
3. **Look**: `render --run R --event <id>` (or `--top N [--type T]`, `--sample N --seed 0`), then **Read
   `cases/<id>/sheet.png` and `timeline.png`** with the Read tool. Never label a case you have not viewed.
   If the tracker's decision matters (gate / coast / kill), run diag once per sequence **before** reviewing
   it (image-only labels changed on 30 % of re-checks): `diag --seq <short> --results_subdir <subdir>
   --tracker_name <name>` (+ `--data_root datasets/synth` for synth runs; for `eval_recovery__peg_rcv` set
   `GMOT_BIRTH_SIZE_GUARD=1 GMOT_OUTPUT_MAX_GAP=90 GMOT_EMIT_CAP=90` so it reproduces). Dumps go to
   `diag/<run>/<seq>.jsonl`. Run diag **one at a time and not next to another tracker run** (16 GB RAM: two
   tracker processes + subagents got background jobs reaped for low memory). Re-render: tiles then show
   `t<id>:<mode>` and the timeline gains mode (dot = emitted, x = hidden), time_since_update vs allowed_gap,
   and the real PEG gate (phi on missed frames vs h, armed bar). Ignore cusum/burn: CUSUM is off by default.
4. **Review**: `review --run R --event <id> --label <taxonomy label> --confidence 0.7 --evidence "tile 3: ..."`
   (labels in `glaremot/analysis/taxonomy.yaml`; `other` needs `--note`; use `unclear` rather than guess).
   Evidence must be concrete and cite a tile ("tile 4: person fully saturated, no pred box").
5. **Report**: `report --run R` -> `casebook.md` (label x type counts, example ids with sheet links, unreviewed count).
   `diff --a eval__peg --b eval__backbone` lists events present in one run but not the other
   ("fixed by PEG" / "introduced by PEG"); needs a backbone run (`GMOT_BIRTH_SIZE_GUARD=0
   scripts/06_eval_mot.py --split test --tracker_name backbone --resume`, ~40 min, background).

Parallelism: one subagent per sequence is safe (`review.json` is one file per case).

## Metric -> failure unit -> event type
All matching replicates TrackEval (IoU >= 0.5, `DO_PREPROC=False`), so counts reconcile with the benchmarks.

| Metric family | Failure unit | Event type / subtypes |
|---|---|---|
| DetA / Rcll / MOTA-FN | GT box unmatched | `FN_RUN` per GT id: `never_tracked`, `late_start`, `gap`, `early_end` |
| Prcn / MOTA-FP | pred box unmatched | `FP_RUN` per pred id: `phantom` (matched <=10 % of its frames), `duplicate` (IoU>=.5 with a GT matched to another id), `overhang` (id continues after its GT left), `stray` |
| DetA+Loc | FP and FN same frame, 0.2<=IoU<0.5 | `LOC_PAIR` (links the FP/FN run ids) |
| MOTA-IDSW / AssA | CLEAR IDSW | `IDSW`: `swap` (new id was on another GT <=30 frames ago), `reinit` (new id never matched before), `transfer` |
| IDF1 / AssA | identity level (global IDF1 assignment) | `ID_FRAG` (GT covered by >=2 pred ids), `ID_MERGE` (pred id covers >=2 GTs) |
| LocA | matched but IoU<0.75 for >=5 frames | `LOW_IOU_RUN` (low priority) |
| Table III (synth) | one burn episode | `BURN_EP`: `dropped`, `reborn`, `drift`, `id_swapped`, `ok` (only if a flag fired), `no_entering_id` |

Event fields: `event_id` (`136_2q/FN_RUN/g5/f0340`, stable), `seq`, `dataset`, `type`, `subtype`,
`frame_start/end`, `key_frame`, `gt_ids`, `pred_ids`, `severity` (frames), `iou_stats`, `tags`, `links`, `extra`.
Tags (measured on the focus box: GT box, or the pred box for FP_RUN, so `gt_h_px` is then the pred height): `gt_h_px`, `small` (<60 px), `edge` (<10 px from border), `occluded` (>=30 % hidden behind a nearer GT),
`crowd` (#GT), `glare_sat` / `glare` (saturated fraction of the box, tag at >=0.15), `glare_core` (lamp-core px),
`m_glare_sched` (synth schedule min over the span), `gt_uncertain`, `near_gt_birth/death` (<=5 frames), `after_gap`.

## Reading the images
`sheet.png`: header (event id, type, tags); left = full frame at `key_frame` with the crop as a yellow
rectangle; right = up to 7 crop tiles (start-5, start, 3 interior, end, end+5), each captioned with
frame, IoU / `miss` / `no-gt`, matched pred id, `m` (synth schedule), `sat` (saturated fraction), and
`t<id>:<mode>` if diag exists.

| Drawn as | Meaning |
|---|---|
| green thin box | GT, matched |
| **magenta thick box** | GT **missed** |
| box in an id colour | pred, matched (per-id colour, same palette as the tracker videos) |
| **red box** | pred **false positive** |
| `g5` / `t12` labels | focus GT id / focus pred id (others are dimmed and unlabelled) |

Some id colours are greenish: use the `g`/`t` labels to tell GT from pred.
`timeline.png` (orange band = event span, dotted line = key frame): row 1 IoU of the focus GT
(magenta = missed), row 2 which pred id carries it (red `|` = FP frame), row 3 glare signal
(synth `m_glare` schedule and saturated fraction), then with diag: tracker mode, time_since_update
(solid) vs allowed_gap (dashed), CUSUM and gate-armed bar.

## Lessons from the first pass (see `results/failure_analysis/REPORT.md`)
- One physical error usually yields several events (FP_RUN + FN_RUN + LOC_PAIR, IDSW + ID_FRAG); label them
  consistently and read sibling `review.json` files in the same seq. `report` groups them into incidents.
- BURN_EP: first check whether any track covered the target just before the burn — the recovery "entering id"
  also uses clear frames after the burn, so an untracked target is scored as a PEG failure.
- Recurring mechanisms worth recognising: frozen/collapsing coast box (area velocity not damped), phi measured on
  a stale box (gate_miss / gate_false_coast on lamp bloom), zombie tracks re-attaching (`stale_reassociation`),
  helmet-lamp `partial_box`, GT truncation (`gt_annotation_error`).
- Reviewing in parallel with Sonnet subagents works: give them a written brief + a list file, one batch per seq.

## Notes
- `diag` re-runs the tracker (`GMOT_TRACKER=beacon`, `GMOT_BIRTH_SIZE_GUARD=0`) and checks the MOT txt equals
  the stored one; a WARNING with a diff size means the run is not reproducible (report it).
- `render --mp4` writes `clip.mp4` for humans only; you cannot watch video, use sheet + timeline.
- BURN_EP sheets use CLEAR matching for colours, the episode verdict itself uses `eval_recovery`'s matching.
