#!/bin/bash
# Colab VM job for the Table I baselines: ReID + GMC + MegaDepth disparity on the scripts/26 detection cache.
# Inputs uploaded first: /content/pegcode.tgz (scripts 24/26/27, configs/yolox/make_overlay.sh, cache/zipindex of the
# GlareMOT2 zip) and /content/dets.tar (results/yolox_glaremot2_half_fix2/dets.tar). The Drive zip is read with the
# short-lived token that configs/yolox/push_token.sh keeps in /content/gdrive_token. Run detached (nohup setsid) and
# keep the kernel alive from the local machine with configs/yolox/keepalive.sh (it tails /content/yx_run.log).
# Ends with /content/feats_<split>.tar and FEATS_TAR_DONE in the log.
set -e
exec >> /content/yx_run.log 2>&1
cd /content
echo "[setup] $(date +%T)"
mkdir -p PEG && tar xzf pegcode.tgz -C PEG
[ -d dets ] || tar xf dets.tar
[ -d TrackTrack ] || git clone -q https://github.com/kamkyu94/TrackTrack.git
git -C TrackTrack checkout -q ee7f1c5
[ -d BoT-SORT ] || git clone -q https://github.com/NirAharon/BoT-SORT.git
git -C BoT-SORT checkout -q 2519854
[ -d MegaDepth ] || git clone -q https://github.com/zl548/MegaDepth.git
pip install -q yacs termcolor tabulate
[ -s mot20_sbs_S50.pth ] || curl -sSL -o mot20_sbs_S50.pth \
  https://github.com/ShuCvlab/DiffMOT/releases/download/v1.0/mot20_sbs_S50.pth
[ -s megadepth.pth ] || curl -sSL -o megadepth.pth \
  http://www.cs.cornell.edu/projects/megadepth/dataset/models/best_generalization_net_G.pth
[ -f /content/overlay/OK ] || { bash PEG/configs/yolox/make_overlay.sh /content/overlay && touch /content/overlay/OK; }
echo "[setup done] $(date +%T)"
export GDRIVE_TOKEN_FILE=/content/gdrive_token
python3 PEG/scripts/27_cache_reid_gmc.py --dets /content/dets --out /content/feats --overlay /content/overlay \
  --reid_root "/content/TrackTrack/2. FastReID" --reid_weights /content/mot20_sbs_S50.pth --botsort /content/BoT-SORT \
  --megadepth /content/MegaDepth --megadepth_weights /content/megadepth.pth ${FEATS_ARGS}
grep -q FEATS_DONE /content/yx_run.log
for sp in test val_half; do [ -d feats/$sp ] && tar cf feats_$sp.tar feats/$sp; done
echo FEATS_TAR_DONE
