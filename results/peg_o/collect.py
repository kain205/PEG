"""Collect every PEG-O number from the report files / ledgers / logs -> results/peg_o/numbers.json + RESULTS.md.
No tracker runs. Run: .venv/Scripts/python.exe results/peg_o/collect.py"""
import json, os, re, subprocess, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
R = lambda *p: os.path.join(ROOT, *p)
PY = sys.executable

# plan-mode feasibility numbers (NOT measured by us in this repo; typed from the plan, plan section 1, tau = 0.05)
PLAN_19 = {"135 g53": 30.4, "204 g300": 21.5, "320 g1": 6.8, "176 g204": 28.9, "325 g3": 82.5}
COMMITS = {"4b13dc3": "PEG-O: pre-registered val protocol (before any run)", "bab4795": "PEG-O: implementation + protocol addendum (relative-R fusion), before any val run"}
ENV = "GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_ODO=1 GPEG_ODO_TAU=0.08 GPEG_ODO_GAMMA=4"
COMMANDS = {
    "estimator_pin": ".venv/Scripts/python.exe scripts/19_peg_o_check.py > results/peg_o/check_19.txt",
    "byte_identity (flags unset, guard off, cached)": "GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 [GPEG_SIZE_LOCK=1] scripts/06_eval_mot.py / 07_eval_recovery.py --percep_cache results/percep_cache/{real,synth} --tracker_name bi_*",
    "smoke 135 (relative-R)": "GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_ODO=1 GPEG_ODO_TAU=0.06 GPEG_ODO_GAMMA=1 .venv/Scripts/python.exe scripts/07_eval_recovery.py --split test --percep_cache results/percep_cache/synth --tracker_name smoke_pego2_135 --seqs 135_sequence_19q_new",
    "val search (Thach harness, guard on)": ".venv/Scripts/python.exe results/thach_v2/tune_val.py --peg_o ; --peg_o --strong ; --peg_o --test",
    "test T1": f"{ENV} .venv/Scripts/python.exe scripts/06_eval_mot.py --split test --percep_cache results/percep_cache/real --tracker_name pego_test",
    "test T2": f"{ENV} .venv/Scripts/python.exe scripts/06_eval_mot.py --split test --data_root datasets/synth --results_subdir eval_synthfs --percep_cache results/percep_cache/synth --tracker_name pego_fs",
    "test T3": f"{ENV} .venv/Scripts/python.exe scripts/07_eval_recovery.py --split test --percep_cache results/percep_cache/synth --tracker_name pego_rcv",
    "val T3 (ours, guard off)": f"{ENV} .venv/Scripts/python.exe scripts/07_eval_recovery.py --split val --percep_cache results/percep_cache/synth --tracker_name v_pego_rcv",
    "episodes": ".venv/Scripts/python.exe results/peg_o/episodes.py",
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
            d[t[0]] = float(t[3].rstrip("%")) if t[0] != "all-burn" else float(t[2 + 1].rstrip("%"))
            n = int(t[2])
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
    "PEG-O O[8] tau .08 gamma 4 (not selected by val)": {"T1": combined(R("results/eval/benchmark_pego_test_test.txt")), "T2": combined(R("results/eval_synthfs/benchmark_pego_fs_test.txt")),
                                                         "T3": recovery(R("results/eval_recovery/recovery_pego_rcv_test.txt"))},
}
val_t3 = {"PEG": recovery(R("results/eval_recovery/recovery_v_peg_rcv_val.txt")), "PEG+": recovery(R("results/eval_recovery/recovery_v_A_rcv_val.txt")),
          "PEG-O O[8]": recovery(R("results/eval_recovery/recovery_v_pego_rcv_val.txt"))}

# b. val search
trace = json.load(open(R("results/thach_v2/tune_O/trace.json")))
final = json.load(open(R("results/thach_v2/tune_O/final.json"))); test_O = json.load(open(R("results/thach_v2/tune_O/test.json")))
O_GRID = [(t, g) for t in (0.04, 0.06, 0.08) for g in (0.25, 1, 4)]
search = {"start_S0P_val": dict(zip(("T1_HOTA", "T2_HOTA", "T3_Rcv"), trace[0]["val"])), "rows": [], "final": final["label"], "final_val": final["val"],
          "accepted": trace[1]["accepted"], "tune_O_test": test_O["test"], "tune_O_test_label": test_O["label"]}
for r in trace[1]["rows"]:
    i = int(r["add"][2:-1]) if r["add"].startswith("O[") else None
    search["rows"].append({"add": r["add"], "tau": O_GRID[i][0] if i is not None else None, "gamma": O_GRID[i][1] if i is not None else None, "key": r["key"],
                           "delta": r["delta"], "score": r["score"], "admissible": r["admissible"]})

# c. episodes
ep = json.load(open(HERE + "/episodes.json"))
changed = {s: [e for e in ep["episodes"] if e["split"] == s and e["PEG-O"] != e["PEG+"]] for s in ("test", "val")}

# d. estimator pin
pin = {}
cur = None
for ln in open(HERE + "/check_19.txt", encoding="utf-8"):
    if ln.startswith("tau"):
        cur = ln.split()[1]; pin[cur] = {}
        continue
    m = re.match(r"(\d+ g\d+): (\d+) fr, box (\d+x\d+) \| frozen mean ([\d.]+) .*MF-odo mean ([\d.]+) max ([\d.]+) .* used (\d+)/(\d+) \| anchor frame (\S+) sharp (\S+) rho", ln)
    if m:
        pin[cur][m.group(1)] = dict(frames=int(m.group(2)), box=m.group(3), frozen=float(m.group(4)), odo=float(m.group(5)), odo_max=float(m.group(6)),
                                    used=int(m.group(7)), anchor_frame=m.group(9), anchor_k=m.group(10))

# e. smoke 135
def smoke(tracker=None):
    out = subprocess.run([PY, HERE + "/smoke_135.py"] + ([tracker] if tracker else []), capture_output=True, text=True, encoding="utf-8", cwd=ROOT).stdout
    d = {}
    for ln in out.splitlines():
        m = re.match(r"g53 frames 409-451 n=(\d+) coverage PEG (\d+)/\d+=\S+\s+PEG\+ (\d+)/\d+=\S+\s+PEG-O (\d+)/\d+", ln)
        if m: d.update(n=int(m.group(1)), PEG=int(m.group(2)), plus=int(m.group(3)), peg_o=int(m.group(4)))
        m = re.search(r"oracle-centred PEG\+ .*coverage (\d+)/", ln)
        if m: d["oracle"] = int(m.group(1))
        m = re.search(r"centre err (PEG\+|PEG-O): mean ([\d.]+) max ([\d.]+)", ln)
        if m: d["cerr_" + ("plus" if m.group(1) == "PEG+" else "peg_o")] = [float(m.group(2)), float(m.group(3))]
        m = re.match(r"g53 frames 815-834 n=(\d+) coverage PEG (\d+)/\d+=\S+\s+PEG\+ (\d+)/\d+=\S+\s+PEG-O (\d+)/", ln)
        if m: d["ep815"] = dict(n=int(m.group(1)), PEG=int(m.group(2)), plus=int(m.group(3)), peg_o=int(m.group(4)))
    return d
sm_old, sm_new = smoke("smoke_pego_135"), smoke("smoke_pego2_135")

# f. val failure diagnosis
vc = []
for ln in open(HERE + "/val_check.txt", encoding="utf-8"):
    m = re.match(r"(\S+) tau([\d.]+): (\d+) fr, box (\d+x\d+) \| frozen mean ([\d.]+) .*MF-odo mean ([\d.]+) max ([\d.]+) .* used (\d+)/(\d+) \| anchor frame (\S+) sharp (\S+)", ln)
    if m:
        vc.append(dict(episode=m.group(1), tau=float(m.group(2)), frames=int(m.group(3)), box=m.group(4), frozen=float(m.group(5)), odo=float(m.group(6)),
                       odo_max=float(m.group(7)), used=int(m.group(8)), anchor_frame=m.group(10), anchor_k=m.group(11)))
lg = json.load(open(HERE + "/val_odo_log.json")); upd = [e for e in lg if e["upd"]]
stale = [e for e in upd if e["anc_frame"] is not None and e["anc_frame"] < e["loss_start"]]
off = int(re.search(r"updates not near a GT burning target.*?: (\d+)", open(HERE + "/val_trace.txt", encoding="utf-8").read()).group(1))
zc = np.array([e["zc"] for e in upd]); g = np.array([e["gain"][0] for e in upd])
d2 = {"odometry_calls": len(lg), "updates": len(upd), "tracks_with_updates": len({(e["seq"], e["tid"]) for e in upd}), "stale_anchor_updates": len(stale),
      "updates_off_gt_burn": off, "zc_median_px": round(float(np.median(zc)), 1), "zc_max_px": round(float(zc.max()), 1),
      "gain_x_min": round(float(g.min()), 2), "gain_x_max": round(float(g.max()), 2), "gain_x_median": round(float(np.median(g)), 2),
      "median_box_wh": [round(float(np.median([e["w"] for e in upd])), 0), round(float(np.median([e["h"] for e in upd])), 0)]}

# episode facts for the deck captions (from GT)
sys.path.insert(0, ROOT)
from glaremot.eval.eval_recovery import load_mot  # noqa: E402
def ep_facts(seq, tid, f0, f1):
    gt = load_mot(R("datasets", "synth", seq, "mot", "gt", "gt.txt"))
    bx = {f: [r for r in gt[f] if r[0] == tid][0] for f in range(f0, f1 + 1) if f in gt and any(r[0] == tid for r in gt[f])}
    c = {f: np.array([r[1] + r[3] / 2, r[2] + r[4] / 2]) for f, r in bx.items()}
    first = min(c)
    return {"walk_px": round(float(max(np.linalg.norm(c[f] - c[first]) for f in c)), 0), "box_w_start": round(bx[first][3], 0), "box_h_start": round(bx[first][4], 0),
            "box_w_median": round(float(np.median([r[3] for r in bx.values()])), 0), "frames": [f0, f1]}
episode_facts = {"135_19q_g53": ep_facts("135_sequence_19q_new", 53, 409, 451), "187_66q_g247_141": ep_facts("187_sequence_66q_new", 247, 141, 173)}

vn = {"title": "PEG-O: odometry từ vùng cháy sáng", "idea": "Dùng chính vùng bão hòa để đo box đã dời bao xa, không giả định đèn ở đâu trên người.",
      "result": "Val từ chối: không điểm O nào được chấp nhận (T3 Rcv −13.5 đến −41.2). Test (không được chọn bởi val): T3 Rcv@.5 82.2 → 73.6.",
      "mechanism": "Đĩa bão hòa đổi hình khi cháy tăng/giảm nên đỉnh lọc dịch 10–20 px dù người đứng yên; với box rộng 30–40 px là mất IoU.",
      "fixed": "Cải thiện 135_19q g53 (4 → 11/43 frame), 204_81q g300, 316_112q g6.",
      "not_fixed": "Làm tệ 211_88q, 183_62q, 192_70q, 176_56q; trên val tệ ở 187_66q, 203_80q, 210_87q."}

out = {"commits": COMMITS, "commands": COMMANDS, "env_note": "T-b env: " + ENV + "; Thach harness runs use guard ON (his setting)",
       "paper_setting_test": rows, "val_T3": val_t3, "val_search": search, "episodes_summary": ep["summary"], "episodes_changed": changed,
       "estimator_pin": {"plan_19_tau_0.05": PLAN_19, "plan_19_source": "plan-mode feasibility (NOT re-measured here)", "ours": pin},
       "smoke_135": {"old_fusion_tau.06_gamma4_absoluteR": sm_old, "relative_R_tau.06_gamma1": sm_new},
       "val_diagnosis": {"D1_offline_estimator_on_val": vc, "D2": d2}, "episode_facts": episode_facts, "vn": vn}
json.dump(out, open(HERE + "/numbers.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# ---- RESULTS.md (Vietnamese, short; numbers from `out`)
P = rows["PEG (ours reproduction)"]; PP = rows["PEG+"]; PO = rows["PEG-O O[8] tau .08 gamma 4 (not selected by val)"]; PA = rows["paper PEG"]
f = lambda x: "–" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))
f1 = lambda x: "–" if x is None else (f"{x:.1f}" if isinstance(x, (int, float)) else str(x))
md = ["# PEG-O: photometric odometry (kết quả)", "",
      f"Commit: `4b13dc3` (protocol), `bab4795` (code + addendum). Mọi số dưới đây sinh bởi `results/peg_o/collect.py` từ report/ledger (không gõ tay), trừ `PLAN_19` (số của plan).", "",
      "## Ý tưởng", "PEG dùng vùng bão hòa để *quyết định* giữ box (phi >= h). PEG-O dùng cùng vùng đó để *đo* box đã dời bao xa: lọc đĩa (disc matched filter) trên thành phần bão hòa, "
      "đo dịch chuyển của tâm đĩa từ một mốc (anchor) và đưa vào Kalman như pseudo-measurement chỉ cho tâm; chỉ tin khi đỉnh nhọn (độ cong k >= tau). "
      "Kích thước vẫn khóa (PEG+). Fusion cuối: R tương đối = gamma·(tau/k)·P (gain = 1/(1+gamma·tau/k)), cổng nhảy 0.5·đường chéo.", "",
      "## Bảng test, guard tắt (setting của paper), O[8] = tau .08, gamma 4 — *không được val chọn*", "",
      "| | T1 HOTA | DetA | AssA | IDF1 | MOTA | IDSW | FP | FN |", "|---|---|---|---|---|---|---|---|---|"]
for n, r in (("paper PEG", PA), ("PEG", P), ("PEG+", PP), ("PEG-O", PO)):
    t = r["T1"]; md.append(f"| {n} | " + " | ".join(f(t.get(k)) for k in ("HOTA", "DetA", "AssA", "IDF1", "MOTA", "IDSW", "FP", "FN")) + " |")
md += ["", "| | T2 HOTA | MOTA | FP | Rcll | IDF1 | IDSW |", "|---|---|---|---|---|---|---|"]
for n, r in (("paper PEG", PA), ("PEG", P), ("PEG+", PP), ("PEG-O", PO)):
    t = r["T2"]; md.append(f"| {n} | " + " | ".join(f(t.get(k)) for k in ("HOTA", "MOTA", "FP", "Rcll", "IDF1", "IDSW")) + " |")
md += ["", "| | T3 clear | Rcv@.5 | heavy | total | ID-off % | survived |", "|---|---|---|---|---|---|---|"]
for n, r in (("paper PEG", PA), ("PEG", P), ("PEG+", PP), ("PEG-O", PO)):
    t = r["T3"]; md.append(f"| {n} | " + " | ".join(f1(t.get(k)) for k in ("clear", "Rcv@.5", "heavy", "total", "ID_off_pct", "survived")) + " |")
md += ["", f"Val T3 Rcv@.5 (guard tắt): PEG {val_t3['PEG']['Rcv@.5']}, PEG+ {val_t3['PEG+']['Rcv@.5']}, PEG-O {val_t3['PEG-O O[8]']['Rcv@.5']}.", "",
       "## Chọn trên val (Thach harness, guard bật, pre-registered)", "",
       f"Bắt đầu S0+P: val T1 {search['start_S0P_val']['T1_HOTA']} / T2 {search['start_S0P_val']['T2_HOTA']} / T3 {search['start_S0P_val']['T3_Rcv']}.", "",
       "| thêm | tau | gamma | Δ T1 | Δ T2 | Δ T3 | score | admissible |", "|---|---|---|---|---|---|---|---|"]
for r in search["rows"]:
    md.append(f"| {r['add']} | {r['tau'] if r['tau'] is not None else ''} | {r['gamma'] if r['gamma'] is not None else ''} | {r['delta'][0]:+.2f} | {r['delta'][1]:+.2f} | {r['delta'][2]:+.1f} | {r['score']:+.2f} | {'có' if r['admissible'] else 'không'}{' (score <= 0.5: không chọn)' if r['admissible'] and r['score'] <= 0.5 else ''} |")
md += ["", f"Final = `{search['final']}` (không O, không S). `tune_O/test.json` = S0+P test: T1 {search['tune_O_test']['T1']['HOTA']} / T2 {search['tune_O_test']['T2']['HOTA']} / T3 {search['tune_O_test']['T3']['Rcv@.5']}. "
       "S (armed survival) byte-identical với PEG+ trên val (không bao giờ kích hoạt).", "",
       "## Theo episode (T3)", ""]
for s in ("test", "val", "pooled"):
    e = ep["summary"][s]
    md.append(f"- {s}: {e['n_episodes']} ep. — Rcv PEG {e['PEG']} / PEG+ {e['PEG+']} / PEG-O {e['PEG-O']}; PEG-O so với PEG+ Δ {e['PEG-O_vs_PEG+']['delta']:+.1f} "
              f"CI95 [{e['PEG-O_vs_PEG+']['ci95'][0]:+.1f}, {e['PEG-O_vs_PEG+']['ci95'][1]:+.1f}], tốt hơn {e['PEG-O_vs_PEG+']['better']} / tệ hơn {e['PEG-O_vs_PEG+']['worse']} "
              f"(+{e['PEG-O_vs_PEG+']['frames_gained']} / −{e['PEG-O_vs_PEG+']['frames_lost']} frame); so với PEG Δ {e['PEG-O_vs_PEG']['delta']:+.1f} CI95 [{e['PEG-O_vs_PEG']['ci95'][0]:+.1f}, {e['PEG-O_vs_PEG']['ci95'][1]:+.1f}].")
for s in ("test", "val"):
    md += ["", f"Episode khác PEG+ ({s}): seq g<id> frames: covered PEG+ → PEG-O (n) | sai số tâm px PEG+ → PEG-O", ""]
    for e in changed[s]:
        md.append(f"- {e['seq']} g{e['tid']} {e['start']}-{e['end']}: {e['PEG+']} → {e['PEG-O']} ({e['n']}) | {e['cerr_PEG+']} → {e['cerr_PEG-O']}")
md += ["", "## Estimator pin (scripts/19_peg_o_check.py, tau .05, sai số tâm trung bình, px)", "", "| episode | frozen (PEG+) | MF-odo (ours) | plan (nhập tay từ plan) |", "|---|---|---|---|"]
for k, v in pin["0.05"].items():
    md.append(f"| {k} | {v['frozen']} | {v['odo']} | {PLAN_19[k]} |")
md += ["", "tau .06 / .08 (MF-odo): " + "; ".join(f"{k}: {pin['0.06'][k]['odo']} / {pin['0.08'][k]['odo']}" for k in pin["0.06"]), "",
       "## Smoke 135_19q g53 409–451 (test, một sequence)", "",
       f"- PEG+ {sm_new['plus']}/{sm_new['n']}, sai số tâm {sm_new['cerr_plus'][0]} px (max {sm_new['cerr_plus'][1]}).",
       f"- Fusion cũ (R tuyệt đối, tau .06 gamma 4): {sm_old['peg_o']}/{sm_old['n']}, {sm_old['cerr_peg_o'][0]} px — gain ≈ 0.01, không làm gì.",
       f"- Fusion R tương đối (tau .06 gamma 1): {sm_new['peg_o']}/{sm_new['n']}, {sm_new['cerr_peg_o'][0]} px (max {sm_new['cerr_peg_o'][1]}); cận trên oracle (box PEG+ căn đúng tâm GT) {sm_new['oracle']}/{sm_new['n']}.",
       f"- Episode 815–834 giữ {sm_new['ep815']['peg_o']}/{sm_new['ep815']['n']}.", "",
       "## Vì sao val thất bại", "",
       "D1 — estimator offline (anchor = GT, thay trực tiếp) trên các episode val bị mất >= 5 frame với O[8]: sai số tâm trung bình (px)", "",
       "| episode | box | frozen | MF-odo tau .06 | MF-odo tau .08 |", "|---|---|---|---|---|"]
byep = {}
for r in vc: byep.setdefault(r["episode"], {})[r["tau"]] = r
for k, v in byep.items():
    md.append(f"| {k.replace('|', ' g', 1).replace('|', ' f')} | {v[0.06]['box']} | {v[0.06]['frozen']} | {v[0.06]['odo']} | {v[0.08]['odo']} |")
md += ["", f"D2 — tracker O[4] trên val: {d2['updates']} update ({d2['tracks_with_updates']} track), median |z−c| {d2['zc_median_px']} px (max {d2['zc_max_px']}), gain {d2['gain_x_min']}–{d2['gain_x_max']}, "
       f"anchor cũ (stale) {d2['stale_anchor_updates']}, update ngoài vùng GT cháy nặng {d2['updates_off_gt_burn']}; box median {d2['median_box_wh'][0]:.0f}×{d2['median_box_wh'][1]:.0f} px.", "",
       "Cơ chế: đĩa bão hòa đổi hình khi độ cháy tăng/giảm (và dính hàng xóm/tường), nên đỉnh lọc dịch 10–20 px dù người gần như đứng yên; anchor lấy đúng lúc đang tăng; gain ≈ 0.6 mỗi update và vận tốc bị bơm vào Kalman nên box tiếp tục trôi. "
       "Với box rộng 28–41 px sai số đó làm mất IoU .5; với 135_19q (box 264 px, người đi 108 px) thì không đáng kể.", "",
       "## Lệnh", ""]
for k, v in COMMANDS.items():
    md.append(f"- {k}: `{v}`")
md.append("")
open(HERE + "/RESULTS.md", "w", encoding="utf-8").write("\n".join(md))
print("keys:", list(out)); print("wrote numbers.json, RESULTS.md")
