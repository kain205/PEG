"""Per-frame PEG-O log on 135_19q (replays the cached smoke run in-process, logs k / update) and a
table f405-452: k, update?, held-box centre x, GT g53 centre x, IoU.
Run: GPEG_SIZE_LOCK=1 GPEG_ODO=1 GPEG_ODO_TAU=0.06 GPEG_ODO_GAMMA=1 .venv/Scripts/python.exe results/peg_o/smoke_135_frames.py"""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.environ.update(GMOT_TRACKER='beacon', GMOT_BIRTH_SIZE_GUARD='0')
os.chdir(ROOT)
sys.argv = ['x', '--split', 'test', '--percep_cache', 'results/percep_cache/synth', '--tracker_name', 'dbg_frames_tmp',
            '--seqs', '135_sequence_19q_new']
import shutil
import glaremot.tracking.beacon_tracker as bt
LOG = {}
orig = bt.PEG._odometry_update
def wrap(self, mt, W, H):
    f = self._cur_frame
    z0 = getattr(mt, '_odo_z', None); mt._odo_k = None
    x0 = mt.kf.kf.x.copy()
    orig(self, mt, W, H)
    LOG[f] = (mt._odo_k, bool((mt.kf.kf.x != x0).any()))
bt.PEG._odometry_update = wrap
from glaremot.eval.eval_recovery import main, load_mot, _iou
main()
gt = load_mot('datasets/synth/135_sequence_19q_new/mot/gt/gt.txt')
trk = load_mot('results/eval_recovery/trackers/dbg_frames_tmp/data/135_sequence_19q_new.txt')
print("frame      k  upd  boxcx   gtcx   IoU")
for f in range(405, 453):
    g = [r for r in gt.get(f, []) if r[0] == 53]
    if not g:
        continue
    g = g[0]
    tr = trk.get(f, [])
    k, u = LOG.get(f, (None, False))
    ks = f"{k:6.3f}" if k is not None else "   -  "
    if tr:
        r = max(tr, key=lambda r: _iou(g[1:], r[1:]))
        print(f"f{f}  {ks}  {'Y' if u else '.'}  {r[1]+r[3]/2:6.0f} {g[1]+g[3]/2:6.0f}  {_iou(g[1:], r[1:]):.2f}")
    else:
        print(f"f{f}  {ks}  {'Y' if u else '.'}   no box {g[1]+g[3]/2:6.0f}")
shutil.rmtree('results/eval_recovery/trackers/dbg_frames_tmp', ignore_errors=True)
for fn in os.listdir('results/eval_recovery'):
    if 'dbg_frames_tmp' in fn:
        os.remove(os.path.join('results/eval_recovery', fn))
