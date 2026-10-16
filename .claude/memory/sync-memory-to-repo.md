---
name: sync-memory-to-repo
description: Auto-memory is mirrored into the repo at .claude/memory/ and pushed to origin (kain205/PEG) whenever it changes
metadata:
  node_type: memory
  type: feedback
  originSessionId: 1fac5c16-d7a8-4a82-9a67-c02b9892658f
  modified: 2026-10-16T14:58:04.770Z
---

After adding or changing any memory file, copy the whole memory dir to `D:/PROJECT/PEG/.claude/memory/`, commit only that path, and push to `origin` (kain205/PEG, main). Never push to `upstream`.

**Why:** User said (2026-10-16): "Tự động ghi nhớ là push lên repo đi nhé, cũng để mày dùng thôi" — memory is for the agent anyway, so keep it in the repo where other machines/sessions get it.

**How to apply:** Standing permission for memory-only commits (`git add .claude/memory && git commit` + push). It does not extend to other uncommitted work; AGENTS.md's "commit/push only when asked" still holds for everything else. Related: [[delegate-easy-tasks-to-sonnet]]
