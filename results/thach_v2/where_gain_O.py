"""where-gain for the PEG-O val point O[8]+P (val only; no tracker runs, no test): adds key 'val|O' to where_gain.json
(other entries untouched). Reads existing reports via an.metrics / an.episodes."""
import importlib.util, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("tv", os.path.join(HERE, "tune_val.py")); tv = importlib.util.module_from_spec(spec); spec.loader.exec_module(tv)
an = tv.an
trace = json.load(open(os.path.join(HERE, "tune_O", "trace.json")))
k = next(r["key"] for r in trace[1]["rows"] if r["add"].startswith("O[8]"))
k0 = trace[0]["key"] if False else "tvb9600652"          # PEG = S0
split = "val"
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
p = os.path.join(HERE, "where_gain.json")
wg = json.load(open(p)); wg["val|O"] = r
json.dump(wg, open(p, "w"), indent=1, ensure_ascii=False)
print(json.dumps(r, ensure_ascii=False))
