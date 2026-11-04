# Pack the run's results into /content/yx_out: per-epoch AP table, logs, and model-only fp16 checkpoints (~200 MB
# each instead of ~800 MB with the optimizer). Run from /content/ByteTrack after colab_run.sh.
import glob, json, os, re, shutil, sys

import torch

src = "YOLOX_outputs/" + os.environ.get("YX_EXP_NAME", "yolox_x_glaremot2_half")
out = sys.argv[1] if len(sys.argv) > 1 else "/content/yx_out"
os.makedirs(f"{out}/ckpt", exist_ok=True)
log = open(f"{src}/train_log.txt").read()
ap = re.findall(r"IoU=0.50:0.95 \| area=   all \| maxDets=100 \] = ([\d.]+)\n.*IoU=0.50      \| area=   all \| maxDets=100 \] = ([\d.]+)", log)
run = open("/content/yx_run.log").read()
extra = dict(re.findall(r"== (epoch_\d+)_ckpt.pth.tar val_half_nomrm\n.*?RESULT AP50_95 [\d.]+ AP50 ([\d.]+)", run))
rows = [{"epoch": i, "val_AP50_95": float(a), "val_AP50": float(b), "nomrm_AP50": float(extra.get(f"epoch_{i}", "nan"))}
        for i, (a, b) in enumerate(ap, 1)]
json.dump({"epochs": rows, "init": re.findall(r"== epoch 0 \(init\) (\S+)\nRESULT (.*)", run)}, open(f"{out}/ap.json", "w"), indent=1)
for f in [f"{src}/train_log.txt", "/content/yx_run.log"] + glob.glob("/content/yx/build_stats*.json"):
    if os.path.isfile(f):
        shutil.copy(f, out)
for ck in sorted(glob.glob(f"{src}/epoch_*_ckpt.pth.tar")):
    sd = torch.load(ck, map_location="cpu", weights_only=True)["model"]
    torch.save({"model": {k: v.half() for k, v in sd.items()}}, f"{out}/ckpt/{os.path.basename(ck).replace('_ckpt.pth.tar', '_fp16.pth')}")
for r in rows:
    print(r)
print("EXPORT_DONE", out)
