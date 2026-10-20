# PEG-C (the coast, designed) on val, pre-registered (2026-10-20)

Committed **before** any val or test run of PEG-C. Plan: `C:\Users\thanh\.claude\plans\peg-c-coast-design.md`.
PEG decides *whether* to coast (φ ≥ h). PEG-C designs *how*: one constant-velocity (CV) model, used as a filter online
(V, C, S) and as a fixed-lag smoother (B, BB). Size lock (PEG+) is on by design. Code: `glaremot/tracking/tracker.py`,
`glaremot/tracking/beacon_tracker.py`, `glaremot/eval/eval_mot.py` (env flags below; all unset = PEG(+) byte-identical).

## Stated up front
- The components were chosen from oracle analyses that **pooled val AND test** burn episodes (`results/research/
  ORACLE_T3.md` Follow-up 3, `LITERATURE_IDEAS.md` idea 1, `RESIDUAL_POOLS.md` H1/H2) and from test failure cases.
  No parameter is tuned on test; val chooses among the pre-registered grid points below; test is run once per final.
- **Synthetic leak**: `synth_glare.apply_glare` centres and sizes the burn disc on the GT box, so a method that reads
  the disc geometry leaks GT on T2/T3. PEG-C reads only the existence gate (φ ≥ h, exactly as PEG does) and the
  track's own detections; it never reads the disc shape or position.
- **Fixed-lag rows are not online.** B and BB rewrite / add output rows up to L frames in the past. Every result row of
  that family is labelled "fixed-lag L" and is reported separately from online rows, never mixed.
- Val is small (17 real seqs, 18 T3 burn episodes); a val null result is weakly informative; it is still the rule.

## Components and grids
| comp | what (env) | grid |
|---|---|---|
| P | PEG+ size lock (`GPEG_SIZE_LOCK=1`) | in by design (FORCE), as Addendum 2 of `THACH_V2_TUNE_PROTOCOL.md` |
| V | long-baseline velocity at coast entry (`GPEG_VEL_K`, `GPEG_VEL_T`) | K ∈ {20, 40} × t ∈ {0, 2} (4 points) |
| C | causal cap: the gate may arm a track only while `time_since_update ≤ N` (`GPEG_CAP`) | N ∈ {48, 90} (2 points) |
| S | burn-exit stitch (`GPEG_STITCH_K`) | k ∈ {1.0, 1.5} (2 points) |
| B | burn-gated backfill, fixed-lag (`GPEG_BACKFILL_L`, `GPEG_BACKFILL_MODE`) | L ∈ {45, 90} × mode ∈ {hidden, all} (4 points) |
| BB | backward birth, fixed-lag (`GPEG_BACKBIRTH=1`) | on (1 point) |

### Exact definitions (implementation details fixed now, before any run)
- **V.** At coast entry (`MotionTrack.update_missing`, `gap == 1`, track with ≥ `FC_MIN_GOOD_HITS` good hits; the
  existing young-track rule "velocity = 0" is kept). Data: the centres (px) of the track's **raw detection boxes**
  (the tight box it emits on detection frames) with their frame indices, in a separate buffer (not the smoothed
  `centers` deque; not cleared on re-entry) — this is the estimator of the oracle b40 (`oracle_t3_vest.py`).
  If fewer than K/2 detection frames lie in the last 2K frames → v = 0. Else v = OLS slope (px/frame) per axis over the
  last K detection frames; per axis, if |v_axis| ≤ t·SE(slope_axis) (SE = sqrt(RSS/(n−2) / Σ(f−f̄)²)) that axis is 0;
  speed guard: if |v| > 0.1·h (h = predicted box height, px) → v = 0. Then the existing ceiling |v| ≤ 2·median step
  (`median_step_px`) is applied, and v is written to the Kalman velocity x[4:6]. VEL_DAMP past FORECAST_START unchanged.
- **C.** In `PEG._try_beacon`, after φ is computed: `if gap > N: return False` (the track is not armed).
- **S.** Placed after the BYTE-lite round and **before** the missed-track loop of `GlareAwareTracker.step` (so a stitched
  track gets one ordinary detection update this frame, never a miss followed by an update). Candidates: confirmed,
  unmatched, non-exiting tracks whose gate armed within the last A = 10 frames (`frame_idx − _armed_frame ≤ 10`;
  `_armed_frame` is set when `PEG._try_beacon` returns True). An unmatched detection that passes `_birth_allowed`
  (i.e. would be born) is paired with a candidate whose predicted-box centre is within k·max(w, h) (predicted box,
  px) of the detection centre. A pair is applied (`_apply_det`, no `_match_ok` gate) only if the detection has exactly
  one candidate and the track is the candidate of exactly one such detection. Without PEG (no gate) S never fires.
- **B.** When a confirmed track is re-acquired by a detection (`_apply_det`) after M missed frames, 1 ≤ M ≤ L, and its
  gate armed at least once during the gap (`_armed_frame > last detection frame`), the tracker emits a backfill record:
  for each gap frame f, the box linearly interpolated (centre and size) between the two detection boxes it emitted at
  the last detection frame and at the re-acquisition frame. The eval writer (`track_sequence`) applies the record to
  rows already written: mode **hidden** adds rows only for frames where that id has no row; mode **all** also replaces
  that id's emitted coast boxes. Rows are only touched within L frames of the current frame. Replaced rows keep their
  confidence column; added rows get confidence 0.001. If no record was applied, the row order is unchanged.
- **BB.** When a track becomes confirmed (frame f_c; birth frame f_b, birth box b_b = its first detection box): if
  φ(b_b on the saturation mask of f_b) ≥ h, the tracker emits records (a) for the frames f_b..f_c−1 on which the track
  had a detection, its own detection box, and (b) for f = f_b−1, f_b−2, … the frozen box b_b while φ(b_b on the mask of
  frame f) ≥ h, stopping at the first frame that fails, and never before f_c − L (L = `GPEG_BACKFILL_L` if set, else 90).
  Masks are kept in a ring buffer of the last L+2 frames only when BB is on. Records only add rows.

## Harness
Thach v2 harness (`results/thach_v2/tune_val.py`, his code `dataset/thach_v2/PEG-main` with PEG-C ported at the same
places, guard ON = his setting, his caches `results/thach_v2/cache_{real,synth}`), because PEG, PEG+, every Thach
component and the strongest finals already have val+test numbers there. Same primary metrics and thresholds:
Δ = (T1 HOTA, T2 HOTA, T3 all-burn Rcv@.5) vs current X on val COMBINED; admissible iff every Δ ≥ −0.5;
score = ΣΔ > +0.5; single-event check = drop the val unit most favourable to the candidate in T1, T2 (TrackEval
re-run) and T3 (burn episode), the summed Δ must stay > 0. Every evaluation is logged (`ledger.json`, `trace.json`).

## Stages
1. **Online** (`tune_val.py --peg_c` → `results/thach_v2/tune_C/`): X = S0 + P (val 70.11 / 76.30 / 67.3, in the
   ledger). Greedy over GRID = {V, C, S} (8 points), strict rule (single-event check) → `tune_C/final.json`.
   **Strongest** variant (same, no single-event check): `--peg_c --strong` → `tune_C_strong/`.
2. **Fixed-lag** (`--peg_c --lag` → `tune_C_lag/`): X = `tune_C/final.json` (its components fixed). Greedy over
   {B (4 points), BB (1 point)}, strict rule → `tune_C_lag/final.json`.
3. **ALL** (Addendum 1 style, strongest rule, candidates = Thach's GRID R, M1q, M1c, M1d, M2, M3, M4, M5, M6;
   PEG-C components fixed): `--peg_c --all` from `tune_C/final.json` → `tune_C_all/`; `--peg_c --lag --all` from
   `tune_C_lag/final.json` → `tune_C_lag_all/`. If a start equals an earlier start (e.g. the lag stage accepts
   nothing), the duplicate search is not run and is reported as "= …".

## Test (once per final directory, all three tables, all metrics)
- `tune_C/test.json` (online), `tune_C_lag/test.json` (fixed-lag L), `tune_C_all/test.json`, `tune_C_lag_all/test.json`,
  plus `tune_C_strong/test.json` only if its final differs from `tune_C`'s. A final identical to one already tested
  (same env key) is not re-run; its row points to the earlier test. No other PEG-C config is run on test there.
- Our repo, guard OFF (paper setting), test once, three tables, cached replays: online final → `pegc_test`,
  `pegc_fs`, `pegc_rcv`; fixed-lag final → `pegcl_test`, `pegcl_fs`, `pegcl_rcv` (06 real, 06 synth, 07), with
  `GPEG_SIZE_LOCK=1` + the chosen env. Val T3 in our repo for the per-episode CI: `v_pegc_rcv`, `v_pegcl_rcv`.
  If a stage accepts nothing, its paper-setting rows use that stage's best-scoring round-1 point, labelled "not
  selected by val" (ties: the first in grid order).
- Reported regardless of outcome: val+test table next to PEG, PEG+, each Thach component, Thach full+M6 and the
  strongest finals; per-episode T3 change vs PEG+ with bootstrap 95% CI over episodes (test, val, pooled; B = 10000,
  seed 0, `results/peg_o/episodes.py` logic); which components val accepted and why. No re-selection after test.

## Checks before tuning (implementation checks, not selection)
1. `scripts/21_peg_c_check.py`: the oracle policy b40 recomputed with the tracker's own velocity function (K = 40,
   t = 0) on the 43 tracked burn episodes must give ≈ 87.8 pooled (±1). Only the already-published points (K 20/40,
   t = 0) are computed; no new test-informed variant is looked at.
2. Flags unset ⇒ byte-identical MOT txt vs the existing PEG and PEG+ runs (test real + synth, three tables), in our
   repo and in the port.
3. Smoke on **val** `187_sequence_66q_new` g247 and `133_sequence_17q_new` g117 (T3, our repo, guard off, P + V K=40 t=0): coverage
   should improve vs PEG+ (`v_A_rcv`); this checks the wiring only (oracle b40: 35 vs 19 and 26 vs 17 frames).
   A failure is diagnosed as a bug; any design change after it is written here as an addendum before the val search.
4. Port check: Thach-fork rows = ours on those sequences (same config, guard on).

## Addendum 1 (2026-10-20, before the val search): implementation checks done, one disclosure
- Checks passed: `21_peg_c_check.py` b40 = 88.5 / 86.6 / 87.8 (test / val / pooled), b20 = 85.5 pooled, all 43
  episodes equal to the published json; flags unset ⇒ byte-identical on 6 pairs (T1 20/20 ×2, T2 15/15 ×2,
  T3 15/15 ×2, PEG and PEG+); val smoke P + V(40, 0): 187 g247 19 → 35, 133 g117 17 → 24 covered frames (wiring
  check passed, no change made). Structural check of C/S/B/BB on val (MOT txt + firing counters only): B rows lie on
  the interpolation line (max 0.012 px), hidden mode leaves every online row byte-identical, no row older than L+1.
  BB never fired on any val run (a forced-mask plumbing test produced one row as intended).
- Disclosure: while wiring C/S/B/BB the executor ran ad-hoc val runs on 4 T3 / 17 T1 val sequences whose COMBINED /
  all-burn lines were printed in its terminal before it was told not to look. Those runs were deleted, the numbers
  were not reported to the orchestrator, and no design or grid was changed afterwards. The selection below is a
  mechanical greedy rule, unchanged.

## Addendum 2 (2026-10-20, committed before any run of it): Stage 2b — B on PEG+ without V
Reason: the staged protocol only tried B after V. With V on, the gate already emits a box on nearly every gap frame,
so B "hidden" had nothing to fill and B "all" overwrote V's coast: B could not be judged on its own mechanism. The
literature check (`results/research/LITERATURE_IDEAS.md` idea 1) measured burn-gated backfill on PEG+ outputs on
both splits (T3 +4.3 test / +3.8 val, FP flat), so it is tested here on its own. Disclosed: that check looked at test.
B interpolates between the track's own two detection boxes and is gated by the existence gate only (an armed frame in
the gap); it reads no disc geometry. Definitions of B and BB are unchanged (§ Exact definitions).
- **Stage 2b** (`tune_val.py --peg_c --lag_base` → `results/thach_v2/tune_C_lagP/`): start S0 = P only (PEG+, no V,
  no S; val 70.11 / 76.30 / 67.3). Greedy over B (4 points: L ∈ {45, 90} × mode ∈ {hidden, all}) and BB (1 point),
  strict rule as before (admissible every Δ ≥ −0.5, score > +0.5, single-event check). The strongest variant (no
  single-event check) is also recorded (`--peg_c --lag_base --strong` → `tune_C_lagP_strong/`).
- Test once (Thach harness) only if a point is accepted: the strict final (`tune_C_lagP/test.json`); the strongest
  final only if it differs from the strict one and accepted a point. If neither rule accepts a point, no test run.
- Our repo, guard off, test once for the accepted config (strict, else strongest; labelled "fixed-lag L"):
  `pegcbl_test`, `pegcbl_fs`, `pegcbl_rcv`, plus val T3 `v_pegcbl_rcv`; per-episode CI vs PEG+ via
  `results/peg_c/episodes.py` (test, val, pooled). Rows labelled "PEG-C fixed-lag L (B on PEG+)", separate from online.
