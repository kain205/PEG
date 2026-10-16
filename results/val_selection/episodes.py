"""Per burn-episode coverage (Table III, IoU .5) on val and test + bootstrap CIs of dRcv vs PEG.
Run: .venv/Scripts/python.exe results/val_selection/episodes.py  -> results/val_selection/episodes.json"""
import json, os, random, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import BURN_THR, burn_index, load_events, load_mot, match_frame  # noqa: E402

SYNTH = os.path.join(ROOT, "datasets", "synth")
RCV = os.path.join(ROOT, "results", "eval_recovery", "trackers")
RUNS = {"test": {"PEG": "peg_rcv_ng", "A": "pf_A_rcv", "M1damp": "pf_P+M1damp_rcv", "M1swap": "pf_P+M1swap_rcv",
                 "M3": "pf_P+M3_rcv", "A+M1swap+M3": "pf_A+M1swap+M3_rcv"},
        "val": {"PEG": "v_peg_rcv", "A": "v_A_rcv", "M1damp": "v_M1damp_rcv", "M1swap": "v_M1swap_rcv",
                "M3": "v_M3_rcv", "A+M1swap+M3": "v_A+M1swap+M3_rcv"}}


def episodes(split):
    runs = RUNS[split]
    seqs = sorted(f[:-4] for f in os.listdir(os.path.join(RCV, runs["PEG"], "data")))
    out = []
    for seq in seqs:
        gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
        bi = burn_index(seq, SYNTH)
        trk = {k: load_mot(os.path.join(RCV, n, "data", f"{seq}.txt")) for k, n in runs.items()}
        for tid, s0, dur in load_events(seq, SYNTH):
            ep = [f for f in range(s0 + 1, s0 + dur + 1)
                  if any(r[0] == tid for r in gt.get(f, [])) and bi.get((tid, f), 1.0) < BURN_THR]
            if not ep:
                continue
            row = dict(split=split, seq=seq, tid=tid, start=ep[0], end=ep[-1], n=len(ep))
            for k, t in trk.items():
                row[k] = sum(1 for f in ep if match_frame(gt.get(f, []), t.get(f, []), 0.5).get(tid))
            out.append(row)
    return out


def rcv(eps, k):
    return 100.0 * sum(e[k] for e in eps) / sum(e["n"] for e in eps)


def boot(eps, k, B=10000, seed=0):
    rng = random.Random(seed)
    d = sorted(rcv(s, k) - rcv(s, "PEG") for s in ([rng.choice(eps) for _ in eps] for _ in range(B)))
    return round(d[int(0.025 * B)], 1), round(d[int(0.975 * B)], 1)


res = {"episodes": [], "summary": {}}
allx = []
for split in ("test", "val"):
    eps = episodes(split)
    res["episodes"] += eps
    allx += eps
    for name, e in ((split, eps),):
        pass
for name, eps in (("test", [e for e in allx if e["split"] == "test"]), ("val", [e for e in allx if e["split"] == "val"]),
                  ("pooled", allx)):
    s = {"n_episodes": len(eps), "burn_frames": sum(e["n"] for e in eps), "PEG": round(rcv(eps, "PEG"), 1)}
    for k in [k for k in RUNS["test"] if k != "PEG"]:
        ch = [e[k] - e["PEG"] for e in eps]
        s[k] = {"rcv": round(rcv(eps, k), 1), "delta": round(rcv(eps, k) - rcv(eps, "PEG"), 1), "ci95": boot(eps, k),
                "better": sum(c > 0 for c in ch), "worse": sum(c < 0 for c in ch), "frames_gained": sum(ch),
                "top_episode_share": None if not any(ch) else round(max(abs(c) for c in ch) / max(1, abs(sum(ch))), 2)}
    res["summary"][name] = s
json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "episodes.json"), "w"), indent=1)
for name, s in res["summary"].items():
    print(f"== {name}: {s['n_episodes']} episodes, {s['burn_frames']} burn frames, PEG Rcv {s['PEG']}")
    for k, v in s.items():
        if isinstance(v, dict):
            print(f"  {k:12s} Rcv {v['rcv']:5.1f}  d {v['delta']:+5.1f}  CI95 [{v['ci95'][0]:+.1f}, {v['ci95'][1]:+.1f}]  "
                  f"better {v['better']:2d} worse {v['worse']:2d}  frames {v['frames_gained']:+d}  top-ep share {v['top_episode_share']}")
