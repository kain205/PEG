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
