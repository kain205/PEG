# PEG-C orchestrator log

Plan: `C:\Users\thanh\.claude\plans\peg-c-coast-design.md`. Orchestrator = Opus (decides, reviews), executor = one Sonnet agent.

## WP0 (2026-10-20)
- Wrote `docs/PEG_C_PROTOCOL.md` myself, committed locally **0f92215** before any PEG-C run.
- Decisions recorded in the protocol (plan left them open or ambiguous):
  - V uses the raw detection-box centres with frame indices in a separate buffer (= the oracle b40 estimator), not the
    smoothed `centers` deque (that one is cleared on re-entry and holds fused EMA centres). Young-track rule kept.
    Speed-guard failure → v = 0 (fallback, as the oracle verdict asks). The old 2× median-step clamp stays as a ceiling.
  - S runs before the missed-track loop (not inside the birth loop): in the birth loop the track has already had
    `kf.update(None)` this frame, and a second update would corrupt OC-SORT's ORU replay. Candidates = unmatched
    confirmed non-exiting tracks armed within 10 frames; detections = unmatched ones that pass `_birth_allowed`.
  - B endpoints = the emitted detection boxes; "armed in the gap" = `_armed_frame > last detection frame`; added rows
    conf 0.001; row order untouched unless a record is applied.
  - BB trigger = φ(birth box, mask of the birth frame) ≥ h (plan wording); also fills the tentative frames f_b..f_c−1
    with the track's own detection boxes (otherwise the backward extension leaves a hole at the birth frames);
    L = `GPEG_BACKFILL_L` if set, else 90.
  - Strongest variant only for the online stage (plan); lag stage and ALL as in the plan. Duplicate finals not re-tested.
  - If a stage accepts nothing, the paper-setting rows use its best round-1 point, labelled "not selected by val" (PEG-O precedent).
- Pre-existing uncommitted user changes (AGENTS.md MoRongMo line, scripts/14-18) left untouched.

## WP1
- Executor implemented V, C, S, B, BB (tracker.py, beacon_tracker.py, eval_mot.py; shared `ols_velocity`, `mot_row`,
  `apply_backfill`, `backfill_lag`). I read the full diff: matches the protocol definitions. B/BB records are applied by
  the eval writer after each step; rows re-sorted only if a row was added.
- Verified myself: byte-identity 6/6 pairs (cmp), check21 b40 87.8 pooled exact (0 episodes differ from the json).
- Val smoke P+V40: 187 g247 n35 19→35, 133 g117 n37 17→24 (oracle 35, 26); 133 g117 n36 36→36 (centre err 2.7→6.8).
- WP1b structural check (I asked for txt + counters only): pass. Counters on val: cap_block T3 518 / T1 2452, stitch 2/0,
  backfill frames 389/71 (hidden mode adds 0 rows on T3 val, 17 on T1 val: the gate already emits almost every gap frame,
  so B's effect lives in mode `all`), BB never fires (0 tracks).
- Executor disclosed it saw COMBINED/all-burn lines of ad-hoc wiring runs before my "no metrics" instruction; recorded in
  protocol Addendum 1. No design change followed; selection is mechanical.

## WP2
- Port (`results/thach_v2/peg_c_port.patch`, base copies `peg_c_port_base/`; his fork has no FS → counters dropped). Checks
  verified by me from the txt reports: flags-off S0+P on test byte-identical to th_tv51d09158 (T1 20/20, T2 15/15, T3 15/15);
  port = ours (guard on, P+V40+C48+S1.5+B90all, val T3 187/133): byte-identical, 484/5571 rows. Harness diff read: grids
  and modes as in the protocol; old keys unchanged.
- **Online strict (tune_C): final P + V[3] (K 40, t 2)**, val (69.67, 76.20, 75.8) vs PEG+ (70.11, 76.30, 67.3): T3 +8.5,
  T1 HOTA −0.44 (admissible, margin −0.5), single-event check +5.36. Round 1: V K20 +3.6/+3.4, V K40 +7.95/+7.96, C +0.07/+0.04,
  S +0.66 (T2 only). Round 2: S +1.30 (T2) fails the single-event check (−0.07 without its best unit); C ≤ +0.09.
- **Online strongest (tune_C_strong): P + V[3] + S[0]** (69.67, 77.5, 75.8) — differs from strict → tested once.
- C (causal cap) never moves anything beyond +0.09 on val: the stale-zombie re-arms it targets are rare on val.
- **Fixed-lag (tune_C_lag): nothing accepted**, final = online final (P + V[3]). Round 1 vs P+V[3]: B L45/L90 hidden
  +0.00/+0.03 (with V and the gate, the id already has a row on almost every gap frame, so "hidden" fills nothing), B all
  −1.83/−1.80 (T3 −2.1, T2 +0.28), BB +0.00 (never fires). Per protocol the paper-setting fixed-lag rows use the best
  round-1 point B[2] (L 90, hidden), labelled "not selected by val". tune_C_lag_all skipped (= tune_C_all).
- My val-only diagnosis of B all (after the stage decision; `analyze.episodes`): the T3 loss is 2 episodes, 332 g1030 10→0
  and 178 g206 4→0 (141 g71 22→24): the straight line between the two detection boxes overwrites V's partially right
  coast when the re-acquisition box is off (178 g206 = the stationary worker the oracle also loses).
- **ALL (tune_C_all, strongest rule, Thach comps on top of P+V[3]): final M1c[0] + P + V[3]**, val (70.09, 77.49, 75.8).
  Round 1: M1c +1.71 (T1 +0.42, T2 +1.29, T3 0), M5 −0.87…−3.41 (T3 −0.8…−3.1: the anchor fights V), M1d −0.33, R −0.18,
  M6 −0.02, M3 +0.06, M1q/M2/M4 0. Round 2: nothing > +0.5.
- Val search complete. Test plan (once each): tune_C (P+V[3]); tune_C_strong (P+V[3]+S[0]); tune_C_all (M1c+P+V[3]);
  tune_C_lag = same key as tune_C (not re-run); tune_C_lag_all skipped. Our repo guard off: online P+V[3] (pegc_*),
  fixed-lag P+V[3]+B[2] L90 hidden "not selected by val" (pegcl_*), val T3 for the CI (v_pegc_rcv, v_pegcl_rcv).
- **Test, once each (Thach harness, guard on)** — T1 HOTA/IDF1/MOTA/IDSW | T2 HOTA/IDF1/MOTA | T3 Rcv@.5/total/ID-off:
  tune_C P+V[3] 68.80/84.26/80.98/15 | 60.89/74.61/74.55 | 80.4/81.8/18.5; tune_C_strong P+S[0]+V[3] 68.86/84.34/81.16/14 |
  62.67/78.29/75.55 | 81.2/81.8/10.5; tune_C_all M1c+P+V[3] 68.78/84.24/80.95/15 | 61.35/75.45/75.13 | 81.2/81.8/11.6.
  (PEG+ there: 68.41/82.68/80.77/15 | 62.33/77.52/73.99 | 82.2/85.1/15.5.) tune_C_lag = tune_C key, not re-run.
- **Our repo, guard off, test once** (verified from the report files myself): pegc T1 68.49/IDF1 83.24/MOTA 80.58/IDSW 18/FP 1461/FN 2583
  (PEG+ 68.23/82.24/80.52/17/1440/2618); T2 HOTA 61.15/MOTA 73.63/IDF1 75.30/IDSW 20/FP 2058 (PEG+ 62.54/73.37/77.95/16/2113);
  T3 Rcv@.5 80.5/total 81.8/ID-off 14.6% (PEG+ 82.2/85.1/15.5%). pegcl (fixed-lag L90 hidden, not selected by val): T1 68.48,
  T2 HOTA 61.04 MOTA 73.21 (FP 2128), T3 identical to pegc.
- Episodes (results/peg_c/episodes.txt): PEG-C vs PEG+ test −1.8 [−7.7, +3.6] (4 better/5 worse), val +8.6 [+3.0, +15.7]
  (9/1), pooled +2.4 [−2.1, +6.8] (13/6). Test losses 211 g320 25→13, 176 g204 25→10, 204 g300 25→21, 183 g241 24→21, 135 g53 4→2;
  gains 316 g6 22→35, 145 g84 31→36, 204 g300 38→40, 325 g3 30→31 (centre err 59→36 px).
- Reading: the result follows the oracle's own warning (b40 gain val-driven: all-episode test +0.5, val +7.3). Val accepted V
  honestly and test does not confirm it on T3; T1 IDF1 +1.0 (guard off) / +1.6 (guard on) is the one test gain; T2 HOTA −1.4
  (AssA −2.8, IDSW 16→20) is a cost. No re-selection.

## WP3
- full_metrics.py + where_gain_C.py: 4 rows (online, fixed-lag 90 val-only, strongest, ALL); pre-existing row lines identical
  after stripping bold (executor diff; I read the new rows). Best overall (val ΣΔ vs PEG) is now ALL = PEG-C + M1 cone
  (+9.29; test 68.78 / 61.35 / 81.2) — val-driven by T3 +8.2, which test does not reproduce.
- numbers.json (collect.py), figures (22_peg_c_figures.py): viewed 187_66q_strip (val win: PEG+ misses f224/f235, PEG-C
  IoU .69/.55), 211_88q_strip (test loss: PEG-C drifts below GT, misses f452), slope_noise (σ 2.21 px; measured error
  0.84→0.28 px/f then plateaus with the GT-past model error 0.30: CV model is the floor). Accepted.
- Post-test diagnosis (replays byte-identical): on 176/211 v_ols equals the oracle's or is close; guard/ceiling/t=2 never hit.
  My own per-frame check: PEG+ and PEG-C differ only by the entry velocity, and PEG+'s Kalman velocity was the better one
  on both losses (176 Kalman (−1.29,−0.77) vs OLS (−1.02,−0.87), true (−1.24,−0.47); 211 (−0.33,+1.42) vs (+0.53,+1.08), true
  (−0.08,+1.96); 211's 40-detection history straddles an earlier 40-frame gap, `_det_hist` is never cleared by design).

## WP4
- Deck 43 slides: new 39 (oracle table + slope_noise), 40 (algorithm, knob grid, leak + fixed-lag caveat), 41 (val vs test
  strip with a separate "fixed-lag 90" row, per-episode CI, 187 win / 211 loss strips, why test loses); 34/35 full metrics
  (19 rows, new best-overall footer); 42 Kết luận; 43 Q&A; SCRIPT_PEG_F.md Q&A 14–16 (fixed-lag, synth leak, why val≠test).
- I viewed 34, 35, 39, 40, 41, 42, 43. Fixed myself: slide 42 said "chỉ T1 IDF1 +1.0 nhất quán" — but val T1 IDF1 is −1.10;
  now "+1.0 trên test (val −1.1: chưa chắc)", the val number computed from full_metrics.json (not typed). Same wording fix
  in make_results_md.py → RESULTS.md (there the −1.1 is in the generator text). Rebuilt + re-rendered, viewed 42 again.

## WP5
- docs/PEG_C_RESULTS.md (me), AGENTS.md (repo map 21/22, PEG-C knobs, reference line), memory peg-c-coast-design.md +
  MEMORY.md, mirrored to .claude/memory and the auto-memory dir (also mirrored principles-from-failures-ok.md, which
  existed only in the auto dir).
- Incident (mine): an AGENTS.md edit script opened the file for writing before an assertion failed and truncated it. Restored
  from HEAD + the user's single uncommitted MoRongMo line (known from the earlier `git diff`); blob hash 4fcd236 = the user's
  original working copy, so the restore is exact. AGENTS.md committed WITHOUT the user's line (staged via hash-object).
- One local commit, no push.
