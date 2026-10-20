"""Full metrics (val + test) vs PEG: each component's best val point, PEG+, Thach's full+M6 (his params), and the
two "strongest" finals. Notes = where the gain sits (where_gain.json). -> full_metrics.json + full_metrics.md"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
L = {}
for d, f in (("tune", "ledger.json"), ("tune", "ledger_extra.json"), ("tune_strong", "ledger.json"), ("tune_strong_P", "ledger.json"), ("tune_O", "ledger.json"),
          ("tune_C", "ledger.json"), ("tune_C_strong", "ledger.json"), ("tune_C_lag", "ledger.json"), ("tune_C_all", "ledger.json"), ("tune_C_lagP", "ledger.json")):
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
    # PEG-O row (best val point of the pre-registered O grid, rejected by val); test was not run in this harness by protocol
    tO = json.load(open(os.path.join(HERE, "tune_O", "trace.json")))
    kO = next(r["key"] for r in tO[1]["rows"] if r["add"].startswith("O[8]"))
    out[s].append({"config": "PEG-O (P+O, best val point τ .08 γ 4; rejected by val)", **(by_key(s, kO) if s == "val" else {}),
                   "note": note(s, "O") if s == "val" else "not run on test: rejected on val"})
    # PEG-C rows (docs/PEG_C_PROTOCOL.md): online final, fixed-lag B[2] (val only), strongest, ALL
    fin = lambda d: json.load(open(os.path.join(HERE, d, "final.json")))
    kB = next(r["key"] for r in json.load(open(os.path.join(HERE, "tune_C_lag", "trace.json")))[1]["rows"] if r["add"] == "B[2]")
    out[s].append({"config": "PEG-C online (P + V K40 t2; val-chosen)", **by_key(s, fin("tune_C")["key"]), "note": note(s, "C")})
    out[s].append({"config": "PEG-C fixed-lag 90 (B hidden; rejected by val)", **(by_key(s, kB) if s == "val" else {}),
                   "note": note(s, "Clag") if s == "val" else "not run in this harness: rejected on val; paper-setting row in results/peg_c"})
    out[s].append({"config": "PEG-C strongest (+ S stitch k 1.0)", **by_key(s, fin("tune_C_strong")["key"]), "note": note(s, "Cstrong")})
    out[s].append({"config": "ALL = PEG-C + Thach greedy (M1 cone)", **by_key(s, fin("tune_C_all")["key"]), "note": note(s, "Call")})
    # Stage 2b (Addendum 2): B on PEG+ without V, val-chosen B[3] (L90, mode all); fixed-lag
    out[s].append({"config": "PEG-C fixed-lag 90 (B all on PEG+; val-chosen)", **by_key(s, fin("tune_C_lagP")["key"]), "note": note(s, "ClagP")})
LOWER = ("T1 IDSW", "T3 ID-off")      # lower is better; everything else higher is better
for s in ("val", "test"):
    for c in COLS:
        vals = [r[c] for r in out[s] if r.get(c) is not None]
        b = (min if c in LOWER else max)(vals)
        for r in out[s]:
            if r.get(c) is not None and r[c] == b:
                r.setdefault("best", []).append(c)
# best overall: chosen on val by sum of deltas vs PEG (T1 HOTA + T2 HOTA + T3 Rcv@.5) over rows with complete val numbers
KEYC = ("T1 HOTA", "T2 HOTA", "T3 Rcv@.5")
peg_val = out["val"][0]
cand = [i for i, r in enumerate(out["val"]) if i and all(r.get(c) is not None for c in COLS)]
sd = {i: sum(out["val"][i][c] - peg_val[c] for c in KEYC) for i in cand}
bi = max(sd, key=sd.get)
def best_line(s):
    r = out["test"][bi]
    tv = ", ".join(f"{c.split()[0]} {c.split()[1]} {r[c]:.2f}" if r.get(c) is not None else f"{c} –" for c in KEYC)
    return (f"Best overall (chosen on val by ΣΔ T1 HOTA + T2 HOTA + T3 Rcv@.5 vs PEG): {out['val'][bi]['config']} — val ΣΔ {sd[bi]:+.2f}; "
            f"test: {tv}")
FOOT = ("S (armed survival): byte-identical to PEG+ on val, never fires. ALL (Stage B: PEG-O's Stage-A final + Thach greedy) = Stage-A final is PEG+, "
        "so ALL = 'STRONGEST with PEG+ by design' above. "
        "PEG-C: lag stage (B, BB) on top of V accepted nothing (B hidden ±0.03, B all T3 −2.1; BB never fires); C (cap) ≤ +0.09; tune_C_lag_all = tune_C_all. "
        "Stage 2b (B on PEG+, no V): B[3] (L90, all) accepted on val (fixed-lag; test run once in this harness).")
out["best_overall"] = {"config": out["val"][bi]["config"], "val_sum_delta": round(sd[bi], 2), "val": {c: out["val"][bi][c] for c in KEYC},
                       "test": {c: out["test"][bi].get(c) for c in KEYC}, "line": {s: best_line(s) for s in ("val", "test")}, "footnote": FOOT}
json.dump(out, open(os.path.join(HERE, "full_metrics.json"), "w"), indent=1)
md = []
for s in ("val", "test"):
    md += [f"### {s}", "", "| config | " + " | ".join(COLS) + " | where the change vs PEG sits |", "|---" * (len(COLS) + 2) + "|"]
    for r in out[s]:
        def cell(c):
            if r.get(c) is None:
                return "–"
            t = ("%.0f" if "IDSW" in c else "%.1f" if "T3" in c else "%.2f") % r[c]
            return f"**{t}**" if c in r.get("best", []) else t
        md.append(f"| {r['config']} | " + " | ".join(cell(c) for c in COLS) + f" | {r['note']} |")
    md += ["", FOOT, "", best_line(s), ""]
open(os.path.join(HERE, "full_metrics.md"), "w", encoding="utf-8").write("\n".join(md))
print("\n".join(md))
