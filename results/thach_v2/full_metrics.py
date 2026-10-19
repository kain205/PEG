"""Full metrics (val + test) vs PEG: each component's best val point, PEG+, Thach's full+M6 (his params), and the
two "strongest" finals. Notes = where the gain sits (where_gain.json). -> full_metrics.json + full_metrics.md"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
L = {}
for d, f in (("tune", "ledger.json"), ("tune", "ledger_extra.json"), ("tune_strong", "ledger.json"), ("tune_strong_P", "ledger.json")):
    p = os.path.join(HERE, d, f)
    if os.path.exists(p):
        L.update(json.load(open(p)))
WG = json.load(open(os.path.join(HERE, "where_gain.json"))) if os.path.exists(os.path.join(HERE, "where_gain.json")) else {}
TH = json.load(open(os.path.join(HERE, "numbers_thach.json")))["metrics"]
trace = json.load(open(os.path.join(HERE, "tune", "trace.json")))
best = {}
for r in trace[1]["rows"]:
    if r["comp"] not in best or r["score"] > best[r["comp"]]["score"]:
        best[r["comp"]] = r
NAME = {"R": "his ID-resolver rewrite", "M1q": "M1 adaptive Q", "M1c": "M1 cone", "M1d": "M1 damping", "M2": "M2 Re-ID",
        "M3": "M3 dyn-h/TTL", "M4": "M4 dormant", "M5": "M5 anchor", "M6": "M6 tone-map", "P": "PEG+ (size lock)"}
COLS = ["T1 HOTA", "T1 IDF1", "T1 MOTA", "T1 IDSW", "T2 HOTA", "T2 IDF1", "T2 MOTA", "T3 Rcv@.5", "T3 total", "T3 ID-off"]


def flat(t1, t2, t3):
    return dict(zip(COLS, (t1["HOTA"], t1["IDF1"], t1["MOTA"], t1["IDSW"], t2["HOTA"], t2["IDF1"], t2["MOTA"], t3["Rcv@.5"], t3["total"], t3["ID_off"])))


def by_key(split, key):
    e = L.get(f"{split}|{key}")
    return flat(e["T1"], e["T2"], e["T3"]) if e else {}


def note(split, name):
    w = WG.get(f"{split}|{name}")
    if not w:
        return ""
    parts = []
    for t in ("T1", "T2"):
        x = w[t]
        if abs(x["delta"]) >= 0.3:
            parts.append(f"{t} {x['delta']:+.2f}: top {x['top'][0][0]} {x['top'][0][1]:+.1f}, without it {x['without_top']:+.2f}")
    x = w["T3"]
    if abs(x["delta"]) >= 0.5:
        parts.append(f"T3 {x['delta']:+.1f}: {x['better']} ep. better / {x['worse']} worse, without top ({x['top'][0]}) {x['without_top']:+.2f}")
    return "; ".join(parts)


def key_of(label_dir):
    return json.load(open(os.path.join(HERE, label_dir, "final.json")))["key"]


P_KEY = next(k.split("|")[1] for k, e in L.items() if e.get("chosen") == {"P": 0})
rows = [("PEG", "S0", trace[0]["key"]), ("PEG+ (ours)", "P", P_KEY)]
rows += [(f"PEG + {NAME[c]} [{r['add']}]", c, r["key"]) for c, r in sorted(best.items(), key=lambda kv: -kv[1]["score"])]
out = {}
for s in ("val", "test"):
    out[s] = [{"config": n, **by_key(s, k), "note": note(s, nm)} for n, nm, k in rows]
    th = TH[s]["full+M6"]
    out[s].append({"config": "Thach full+M6 (his params, tuned on test)", **flat(th["T1"], th["T2"], th["T3"]), "note": ""})
    for d, lab in (("tune_strong", "STRONGEST (val, no single-event check)"), ("tune_strong_P", "STRONGEST with PEG+ by design")):
        f = json.load(open(os.path.join(HERE, d, "final.json")))
        out[s].append({"config": f"{lab}: {f['label']}", **by_key(s, f["key"]), "note": note(s, d)})
json.dump(out, open(os.path.join(HERE, "full_metrics.json"), "w"), indent=1)
md = []
for s in ("val", "test"):
    md += [f"### {s}", "", "| config | " + " | ".join(COLS) + " | where the change vs PEG sits |", "|---" * (len(COLS) + 2) + "|"]
    for r in out[s]:
        md.append(f"| {r['config']} | " + " | ".join(("%.0f" if "IDSW" in c else "%.1f" if "T3" in c else "%.2f") % r[c] if r.get(c) is not None else "–" for c in COLS) + f" | {r['note']} |")
    md.append("")
open(os.path.join(HERE, "full_metrics.md"), "w", encoding="utf-8").write("\n".join(md))
print("\n".join(md))
