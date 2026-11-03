---
name: local-disk-is-drive-d
description: WSL disk lives on Windows D: (~48 GB free on 2026-11-03); df / overstates free space; D: full crashes WSL
metadata:
  type: project
---

WSL's virtual disk (ext4.vhdx) sits on Windows drive D:. The real free space is D:'s (`df -h /mnt/d`, 48 GB on
2026-11-03), not the 591 GB that `df /` reports. If D: fills up, WSL crashes.

**Why:** the user corrected me on 2026-11-03 when I offered to stream ~160 GB of GlareMOT2 through `/`.

**How to apply:** check `df -h /mnt/d` before any local download or large output. Keep big data (datasets,
caches) on Colab and pull only small results. Related: [[yolox-detector-glaremot2]].
