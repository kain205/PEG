---
name: coast-design-research
description: 2026-10-20 research round after PEG-O failed — oracle headroom, residual pools, literature; what is dead, what has data support (long-baseline velocity, burn-gated backfill, causal cap, burn-region stitch), and the synthetic GT leak caveat
metadata:
  type: project
---

Reports: results/research/{ORACLE_T3.md, RESIDUAL_POOLS.md, LITERATURE_IDEAS.md} (+ json, scripts). Key facts:
- T3 is all about the centre: oracle centre 99.9, oracle TRUE constant velocity 96.0 (+12 vs PEG+), size/looser/approach <= +1.8.
- Velocity from the last 5 frames is noise (-10); OLS over the last K=40 detection frames gives 87.8 vs PEG+ 84.2 on
  43 tracked episodes (all 48: test 82.7 vs 82.2, val 74.6 vs 67.3, pooled 79.5 vs 76.2; CI vs PEG+ [-0.6,+7.9]).
  GT-fitted K=40 bound 91. Damping costs nothing. Slope noise ~ sigma*sqrt(12/K^3).
- Dead on data: disc-geometry centre (PEG-O), DT peak, re-anchor on dropped core_frac>.85 dets (80% precise, net -7),
  gated dropped tier (-1), scene-flow prior (chance), longer frozen coast on real (+185 TP / +633 FP), size adaptation.
- Real data: only 2.2%/1.0% of GT frames (test/val) are burnt; detector still hits 35%; T1 coast-through-burn ceiling ~+1.4 recall.
  Missed workers on real mostly stand still (frozen box bridges 98% of gaps <= 24) but FP cost of blind coast is 3x the gain.
- Zombie re-arm: a cap at 48 hidden frames = T2 -354 FP for 24 TP, T1 -26 FP / 0 TP (free). Burn-exit stitch fixes 5-6/6
  new-id episodes (1 false merge / 48). Pre-loss boxes are NOT inflated (H3 dead).
- Burn-gated backfill (fixed-lag, interpolate the gated gap once re-acquired): T3 82.2->86.5 test, 67.3->71.1 val, FN down,
  FP flat; without the gate T1 FP 1440->1989. Needs its own 'fixed-lag' row (not online). Stitch raises its bound to 92.6/83.7.
- CAVEAT: synth_glare centres/sizes the burn disc on the GT box -> any method reading disc geometry leaks GT on T2/T3.
  Velocity/backfill/cap/stitch do not read the disc (only the existence gate), so they are immune.

**Why:** these are oracle/pooled-episode measurements on val+test, not single-episode intuition (the PEG-O mistake).
**How to apply:** next method = design the coast (PEG decides *whether*, this designs *how*): CV-model filter online with
K~40 slope (use only if slope significant), RTS-smoother/backfill at fixed lag, causal cap, burn-exit stitch. Tune on val
([[tune-on-val-from-scratch]]), report online and fixed-lag rows separately. See [[peg-o-photometric-odometry]].
