---
name: delegate-easy-tasks-to-sonnet
description: User wants mechanical/easy work handed to Sonnet subagents; the main model does the thinking and decisions
metadata:
  node_type: memory
  type: feedback
  originSessionId: 7a590f5f-3c0d-41e6-985b-99442d9be939
  modified: 2026-10-06T16:18:25.548Z
---

Hand off easier tasks (deck building, rendering, figure checks, boilerplate scripts) to subagents with `model: "sonnet"`; keep the main model on reasoning, experiment design and decisions.

**Why:** User said (2026-10-06): "hand off easier task to sonnet nhé m làm việc nghĩ thôi".

**How to apply:** For long multi-step jobs in this repo (e.g. PEG+ slides), plan + decide yourself, then spawn Sonnet agents with precise, self-contained briefs and verify their output. Related: [[peg-plus-project]]
