# ExSORT FP diagnostics (2026-11-18), kept as run; paths are hard-coded to this machine's results/baselines_t1 layout.
"""Post-hoc emission filters on the instrumented ExSORT rows (emission never changes tracker state), scored by TrackEval."""
import json, os, sys, glob
import numpy as np
import trackeval
sys.path.insert(0, "/home/thanh1402/Projects/PEG")
from glaremot.eval.eval_mot import run_trackeval
from multiprocessing import Pool
B = "/home/thanh1402/Projects/PEG/results/baselines_t1"; D = sys.argv[1]
RULES = {
    "base": lambda a, ph: np.ones(len(a), bool),
    "nocoast": lambda a, ph: a[:, 2] == 0,
    "sh<=3": lambda a, ph: a[:, 24] <= 3,
    "sh<=6": lambda a, ph: a[:, 24] <= 6,
    "sh<=12": lambda a, ph: a[:, 24] <= 12,
    "sh<=25": lambda a, ph: a[:, 24] <= 25,
    "coast_sh<=12_keeplow": lambda a, ph: (a[:, 2] == 0) | (a[:, 24] <= 12),
    "tsu<=25": lambda a, ph: a[:, 2] <= 25,
    "tsu<=50": lambda a, ph: a[:, 2] <= 50,
    "oracle_no_phantom": lambda a, ph: ~ph,
    "highonly": lambda a, ph: a[:, 24] == 0,
}
def job(arg):
    sp, name = arg
    root = f"{D}/filt/{sp}"; dd = f"{root}/{name}/data"; os.makedirs(dd, exist_ok=True)
    ranges = json.load(open(B + "/dets/splits.json"))[sp]
    for s, (a, b) in ranges.items():
        A = np.load(f"{D}/{sp}/{s}.npy"); lines = open(f"{D}/{sp}/{s}.txt").readlines()
        assert len(A) == len(lines)
        fp = A[:, 25] < 0; u, inv = np.unique(A[:, 1], return_inverse=True)
        ph = ((np.bincount(inv, ~fp) / np.maximum(np.bincount(inv), 1)) < .2)[inv] if len(A) else np.zeros(0, bool)
        k = RULES[name](A, ph)
        open(f"{dd}/{s}.txt", "w").writelines([l for l, kk in zip(lines, k) if kk])
    lengths = {s: b - a + 1 for s, (a, b) in ranges.items()}
    gt = f"{B}/runs/{sp}/_gt"
    out = []
    for lab, L in (("all", lengths), ("noBig", {s: v for s, v in lengths.items() if not s.startswith("40")})):
        r = run_trackeval(gt, root, name, L, f"{root}/{name}")["COMBINED_SEQ"]
        out.append(f"{sp:8s} {name:22s} {lab:5s} HOTA {r['HOTA']*100 if r['HOTA']<1.01 else r['HOTA']:.2f} DetA {r['DetA']*100 if r['DetA']<1.01 else r['DetA']:.2f} AssA {r['AssA']*100 if r['AssA']<1.01 else r['AssA']:.2f} IDF1 {r['IDF1']*100 if r['IDF1']<1.01 else r['IDF1']:.2f} MOTA {r['MOTA']*100 if abs(r['MOTA'])<1.01 else r['MOTA']:.2f} IDSW {r['IDSW']} FP {r['FP']} FN {r['FN']}")
    return "\n".join(out)
if __name__ == "__main__":
    names = sys.argv[3].split(",") if len(sys.argv) > 3 else list(RULES)
    jobs = [(sp, n) for sp in sys.argv[2].split(",") for n in names]
    with Pool(11) as p:
        for r in p.imap(job, jobs): print(r, flush=True)
