---
name: keyframe-vision-check
description: "2026-10-21 MoRongMo labels redone as few keyframes + every keyframe checked by Claude Opus vision via API (scripts/23); user's rules and cost facts"
metadata:
  node_type: memory
  type: project
  originSessionId: 0df269ad-f5e2-495b-a234-6df8236c01ce
  modified: 2026-10-20T23:09:18.496Z
---

MoRongMo labeling (frames 35068-56611) was redone on 2026-10-21 as a KEYFRAME job: `scripts/18_project_edit.py rekey`
(smooth + Douglas-Peucker, ids 200+) then `scripts/23_keyframe_check.py` (run / apply / review / review --sweep):
Claude Opus 5.5 vision judges every keyframe (same person? whole body? best of box A vs detector boxes B/C/D) and an
identity sweep over strips of 14 keyframes finds id hops (split/clear/end ops). Final: 95 tracks ids 200-294,
`results/label_MoRongMo/kf/project_final.json`, copied into the app project. Details in `results/label_MoRongMo/NOTES.md`.

User's rules for this job (stated 2026-10-21):
- Keyframes decide the label: pick few, make them right; never label frame by frame with a weak model.
- Box = whole person: helmet to shoes, outstretched arms included; visible extent only if occluded/cut.
- Spend the Anthropic API key in `.env` freely (Opus), but SAVE Claude Code tokens: subagents only orchestrate,
  no image viewing in subagents; hand every judgement to the API. Whole check cost ~$46 + ~$8 review/sweep.
- Hand-edited tracks (found by diffing against the last delivered project) are kept verbatim, only renumbered.
- `.env` holds the bare key (no VAR= prefix); it is now in `.gitignore`.

Round 7 (same day): user reviewed the early part by hand, then asked for three fixes, all in script 23: `unshrink`
(standing person occluded -> box pulled up; geometry = bottom/side moves in while the top stays, API confirms),
`extend` (track ends inside the image -> probe later frames, merge with the continuation track or hold the box),
`blob` (delete tracks that are not a recognizable person; none found). 95 -> 59 tracks, ids 200-258.
The API key hit its monthly usage limit on 2026-10-21; the user raised the limit the same day, so the second
`unshrink` pass ran (423 more keyframes). Final round-7 result: 59 tracks, ids 200-258, `kf/project_r7.json`.

**How to apply:** for any further label fixes, edit the app project with script 18 (app closed), re-run
`23 run` only for changed tracks (resumable), then `rekey --keep '*' --first_id 200`. Related: [[morongmo-labeling-task]],
[[delegate-easy-tasks-to-sonnet]].
