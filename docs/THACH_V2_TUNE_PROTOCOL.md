# Tuning Thach v2 (M1-M6) on val, pre-registered (2026-10-19)

Committed **before** any tuning run. Why: Thach's parameters were set on Table I test (0 val runs), so the previous
check (`docs/THACH_V2_PROTOCOL.md`) only re-*selected* among his configs on val. Here the parameters and the
combination are chosen on val only, and test is reported once. Runner: `results/thach_v2/tune_val.py`.

## Setup
- His code (`dataset/thach_v2/PEG-main`), guard on (his setting), perception caches as before (val real+synth,
  de-glare off/on). PEG's own parameters are not touched; only his switches and the knobs below.
- Harness change (ours): PEG has its own anti steal/swap resolver; Thach rewrote it without a switch (direction-aware
  swap, velocity-continuity and height-consistency swaps, a wider "nearby pair" test). We copied the original PEG
  resolver into his tracker as `_resolve_identity_peg` behind `GMOT_ID_RESOLVE_V2=0`
  (`results/thach_v2/tracker_id_resolve_switch.patch`), so his rewrite becomes a component (R).
- Start S0 = his code, every switch off, `GMOT_ID_RESOLVE_V2=0`. Verified equal to our PEG (guard on) on test:
  T1 68.34/IDSW 15, T2 61.41, T3 76.2, identical metrics; T2/T3 MOT files byte-identical, T1 files differ only by
  0.01 px rounding (float32 cache). Nothing else in his code differs from PEG with the switches off (diff of
  tracking/perception/eval code against `a39fddb^`).
- Reference = our PEG, guard on (val T1 70.24, T2 HOTA 76.25, T3 Rcv@.5 67.6; test known).

## Components and grids (his default marked *)
| comp | what | grid |
|---|---|---|
| R | old anti steal/swap resolver | on |
| M1q | adaptive Q (Kalman uncertainty grows while lost) | pos std/frame ∈ {0.01, 0.02, 0.03*}·h, vel = pos/3 |
| M1c | uncertainty cone association | χ² ∈ {5.99, 9.21*} × walk speed ∈ {0.04, 0.06*}·h |
| M1d | interaction damping ×0.88 (coasting tracks) | on |
| M2 | Re-ID (P4 feature + HSV) | deep weight ∈ {0.5, 0.7*, 0.9} |
| M3 | dynamic h / adaptive TTL | h decay ∈ {0.03, 0.06*, 0.12} × TTL {off, on*}; or TTL only |
| M4 | dormant pool | similarity ≥ {0.50, 0.60*, 0.70}; brings M2 (0.7) if M2 is not chosen |
| M5 | headlamp anchor | weak-update noise multiplier ∈ {6*, 24, 96} |
| M6 | de-glare tone mapping | on, his parameters (each new M6 setting needs a detector re-run on val, ~2.6 h) |

26 grid points per round. Points are evaluated on the val COMBINED of all three tables.

## Rule (greedy forward selection, same thresholds as before)
X = S0. Each round, every grid point of every component not in X is added to X and evaluated.
Δ = (T1 HOTA, T2 HOTA, T3 all-burn Rcv@.5)(X + point) − (X). Admissible: every Δ ≥ −0.5. Score = ΣΔ.
1. Rank admissible points with score > +0.5 (ties: component name).
2. Single-event check on the best one: drop the val sequence most favourable to it in T1 and in T2 (TrackEval
   re-run) and the most favourable burn episode in T3; the summed Δ without them must stay > 0. If it fails, try the
   next point in rank order.
3. The first point that passes is accepted (X ← X + point, its value fixed). If none passes, stop.
4. Final F = X. **Test is run once, for F only**, all three tables, next to PEG. No other config is run on test.

Also reported (not used for selection): the whole search trace (`results/thach_v2/tune/trace.json`), F vs PEG
on val with per-episode bootstrap CI for T3.
