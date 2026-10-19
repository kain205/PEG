"""Tune Thach v2 (M1-M6) on val only, greedy forward selection (docs/THACH_V2_TUNE_PROTOCOL.md).
Every evaluation is logged to results/thach_v2/tune/ledger.json; the trace to tune/trace.json.
  .venv/Scripts/python.exe results/thach_v2/tune_val.py            # val search
  .venv/Scripts/python.exe results/thach_v2/tune_val.py --test     # test once, for the final config only
"""
import argparse, hashlib, importlib.util, json, os, sys
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, file))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


an = _load("an", "analyze.py")
run = an.run          # one shared run module: CONFIGS registered here are seen by an.rescore_without
run.CLEAR += ["GMOT_ID_RESOLVE_V2"]
TUNE = os.path.join(HERE, "tune"); os.makedirs(TUNE, exist_ok=True)
LEDGER = os.path.join(TUNE, "ledger.json")
MARGIN, MIN_GAIN = -0.5, 0.5

# S0: his code with every switch off and the original PEG resolver (== our PEG, verified on test) (all of his flags explicit)
S0 = dict(run.CONFIGS["base"][0]); S0.update(GMOT_ID_RESOLVE_V2="0", GMOT_ADAPTIVE_Q="0", GMOT_CONE="0", GMOT_REID_DEEP="1")

# component -> list of grid points (env deltas). * = his default. Pre-registered in docs/THACH_V2_TUNE_PROTOCOL.md
def _q(pos):
    return {"GMOT_ADAPTIVE_MOTION": "1", "GMOT_ADAPTIVE_Q": "1", "GMOT_ADAPTIVE_Q_POS": str(pos), "GMOT_ADAPTIVE_Q_VEL": str(round(pos / 3, 4))}


GRID = {
    "R":   [{"GMOT_ID_RESOLVE_V2": "1"}],
    "M1q": [_q(0.01), _q(0.02), _q(0.03)],
    "M1c": [{"GMOT_ADAPTIVE_MOTION": "1", "GMOT_CONE": "1", "GMOT_CONE_CHI2": c, "GMOT_CONE_SPEED": v}
            for c in ("5.99", "9.21") for v in ("0.04", "0.06")],
    "M1d": [{"GMOT_INTERACT_DAMP": "1"}],
    "M2":  [{"GMOT_REID": "1", "GMOT_REID_DEEP_W": w} for w in ("0.5", "0.7", "0.9")],
    "M3":  [{"GBEACON_DYNAMIC_H": "1", "GBEACON_H_DECAY": d, "GBEACON_ADAPTIVE_TTL": t} for d in ("0.03", "0.06", "0.12") for t in ("0", "1")]
           + [{"GBEACON_DYNAMIC_H": "0", "GBEACON_ADAPTIVE_TTL": "1"}],
    "M4":  [{"GMOT_DORMANT": "1", "GMOT_DORMANT_APP_THRESH": a} for a in ("0.50", "0.60", "0.70")],
    "M5":  [{"GBEACON_ANCHOR": "1", "GBEACON_WEAK_R": r} for r in ("6.0", "24.0", "96.0")],
    "M6":  [{"GMOT_DEGLARE": "1"}],
}


def env_of(chosen):
    """chosen: {component: point index}. M4 brings M2 (his default 0.7) when M2 is not chosen."""
    env = dict(S0)
    for c, i in sorted(chosen.items()):
        env.update(GRID[c][i])
    if "M4" in chosen and "M2" not in chosen:
        env.update(GRID["M2"][1])
    return env


def key_of(chosen):
    env = env_of(chosen)
    return "tv" + hashlib.sha1(json.dumps(env, sort_keys=True).encode()).hexdigest()[:8]


def label(chosen):
    return " + ".join(f"{c}[{i}]" for c, i in sorted(chosen.items())) or "S0"


def load_ledger():
    return json.load(open(LEDGER)) if os.path.exists(LEDGER) else {}


def evaluate(chosen, split="val"):
    k = key_of(chosen)
    run.CONFIGS[k] = (env_of(chosen), label(chosen))
    with ThreadPoolExecutor(int(os.environ.get("TUNE_WORKERS", "2"))) as ex:   # tables write to separate result dirs; 2 keeps RAM ~2 GB
        list(ex.map(lambda t: run.run(k, t, split, False), ("t1", "t2", "t3")))
    m = an.metrics(k, split)
    led = load_ledger()
    led[f"{split}|{k}"] = {"label": label(chosen), "chosen": chosen, "T1": m["T1"], "T2": m["T2"], "T3": m["T3"]}
    json.dump(led, open(LEDGER, "w"), indent=1)
    return k, m


def prim(m):
    return (m["T1"]["HOTA"], m["T2"]["HOTA"], m["T3"]["Rcv@.5"])


def single_event(kx, mx, kc, mc):
    """Drop the val unit most favourable to the candidate in each table; score must stay > 0."""
    chk = {}
    for t, s in (("t1", "T1_seq"), ("t2", "T2_seq")):
        a, b = mx[s], mc[s]
        seq = max(a, key=lambda q: b[q]["HOTA"] - a[q]["HOTA"])
        chk[t] = {"dropped": seq, "delta_without": round(an.rescore_without(kc, t, "val", seq) - an.rescore_without(kx, t, "val", seq), 2)}
    ea, eb = an.episodes(kx, "val"), an.episodes(kc, "val")
    ep = max(ea, key=lambda q: eb[q][1] - ea[q][1])
    keys = [q for q in ea if q != ep]
    chk["t3"] = {"dropped": ep, "delta_without": round(an.rcv(eb, keys) - an.rcv(ea, keys), 2)}
    return chk, round(sum(v["delta_without"] for v in chk.values()), 2)


FORCE = {}   # components included by design (not judged on val), e.g. {'P': 0}


def search():
    chosen, trace = dict(FORCE), []
    kx, mx = evaluate(chosen)
    trace.append({"round": 0, "config": label(chosen), "key": kx, "val": prim(mx)})
    print("S0", prim(mx), flush=True)
    while len(chosen) < len(GRID):  # noqa: E501
        rows = []
        for c in GRID:
            if c in chosen:
                continue
            for i in range(len(GRID[c])):
                cand = {**chosen, c: i}
                kc, mc = evaluate(cand)
                d = [round(x - y, 4) for x, y in zip(prim(mc), prim(mx))]
                rows.append({"add": f"{c}[{i}]", "comp": c, "idx": i, "key": kc, "delta": d, "score": round(sum(d), 4),
                             "admissible": all(x >= MARGIN for x in d), "m": mc})
                print(f"  round {len(trace)}: {label(cand):40s} d={d} score={sum(d):+.2f}", flush=True)
        ranked = sorted([r for r in rows if r["admissible"] and r["score"] > MIN_GAIN], key=lambda r: (-r["score"], r["comp"]))
        checks, acc = [], None
        if STRONG:   # "strongest" variant: any admissible gain > 0.5 counts, no single-event check
            ranked, acc = [], (ranked[0] if ranked else None)
        for r in ranked:
            chk, s_wo = single_event(kx, mx, r["key"], r["m"])
            checks.append({"add": r["add"], "score": r["score"], "checks": chk, "score_without": s_wo, "pass": s_wo > 0})
            print(f"  check {r['add']}: score {r['score']:+.2f}, without most favourable unit {s_wo:+.2f}", flush=True)
            if s_wo > 0:
                acc = r
                break
        strip = [{k: v for k, v in r.items() if k != "m"} for r in rows]
        trace.append({"round": len(trace), "rows": strip, "checks": checks, "accepted": acc and acc["add"]})
        json.dump(trace, open(os.path.join(TUNE, "trace.json"), "w"), indent=1)
        if acc is None:
            break
        chosen[acc["comp"]] = acc["idx"]
        kx, mx = acc["key"], acc["m"]
        print("ACCEPT", acc["add"], "->", label(chosen), prim(mx), flush=True)
    final = {"chosen": chosen, "label": label(chosen), "key": kx, "env": env_of(chosen), "val": prim(mx)}
    json.dump(final, open(os.path.join(TUNE, "final.json"), "w"), indent=1)
    json.dump(trace, open(os.path.join(TUNE, "trace.json"), "w"), indent=1)
    print("FINAL", final["label"], final["val"], flush=True)


def test_once():
    final = json.load(open(os.path.join(TUNE, "final.json")))
    if os.path.exists(os.path.join(TUNE, "test.json")):
        raise SystemExit("test already reported once: tune/test.json")
    k, m = evaluate({c: int(i) for c, i in final["chosen"].items()}, "test")
    assert k == final["key"]
    out = {"label": final["label"], "key": k, "test": {t: m[t] for t in ("T1", "T2", "T3")}}
    json.dump(out, open(os.path.join(TUNE, "test.json"), "w"), indent=1)
    print("TEST", final["label"], prim(m), flush=True)


STRONG = False

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--strong", action="store_true", help="strongest variant: + PEG+ component, no single-event check -> tune_strong/")
    ap.add_argument("--force_peg_plus", action="store_true", help="with --strong: PEG+ always on (by design) -> tune_strong_P/")
    a = ap.parse_args()
    if a.strong:
        STRONG = True
        GRID["P"] = [{"GPEG_SIZE_LOCK": "1"}]
        TUNE = os.path.join(HERE, "tune_strong"); os.makedirs(TUNE, exist_ok=True)
        LEDGER = os.path.join(TUNE, "ledger.json")
        if a.force_peg_plus:
            FORCE = {"P": 0}
            TUNE = os.path.join(HERE, "tune_strong_P"); os.makedirs(TUNE, exist_ok=True)
            LEDGER = os.path.join(TUNE, "ledger.json")
    sys.stdout.reconfigure(encoding="utf-8")
    test_once() if a.test else search()
