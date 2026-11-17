---
name: drive-upload-remotes
description: which rclone remote uploads as which Google account; team Drive folder ids for PEG deliverables
metadata:
  type: reference
---
rclone remotes on this machine (checked 2026-11-17 by uploading a probe and reading its owner):
- `gdrive_rw` = the user's own account (thanh…, owner of the team uploads); scope drive.
- `gdrive_own`, `gdrive2` = the hieukainxoi account; the user said to use it for uploads (2026-11-17).
- `gdrive` = read-only. Upload with `rclone copy <dir> <remote>: --drive-root-folder-id <folder>`.
Team folder (Minh's) id 1uh6LwB9QHm9R0z3nDZBqJPxk162WRgE9. Deliverables folder "ExSORT_bo_sung_cache_fix2 (2026-11-17)" (renamed from PEG_… same id)
id 1EiYu2hzjU-wYmVMNNvhKi-goNvdR3a-V: README, glare masks (ExSORT test + val_half; PEG mask zip removed), training charts, report charts
+ PHAN_TICH.md, YOLOX run-3 training outputs + best weight. Det cache zip 1XPU7xqfqqC8zAXhbtyX838_Ndqx77GhZ.
Related: [[yolox-detector-glaremot2]]
