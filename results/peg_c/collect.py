"""Collect every PEG-C number from report files / ledgers / json -> results/peg_c/numbers.json. No tracker runs, nothing typed by hand.
Run: .venv/Scripts/python.exe results/peg_c/collect.py"""
import json, math, os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
R = lambda *p: os.path.join(ROOT, *p)
os.chdir(ROOT)
sys.path.insert(0, R("results", "research")); sys.path.insert(0, ROOT)

ENV = "GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_VEL_K=40 GPEG_VEL_T=2"
COMMANDS = {
    "implementation_checks": ".venv/Scripts/python.exe scripts/21_peg_c_check.py > results/peg_c/check21.txt ; bash results/peg_c/run_byteident.sh ; .venv/Scripts/python.exe results/peg_c/smoke_val.py ; .venv/Scripts/python.exe results/peg_c/wire_check.py ; .venv/Scripts/python.exe results/peg_c/port_check.py 1|2",
    "val search (Thach harness, guard on)": ".venv/Scripts/python.exe results/thach_v2/tune_val.py --peg_c ; --peg_c --strong ; --peg_c --lag ; --peg_c --all ; (--peg_c --lag --all skipped: lag accepted nothing); then --test for tune_C, tune_C_strong, tune_C_all",
    "paper-setting rows (ours, guard off, cached)": "bash results/peg_c/run_paper_rows.sh   # " + ENV + " [+ GPEG_BACKFILL_L=90 GPEG_BACKFILL_MODE=hidden for pegcl_*]",
    "episodes": ".venv/Scripts/python.exe results/peg_c/episodes.py",
    "post-test diagnosis": ".venv/Scripts/python.exe results/peg_c/diag_test_losses.py",
    "figures": ".venv/Scripts/python.exe results/peg_c/collect.py && .venv/Scripts/python.exe scripts/22_peg_c_figures.py",
}


def combined(path):
    for ln in open(path, encoding="utf-8"):
        if ln.startswith("COMBINED"):
            v = ln.split()[1:]
            d = dict(zip(["HOTA", "DetA", "AssA", "IDF1", "MOTA", "IDSW", "Rcll", "Prcn", "FP", "FN"], [float(x) for x in v]))
            for k in ("IDSW", "FP", "FN"):
                d[k] = int(d[k])
            return d


def recovery(path):
    d = {}
    for ln in open(path, encoding="utf-8"):
        t = ln.split()
        if ln.startswith(("clear-ref", "partial", "heavy", "total", "all-burn")):
            d[t[0]] = float(t[3].rstrip("%"))
        m = re.search(r"ID turned off \(track gone\): (\d+) frames \(([\d.]+)% of burn\)", ln)
        if m:
            d["ID_off_frames"], d["ID_off_pct"] = int(m.group(1)), float(m.group(2))
        m = re.search(r"ID survived to burn end : (\d+)/(\d+)", ln)
        if m:
            d["survived"] = f"{m.group(1)}/{m.group(2)}"
        m = re.search(r"ID switches \(IDSW\)\s*: (\d+)", ln)
        if m:
            d["IDSW"] = int(m.group(1))
        m = re.search(r"fragmentation \(Frag\)\s*: (\d+)", ln)
        if m:
            d["Frag"] = int(m.group(1))
    return {"clear": d["clear-ref"], "Rcv@.5": d["all-burn"], "partial": d["partial"], "heavy": d["heavy"], "total": d["total"],
            "ID_off_pct": d["ID_off_pct"], "ID_off_frames": d["ID_off_frames"], "survived": d["survived"], "IDSW": d["IDSW"], "Frag": d["Frag"]}


# a. paper-setting rows (our repo, guard off, cached)
peg_plus = json.load(open(R("results", "peg_plus", "numbers.json"), encoding="utf-8"))
t1c, t2c, t3c = ["HOTA", "IDF1", "MOTA", "IDSW", "FP", "FN"], ["MOTA", "FP", "Rcll", "IDF1"], ["clear", "Rcv@.5", "heavy", "total", "ID_off_pct"]
paper = {"T1": dict(zip(t1c, peg_plus["table1"]["rows"]["paper_peg"])), "T2": dict(zip(t2c, peg_plus["table2"]["rows"]["paper_peg"])),
         "T3": dict(zip(t3c, peg_plus["table3"]["rows"]["paper_peg"]))}
rows = {
    "paper PEG": paper,
    "PEG (ours reproduction)": {"T1": combined(R("results/eval/benchmark_peg_cached_test.txt")), "T2": combined(R("results/eval_synthfs/benchmark_peg_fs_noguard_test.txt")),
                                "T3": recovery(R("results/eval_recovery/recovery_peg_rcv_ng_test.txt"))},
    "PEG+": {"T1": combined(R("results/eval/benchmark_pegplus_A_test.txt")), "T2": combined(R("results/eval_synthfs/benchmark_pegplus_A_fs_test.txt")),
             "T3": recovery(R("results/eval_recovery/recovery_pegplus_A_rcv_test.txt"))},
    "PEG-C online (P + V K40 t2)": {"T1": combined(R("results/eval/benchmark_pegc_test_test.txt")), "T2": combined(R("results/eval_synthfs/benchmark_pegc_fs_test.txt")),
                                    "T3": recovery(R("results/eval_recovery/recovery_pegc_rcv_test.txt"))},
    "PEG-C fixed-lag 90 (B hidden; label: fixed-lag)": {"T1": combined(R("results/eval/benchmark_pegcl_test_test.txt")), "T2": combined(R("results/eval_synthfs/benchmark_pegcl_fs_test.txt")),
                                                         "T3": recovery(R("results/eval_recovery/recovery_pegcl_rcv_test.txt"))},
}
val_t3 = {"PEG": recovery(R("results/eval_recovery/recovery_v_peg_rcv_val.txt")), "PEG+": recovery(R("results/eval_recovery/recovery_v_A_rcv_val.txt")),
          "PEG-C online": recovery(R("results/eval_recovery/recovery_v_pegc_rcv_val.txt")), "PEG-C fixed-lag 90": recovery(R("results/eval_recovery/recovery_v_pegcl_rcv_val.txt"))}

# b. Thach-harness rows (guard on, his setting), val + test, from full_metrics.json
fm = json.load(open(R("results", "thach_v2", "full_metrics.json"), encoding="utf-8"))
def pick(prefix):
    return {s: next(r for r in fm[s] if r["config"].startswith(prefix)) for s in ("val", "test")}
harness = {"PEG": pick("PEG"), "PEG+": pick("PEG+ (ours)"), "PEG-C online": pick("PEG-C online"), "PEG-C fixed-lag 90 (B hidden; val only)": pick("PEG-C fixed-lag"),
           "PEG-C strongest": pick("PEG-C strongest"), "ALL = PEG-C + Thach greedy": pick("ALL = PEG-C"),
           "Thach best (STRONGEST with PEG+ by design)": pick("STRONGEST with PEG+ by design"), "Thach full+M6 (his params, tuned on test)": pick("Thach full+M6")}
harness["PEG"] = {s: next(r for r in fm[s] if r["config"] == "PEG") for s in ("val", "test")}

# c. search traces (all rounds, rows + checks + accepted) and finals / tests
def trace(d):
    t = json.load(open(R("results", "thach_v2", d, "trace.json")))
    fin = json.load(open(R("results", "thach_v2", d, "final.json")))
    out = {"start_val": dict(zip(("T1_HOTA", "T2_HOTA", "T3_Rcv"), t[0]["val"])), "final": fin["label"], "final_key": fin["key"], "final_val": fin["val"], "rounds": []}
    for r in t[1:]:
        out["rounds"].append({"round": r["round"], "accepted": r["accepted"], "checks": r["checks"],
                              "rows": [{"add": x["add"], "delta": x["delta"], "score": x["score"], "admissible": x["admissible"]} for x in r["rows"]]})
    p = R("results", "thach_v2", d, "test.json")
    if os.path.exists(p):
        out["test"] = json.load(open(p))["test"]
    return out
search = {d: trace(d) for d in ("tune_C", "tune_C_strong", "tune_C_lag", "tune_C_all")}
search["tune_C_lag_all"] = {"skipped": open(R("results/thach_v2/tune_C_lag_all/SKIPPED.txt")).read().strip()}
GRIDS = {"V": ["K20 t0", "K20 t2", "K40 t0", "K40 t2"], "C": ["cap 48", "cap 90"], "S": ["stitch k 1.0", "stitch k 1.5"],
         "B": ["L45 hidden", "L45 all", "L90 hidden", "L90 all"], "BB": ["backward birth"]}

# d. episodes
ep = json.load(open(HERE + "/episodes.json"))
changed = {s: [e for e in ep["episodes"] if e["split"] == s and (e["PEG-C"] != e["PEG+"] or e["PEG-C lag"] != e["PEG+"])] for s in ("test", "val")}

# e. oracle rows
J = json.load(open(R("results", "research", "oracle_t3.json")))
V = J["vest"]["summary"]
oracle = {"median_vtrue_speed": J["vest"]["median_vtrue_speed"], "vest": {}, "other": {}}
for sp in ("pooled", "test", "val"):
    oracle["vest"][sp] = {k: {"rcv": V[sp][k]["rcv"], "ci95": V[sp][k]["ci95"], "med_verr": V[sp][k]["med_verr"]} for k in ("b5", "b10", "b20", "b40", "b80", "g10", "g20", "g40", "g80")}
    P_ = J["summary"][sp]["policies"]
    oracle["other"][sp] = {"a_frozen": P_["a_frozen"]["rcv"], "d_oracle_centre": P_["d_oracle_centre"]["rcv"], "i_oracle_constvel": J["flow"]["summary"][sp]["i_oracle_constvel"]["rcv"],
                           "PEGp_tracked_actual": J["summary"][sp]["PEGp_tracked"], "PEG_tracked_actual": J["summary"][sp]["PEG_tracked"],
                           "PEGp_all_episodes": J["summary"][sp]["PEGp_all"], "n_tracked": J["summary"][sp]["n_tracked"]}

# f. check21
chk = {}
for ln in open(HERE + "/check21.txt", encoding="utf-8"):
    m = re.match(r"b(\d+): test ([\d.]+)\s+val ([\d.]+)\s+pooled ([\d.]+)", ln)
    if m:
        chk["b" + m.group(1)] = {"test": float(m.group(2)), "val": float(m.group(3)), "pooled": float(m.group(4))}
    m = re.search(r"episodes differing from the published json: (\d+)", ln)
    if m:
        chk["episodes_differing_from_published"] = int(m.group(1))
chk["expected"] = {"b40": {"test": 88.5, "val": 86.6, "pooled": 87.8}, "b20": {"test": 87.9, "val": 81.6, "pooled": 85.5}}

# g. slope-noise data: residual std of the PEG+ detection centres over their last 40 detection frames, 43 tracked episodes
from oracle_t3 import RCV, RUNS, SYNTH, _iou, coast_flags, cx as cx_, load_mot, load_raw  # noqa: E402
from glaremot.eval.eval_recovery import BURN_THR, burn_index  # noqa: E402
os.chdir(ROOT)
sig = []
for r in J["episodes"]:
    if r["status"] != "tracked":
        continue
    seq, tid = r["seq"], r["tid"]
    gt = load_mot(os.path.join(SYNTH, seq, "mot", "gt", "gt.txt"))
    gtb = lambda f, t: next(((q[1], q[2], q[3], q[4]) for q in gt.get(f, []) if q[0] == t), None)
    rawp = load_raw(os.path.join(RCV, RUNS[r["split"]]["PEG+"], "data", f"{seq}.txt")); fa = r["anchor_frame"]; tr = None
    for t, rr in rawp.items():
        if fa in rr and not coast_flags(rr)[fa] and _iou(gtb(fa, tid), rr[fa][:4]) > 0.5:
            tr = rr; break
    fl = coast_flags(tr)
    det = [f for f in sorted(tr) if f <= fa and not fl[f]][-40:]
    f = np.array(det, float); c = np.array([cx_(tr[q][:4]) for q in det])
    A = np.vstack([f - f.mean(), np.ones(len(f))]).T
    s_ax = []
    for d in (0, 1):
        co = np.linalg.lstsq(A, c[:, d], rcond=None)[0]
        res = c[:, d] - A @ co
        s_ax.append(float(np.sqrt(np.sum(res ** 2) / max(len(f) - 2, 1))))
    sig.append({"seq": seq, "tid": tid, "start": r["start"], "n_det": len(det), "sigma_x": s_ax[0], "sigma_y": s_ax[1], "sigma": math.hypot(*s_ax)})
sigma = float(np.median([s["sigma"] for s in sig]))
Ks = [5, 10, 20, 40, 80]
slope_noise = {
    "definition": "per episode: OLS line (centre vs frame) over the last min(40, n) detection frames of the PEG+ track before the anchor; sigma_ax = sqrt(RSS/(n-2)) per axis; "
                  "sigma_ep = sqrt(sigma_x^2 + sigma_y^2) (= sqrt(2) sigma_axis when equal); sigma = median over the 43 tracked episodes.",
    "curve": "rms_err(K) = sigma * sqrt(12 / K^3)  (RMS length of the 2-D slope error of an OLS fit on K equally spaced points with white noise sigma_ep; "
             "median length of the 2-D error would be x sqrt(ln 4 / 2) = x 0.83 of this)",
    "sigma_px": sigma, "sigma_x_median": float(np.median([s["sigma_x"] for s in sig])), "sigma_y_median": float(np.median([s["sigma_y"] for s in sig])),
    "n_episodes": len(sig), "curve_points": {str(K): sigma * math.sqrt(12.0 / K ** 3) for K in (5, 10, 20, 40, 80)},
    "measured_med_verr_pooled": {f"b{K}": V["pooled"][f"b{K}"]["med_verr"] for K in Ks}, "model_error_med_verr_pooled": {f"g{K}": V["pooled"][f"g{K}"]["med_verr"] for K in (10, 20, 40, 80)},
    "median_vtrue_speed": J["vest"]["median_vtrue_speed"], "per_episode": sig}

# g2. why the lag stage / S were rejected (existing harness outputs only)
import importlib.util
_spec = importlib.util.spec_from_file_location("tv_c", R("results", "thach_v2", "tune_val.py")); _tv = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_tv)
_an = _tv.an
_base = search["tune_C"]["final_key"]
_lag = json.load(open(R("results", "thach_v2", "tune_C_lag", "trace.json")))
lag_B_changes = {}
for r_ in _lag[1]["rows"]:
    ea_, eb_ = _an.episodes(_base, "val"), _an.episodes(r_["key"], "val")
    lag_B_changes[r_["add"]] = [{"episode": q, "covered_before": ea_[q][1], "covered_after": eb_[q][1], "n": ea_[q][0]} for q in ea_ if ea_[q] != eb_[q]]
wgj = json.load(open(R("results", "thach_v2", "where_gain.json"), encoding="utf-8"))
where_gain_C = {k: v for k, v in wgj.items() if k.split("|")[1] in ("C", "Clag", "Cstrong", "Call")}

# h. post-test diagnosis (written by diag_test_losses.py), optional
diag = json.load(open(HERE + "/diag_test_losses.json")) if os.path.exists(HERE + "/diag_test_losses.json") else None

out = {"commands": COMMANDS, "env_note": "paper-setting rows: " + ENV + "; Thach harness rows use guard ON (his setting)",
       "grids": GRIDS, "paper_setting_test": rows, "val_T3": val_t3, "harness_rows": harness, "search": search,
       "episodes_summary": ep["summary"], "episodes_changed": changed, "episodes_all": ep["episodes"],
       "lag_B_val_episode_changes_vs_online": lag_B_changes, "where_gain_C": where_gain_C,
       "oracle": oracle, "check21": chk, "slope_noise": slope_noise, "diag_test_losses": diag}
json.dump(out, open(HERE + "/numbers.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print("sigma", round(sigma, 3), "keys", list(out))
