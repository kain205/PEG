"""Per T3 burn episode: covered frames @IoU .5 for PEG / PEG+ / PEG-C (online) / PEG-C lag (fixed-lag L=90, hidden) on test + val,
mean centre error (px) of the emitted box nearest the GT centre on the burn frames (PEG+, PEG-C, PEG-C lag; NaN if no box on
any burn frame), and bootstrap CIs of delta Rcv over episodes (B=10000, seed 0, same boot as results/peg_o/episodes.py).
Run: .venv/Scripts/python.exe results/peg_c/episodes.py -> results/peg_c/episodes.json + episodes.txt"""
import io, json, math, os, random, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import BURN_THR, burn_index, load_events, load_mot, match_frame  # noqa: E402
SYNTH = os.path.join(ROOT, "datasets", "synth"); RCV = os.path.join(ROOT, "results", "eval_recovery", "trackers")
HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = {"test": {"PEG": "peg_rcv_ng", "PEG+": "pegplus_A_rcv", "PEG-C": "pegc_rcv", "PEG-C lag": "pegcl_rcv"},
        "val": {"PEG": "v_peg_rcv", "PEG+": "v_A_rcv", "PEG-C": "v_pegc_rcv", "PEG-C lag": "v_pegcl_rcv"}}
METHODS = ("PEG", "PEG+", "PEG-C", "PEG-C lag")
CERR = ("PEG+", "PEG-C", "PEG-C lag")


def cerr(gt, trk, ep, tid):
    errs = []
    for f in ep:
        g = [r for r in gt.get(f, []) if r[0] == tid]
        if not g or not trk.get(f):
            continue
        gc = np.array([g[0][1] + g[0][3] / 2, g[0][2] + g[0][4] / 2])
        errs.append(min(np.linalg.norm(np.array([r[1] + r[3] / 2, r[2] + r[4] / 2]) - gc) for r in trk[f]))
    return (float(np.mean(errs)) if errs else float("nan")), len(errs)


def episodes(split):
    runs = RUNS[split]
    seqs = sorted(f[:-4] for f in os.listdir(os.path.join(RCV, runs["PEG"], "data")))
    out = []
    for seq in seqs:
        gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt")); bi = burn_index(seq, SYNTH)
        trk = {k: load_mot(os.path.join(RCV, n, "data", f"{seq}.txt")) for k, n in runs.items()}
        for tid, s0, dur in load_events(seq, SYNTH):
            ep = [f for f in range(s0 + 1, s0 + dur + 1) if any(r[0] == tid for r in gt.get(f, [])) and bi.get((tid, f), 1.0) < BURN_THR]
            if not ep:
                continue
            row = dict(split=split, seq=seq, tid=tid, start=ep[0], end=ep[-1], n=len(ep))
            for k, t in trk.items():
                row[k] = sum(1 for f in ep if match_frame(gt.get(f, []), t.get(f, []), 0.5).get(tid))
            for k in CERR:
                e, nb = cerr(gt, trk[k], ep, tid)
                row["cerr_" + k] = None if math.isnan(e) else round(e, 1); row["nbox_" + k] = nb
            out.append(row)
    return out


def rcv(eps, k): return 100.0 * sum(e[k] for e in eps) / sum(e["n"] for e in eps)


def boot(eps, k, ref, B=10000, seed=0):
    rng = random.Random(seed)
    d = sorted(rcv(s, k) - rcv(s, ref) for s in ([rng.choice(eps) for _ in eps] for _ in range(B)))
    return round(d[int(0.025 * B)], 1), round(d[int(0.975 * B)], 1)


res = {"episodes": [], "summary": {}}; allx = []
for split in ("test", "val"):
    eps = episodes(split); res["episodes"] += eps; allx += eps
for name, eps in (("test", [e for e in allx if e["split"] == "test"]), ("val", [e for e in allx if e["split"] == "val"]), ("pooled", allx)):
    s = {"n_episodes": len(eps), "burn_frames": sum(e["n"] for e in eps), **{k: round(rcv(eps, k), 1) for k in METHODS}}
    for m in ("PEG-C", "PEG-C lag"):
        for ref in ("PEG+", "PEG"):
            ch = [e[m] - e[ref] for e in eps]
            s[f"{m}_vs_{ref}"] = {"delta": round(rcv(eps, m) - rcv(eps, ref), 1), "ci95": boot(eps, m, ref),
                                  "better": sum(c > 0 for c in ch), "worse": sum(c < 0 for c in ch), "same": sum(c == 0 for c in ch),
                                  "frames_gained": sum(c for c in ch if c > 0), "frames_lost": -sum(c for c in ch if c < 0)}
    res["summary"][name] = s
json.dump(res, open(os.path.join(HERE, "episodes.json"), "w"), indent=1)

buf = io.StringIO()
def P(s=""): print(s, file=buf)
for name, s in res["summary"].items():
    P(f"== {name}: {s['n_episodes']} episodes, {s['burn_frames']} burn frames | Rcv@.5 PEG {s['PEG']} PEG+ {s['PEG+']} PEG-C {s['PEG-C']} PEG-C lag {s['PEG-C lag']}")
    for m in ("PEG-C", "PEG-C lag"):
        for ref in ("PEG+", "PEG"):
            v = s[f"{m}_vs_{ref}"]
            P(f"   {m} vs {ref}: d {v['delta']:+.1f} CI95 [{v['ci95'][0]:+.1f}, {v['ci95'][1]:+.1f}] better {v['better']} worse {v['worse']} same {v['same']} frames +{v['frames_gained']} -{v['frames_lost']}")
for sp in ("test", "val"):
    P(f"\n{sp} episodes where PEG-C or PEG-C lag != PEG+ (seq tid frames: covered PEG / PEG+ / PEG-C / PEG-C lag of n | centre err px PEG+ / PEG-C / PEG-C lag):")
    for e in res["episodes"]:
        if e["split"] == sp and (e["PEG-C"] != e["PEG+"] or e["PEG-C lag"] != e["PEG+"]):
            P(f"  {e['seq']} g{e['tid']} {e['start']}-{e['end']}: {e['PEG']} / {e['PEG+']} / {e['PEG-C']} / {e['PEG-C lag']} of {e['n']} | "
              f"{e['cerr_PEG+']} / {e['cerr_PEG-C']} / {e['cerr_PEG-C lag']}")
txt = buf.getvalue()
print(txt)
open(os.path.join(HERE, "episodes.txt"), "w", encoding="utf-8").write(txt)
