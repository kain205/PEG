---
name: morongmo-labeling-task
description: "MoRongMo video labeling job (frames 35068-56611, ids from 20) for FastLabeler Local - key facts and pitfalls"
metadata:
  node_type: memory
  type: project
  originSessionId: 271728d8-cb06-4fc3-9c40-6928b96f81a6
  modified: 2026-10-19T17:00:58.306Z
---

Labeling job started 2026-10-19: label `dataset/MoRongMo/00000001754000000.mp4` (73 353 timeline frames @25 fps,
2688x1520, HEVC) for the user's friend's tool FastLabeler Local v4.5 (github.com/minhdq245/fastlabelerlocal, Tk exe
in `dataset/fastlabeler/`). User's share: display frames 35068-56611 (1-based, app numbering), track ids from 20.
Friend did 1-14330 (snapshot on Releases) and 14330-35067. Deliverable: handoff zip (project.json + manifest) + gt.txt.

Pitfalls found:
- The app indexes frames by timestamp: slot t = floor((pts-start_pts)*tb*fps+0.5); the camera pts drift 1 ms
  every ~750 frames, so decode order n != t (n-t = 47 at 35068, 75 at 56611; 73 451 decoded vs 73 353 slots).
  `scripts/17_app_timeline_frames.py` builds `dataset/MoRongMo/app_35068_56611/images` in app order (hard links).
- The shipped PEG detector is useless on this footage (bright, close-up workers): ~0 detections. COCO yolo11l
  @1280 (`weights/pretrained/`) works well; pipeline = `scripts/14_autolabel_range.py --detector coco --tracker bytetrack`
  (chunked percep cache in `cache/label_MoRongMo`, ~7.3 fps on the GTX 1650), 15 (MOT->project.json), 16 (QA sheets).
- App project dir on this machine: `%LOCALAPPDATA%\FastLabeler\video_projects\00000001754000000__e410f9371a`
  (template saved by the app: `results/label_MoRongMo/template_project.json`). GUI driver: `results/label_MoRongMo/gui.ps1`
  (PrintWindow screenshots; Focus via AttachThreadInput; Save button at window-relative (1418,403)).
- Friend's style: continuous tracks (manual_carry, interpolation across occlusions, no occluded flags), full-body boxes,
  one `outside` keyframe at the end.

- Done 2026-10-20: 49 review edits applied via `scripts/18_project_edit.py` (reads/edits project.json like the app;
  validated against the app's Export). Deliverable `results/label_MoRongMo/handoff_MoRongMo_35068_56611.zip`
  (project.json + gt.txt + classes). Low-confidence leftovers in `handoff/README_VI.md`. User's rule: lost track → new id.

**How to apply:** continue from `results/label_MoRongMo/NOTES.md`; never trust decode-order frame numbers; the app's
project.json is the source of truth once the user has edited in the app (edit with script 18, app closed).
