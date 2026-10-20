# PEG-O orchestrator log

Plan: `C:\Users\thanh\.claude\plans\read-the-all-the-pure-creek.md`. Orchestrator = Opus (reviews), executor = one Sonnet agent.

## WP0 (2026-10-20)
- Wrote `docs/PEG_O_PROTOCOL.md` myself (decision doc), committed locally **4b13dc3** before any PEG-O run.
- Decisions recorded in the protocol (plan left them open):
  - Stage A strongest variant → separate dir `tune_O_strong/`; tested only if its final differs from strict.
  - Stage B candidates = Thach GRID only (P/O/S fixed from Stage A, not candidates).
  - If Stage A accepts no O point, the guard-off paper rows use the best-scoring O point of round 1 (labelled "not selected by val").
  - S = skip deletion **and** the `allowed_gap` emission check in `PEG.step` while armed (otherwise a survived track is kept but never emitted, so S could not recover frames).
  - Per-episode CI for val needs a guard-off val T3 run of PEG-O in our repo (`v_pego_rcv`), val only.
- Pre-existing uncommitted user changes (AGENTS.md MoRongMo line, scripts/14-18) are left untouched and not committed by me except AGENTS.md at WP5 (it already contains the user's line).
- Deck numbering: the brief says "slide 28 = Full metrics", but the current deck has Full metrics test/val = slides 34/35,
  "Kết luận và bài học" = 36, Q&A = 37 (SCRIPT_PEG_F.md). New PEG-O slides go after "Full metrics trên val" (35).

## WP1
- Executor brief: shared estimator `odo_measure` in beacon_tracker.py used by both the tracker and scripts/19_peg_o_check.py;
  hooks in `_try_beacon`; S helper `armed_survives` in tracker.py; `--seqs` filter in eval_recovery for the 135 smoke.
- Code reviewed (git diff): matches §2.2; flags-off path only adds `mt._odo_anchor = None`.
- 19_peg_o_check at τ=0.05 with the plan's keep-trying anchor rule: 135 30.4, 320 6.8, 176 28.9 (= plan);
  204 25.8 (plan said 21.5; bound ≤ 28.3 met); **325 83.7** (plan: 82.5 "falls back"). Under the keep-trying rule 325
  anchors at f268 (k=0.075 ≥ 0.05) and is 1.2 px worse than frozen — the plan's claim that the keep-trying rule makes
  325 fall back is not true at τ=0.05 (it is at τ=0.10). Decision: keep the pre-registered §2.2 rule unchanged (no
  tuning of the rule on test episodes); record the deviation. The reference script's own output was 204=28.3 (first-frame rule).
- Byte-identity (flags unset, guard off, caches): 7 pairs all identical (T1 20/20 ×2, T2 15/15 ×3 incl. peg_fs_noguard
  and peg_fs_cached, T3 15/15 ×2). `--seqs` filter added to glaremot/eval/eval_recovery.py (default all).
- **135 smoke FAILED** with plan §2.2 fusion (τ .06, γ 4): g53 409–451 coverage 0.09 = PEG+; centre error 70.5 → 65.1 px.
  Causes (executor diagnosis, checked by me against the code): (1) R = γ(0.08h)²τ/k ≈ 860 px² vs OC-SORT position P of a
  few px² → Kalman gain ≈ 0.03: the update is a no-op (the feasibility script replaced the estimate outright);
  (2) the tracker's held box is 146×229 while GT is 264×272 → 124×332, so even a perfectly centred box has IoU ≈ 0.5
  at best: the ≥ 0.8 smoke target (made with the GT box size) is unattainable for any centre-only fix.
- Decision: fusion change (test-informed, disclosed, pre-registered as protocol Addendum before any val run):
  relative R = γ·(τ/k)·P (centre gain 1/(1+γτ/k)), jump gate 0.5·diag (the feasibility's stand-in) instead of NIS,
  γ grid {0.25, 1, 4}. One re-run of the 135 smoke, no iteration on test. Smoke criterion replaced by: centre error
  falls clearly and coverage vs the oracle-centred upper bound.
- Re-diagnosis (P logged): P00 = 9–14 px² at f410–412 → gain 0.01; oracle-centred PEG+ box (own w×h) covers 41/43, so the
  size-cap hypothesis was WRONG; only the gain was the problem.
- Fusion change implemented (relative R, jump gate 0.5·diag, default γ 1). T3 byte-identity re-checked (15/15 ×2).
  Smoke once (τ .06, γ 1): g53 409–451 0.95 (= oracle bound), centre err 31.6 mean / 52.1 max (PEG+ 70.5/101.2).
  I re-ran `results/peg_o/smoke_135.py smoke_pego2_135` myself: same numbers.
- Protocol Addendum (fusion + γ grid {0.25,1,4}) committed with the code before any val run.

## WP2
- Port to Thach fork (`results/thach_v2/peg_o_port.patch`, base copies in `peg_o_port_base/`). His fork has no FS/peg_f_flag →
  counters dropped there. Checks: flags-off S0+P on test byte-identical to th_tv51d09158 (T1 20/20, T2 15/15, T3 15/15, max diff 0.0);
  port vs ours on test 135_19q (guard on, P+O τ .06 γ 1): 882 rows byte-identical.
- Harness: run.CLEAR += GPEG_ODO*, GPEG_ARMED_SURVIVE; tune_val.py `--peg_o` (tune_O), `--peg_o --strong` (tune_O_strong),
  `--peg_o --all` (tune_O_all, CANDIDATES = Thach comps). Old keys unchanged (S0 tvb9600652, S0+P tv51d09158).
- **Val Stage A (strict and strongest): nothing accepted, final = P (PEG+).** Every O point: ΔT1 ≈ 0, ΔT2 −1.0…−4.8,
  ΔT3 Rcv@.5 −13.5…−41.2 vs S0+P (67.3). S is a no-op on val (byte-identical to P; armed-while-over-age never happens).
  Best (least bad) O point = O[8] τ .08 γ 4 (score −15.05). Stage B not run (would equal tune_strong_P, protocol).
- Bug hunt before accepting (val only): (D1) the offline GT-anchored estimator (19-check `run()`) ALSO fails on the
  broken val episodes (adds 3–9 px on 28–34 px wide near-static workers; frozen 6–13 px); (D2) 0 stale anchors, gains
  0.50–0.71 as intended, median |z−c| 9.7 px; 73/216 updates on non-T3 glare (147, 332); (D3) val sat cache = ours, aligned.
  Verdict: **method failure** — the saturated component's matched-filter peak moves 10–20 px with no body motion
  (ramp-up/fade, merging), the anchor is often taken on the ramp, gain ~0.6 + injected velocity keep the box drifting.
  On the motivating test episode (264 px box, 100 px walk) this noise is negligible; on narrow val workers it exceeds the box width.
- Decision: no redesign after val (that would be tuning the design on val after the pre-registered grid failed); report as is.
- Test, once each (protocol): tune_O/test.json = S0+P (guard on) 68.41 / 62.33 / 82.2 (= known PEG+). tune_O_strong not tested
  (same final), tune_O_all not run (= tune_strong_P).
- Our repo, guard off, O[8] (τ .08 γ 4, "not selected by val"): T1 pego_test HOTA 68.15 / IDF1 82.15 / MOTA 80.36 / IDSW 17;
  T2 pego_fs HOTA 61.73 / MOTA 73.06 / IDF1 77.26; T3 pego_rcv Rcv@.5 73.6 / total 74.5 / ID-off 9.5% (PEG+ 82.2 / 85.1 / 15.5%).
  Val T3 v_pego_rcv 53.8 (PEG+ 67.3). v_pegplus_chk_rcv == v_A_rcv (9/9). Verified the report lines myself.
- Episodes (results/peg_o/episodes.json): PEG-O vs PEG+ test −8.6 [−19.8, +1.0] (6 better / 5 worse), val −13.5 [−29.0, −0.8],
  pooled −10.6 [−19.5, −2.7] (48 episodes). 135 g53 4→11/43 at O[8] (smoke config τ.06 γ1 gave 41/43).

## WP3
- full_metrics.py: + tune_O ledger, row "PEG-O (P+O, best val point τ .08 γ 4; rejected by val)" (val only; test "–" by protocol),
  S/ALL footnote, best-per-column bold, best-overall line (val ΣΔ: STRONGEST M1c+M1d, +3.03; its test T3 70.0). Old 32 row
  lines identical (except bold). where_gain `val|O` from val data only (where_gain_O.py), other entries untouched.
- results/peg_o/{collect.py, numbers.json, RESULTS.md}; scripts/20_peg_o_figures.py → figures/{135_19q_strip, 187_66q_strip, scoremap}.png.
  Viewed all three: strips fine; scoremap 187 panel too narrow / single frame cannot show drift → asked for square crops + peak trail f142–150.

## WP4
- Deviation: 3 new slides instead of 2 (A algorithm, B val/test result, C mechanism with the 135 vs 187 strips): a negative
  result needs its mechanism shown; one slide could not hold effect strip + grid + CI + two filmstrips legibly.
- Q&A "sao B/M5 thua mà PEG-O thắng?" reworded to "B và M5 thua, PEG-O khác gì mà vẫn thua?" (PEG-O did not win).
- Deck built + rendered: slides 34/35 full metrics (15 rows, PEG-O row, best marked, best-overall footer), 36 PEG-O algorithm,
  37 val/test result, 38 mechanism (135 vs 187 strips), 39 Kết luận (PEG-O bullet, direction 3 replaced), 40 Q&A;
  2 Q&A entries in SCRIPT_PEG_F.md. I viewed 34–39: fixed by executor on my review: slide 38 strips enlarged,
  "Thạch" diacritic, 325 wording. scoremap.png kept out of the deck (illegible at slide size; in RESULTS figures).
- Caught myself: 325 at τ .08 is NOT "no update" — pego_rcv differs from PEG+ from f296 (end of burn), coverage unchanged.
  Docs/Q&A worded accordingly.

## WP5
- docs/PEG_O_RESULTS.md (me), AGENTS.md (repo map 19/20, PEG-O knobs, reference line), memory file updated + mirrored to
  .claude/memory/. AGENTS.md committed WITHOUT the user's pre-existing uncommitted MoRongMo line (staged via hash-object).
- No push (parent instruction; the memory-sync convention says push — left for the user).
