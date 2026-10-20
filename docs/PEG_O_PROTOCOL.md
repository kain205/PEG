# PEG-O (photometric odometry) on val, pre-registered (2026-10-20)

Committed **before** any val or test run of PEG-O. Plan: the burn that PEG uses to *decide* (φ ≥ h) is also used to
*measure* how far the held box has moved: a disc matched filter on the saturated component under the prediction,
odometry from the first sharp peak (offset-free, no lamp→body geometry), trusted only when the peak is sharp
(Laplace curvature k ≥ τ), fused as a centre-only Kalman update with R = γ·(0.08h)²·diag(τ/k_x, τ/k_y) behind a
χ²(2) 9.21 NIS gate. Size stays locked (PEG+). Code: `glaremot/tracking/beacon_tracker.py` (`GPEG_ODO*`).

## Stated up front
- The idea and the feasibility numbers came from looking at **test** T3 burn episodes (135_19q g53, 204_81q g300,
  320_116q g1, 176_56q g204, 325_92q g3), exactly like PEG+. The estimator was pinned on those episodes before this
  protocol (`scripts/19_peg_o_check.py`, reference script from plan mode). Val only tunes τ and γ (and decides S).
- Val is small (17 sequences, 18 T3 burn episodes; most val misses are targets that were never tracked), so a val
  null result is weakly informative; it is still the rule.
- Checks run on test before tuning, not used for any selection: (1) flags off ⇒ byte-identical MOT txt vs the
  existing PEG / PEG+ runs (test real + synth); (2) one recovery smoke on `135_sequence_19q_new` (P+O, expect the
  g53 episode coverage 0.09 → ≥ 0.8); (3) port check: Thach-fork boxes = ours on 135_19q. No table-level PEG-O test
  number is looked at before the val selection is final.

## Harness
Thach v2 harness (`results/thach_v2/tune_val.py`, his code `dataset/thach_v2/PEG-main` with PEG-O ported at the
same places, guard ON = his setting, his perception caches `results/thach_v2/cache_{real,synth}`), because PEG,
PEG+, every Thach component and both "strongest" finals already have val+test numbers there. Same primary metrics,
same thresholds: Δ = (T1 HOTA, T2 HOTA, T3 all-burn Rcv@.5) vs current X on val COMBINED; admissible iff every
Δ ≥ −0.5; score = ΣΔ > +0.5; single-event check = drop the val unit most favourable to the candidate in T1, T2
(TrackEval re-run) and T3 (burn episode), summed Δ must stay > 0.

## Components
| comp | what | grid |
|---|---|---|
| P | PEG+ size lock (`GPEG_SIZE_LOCK=1`) | **in by design (FORCE)**, as in Addendum 2 of `THACH_V2_TUNE_PROTOCOL.md` |
| O | PEG-O odometry (`GPEG_ODO=1`) | τ (`GPEG_ODO_TAU`) ∈ {0.04, 0.06, 0.08} × γ (`GPEG_ODO_GAMMA`) ∈ {1, 4, 16} (9 points) |
| S | evidence-gated survival (`GPEG_ARMED_SURVIVE=1`): a confirmed track whose gate is armed this frame is not deleted (nor withheld from output) by `allowed_gap()`; hard cap MAX_AGE stays | on (1 point) |

Fixed (not tuned): κ = 2 (search window = box ×2 around the predicted burn centre), ρ = √(area/π) clipped to
[0.3·min(w,h), 1.5·max(w,h)] (512² grid), Δ = max(2, ρ/4), R floor 25 px², NIS 9.21.

## Stage A — PEG-O on top of PEG+ (`tune_val.py --peg_o` → `results/thach_v2/tune_O/`)
Start X = S0 + P (val 70.11 / 76.30 / 67.3, already in the ledger). Greedy over GRID = {O, S} with the strict rule
(single-event check) → `tune_O/final.json`. The "strongest" variant (same greedy, no single-event check) is also
run → `tune_O_strong/final.json` (`--peg_o --strong`). Every evaluation is logged (`ledger.json`, `trace.json`).

## Stage B — "cộng lại mọi thứ" (`tune_val.py --peg_o --all` → `results/thach_v2/tune_O_all/`)
Start X = `tune_O/final.json` (all its components fixed). Greedy over Thach's GRID (R, M1q, M1c, M1d, M2, M3, M4,
M5, M6, same 26 points), strongest rule (no single-event check) as Addendum 1. P/O/S are not candidates in Stage B.
If Stage A accepts nothing, Stage B starts from S0 + P and equals the existing `tune_strong_P` search (reported as
such, not re-tested).

## Test (once per directory, all three tables, all metrics)
- `tune_O/test.json` (Stage-A strict final), `tune_O_strong/test.json` only if its final differs from the strict one,
  `tune_O_all/test.json`. At most 3 test configs in the Thach harness. No other PEG-O config is run on test there.
- Our repo, guard OFF (paper setting), test once, three tables (`pego_test`, `pego_fs`, `pego_rcv`), with
  `GPEG_SIZE_LOCK=1 GPEG_ODO=1` and the (τ, γ) [+S] of `tune_O/final.json`. If Stage A accepts no O point, these
  paper-setting rows use the O point with the highest val score in round 1 of `tune_O` (ties: smaller τ, then smaller
  γ) and are labelled "not selected by val". The same config is also run on val in our repo (T3 only) for the
  per-episode CI.
- Reported regardless of outcome: val+test table next to PEG, PEG+, each Thach component, Thach full+M6 and the
  two existing "strongest" finals; per-episode T3 change vs PEG+ with bootstrap 95% CI over episodes (test, val,
  pooled); what PEG-O fixed per episode and what it did not. No re-selection after seeing test.

## Addendum (2026-10-20, committed before any val run): fusion changed after the 135 smoke (test)
Disclosed: this change was triggered by the one-sequence recovery smoke on test `135_sequence_19q_new` (the same
episode the idea came from). One re-run of the smoke, no parameter iteration on test.
- Finding: with the plan's absolute noise R = γ(0.08h)²·τ/k (≈ 850 px²) and OC-SORT's position covariance P of only
  9–14 px² right after the loss, the Kalman gain is ≈ 0.01: the update does nothing (g53 409–451 coverage 0.09 = PEG+,
  centre error 70.5 → 65.1 px). The feasibility script, by contrast, replaced the estimate outright.
- Change (`PEG._odometry_update`): **relative R** = γ·(τ/k)·P per axis (P = Kalman position variance before the update),
  so the centre gain is 1/(1 + γτ/k), set by the peak sharpness alone; velocity follows through the covariance.
  The χ² NIS gate is replaced by the feasibility script's jump gate (skip if ‖z − ĉ‖ > 0.5 · box diagonal), because with
  R ∝ P the NIS no longer measures anything calibrated. Estimator and anchor rule unchanged.
- Smoke after the change (τ 0.06, γ 1): g53 409–451 coverage 41/43 = 0.95 (= the oracle bound: PEG+'s own box
  re-centred on GT), centre error 31.6 px mean / 52.1 max; g53 815–834 stays 20/20. Flags off: still byte-identical.
- **New O grid**: τ ∈ {0.04, 0.06, 0.08} × γ ∈ {0.25, 1, 4} (centre gain at k = τ: 0.8 / 0.5 / 0.2). Everything else in
  this protocol is unchanged.
- Estimator pin (`scripts/19_peg_o_check.py`, τ 0.05, plan's keep-trying anchor rule): 135 30.4, 320 6.8, 176 28.9
  (= plan), 204 25.8 (plan 21.5), 325 83.7 (plan 82.5: 325 anchors at f268 with k = 0.075, so it does not fall back
  at τ ≤ 0.075).
