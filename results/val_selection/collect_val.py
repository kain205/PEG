"""Merge val selection + extra val configs + per-episode stats + test numbers into numbers_val.json (deck input)."""
import importlib.util, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
os.chdir(ROOT)
spec = importlib.util.spec_from_file_location("rs", os.path.join(HERE, "run_selection.py"))
rs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rs)
S = json.load(open(os.path.join(HERE, "selection.json")))
val = dict(S["configs"])
for cfg in [("A", "M1swap", "M3")]:          # reported for comparison only, not part of the selection
    val[rs.cfg_name(cfg)] = rs.run_cfg(cfg, False)
N = json.load(open("results/peg_f/numbers.json"))["variants"]
test = {}
for k, v in {"v_peg": "peg", "v_A": "A", "v_M1damp": "P+M1damp", "v_M1swap": "P+M1swap", "v_M3": "P+M3",
             "v_A+M1swap+M3": "A+M1swap+M3"}.items():
    t = N[v]
    test[k] = {"T1": t["table1"]["combined"], "T2": t["table2"]["combined"],
               "T3": {"all_burn": t["table3"]["all_burn"], "total": t["table3"]["total"], "ID_off_pct": t["table3"].get("ID_off_pct")}}
out = {"selection": {"rounds": S["rounds"], "final": S["final_config"], "final_env": S["final_env"], "sequence": S["chosen_sequence"]},
       "val": val, "test": test, "episodes": json.load(open(os.path.join(HERE, "episodes.json")))["summary"]}
json.dump(out, open(os.path.join(HERE, "numbers_val.json"), "w"), indent=1)
print("wrote numbers_val.json", sorted(val), sorted(test))
