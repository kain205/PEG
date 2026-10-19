"""Where does a config's gain over PEG sit? Top/worst sequences (T1, T2 HOTA), drop-top re-score, T3 episodes.
-> where_gain.json. Configs: each component's best val point, PEG+ alone, the two "strongest" finals."""
import importlib.util, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("tv", os.path.join(HERE, "tune_val.py")); tv = importlib.util.module_from_spec(spec); spec.loader.exec_module(tv)
tv.GRID["P"] = [{"GPEG_SIZE_LOCK": "1"}]
tv.LEDGER = os.path.join(HERE, "tune", "ledger_extra.json")
an = tv.an
trace = json.load(open(os.path.join(HERE, "tune", "trace.json")))
best = {}
for r in trace[1]["rows"]:
    if r["comp"] not in best or r["score"] > best[r["comp"]]["score"]:
        best[r["comp"]] = r
cfgs = {r["comp"]: {r["comp"]: r["idx"]} for r in best.values()}
cfgs["P"] = {"P": 0}
for d in ("tune_strong", "tune_strong_P"):
    f = json.load(open(os.path.join(HERE, d, "final.json")))
    cfgs[d] = {c: int(i) for c, i in f["chosen"].items()}
out = {}
for split in ("val", "test"):
    k0, m0 = tv.evaluate({}, split)
    for name, ch in cfgs.items():
        k, m = tv.evaluate(ch, split)
        r = {}
        for t in ("T1", "T2"):
            d = sorted(((m[t + "_seq"][s]["HOTA"] - m0[t + "_seq"][s]["HOTA"], s) for s in m0[t + "_seq"]), reverse=True)
            r[t] = {"delta": round(m[t]["HOTA"] - m0[t]["HOTA"], 2), "top": [(s.split("_")[0], round(x, 1)) for x, s in d[:2]],
                    "worst": [(s.split("_")[0], round(x, 1)) for x, s in d[-2:]],
                    "without_top": round(an.rescore_without(k, t.lower(), split, d[0][1]) - an.rescore_without(k0, t.lower(), split, d[0][1]), 2)}
        ea, eb = an.episodes(k0, split), an.episodes(k, split)
        ch_ = sorted(((eb[q][1] - ea[q][1], q) for q in ea), reverse=True)
        keys = [q for q in ea if q != ch_[0][1]]
        r["T3"] = {"delta": round(m["T3"]["Rcv@.5"] - m0["T3"]["Rcv@.5"], 1), "better": sum(x > 0 for x, _ in ch_), "worse": sum(x < 0 for x, _ in ch_),
                   "top": (ch_[0][1].split("|")[0].split("_")[0], ch_[0][0]), "without_top": round(an.rcv(eb, keys) - an.rcv(ea, keys), 2)}
        out[f"{split}|{name}"] = r
        print(split, name, json.dumps(r, ensure_ascii=False), flush=True)
json.dump(out, open(os.path.join(HERE, "where_gain.json"), "w"), indent=1, ensure_ascii=False)
