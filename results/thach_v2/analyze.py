"""Thach v2 (M1-M6): collect all three tables on test + val, apply the pre-registered val rule
(docs/THACH_V2_PROTOCOL.md), per-sequence and per-episode breakdowns. -> numbers_thach.json, THACH_V2.md
Run after build_caches.sh:  .venv/Scripts/python.exe results/thach_v2/analyze.py"""
import importlib.util, json, os, random, re, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import BURN_THR, burn_index, load_events, load_mot, match_frame  # noqa: E402

spec = importlib.util.spec_from_file_location("run", os.path.join(HERE, "run.py"))
run = importlib.util.module_from_spec(spec); spec.loader.exec_module(run)
CFGS = list(run.CONFIGS)
OUT = os.path.join(HERE, "out")
SYNTH = os.path.join(ROOT, "datasets", "synth")
SEQ = re.compile(r"^\d+_sequence")
MARGIN, MIN_GAIN = -0.5, 0.5
# our PEG, guard on (his setting): tracker names in our repo
PEG = {"test": ("pf_peg_g", "pf_peg_g_fs", "pf_peg_g_rcv"), "val": ("v_peg_g", "v_peg_g_fs", "v_peg_g_rcv")}


def short(s):
    return re.sub(r"_(complete|new|in_progress)$", "", s)


SPLITS = {k: {short(x) for x in v} for k, v in json.load(open(os.path.join(ROOT, "glaremot", "data", "splits.json"))).items()
          if k in ("test", "val")}


def parse_mot(path):
    per, comb = {}, None
    for ln in open(path, encoding="utf-8"):
        p = ln.split()
        if len(p) >= 11 and (SEQ.match(p[0]) or p[0] == "COMBINED"):
            r = dict(zip(("HOTA", "DetA", "AssA", "IDF1", "MOTA", "IDSW", "Rcll", "Prcn", "FP", "FN"), map(float, p[1:11])))
            if p[0] == "COMBINED":
                comb = r
            else:
                per[short(p[0])] = r
    return comb, per


def parse_rcv(path):
    t = open(path, encoding="utf-8").read()
    g = lambda name: float(re.search(rf"^{name}\s+\S+\s+\d+\s+([\d.]+)%", t, re.M)[1])
    off = re.search(r"ID turned off.*?\(([\d.]+)% of burn\)", t)
    surv = re.search(r"ID survived to burn end : (\d+)/(\d+)", t)
    return {"Rcv@.5": g("all-burn"), "total": g("total"), "clear": g("clear-ref"),
            "ID_off": float(off[1]) if off else None, "survived": int(surv[1]), "episodes": int(surv[2])}


def paths(cfg, split):
    if cfg == "PEG":
        a, b, c = PEG[split]
        return (f"{ROOT}/results/eval/benchmark_{a}_{split}.txt", f"{ROOT}/results/eval_synthfs/benchmark_{b}_{split}.txt",
                f"{ROOT}/results/eval_recovery/recovery_{c}_{split}.txt", f"{ROOT}/results/eval_recovery/trackers/{c}/data")
    return (run.report(cfg, "t1", split, False), run.report(cfg, "t2", split, False), run.report(cfg, "t3", split, False),
            f"{OUT}/eval_recovery/trackers/{run.name(cfg, 't3', split, False)}/data")


def metrics(cfg, split):
    p1, p2, p3, _ = paths(cfg, split)
    c1, s1 = parse_mot(p1)
    c2, s2 = parse_mot(p2)
    return {"T1": c1, "T2": c2, "T3": parse_rcv(p3), "T1_seq": s1, "T2_seq": s2}


def episodes(cfg, split):
    """Per burn episode: (key, n burn frames, covered frames @IoU .5) for this config."""
    d = paths(cfg, split)[3]
    out = {}
    for f in sorted(os.listdir(d)):
        seq = f[:-4]
        if short(seq) not in SPLITS[split]:  # his tracker dirs hold both splits (name has no split suffix)
            continue
        gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
        bi = burn_index(seq, SYNTH)
        trk = load_mot(os.path.join(d, f))
        for tid, s0, dur in load_events(seq, SYNTH):
            ep = [x for x in range(s0 + 1, s0 + dur + 1)
                  if any(r[0] == tid for r in gt.get(x, [])) and bi.get((tid, x), 1.0) < BURN_THR]
            if ep:
                cov = sum(1 for x in ep if match_frame(gt.get(x, []), trk.get(x, []), 0.5).get(tid))
                out[f"{short(seq)}|{tid}|{ep[0]}"] = (len(ep), cov)
    return out


def rcv(eps, keys=None):
    keys = list(eps) if keys is None else keys
    return 100.0 * sum(eps[k][1] for k in keys) / max(1, sum(eps[k][0] for k in keys))


def boot(a, b, B=10000, seed=0):
    rng, keys = random.Random(seed), list(a)
    d = sorted(rcv(b, s) - rcv(a, s) for s in ([rng.choice(keys) for _ in keys] for _ in range(B)))
    return round(d[int(0.025 * B)], 1), round(d[int(0.975 * B)], 1)


def rescore_without(cfg, table, split, drop_seq):
    """COMBINED HOTA of cfg on `table` (t1/t2) with one sequence removed (TrackEval re-run on a copy)."""
    src_name = run.name(cfg, table, split, False)
    sub = "eval" if table == "t1" else "eval_synthfs"
    dst_name = src_name + "_lo"
    src = f"{OUT}/{sub}/trackers/{src_name}/data"
    dst = f"{OUT}/{sub}/trackers/{dst_name}/data"
    shutil.rmtree(os.path.dirname(dst), ignore_errors=True)
    shutil.copytree(src, dst)
    keep = [short(f[:-4]) for f in os.listdir(dst) if short(f[:-4]) != drop_seq and short(f[:-4]) in SPLITS[split]]
    env = {k: v for k, v in os.environ.items() if k not in run.CLEAR}
    env.update(PYTHONIOENCODING="utf-8", GLAREMOT_CONFIG=os.path.join(run.REPO, "configs", "ours_real.yaml" if table == "t1" else "ours_synth.yaml"))
    argv = [run.PY, "scripts/06_eval_mot.py", "--split", split, "--skip_track", "--tracker_name", dst_name, "--seqs"] + keep
    if table == "t2":
        argv += ["--data_root", "D:/PROJECT/PEG/datasets/synth", "--results_subdir", "eval_synthfs"]
    subprocess.run(argv, cwd=run.REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, check=True)
    return parse_mot(f"{OUT}/{sub}/benchmark_{dst_name}_{split}.txt")[0]["HOTA"]


def main():
    M = {s: {c: metrics(c, s) for c in ["PEG"] + CFGS} for s in ("test", "val")}
    E = {s: {c: episodes(c, s) for c in ["PEG"] + CFGS} for s in ("test", "val")}
    prim = lambda m: (m["T1"]["HOTA"], m["T2"]["HOTA"], m["T3"]["Rcv@.5"])

    # ---- val rule
    vb = prim(M["val"]["base"])
    rows = []
    for c in CFGS[1:]:
        d = [round(x - y, 4) for x, y in zip(prim(M["val"][c]), vb)]
        rows.append({"config": c, "delta": d, "score": round(sum(d), 4), "admissible": all(x >= MARGIN for x in d)})
    ranked = sorted([r for r in rows if r["admissible"] and r["score"] > MIN_GAIN], key=lambda r: -r["score"])
    selected, checks = "base", []
    for r in ranked:
        c = r["config"]
        # most favourable single unit per table
        chk = {}
        for t, k in (("t1", "T1_seq"), ("t2", "T2_seq")):
            a, b = M["val"]["base"][k], M["val"][c][k]
            seq = max(a, key=lambda s: b[s]["HOTA"] - a[s]["HOTA"])
            hb, hc = rescore_without("base", t, "val", seq), rescore_without(c, t, "val", seq)
            chk[t] = {"dropped": seq, "delta_without": round(hc - hb, 2)}
        ea, eb = E["val"]["base"], E["val"][c]
        ep = max(ea, key=lambda k: eb[k][1] - ea[k][1])
        keys = [k for k in ea if k != ep]
        chk["t3"] = {"dropped": ep, "delta_without": round(rcv(eb, keys) - rcv(ea, keys), 2)}
        s_wo = round(sum(v["delta_without"] for v in chk.values()), 2)
        checks.append({"config": c, "checks": chk, "score_without": s_wo, "pass": s_wo > 0})
        if s_wo > 0:
            selected = c
            break

    # ---- per-episode summaries (Table III), vs base and vs PEG
    ep_sum = {}
    for split in ("test", "val", "pooled"):
        for ref in ("base", "PEG"):
            for c in CFGS:
                if c == ref:
                    continue
                if split == "pooled":
                    A = {**{"t|" + k: v for k, v in E["test"][ref].items()}, **{"v|" + k: v for k, v in E["val"][ref].items()}}
                    B = {**{"t|" + k: v for k, v in E["test"][c].items()}, **{"v|" + k: v for k, v in E["val"][c].items()}}
                else:
                    A, B = E[split][ref], E[split][c]
                ch = [B[k][1] - A[k][1] for k in A]
                ep_sum[f"{split}|{c}|vs_{ref}"] = {"delta": round(rcv(B) - rcv(A), 1), "ci95": boot(A, B), "better": sum(x > 0 for x in ch),
                                                    "worse": sum(x < 0 for x in ch), "frames": sum(ch), "n_ep": len(A)}

    # ---- firing counters from his [diag] lines
    diag = {}
    for c in CFGS:
        for t, sp in (("t1", "test"), ("t1", "val")):
            log = os.path.join(HERE, "logs", f"{t}_{sp}_{run.name(c, t, sp, False)}.log")
            if os.path.exists(log):
                tot = {}
                for k, v in re.findall(r"(\w+\(M\d\))=(\d+)", open(log, encoding="utf-8").read()):
                    tot[k] = tot.get(k, 0) + int(v)
                diag[f"{sp}|{c}"] = tot

    strip = lambda m: {k: v for k, v in m.items() if not k.endswith("_seq")}
    out = {"metrics": {s: {c: strip(m) for c, m in M[s].items()} for s in M},
           "per_seq": {s: {c: {"T1": M[s][c]["T1_seq"], "T2": M[s][c]["T2_seq"]} for c in M[s]} for s in M},
           "val_rule": {"rows": rows, "checks": checks, "selected": selected}, "episodes": ep_sum, "diag": diag}
    json.dump(out, open(os.path.join(HERE, "numbers_thach.json"), "w"), indent=1)

    L = ["# Thach v2 (M1-M6): all three tables, test + val", "", "Protocol: `docs/THACH_V2_PROTOCOL.md`. Guard on (his setting). PEG = ours, guard on.", ""]
    for s in ("test", "val"):
        L += [f"## {s}", "", "| config | T1 HOTA | T1 IDF1 | T1 IDSW | T2 HOTA | T2 MOTA | T3 Rcv@.5 | T3 total | T3 ID-off |", "|---|---|---|---|---|---|---|---|---|"]
        for c in ["PEG"] + CFGS:
            m = M[s][c]
            L.append(f"| {c} | {m['T1']['HOTA']:.2f} | {m['T1']['IDF1']:.2f} | {m['T1']['IDSW']:.0f} | {m['T2']['HOTA']:.2f} | {m['T2']['MOTA']:.2f} | "
                     f"{m['T3']['Rcv@.5']:.1f} | {m['T3']['total']:.1f} | {m['T3']['ID_off']} |")
        L.append("")
    L += ["## Val rule (deltas vs his base)", "", "| config | ΔT1 HOTA | ΔT2 HOTA | ΔT3 Rcv | score | admissible |", "|---|---|---|---|---|---|"]
    L += [f"| {r['config']} | {r['delta'][0]:+.2f} | {r['delta'][1]:+.2f} | {r['delta'][2]:+.1f} | {r['score']:+.2f} | {'yes' if r['admissible'] else 'no'} |" for r in rows]
    L += ["", "Single-event checks (in rank order):", ""]
    L += [f"- {c['config']}: drop {c['checks']['t1']['dropped']} (T1 {c['checks']['t1']['delta_without']:+.2f}), "
          f"{c['checks']['t2']['dropped']} (T2 {c['checks']['t2']['delta_without']:+.2f}), episode {c['checks']['t3']['dropped']} "
          f"(T3 {c['checks']['t3']['delta_without']:+.2f}) -> score {c['score_without']:+.2f} {'PASS' if c['pass'] else 'fail'}" for c in checks]
    L += ["", f"**Selected: {selected}**", "", "## Table III per episode (bootstrap 95% CI)", "",
          "| split | config | vs | ΔRcv | CI95 | better/worse | frames |", "|---|---|---|---|---|---|---|"]
    for k, v in ep_sum.items():
        sp, c, ref = k.split("|")
        if c in ("full", "full+M6", "base+M1", "base+M6") or ref == "vs_PEG" and c == "base":
            L.append(f"| {sp} | {c} | {ref[3:]} | {v['delta']:+.1f} | [{v['ci95'][0]:+.1f}, {v['ci95'][1]:+.1f}] | {v['better']}/{v['worse']} | {v['frames']:+d} |")
    L += ["", "## Firing counters (Table I, summed over sequences)", ""] + [f"- {k}: {v}" for k, v in diag.items() if v]
    open(os.path.join(HERE, "THACH_V2.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(L[-60:]))


if __name__ == "__main__":
    main()
