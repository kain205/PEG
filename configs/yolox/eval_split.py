# COCO AP of a YOLOX checkpoint on one COCO json (val_half.json / test.json from scripts/25). Inference runs once;
# AP is then reported on the whole set, without one seq (`--drop` prefixes, e.g. 400_ or 401_), and per seq.
# Same preprocessing / decoding as scripts/26 (checked against ByteTrack's pipeline) at COCO settings: conf 0.001, NMS 0.7.
# Run with the ByteTrack repo on PYTHONPATH:
#   PYTHONPATH=~/Projects/ByteTrack .venv/bin/python configs/yolox/eval_split.py --data results/yolox_test_eval \
#       --ann test.json --ckpt results/yolox_glaremot2_half_fix2/yolox_x_glaremot2_half_best_fp16.pth --drop 401_
import argparse
import contextlib
import importlib.util
import io
import json
import os

import numpy as np
import torch
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location("c26", os.path.join(ROOT, "scripts", "26_cache_yolox_dets.py"))
c26 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c26)


def ap(gt, dets, img_ids):
    if not img_ids:
        return float("nan"), float("nan")
    d = [x for x in dets if x["image_id"] in img_ids]
    if not d:
        return 0.0, 0.0
    with contextlib.redirect_stdout(io.StringIO()):
        e = COCOeval(gt, gt.loadRes(d), "bbox")
        e.params.imgIds = sorted(img_ids)
        e.evaluate(); e.accumulate(); e.summarize()
    return e.stats[1], e.stats[0]


def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--data", required=True)
    ap_.add_argument("--ann", required=True)
    ap_.add_argument("--ckpt", required=True)
    ap_.add_argument("--exp", default=os.path.join(ROOT, "configs", "yolox", "yolox_x_glaremot2_half.py"))
    ap_.add_argument("--drop", default="", help="comma list of seq prefixes to also report without")
    ap_.add_argument("--out", help="write the COCO detections json here")
    ap_.add_argument("--batch", type=int, default=8)
    args = ap_.parse_args()

    from yolox.exp import get_exp
    exp = get_exp(args.exp, None)
    model = exp.get_model().cuda().eval()
    sd = torch.load(args.ckpt, map_location="cpu", weights_only=True)
    model.load_state_dict({k: v.float() for k, v in sd.get("model", sd).items()})
    model.half()

    with contextlib.redirect_stdout(io.StringIO()):
        gt = COCO(os.path.join(args.data, "annotations", args.ann))
    ims = gt.dataset["images"]
    vid = {v["id"]: v["file_name"] for v in gt.dataset["videos"]}
    paths = [os.path.join(args.data, i["file_name"]) for i in ims]
    rows = c26.detect(model, paths, tuple(exp.test_size), 0.001, [0.7], args.batch, 8)[0.7]
    dets = []
    for r in rows:
        f, _, x, y, w, h, s = r.split(",")[:7]
        dets.append({"image_id": ims[int(f) - 1]["id"], "category_id": 1,
                     "bbox": [float(x), float(y), float(w), float(h)], "score": float(s)})
    if args.out:
        json.dump(dets, open(args.out, "w"))
    seq_of = {i["id"]: vid[i["video_id"]] for i in ims}
    allids = set(seq_of)
    res = {"all": ap(gt, dets, allids)}
    for p in [p for p in args.drop.split(",") if p]:
        res[f"without {p}*"] = ap(gt, dets, {i for i in allids if not seq_of[i].startswith(p)})
    per = {}
    for s in sorted(set(seq_of.values())):
        ids = {i for i in allids if seq_of[i] == s}
        nb = len(gt.getAnnIds(imgIds=list(ids)))
        per[s] = (len(ids), nb) + (ap(gt, dets, ids) if nb else (float("nan"), float("nan")))
    print(f"ckpt {os.path.basename(args.ckpt)} | {args.ann}: {len(ims)} imgs, {len(gt.dataset['annotations'])} boxes")
    for k, (a50, a) in res.items():
        print(f"RESULT {k:16s} AP50 {a50:.4f} AP50_95 {a:.4f}")
    print("per seq: imgs boxes AP50 AP50_95")
    for s, (n, nb, a50, a) in per.items():
        print(f"  {s:28s} {n:5d} {nb:5d} {a50:.3f} {a:.3f}")


if __name__ == "__main__":
    main()
