---
name: exsort-is-team-method
description: The team's tracker is ExSORT (minhdq245/exsort); PEG is its old version and is dropped from reports/charts
metadata:
  type: project
---
2026-11-17: the user said the algorithm is named **ExSORT**, not PEG (repo https://github.com/minhdq245/exsort, Minh's;
selected config `configs/selected.json`, no ReID, glare mask V>=235 & S<=89 at 512x512). PEG is the old version:
"Bỏ peg hẳn đó là bản cũ". So in deliverables (charts, analysis, READMEs, Drive folder names, slide text) present
ExSORT + the 8 baselines only; no PEG row. Table I on the YOLOX fix2 cache: ExSORT HOTA 61.39 / IDF1 79.69 / MOTA 72.50.

**Why:** the team's paper/method moved from PEG to ExSORT; showing PEG next to it confuses readers.
**How to apply:** default to ExSORT naming in anything new; the local repo/dir is still called PEG (do not rename it).
Related: [[drive-upload-remotes]], [[yolox-detector-glaremot2]]
