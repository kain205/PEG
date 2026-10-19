---
name: tune-on-val-from-scratch
description: "Evaluating someone's methods = re-tune their parameters on val from scratch (pre-registered), not just re-select their configs; test once"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1fac5c16-d7a8-4a82-9a67-c02b9892658f
  modified: 2026-10-19T02:47:40.644Z
---

When evaluating a method someone else tuned (e.g. Thach's PEG-F), re-selecting among their configs on val is not
enough: their internal parameters may have been tuned on test. Re-tune the parameters and the combination on val
only, starting from a verified PEG-equivalent point, with the rule pre-registered (committed before any val run),
then report test once for the final config.

**Why:** the user said "tất nhiên rồi, làm bước 2 trước chứ, tại vì như thế mới đánh giá đúng" (2026-10-19) after I
had only re-selected Thach's 14 configs on val.

**How to apply:** do the full val tuning by default, without asking first; verify the start point reproduces PEG
exactly; make any always-on change a switchable component. Related: [[delegate-easy-tasks-to-sonnet]],
[[sync-memory-to-repo]].
