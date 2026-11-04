# COCO AP of a YOLOX checkpoint on the exp's val set (used for the epoch-0 baseline of the pretrained weights).
# Run from the ByteTrack repo root: python eval_ckpt.py <exp.py> <ckpt> [batch]
import sys

import torch
from yolox.exp import get_exp

exp = get_exp(sys.argv[1], None)
model = exp.get_model().cuda().eval()
ck = torch.load(sys.argv[2], map_location="cpu", weights_only=True)
print("load:", model.load_state_dict(ck.get("model", ck), strict=False))
ev = exp.get_evaluator(int(sys.argv[3]) if len(sys.argv) > 3 else 8, False)
ap50_95, ap50, summary = ev.evaluate(model, False, half=True)
print(summary)
print(f"RESULT AP50_95 {ap50_95:.4f} AP50 {ap50:.4f}")
