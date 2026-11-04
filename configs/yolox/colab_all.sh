#!/bin/bash
# Whole YOLOX lane on a fresh Colab VM: setup, data build, baseline + fine-tune + per-epoch AP.
# Launch it as a BLOCKING kernel cell (subprocess.run, `colab exec --timeout` short): the CLI returns but the kernel
# stays BUSY, which is what keeps a Colab runtime alive. A nohup'd job with an idle kernel was reclaimed after ~40 min,
# and so was an idle kernel after a finished run (all checkpoints lost). Watch with `colab download /content/yx_run.log`.
# When done it writes /content/yx_out (+ yx_out_small.tar) and holds the VM until /content/PULLED is uploaded (or
# YX_HOLD_H hours): pull, then upload PULLED. A failed data build also holds, so the frames already fetched survive.
hold() {
  end=$(( $(date +%s) + ${YX_HOLD_H:-6} * 3600 ))
  echo "HOLDING until /content/PULLED ($1)"
  while [ ! -e /content/PULLED ] && [ $(date +%s) -lt $end ]; do sleep 60; done
}
set -e
mkdir -p /content/PEG && tar xzf /content/pegcode.tgz -C /content/PEG
bash /content/PEG/configs/yolox/colab_setup.sh
# label fixes after the zip (400/401 timing, 2026-11-01 cam-5 boxes): /content/overlay, used by every build and the cache
bash /content/PEG/configs/yolox/make_overlay.sh /content/overlay || { echo OVERLAY_FAILED; hold overlay_failed; exit 1; }
if [ ! -s /content/yx/annotations/val_half.json ]; then
  python3 /content/PEG/scripts/25_build_yolox_glaremot.py --out /content/yx --workers 32 --overlay /content/overlay \
    ${YX_BUILD_ARGS} || { echo BUILD_FAILED; hold build_failed; exit 1; }
fi
bash /content/PEG/configs/yolox/colab_run.sh || echo RUN_FAILED
(cd /content/ByteTrack && python3 /content/PEG/configs/yolox/export_out.py /content/yx_out) || echo EXPORT_FAILED
tar cf /content/yx_out_small.tar -C /content yx_out/ap.json yx_out/train_log.txt yx_out/yx_run.log || true
# test set (after training, so a lost VM costs less), same sampling + glare filter; scored once with the val-chosen epoch (colab_cache.sh)
if [ ! -s /content/yx/annotations/test.json ]; then
  python3 /content/PEG/scripts/25_build_yolox_glaremot.py --out /content/yx --split test --workers 32 \
    --overlay /content/overlay || echo TEST_BUILD_FAILED
fi
# best epoch -> test AP once -> full-frame det cache (val_half + test)
[ -n "$YX_NO_CACHE" ] || bash /content/PEG/configs/yolox/colab_cache.sh || echo CACHE_FAILED
hold done
