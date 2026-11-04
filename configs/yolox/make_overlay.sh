#!/bin/bash
# Label fixes released after the GlareMOT2 zip, as one overlay dir: /content/overlay/<split>/<seq>/{mot,meta,images}.
# scripts/25 (--overlay) and scripts/26 (--overlay) copy it over each streamed seq, so the zip is never patched.
#   fix 1 (2026-10-28, Minh): 400_sequence_morongmo, 401_sequence_nga3 - labels drifted up to ~100 frames behind the
#         video (25.037 fps read as 25); fixed meta/ + mot/ + the extra frames at the end.
#   fix 2 (2026-11-01, Minh): 23 cam-5 seqs (13 train, 10 test) re-drawn as whole-person boxes; mot/gt only
#         (labels/ match gt.txt; labels_all/ was NOT updated and is not used here).
set -e
O=${1:-/content/overlay}; S=/content/ovl_src
mkdir -p $O $S && cd $S
get() { [ -s $1.zip ] || curl -sSL -o $1.zip "https://drive.usercontent.google.com/download?id=$1&export=download&confirm=t"; \
        python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).testzip() is None or sys.exit('bad zip')" $1.zip; }
get 1S64CCoC6sGWohE7IY4B8x2XBMCCrQKDW   # 400_sequence_morongmo_fixed.zip
get 1U7dOMaZxF5NcwPM914iTP3hE3zAG10qo   # 401_sequence_nga3_fixed.zip
get 1e-TDdN2nTZ9yBDakUi476HVGrWPNd-sn   # GlareMOT_annotations_updated_20261031-20261101.zip
unzip -q -o 1S64CCoC6sGWohE7IY4B8x2XBMCCrQKDW.zip 'train/400_sequence_morongmo/meta/*' 'train/400_sequence_morongmo/mot/*' \
  'train/400_sequence_morongmo/images/*' -d $O
unzip -q -o 1U7dOMaZxF5NcwPM914iTP3hE3zAG10qo.zip 'test/401_sequence_nga3/meta/*' 'test/401_sequence_nga3/mot/*' \
  'test/401_sequence_nga3/images/*' -d $O
rm -rf $S/u && mkdir -p $S/u && unzip -q -o 1e-TDdN2nTZ9yBDakUi476HVGrWPNd-sn.zip 'GlareMOT2 full/*/*/mot/*' UPDATED_SEQUENCES.csv -d $S/u
cp -r "$S/u/GlareMOT2 full/"* $O/
# check fix 2 against its manifest
python3 - $O $S/u/UPDATED_SEQUENCES.csv <<'PY'
import csv, hashlib, sys
o, man = sys.argv[1], sys.argv[2]
rows = list(csv.DictReader(open(man, encoding="utf-8-sig")))
bad = [r["sequence"] for r in rows
       if hashlib.sha256(open(f"{o}/{r['split']}/{r['sequence']}/mot/gt/gt.txt", "rb").read()).hexdigest() != r["gt_sha256"]]
print(f"fix 2: {len(rows)} seqs, gt sha256 mismatches: {bad or 'none'}")
sys.exit(1 if bad else 0)
PY
for d in $O/*/*; do echo "$(basename $(dirname $d))/$(basename $d): $(ls $d | tr '\n' ' ')$( [ -d $d/images ] && echo "images=$(ls $d/images | wc -l)")"; done
echo OVERLAY_OK
