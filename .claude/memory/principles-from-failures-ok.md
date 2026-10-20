---
name: principles-from-failures-ok
description: User's methodology rule (2026-10-20): deriving a general principle from observed failures (even test cases) is fine; what is forbidden is tuning parameters / picking specifics on test
metadata:
  type: feedback
---

Observing failures (even on test) and inferring a general, physically-motivated principle that should transfer is
legitimate; report it as such. Overly specific or biased rules are acceptable only if chosen on val. Parameters are
always tuned on val, test is scored once. Oracle/headroom analyses pooled over val+test episodes are fine for choosing
the *direction*, not for tuning.

**Why:** user said (in Vietnamese) "quan trọng là không tune trên test; failure mình observe rồi nghĩ ra nguyên lý chung
một cách đúng đắn, expect nó translate qua thực tế, thì hợp lý; đừng dùng nguyên lý quá bias và specific trừ khi trên val".
**How to apply:** in every protocol doc, disclose where the idea came from (which failures / which splits), keep knob
grids on val, keep online vs fixed-lag rows separate. See [[tune-on-val-from-scratch]], [[coast-design-research]].
