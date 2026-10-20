"""where-gain for the PEG-C rows (val AND test where a test report exists): adds keys '<split>|C', '|Clag' (val only), '|Cstrong', '|Call' to
where_gain.json (other entries untouched). Reads existing reports via an.metrics / an.episodes; no tracker runs."""
import importlib.util, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("tv", os.path.join(HERE, "tune_val.py")); tv = importlib.util.module_from_spec(spec); spec.loader.exec_module(tv)
an = tv.an
k0 = "tvb9600652"          # PEG = S0
fin = lambda d: json.load(open(os.path.join(HERE, d, "final.json")))["key"]
lag = json.load(open(os.path.join(HERE, "tune_C_lag", "trace.json")))
kB = next(r["key"] for r in lag[1]["rows"] if r["add"] == "B[2]")
CFG = {"C": (fin("tune_C"), ("val", "test")), "Clag": (kB, ("val",)), "Cstrong": (fin("tune_C_strong"), ("val", "test")),
       "Call": (fin("tune_C_all"), ("val", "test"))}
p = os.path.join(HERE, "where_gain.json")
wg = json.load(open(p))
for name, (k, splits) in CFG.items():
    for split in splits:
        m0, m = an.metrics(k0, split), an.metrics(k, split)
        r = {"key": k}
        for t in ("T1", "T2"):
            d = sorted(((m[t + "_seq"][s]["HOTA"] - m0[t + "_seq"][s]["HOTA"], s) for s in m0[t + "_seq"]), reverse=True)
            r[t] = {"delta": round(m[t]["HOTA"] - m0[t]["HOTA"], 2), "top": [(s.split("_")[0], round(x, 1)) for x, s in d[:2]],
                    "worst": [(s.split("_")[0], round(x, 1)) for x, s in d[-2:]],
                    "without_top": round(an.rescore_without(k, t.lower(), split, d[0][1]) - an.rescore_without(k0, t.lower(), split, d[0][1]), 2)}
        ea, eb = an.episodes(k0, split), an.episodes(k, split)
        ch_ = sorted(((eb[q][1] - ea[q][1], q) for q in ea), reverse=True)
        keys = [q for q in ea if q != ch_[0][1]]
        r["T3"] = {"delta": round(m["T3"]["Rcv@.5"] - m0["T3"]["Rcv@.5"], 1), "better": sum(x > 0 for x, _ in ch_), "worse": sum(x < 0 for x, _ in ch_),
                   "top": (ch_[0][1].split("|")[0].split("_")[0], ch_[0][0]), "worst": (ch_[-1][1], ch_[-1][0]), "without_top": round(an.rcv(eb, keys) - an.rcv(ea, keys), 2)}
        wg[f"{split}|{name}"] = r
        print(split, name, json.dumps(r, ensure_ascii=False), flush=True)
json.dump(wg, open(p, "w"), indent=1, ensure_ascii=False)
