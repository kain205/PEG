# Evaluating Thach's v2 (M1-M6), pre-registered (2026-10-18)

Committed **before** any val number of v2 existed. Same criteria as the previous checks: same config for the
baseline, all three tables, choose on val and score test once, and count single events.

## Code and runs
- Code: `dataset/PEG-main.zip` (received 2026-10-18), extracted to `dataset/thach_v2/PEG-main`, run unchanged
  except one harness change: `eval_recovery.py --det_cache` replays the same perception cache as `eval_mot.py`.
  Runner: `results/thach_v2/run.py`, which imports his `scripts/08_ablate_methods.py` CONFIGS verbatim.
- His setting: `GMOT_TRACKER=beacon`, guard at the runtime default (on). Reference: our PEG with guard on.
- Perception caches are built live on our GPU (real/synth × test/val × de-glare off/on). His shipped Table I test
  caches are re-checked live on our machine.

## Test (already seen, his table)
All 14 of his configs reproduce his Table I exactly from his caches. Tables II/IV and III were never reported by
him; we compute them on test for the same 14 configs.

## Val: the candidates and the rule
Candidates: his 14 configs (base, base+M1..M6, full, full−M1..M5, full+M6). No numeric parameter is changed.
Reference for deltas: **his base** (that is what his deltas use). Our PEG (guard on) is reported next to it.

Primary metrics, val COMBINED: T1 HOTA, T2 HOTA, T3 all-burn Rcv@.5. For each candidate C:
Δ = metric(C) − metric(base); score = ΔT1 + ΔT2 + ΔT3.

1. Admissible: every Δ ≥ −0.5.
2. Rank admissible candidates by score. Take the best one with score > +0.5.
3. **Single-event check (new, from the last lesson).** Re-score the candidate and base without the one val
   sequence (T1, T2) and without the one burn episode (T3) that most favours the candidate. The score must stay
   > 0. If it fails, try the next candidate in rank order.
4. If none passes: the selection is **base** (no method is supported by val).
5. The selected config's test numbers are reported as they are, next to base, full, full+M6 and our PEG.

## Also reported (not used for selection)
- base vs our PEG on val and test: base contains the old M1-swap identity logic, which is always on in v2.
- Firing counters from his logs: cone matches (M1), dormant revivals (M4), de-glared frames (M6).
- Table III per-episode deltas with bootstrap 95% CIs (10k resamples over episodes), test, val and pooled.
- Per-sequence Table I/II HOTA deltas: which sequences carry each gain.
