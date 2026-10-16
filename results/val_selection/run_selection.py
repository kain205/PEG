"""Greedy forward selection of PEG+/PEG-F components on VAL (rule: docs/VAL_SELECTION_PROTOCOL.md).
Run (repo root):  .venv/Scripts/python.exe results/val_selection/run_selection.py [--dry_run] [--rerun]
Needs the val perception caches (results/percep_cache/{real,synth}). Reports are cached: a run is skipped if its
report file exists (use --rerun to redo). Outputs: selection.json, SELECTION.md, logs/<t1|t2|t3>_<config>.log"""
import argparse, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LOGS = os.path.join(HERE, "logs")
COLS = ["HOTA", "DetA", "AssA", "IDF1", "MOTA", "IDSW", "Rcll", "Prcn", "FP", "FN"]
INT = {"IDSW", "FP", "FN"}
MARGIN, MIN_GAIN = -0.5, 0.5          # protocol: admissible iff every primary delta >= -0.5; accept iff best score > +0.5
CLEAR = "GPEG_F GPEG_SIZE_LOCK GPEG_LAMP_FOLLOW GMOT_ADAPTIVE_MOTION GMOT_REID GMOT_DORMANT GBEACON_DYNAMIC_H GBEACON_ADAPTIVE_TTL " \
        "GBEACON_ANCHOR GBEACON_H_DECAY GMOT_DORMANT_APP_THRESH GMOT_DORMANT_MAX_AGE GMOT_AM_DAMP GMOT_AM_SWAP GPEG_F_STATS " \
        "GMOT_TRACKER GMOT_BIRTH_SIZE_GUARD".split()
COMP = {"A": {"GPEG_SIZE_LOCK": "1"}, "B": {"GPEG_LAMP_FOLLOW": "1"}, "M1damp": {"GMOT_AM_DAMP": "1"}, "M1swap": {"GMOT_AM_SWAP": "1"},
        "M2": {"GMOT_REID": "1"}, "M3": {"GBEACON_DYNAMIC_H": "1", "GBEACON_ADAPTIVE_TTL": "1"},
        "M4": {"GMOT_DORMANT": "1"}, "M5": {"GBEACON_ANCHOR": "1"}}   # dict order = canonical order = tie-break order
CR, CS = "results/percep_cache/real", "results/percep_cache/synth"


def parse_mot(path):
    comb = None
    for ln in open(path, encoding="utf-8", errors="replace"):
        p = ln.split()
        if len(p) == 11 and p[0] == "COMBINED":
            try:
                comb = {c: (int(x) if c in INT else float(x)) for c, x in zip(COLS, p[1:])}
            except ValueError:
                continue
    return comb


def parse_rcv(path):
    t = open(path, encoding="utf-8", errors="replace").read()
    r = {}
    for key, name in [("total", "total"), ("all_burn", "all-burn")]:
        m = re.search(rf"^{name}\s+\S+\s+(\d+)\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)%\s+([\d.]+)\s+([\d.]+)%", t, re.M)
        if m:
            r[key] = {"n": int(m[1]), "Rcv@.5": float(m[2])}
    for k, pat in [("ID_off_pct", r"ID turned off.*?\(([\d.]+)% of burn"), ("survived", r"ID survived to burn end\s*:\s*(\d+)/(\d+)")]:
        m = re.search(pat, t)
        if m:
            r[k] = float(m[1]) if k == "ID_off_pct" else int(m[1])
            if k == "survived":
                r["episodes"] = int(m[2])
    return r if "all_burn" in r else None


def cfg_name(cfg):
    return "v_" + ("+".join(cfg) if cfg else "peg")


def cfg_env(cfg):
    env = {"GMOT_TRACKER": "beacon", "GMOT_BIRTH_SIZE_GUARD": "0"}
    for c in cfg:
        env.update(COMP[c])
    if "M4" in cfg and "M2" not in cfg:
        env["GMOT_REID"] = "0"
    return env


def jobs(cfg):  # (kind, tracker, argv, report path)
    n = cfg_name(cfg)
    r = lambda *p: os.path.join(ROOT, *p)
    return [("t1", n, ["scripts/06_eval_mot.py", "--split", "val", "--percep_cache", CR, "--tracker_name", n],
             r("results", "eval", f"benchmark_{n}_val.txt")),
            ("t2", n + "_fs", ["scripts/06_eval_mot.py", "--split", "val", "--data_root", "datasets/synth", "--results_subdir", "eval_synthfs",
                               "--percep_cache", CS, "--tracker_name", n + "_fs"], r("results", "eval_synthfs", f"benchmark_{n}_fs_val.txt")),
            ("t3", n + "_rcv", ["scripts/07_eval_recovery.py", "--split", "val", "--percep_cache", CS, "--tracker_name", n + "_rcv"],
             r("results", "eval_recovery", f"recovery_{n}_rcv_val.txt"))]


def run_cfg(cfg, rerun):
    env = {k: v for k, v in os.environ.items() if k not in CLEAR}
    env.update(cfg_env(cfg))
    for kind, trk, argv, rep in jobs(cfg):
        if os.path.exists(rep) and not rerun:
            continue
        with open(os.path.join(LOGS, f"{kind}_{cfg_name(cfg)}.log"), "w", encoding="utf-8") as f:
            rc = subprocess.run([sys.executable] + argv, cwd=ROOT, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
        if rc != 0 or not os.path.exists(rep):
            raise RuntimeError(f"{kind} {trk} failed (rc={rc}); see {LOGS}/{kind}_{cfg_name(cfg)}.log")
    j = jobs(cfg)
    t1, t2, t3 = parse_mot(j[0][3]), parse_mot(j[1][3]), parse_rcv(j[2][3])
    if not (t1 and t2 and t3):
        raise RuntimeError(f"could not parse reports of {cfg_name(cfg)}")
    return {"config": list(cfg), "name": cfg_name(cfg), "T1": t1, "T2": t2, "T3": t3,
            "primary": [t1["HOTA"], t2["HOTA"], t3["all_burn"]["Rcv@.5"]]}


def canon(comps):
    return tuple(c for c in COMP if c in comps)


def f(x, d=2, sign=False):
    return f"{x:+.{d}f}" if sign else f"{x:.{d}f}"


def md_round(i, cur, cands):
    o = [f"## Round {i}: current = {cur}", "",
         "| candidate | T1 HOTA (Δ) | T2 HOTA (Δ) | T3 Rcv@.5 (Δ) | score | admissible | T1 IDF1 | T1 IDSW | T2 MOTA | T3 total | T3 ID-off % |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for c in [cands["current"]] + cands["rows"]:
        m, d = c["m"], c.get("delta")
        pc = [f(m["primary"][k], 2 if k < 2 else 1) + (f" ({f(d[k], 2, True)})" if d else "") for k in range(3)]
        o.append(f"| {m['name']} | {' | '.join(pc)} | {f(c['score'], 2, True) if d else '-'} | "
                 f"{('yes' if c['admissible'] else 'no') if d else '-'} | {f(m['T1']['IDF1'])} | {m['T1']['IDSW']} | {f(m['T2']['MOTA'])} | "
                 f"{f(m['T3']['total']['Rcv@.5'], 1)} | {f(m['T3']['ID_off_pct'], 1)} |")
    return "\n".join(o)


def env_str(cfg):
    return " ".join(f"{k}={v}" for k, v in cfg_env(cfg).items())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--rerun", action="store_true")
    a = ap.parse_args()
    os.makedirs(LOGS, exist_ok=True)
    if a.dry_run:
        print("removed from inherited env:", " ".join(CLEAR))
        for cfg in [()] + [canon([c]) for c in COMP]:
            print(f"\n# {cfg_name(cfg)}   env: {env_str(cfg)}")
            for kind, trk, argv, rep in jobs(cfg):
                print(f"  {kind}: python {' '.join(argv)}\n      -> {os.path.relpath(rep, ROOT)}")
        return
    cache, rounds, cur = {}, [], ()

    def get(cfgs):
        todo = [c for c in cfgs if c not in cache]
        with ThreadPoolExecutor(max_workers=3) as ex:
            for c, m in zip(todo, ex.map(lambda c: run_cfg(c, a.rerun), todo)):
                cache[c] = m
        return [cache[c] for c in cfgs]

    chosen = []
    while True:
        rest = [c for c in COMP if c not in cur]
        if not rest:
            break
        cands = [canon(cur + (x,)) for x in rest]
        base, *ms = get([cur] + cands)
        rows, best = [], None
        for x, m in zip(rest, ms):
            d = [round(m["primary"][k] - base["primary"][k], 4) for k in range(3)]
            row = {"component": x, "m": m, "delta": d, "score": round(sum(d), 4), "admissible": all(v >= MARGIN for v in d)}
            rows.append(row)
            if row["admissible"] and row["score"] > MIN_GAIN and (best is None or row["score"] > best["score"]):
                best = row                       # strict '>' keeps the earlier component on ties
        rounds.append({"current": cfg_name(cur), "cand": {"current": {"m": base}, "rows": rows}, "accepted": best["component"] if best else None})
        print(f"round {len(rounds)}: {cfg_name(cur)} -> " + (f"+{best['component']} (score {best['score']:+.2f})" if best else "stop"))
        if not best:
            break
        cur = canon(cur + (best["component"],))
        chosen.append(best["component"])

    out = {"components": {k: v for k, v in COMP.items()}, "configs": {cfg_name(c): m for c, m in cache.items()},
           "rounds": [{"current": r["current"], "candidates": [{k: v for k, v in x.items() if k != "m"} | {"config": x["m"]["name"]} for x in r["cand"]["rows"]],
                       "accepted": r["accepted"]} for r in rounds],
           "chosen_sequence": chosen, "final_config": cfg_name(cur), "final_env": env_str(cur)}
    json.dump(out, open(os.path.join(HERE, "selection.json"), "w"), indent=1)
    L = ["# Val selection (greedy forward from PEG; rule in docs/VAL_SELECTION_PROTOCOL.md)", "",
         f"Admissible: every primary delta >= {MARGIN}; accept best admissible score (sum of 3 primary deltas) > +{MIN_GAIN}. "
         "Primary = T1 HOTA, T2 HOTA, T3 all-burn Rcv@.5 (val, COMBINED).", ""]
    for i, r in enumerate(rounds, 1):
        c = {"current": {"m": r["cand"]["current"]["m"], "score": 0, "admissible": True}, "rows": r["cand"]["rows"]}
        L += [md_round(i, r["current"], c), "", f"Accepted: {r['accepted'] or 'none (stop)'}", ""]
    L += [f"Selected: {cfg_name(cur)} (sequence: {', '.join(chosen) or 'PEG only'})", "", "Env for the final config (plus inherited flags cleared):", "",
          "```", env_str(cur), "```", ""]
    open(os.path.join(HERE, "SELECTION.md"), "w", encoding="utf-8").write("\n".join(L))
    print("selected:", cfg_name(cur), "| env:", env_str(cur))


if __name__ == "__main__":
    main()
