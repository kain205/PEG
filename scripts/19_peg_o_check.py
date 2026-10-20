"""PEG-O estimator check (stand-alone, no tracker): pins the disc matched-filter odometry on the
synthetic-burn cache before any tracker run.

Uses the SAME estimator as the tracker (`odo_measure` from glaremot.tracking.beacon_tracker) on
the cached saturation masks (results/percep_cache/synth/*.npz) and GT boxes, for five burn
episodes. The window follows the ESTIMATE (feedback loop); the 0.5*diag jump test stands in for
the chi2 NIS gate; the Kalman box at the first armed frame is replaced by the GT centre at the
start of the burn. Anchor rule (plan 2.2 step 5): the anchor is taken on the first burn frame
whose peak sharpness k >= tau; before that the predicted burn centre is the estimate itself and
there is no update; afterwards z = c_anchor + (b - b_anchor).

Run from repo root: .venv/Scripts/python.exe scripts/19_peg_o_check.py
Expected mean centre error during the burn (px, +-1; "frozen" = PEG+ box that does not move), tau=0.05:
  135 g53   frozen 76.2 -> 30.4 | 320 g1 9.0 -> 6.8 | 176 g204 16.5 -> 28.9 | 204 g300 28.3 -> 25.8
  325 g3    frozen 82.5 -> 83.7
The plan-mode reference anchored only on the very first burn frame, so 204 (k=0.049) and 325
(k=0.033) stayed frozen (28.3 / 82.5; the plan's "21.5" for 204 is not reproducible). With the
plan 2.2 rule (anchor on the first frame with k >= tau) 204 anchors at f341 and 325 at f268
(k=0.075), so 325 does not fall back at tau=0.05 (+1.2 px vs frozen; max error 192 -> 154).
Prints tau in {0.04, 0.05, 0.06, 0.08, 0.10}; full output saved in results/peg_o/check_19.txt.
"""
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from glaremot.tracking.beacon_tracker import odo_measure  # noqa: E402

S = 512


def run(seq, gid, f0, f1, tag, tau=0.05):
    d = f'datasets/synth/{seq}'
    img = glob.glob(d + '/images/*.jpg')[0]
    H, W = cv2.imread(img).shape[:2]
    z = np.load(f'results/percep_cache/synth/{seq}.npz')
    sat = z['sat']
    gt = np.loadtxt(d + '/mot/gt/gt.txt', delimiter=',')
    g = {int(r[0]): r[2:6] for r in gt if int(r[1]) == gid}
    sx, sy = S / W, S / H

    def mask(f):   # MOT frame f (1-based) -> cache row f-1
        return np.unpackbits(sat[f - 1], count=S * S).reshape(S, S).astype(np.uint8)

    def phi_of(m, b):
        x, y, w, h = b
        bb = m[int(y * sy):int((y + h) * sy), int(x * sx):int((x + w) * sx)]
        return bb.mean() if bb.size else 0

    def measure(m, c, w, h):
        _, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        return odo_measure(lab, st, c, w, h, sx, sy, S)

    frames = [f for f in range(f0, f1 + 1) if f in g]
    burn = [f for f in frames if phi_of(mask(f), g[f]) >= 0.4]
    if not burn:
        print(tag, 'no burn')
        return
    x, y, w, h = g[burn[0]]
    c0 = np.array([x + w / 2, y + h / 2])
    est = c0.copy()
    c_anc = b_anc = None
    off = np.zeros(2)
    anchor_frame = None
    errs, frozen, used = [], [], 0
    anc_k = anc_rho = float('nan')
    for f in burn:
        r = measure(mask(f), est + off, w, h)
        if r is not None:
            b, rho, pk, kx, ky = r
            k = min(kx, ky)
            if k >= tau:
                if c_anc is None:
                    c_anc, b_anc = est.copy(), b.copy()
                    off = b_anc - c_anc
                    anchor_frame, anc_k, anc_rho = f, k, rho
                new = c_anc + (b - b_anc)
                if np.linalg.norm(new - est) < 0.5 * np.hypot(w, h):
                    est = new
                    used += 1
        gc = np.array([g[f][0] + g[f][2] / 2, g[f][1] + g[f][3] / 2])
        errs.append(np.linalg.norm(est - gc))
        frozen.append(np.linalg.norm(c0 - gc))
    e, fr, diag = np.array(errs), np.array(frozen), np.hypot(w, h)
    print(f"{tag}: {len(burn)} fr, box {w:.0f}x{h:.0f} | frozen mean {fr.mean():.1f} ok@.25diag {(fr < 0.25 * diag).mean():.2f} | "
          f"MF-odo mean {e.mean():.1f} max {e.max():.1f} ok@.25diag {(e < 0.25 * diag).mean():.2f} used {used}/{len(burn)} | "
          f"anchor frame {anchor_frame} sharp {anc_k:.3f} rho {anc_rho:.0f}")


if __name__ == '__main__':
    for tau in (0.04, 0.05, 0.06, 0.08, 0.10):
        print('tau', tau)
        run('204_sequence_81q_complete', 300, 330, 395, '204 g300', tau=tau)
        run('135_sequence_19q_new', 53, 400, 460, '135 g53', tau=tau)
        run('325_sequence_92q_new', 3, 260, 305, '325 g3', tau=tau)
        run('176_sequence_56q_new', 204, 325, 360, '176 g204', tau=tau)
        run('320_sequence_116q_new', 1, 220, 260, '320 g1', tau=tau)
