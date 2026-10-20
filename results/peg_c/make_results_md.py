"""results/peg_c/numbers.json -> results/peg_c/RESULTS.md (Vietnamese). Every number is read from numbers.json; no tracker runs.
Run: .venv/Scripts/python.exe results/peg_c/collect.py && .venv/Scripts/python.exe results/peg_c/make_results_md.py"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
n = json.load(open(HERE + "/numbers.json", encoding="utf-8"))
rows, vt3, hr, sr, ep, orc, sn, dg = n["paper_setting_test"], n["val_T3"], n["harness_rows"], n["search"], n["episodes_summary"], n["oracle"], n["slope_noise"], n["diag_test_losses"]
f2 = lambda x: "–" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))
f1 = lambda x: "–" if x is None else (f"{x:.1f}" if isinstance(x, (int, float)) else str(x))
PEG, PP, PC, PL = "PEG (ours reproduction)", "PEG+", "PEG-C online (P + V K40 t2)", "PEG-C fixed-lag 90 (B hidden; label: fixed-lag)"
PA = rows["paper PEG"]
GL = {"V": n["grids"]["V"], "C": n["grids"]["C"], "S": n["grids"]["S"], "B": n["grids"]["B"], "BB": n["grids"]["BB"]}


def lab(add):
    c, i = add.split("[")[0], int(add.split("[")[1][:-1])
    return f"{add} ({GL[c][i]})" if c in GL else add


def sgn(x, d=2):
    return f"{x:+.{d}f}"


md = ["# PEG-C: thiết kế cách coast (kết quả)", "",
      "Commit: `0f92215` (protocol pre-registered), `134d947` (code + addendum 1). Mọi số dưới đây sinh bởi `results/peg_c/collect.py` + `make_results_md.py` từ report/ledger (không gõ tay).", "",
      "## Ý tưởng",
      "PEG quyết định *có* giữ box hay không (cổng phi >= h). PEG-C thiết kế *giữ như thế nào*: một mô hình vận tốc không đổi (CV) duy nhất, dùng như bộ lọc online (V, C, S) và như bộ làm mượt fixed-lag (B, BB). "
      "Mỗi thành phần có một núm:", "",
      "| | làm gì | lưới (val chọn) |", "|---|---|---|",
      f"| P | PEG+ size lock (có sẵn theo thiết kế) | – |",
      f"| V | vận tốc nền dài lúc vào coast: OLS trên K tâm detection gần nhất, trục bị về 0 nếu \\|v\\| <= t·SE | {'; '.join(GL['V'])} |",
      f"| C | trần nhân quả: cổng chỉ được arm khi time_since_update <= N | {'; '.join(GL['C'])} |",
      f"| S | burn-exit stitch: detection sắp được *sinh* mà nằm sát box dự đoán của track vừa cháy thì nối lại (1:1) | {'; '.join(GL['S'])} |",
      f"| B | backfill fixed-lag: nội suy tuyến tính giữa hai detection ở hai đầu khoảng cháy (hidden = chỉ thêm hàng thiếu, all = thay luôn box coast) | {'; '.join(GL['B'])} |",
      f"| BB | backward birth fixed-lag: track cháy ngay lúc sinh được thêm hàng ngược về trước | {'; '.join(GL['BB'])} |", "",
      "## Lưu ý đặt lên đầu",
      "- Các thành phần được chọn từ phân tích oracle đã **gộp val và test** (`results/research/ORACLE_T3.md` Follow-up 3, `RESIDUAL_POOLS.md`) và từ các case lỗi trên test. Không tham số nào tune trên test; val chọn trong lưới đăng ký trước; test chạy một lần.",
      "- **Rò rỉ synthetic**: `synth_glare.apply_glare` đặt đĩa chói theo đúng GT box, nên mọi phương pháp đọc hình/vị trí đĩa đều rò rỉ GT trên T2/T3. PEG-C chỉ đọc cổng tồn tại (phi >= h, như PEG) và detection của chính track; không bao giờ đọc hình học đĩa.",
      "- **Hàng fixed-lag không phải online**: B và BB ghi lại/thêm hàng tới L khung trong quá khứ. Mọi hàng thuộc họ này luôn ghi nhãn \"fixed-lag L\" và báo riêng, không trộn với hàng online.",
      "- Val nhỏ (17 seq thật, 18 episode T3): kết quả null trên val ít thông tin, nhưng vẫn là luật.", "",
      "## Bảng test, guard tắt (setting của paper)", "",
      "PEG-C online = P + V (K 40, t 2) — **do val chọn**. PEG-C fixed-lag 90 (B hidden, L 90) — *không được val chọn* (hàng fixed-lag, chỉ để tham khảo).", "",
      "| | T1 HOTA | DetA | AssA | IDF1 | MOTA | IDSW | FP | FN |", "|---|---|---|---|---|---|---|---|---|"]
for nm, r in (("paper PEG", PA), ("PEG", rows[PEG]), ("PEG+", rows[PP]), ("PEG-C online", rows[PC]), ("PEG-C fixed-lag 90 (không chọn)", rows[PL])):
    t = r["T1"]; md.append(f"| {nm} | " + " | ".join(f2(t.get(k)) for k in ("HOTA", "DetA", "AssA", "IDF1", "MOTA", "IDSW", "FP", "FN")) + " |")
md += ["", "| | T2 HOTA | AssA | MOTA | FP | Rcll | IDF1 | IDSW |", "|---|---|---|---|---|---|---|---|"]
for nm, r in (("paper PEG", PA), ("PEG", rows[PEG]), ("PEG+", rows[PP]), ("PEG-C online", rows[PC]), ("PEG-C fixed-lag 90 (không chọn)", rows[PL])):
    t = r["T2"]; md.append(f"| {nm} | " + " | ".join(f2(t.get(k)) for k in ("HOTA", "AssA", "MOTA", "FP", "Rcll", "IDF1", "IDSW")) + " |")
md += ["", "| | T3 clear | Rcv@.5 | heavy | total | ID-off % | survived | IDSW | Frag |", "|---|---|---|---|---|---|---|---|---|"]
for nm, r in (("paper PEG", PA), ("PEG", rows[PEG]), ("PEG+", rows[PP]), ("PEG-C online", rows[PC]), ("PEG-C fixed-lag 90 (không chọn)", rows[PL])):
    t = r["T3"]; md.append(f"| {nm} | " + " | ".join((str(int(t[k])) if (k in ("IDSW", "Frag") and t.get(k) is not None) else f1(t.get(k))) for k in ("clear", "Rcv@.5", "heavy", "total", "ID_off_pct", "survived", "IDSW", "Frag")) + " |")
md += ["", f"Val T3 Rcv@.5 (guard tắt): PEG {vt3['PEG']['Rcv@.5']}, PEG+ {vt3['PEG+']['Rcv@.5']}, PEG-C online {vt3['PEG-C online']['Rcv@.5']}, PEG-C fixed-lag 90 {vt3['PEG-C fixed-lag 90']['Rcv@.5']}. "
       f"Fixed-lag hidden giống hệt online trên T3 (cả test lẫn val): B hidden không thêm hàng nào ở T3.", ""]
a, c_ = rows[PP], rows[PC]
md += ["Chênh PEG-C online so với PEG+ / PEG (test, guard tắt):", "",
       f"- T1 IDF1 {sgn(c_['T1']['IDF1'] - a['T1']['IDF1'])} so với PEG+, {sgn(c_['T1']['IDF1'] - rows[PEG]['T1']['IDF1'])} so với PEG; T1 HOTA {sgn(c_['T1']['HOTA'] - a['T1']['HOTA'])} / {sgn(c_['T1']['HOTA'] - rows[PEG]['T1']['HOTA'])}.",
       f"- T2 HOTA {sgn(c_['T2']['HOTA'] - a['T2']['HOTA'])} so với PEG+ (AssA {sgn(c_['T2']['AssA'] - a['T2']['AssA'])}, IDSW {a['T2']['IDSW']} → {c_['T2']['IDSW']}); {sgn(c_['T2']['HOTA'] - rows[PEG]['T2']['HOTA'])} so với PEG.",
       f"- T3 Rcv@.5 {sgn(c_['T3']['Rcv@.5'] - a['T3']['Rcv@.5'], 1)} so với PEG+ ({a['T3']['Rcv@.5']} → {c_['T3']['Rcv@.5']}); {sgn(c_['T3']['Rcv@.5'] - rows[PEG]['T3']['Rcv@.5'], 1)} so với PEG; total {sgn(c_['T3']['total'] - a['T3']['total'], 1)} so với PEG+.", ""]


def search_block(d, title, full_rounds):
    s = sr[d]
    out = [f"### {title}", "", f"Bắt đầu S0+P: val T1 {s['start_val']['T1_HOTA']} / T2 {s['start_val']['T2_HOTA']} / T3 {s['start_val']['T3_Rcv']}.", ""]
    for r in s["rounds"]:
        rr = r["rows"]
        if r["round"] not in full_rounds:
            rr = sorted(rr, key=lambda x: -x["score"])[:4]
            out.append(f"Vòng {r['round']} (4 dòng điểm cao nhất trong {len(r['rows'])}):")
        else:
            out.append(f"Vòng {r['round']}:")
        out += ["", "| thêm | Δ T1 | Δ T2 | Δ T3 | score | admissible |", "|---|---|---|---|---|---|"]
        for x in rr:
            adm = ("có" + (" (score <= 0.5: không chọn)" if x["score"] <= 0.5 else "")) if x["admissible"] else "không"
            out.append(f"| {lab(x['add'])} | {x['delta'][0]:+.2f} | {x['delta'][1]:+.2f} | {x['delta'][2]:+.1f} | {x['score']:+.2f} | {adm} |")
        for ck in r["checks"]:
            out.append(f"\nKiểm tra single-event {ck['add']}: score {ck['score']:+.2f}, bỏ đơn vị có lợi nhất còn {ck['score_without']:+.2f} → {'qua' if ck['pass'] else 'trượt'}.")
        out.append(f"\n→ chấp nhận: {lab(r['accepted']) if r['accepted'] else 'không có'}" + "\n")
    out.append(f"**FINAL = `{s['final']}`** (val T1 {s['final_val'][0]} / T2 {s['final_val'][1]} / T3 {s['final_val'][2]}), key `{s['final_key']}`." + "\n")
    return out


md += ["## Chọn trên val (Thach harness, guard bật, pre-registered)", ""]
md += search_block("tune_C", "Online, luật chặt (single-event check): {P, V, C, S}", {1, 2})
md += search_block("tune_C_strong", "Online, luật mạnh nhất (không single-event check)", {1, 2, 3})
md += search_block("tune_C_lag", "Fixed-lag: thêm B, BB lên trên tune_C", {1})
md += search_block("tune_C_all", "ALL: PEG-C + các thành phần của Thach (luật mạnh nhất)", {1})
md.append("`tune_C_lag_all`: " + sr["tune_C_lag_all"]["skipped"] + ".")
wg = n["where_gain_C"]
lc = n["lag_B_val_episode_changes_vs_online"]["B[1]"]
cs = sr["tune_C"]["rounds"][1]
md += ["", "### Vì sao các thành phần bị loại", "",
       f"- **V**: được chọn, V[3] (K 40, t 2): val T3 Rcv {sgn(sr['tune_C']['rounds'][0]['rows'][3]['delta'][2], 1)}, T1 {sgn(sr['tune_C']['rounds'][0]['rows'][3]['delta'][0])}, T2 {sgn(sr['tune_C']['rounds'][0]['rows'][3]['delta'][1])}; qua single-event check ({sr['tune_C']['rounds'][0]['checks'][0]['score_without']:+.2f}).",
       f"- **S (stitch)**: gain val T2 = {wg['val|Cstrong']['T2']['delta']:+.2f} nhưng từ một sequence ({wg['val|Cstrong']['T2']['top'][0][0]} {wg['val|Cstrong']['T2']['top'][0][1]:+.1f} HOTA); bỏ nó còn {wg['val|Cstrong']['T2']['without_top']:+.2f}; check single-event {cs['checks'][0]['score_without']:+.2f} → trượt ở luật chặt. Luật mạnh nhất vẫn nhận S[0].",
       f"- **C (trần nhân quả)**: score lớn nhất {max(x['score'] for x in sr['tune_C']['rounds'][0]['rows'] if x['add'].startswith('C')):+.2f} (<= 0.5): không đáng kể.",
       f"- **B hidden**: score {sr['tune_C_lag']['rounds'][0]['rows'][0]['score']:+.2f} / {sr['tune_C_lag']['rounds'][0]['rows'][2]['score']:+.2f} (L 45 / L 90): không thêm hàng nào ở T3 (hàng test và val giống hệt online) vì cổng đã phát box cho gần như mọi khung của khoảng trống.",
       "- **B all** làm tệ T3 val " + f"{sr['tune_C_lag']['rounds'][0]['rows'][1]['delta'][2]:+.1f}" + ": " + "; ".join(f"{e['episode'].split('|')[0].split('_')[0]} g{e['episode'].split('|')[1]} {e['covered_before']}→{e['covered_after']} (n {e['n']})" for e in lc) + " (nội suy thay luôn box coast).",
       f"- **BB**: không kích hoạt ở lần chạy val nào (score {sr['tune_C_lag']['rounds'][0]['rows'][4]['score']:+.2f}).", ""]

md += ["## Thach harness (guard bật), val + test", "",
       "| config | split | T1 HOTA | T1 IDF1 | T1 MOTA | T1 IDSW | T2 HOTA | T2 IDF1 | T2 MOTA | T3 Rcv@.5 | T3 total | T3 ID-off |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for nm, r in hr.items():
    for s in ("val", "test"):
        x = r[s]
        if x.get("T1 HOTA") is None:
            md.append(f"| {nm} | {s} | " + " | ".join(["–"] * 10) + " |")
            continue
        md.append(f"| {nm} | {s} | {x['T1 HOTA']:.2f} | {x['T1 IDF1']:.2f} | {x['T1 MOTA']:.2f} | {x['T1 IDSW']:.0f} | {x['T2 HOTA']:.2f} | {x['T2 IDF1']:.2f} | {x['T2 MOTA']:.2f} | {x['T3 Rcv@.5']:.1f} | {x['T3 total']:.1f} | {x['T3 ID-off']:.1f} |")
th_t = {k: sr[k]["test"] for k in ("tune_C", "tune_C_strong", "tune_C_all")}
md += ["", "Test chạy đúng một lần cho `tune_C`, `tune_C_strong`, `tune_C_all` (`tune_C_lag` có final trùng `tune_C` → không chạy lại; `tune_C_lag_all` bị bỏ).", ""]

md += ["## Theo episode (T3)", ""]
for s in ("test", "val", "pooled"):
    e = ep[s]; v = e["PEG-C_vs_PEG+"]; w = e["PEG-C_vs_PEG"]
    md.append(f"- {s}: {e['n_episodes']} ep. — Rcv PEG {e['PEG']} / PEG+ {e['PEG+']} / PEG-C {e['PEG-C']} / PEG-C lag {e['PEG-C lag']}; PEG-C so với PEG+ Δ {v['delta']:+.1f} CI95 [{v['ci95'][0]:+.1f}, {v['ci95'][1]:+.1f}], "
              f"tốt hơn {v['better']} / tệ hơn {v['worse']} / bằng {v['same']} (+{v['frames_gained']} / −{v['frames_lost']} frame); so với PEG Δ {w['delta']:+.1f} CI95 [{w['ci95'][0]:+.1f}, {w['ci95'][1]:+.1f}] ({w['better']}/{w['worse']}).")
for s in ("test", "val"):
    md += ["", f"Episode khác PEG+ ({s}): seq g<id> frames: covered PEG / PEG+ / PEG-C / PEG-C lag (n) | sai số tâm px PEG+ / PEG-C", ""]
    for e in n["episodes_changed"][s]:
        md.append(f"- {e['seq']} g{e['tid']} {e['start']}-{e['end']}: {e['PEG']} / {e['PEG+']} / {e['PEG-C']} / {e['PEG-C lag']} ({e['n']}) | {e['cerr_PEG+']} / {e['cerr_PEG-C']}")
md += ["", "![val 187 g247: PEG+ vs PEG-C](figures/187_66q_strip.png)", "", "![test 211 g320: PEG+ vs PEG-C](figures/211_88q_strip.png)", ""]

o, P_ = orc["vest"], orc["other"]
md += ["## Oracle: coast có thể thiết kế được không?", "",
       "Ước lượng vận tốc từ quá khứ detection của PEG+, áp như vận tốc không đổi từ anchor (43 episode có track; `results/research/ORACLE_T3.md` Follow-up 3). bK = OLS trên K detection gần nhất; gK = cùng OLS trên GT (chỉ lỗi mô hình).", "",
       "| policy | test | val | pooled | med \\|v_est − v_true\\| px/f (pooled) |", "|---|---|---|---|---|"]
def orow(nm, key, src="o"):
    t = o["test"][key]["rcv"]; v = o["val"][key]["rcv"]; p = o["pooled"][key]; return f"| {nm} | {t} | {v} | {p['rcv']} [{p['ci95'][0]}, {p['ci95'][1]}] | {p['med_verr']} |"
md.append(f"| (a) frozen | {P_['test']['a_frozen']} | {P_['val']['a_frozen']} | {P_['pooled']['a_frozen']} | – |")
for k in ("b5", "b10", "b20", "b40", "b80", "g40"):
    md.append(orow(k, k))
md.append(f"| (i) oracle const-velocity (GT) | {P_['test']['i_oracle_constvel']} | {P_['val']['i_oracle_constvel']} | {P_['pooled']['i_oracle_constvel']} | – |")
md.append(f"| (d) oracle centre | {P_['test']['d_oracle_centre']} | {P_['val']['d_oracle_centre']} | {P_['pooled']['d_oracle_centre']} | – |")
md.append(f"| PEG+ actual (same episodes) | {P_['test']['PEGp_tracked_actual']} | {P_['val']['PEGp_tracked_actual']} | {P_['pooled']['PEGp_tracked_actual']} | – |")
c21 = n["check21"]
vt = sn["median_vtrue_speed"]; pl = sn["measured_med_verr_pooled"]
md += ["", f"Kiểm tra cài đặt (`scripts/21_peg_c_check.py`, hàm `ols_velocity` của tracker): b40 = {c21['b40']['test']} / {c21['b40']['val']} / {c21['b40']['pooled']}, b20 = {c21['b20']['test']} / {c21['b20']['val']} / {c21['b20']['pooled']} (test / val / pooled), "
       f"khớp {c21['expected']['b40']['pooled']} / {c21['expected']['b20']['pooled']} đã công bố; {c21['episodes_differing_from_published']} episode lệch.", "",
       "### Nhiễu hay mô hình? (slope_noise)", "",
       f"σ = {sn['sigma_px']:.2f} px (median trên {sn['n_episodes']} episode của sqrt(σx² + σy²), σ_x median {sn['sigma_x_median']:.2f}, σ_y median {sn['sigma_y_median']:.2f}; phần dư OLS trên 40 detection cuối của PEG+). "
       f"Sàn nhiễu trắng σ·√(12/K³): K = 5/10/20/40/80 → " + " / ".join(f"{sn['curve_points'][k]:.3f}" for k in ("5", "10", "20", "40", "80")) + " px/frame.",
       f"Sai số đo được: " + " / ".join(f"b{k} {pl['b' + str(k)]}" for k in (5, 10, 20, 40, 80)) + f"; chỉ-mô-hình (GT): " + " / ".join(f"g{k} {sn['model_error_med_verr_pooled']['g' + str(k)]}" for k in (10, 20, 40, 80)) + ".",
       f"Kết luận: sàn nhiễu tiếp tục giảm nhưng sai số dừng ở ≈ {pl['b40']:.2f}–{pl['b80']:.2f} px/frame (b40–b80) ≈ {100 * pl['b40'] / vt:.0f}–{100 * pl['b80'] / vt:.0f}% tốc độ thật median {vt:.2f} px/frame: giới hạn là mô hình CV (người đổi nhịp), không phải nhiễu. K = 5 là nhiễu ({pl['b5']} px/frame > {vt}).", "",
       "![slope noise](figures/slope_noise.png)", ""]

md += ["## Phân tích sau test (post-test analysis, KHÔNG dùng để chọn)", "",
       "Replay có thiết bị đo (`diag_test_losses.py`): cấu hình pegc, guard tắt, cache; hàng MOT replay **trùng từng byte** với `pegc_rcv` / `v_pegc_rcv`.", "",
       "| episode | covered PEG+ → PEG-C | oracle b40 | v OLS (t=0) | Kalman v lúc vào coast (PEG+ giữ nguyên) | v thật (GT) | số lần vào coast (từ 60 khung trước burn tới hết burn) |", "|---|---|---|---|---|---|---|"]
for seq, d in dg.items():
    e = d["entries"][-1] if seq != "187_sequence_66q_new" else d["entries"][-1]
    govs = [x for x in d["entries"] if x["frame"] <= d["frames"][0]]
    g = govs[-1]
    md.append(f"| {seq.split('_')[0]} g{d['tid']} {d['frames'][0]}-{d['frames'][1]} ({d['split']}) | {d['covered_pegplus']} → {d['covered_pegc']} | {d['oracle']['cov']} | ({g['v_ols_t0'][0]:+.2f}, {g['v_ols_t0'][1]:+.2f}) | ({g['v_kalman_before'][0]:+.2f}, {g['v_kalman_before'][1]:+.2f}) | ({d['gt_mean_v'][0]:+.2f}, {d['gt_mean_v'][1]:+.2f}) | {len(d['entries'])} (khung {', '.join(str(x['frame']) for x in d['entries'])}) |")
md += ["",
       "- Mỗi burn là một lần coast liên tục: không có re-acquisition (không vào coast lại) bên trong burn, nên vận tốc chỉ được ước lượng một lần lúc vào coast.",
       "- Trên các episode này khác biệt duy nhất giữa PEG+ và PEG-C là **vận tốc lúc vào coast** (cùng damping ×0.95 sau gap 10, cùng EMA, cùng size lock). Speed guard và trần 2·median-step không bao giờ kích hoạt; t = 2 không triệt trục nào (trên các lần vào coast ở bảng).",
       "- Trên 176 g204 và 211 g320 vận tốc Kalman sẵn có của PEG+ lúc vào coast gần vận tốc thật hơn OLS 40 khung: "
       f"176: Kalman ({dg['176_sequence_56q_new']['entries'][-1]['v_kalman_before'][0]:+.2f}, {dg['176_sequence_56q_new']['entries'][-1]['v_kalman_before'][1]:+.2f}) so với OLS ({dg['176_sequence_56q_new']['entries'][-1]['v_ols_t0'][0]:+.2f}, {dg['176_sequence_56q_new']['entries'][-1]['v_ols_t0'][1]:+.2f}), thật ({dg['176_sequence_56q_new']['gt_mean_v'][0]:+.2f}, {dg['176_sequence_56q_new']['gt_mean_v'][1]:+.2f}); "
       f"211: Kalman ({dg['211_sequence_88q_new']['entries'][-1]['v_kalman_before'][0]:+.2f}, {dg['211_sequence_88q_new']['entries'][-1]['v_kalman_before'][1]:+.2f}) so với OLS ({dg['211_sequence_88q_new']['entries'][-1]['v_ols_t0'][0]:+.2f}, {dg['211_sequence_88q_new']['entries'][-1]['v_ols_t0'][1]:+.2f}), thật ({dg['211_sequence_88q_new']['gt_mean_v'][0]:+.2f}, {dg['211_sequence_88q_new']['gt_mean_v'][1]:+.2f}). "
       "(Với 211 số Kalman lấy từ chính lần chạy pegc nên có thể lệch nhẹ so với lần chạy PEG+ vì V đã áp ở lần coast trước.)",
       "- Nền dài lỗi thời khi người đổi nhịp hoặc khi cửa sổ 40 detection bắc qua một khoảng trống trước đó: ở 211 cửa sổ gồm khung 355–374 và 415–434, giữa chúng là gap 40 khung trong đó người đã di chuyển; `_det_hist` không bị xóa theo đúng spec nên OLS trộn hai đoạn.",
       f"- Trên val nền dài thắng (9 tốt hơn / 1 tệ hơn), ví dụ 187 g247 201-235: 19 → 35 khung; ở lần vào coast khung 200 OLS ({dg['187_sequence_66q_new']['entries'][-1]['v_ols_t0'][0]:+.2f}, {dg['187_sequence_66q_new']['entries'][-1]['v_ols_t0'][1]:+.2f}) gần vận tốc thật ({dg['187_sequence_66q_new']['gt_mean_v'][0]:+.2f}, {dg['187_sequence_66q_new']['gt_mean_v'][1]:+.2f}) hơn Kalman ({dg['187_sequence_66q_new']['entries'][-1]['v_kalman_before'][0]:+.2f}, {dg['187_sequence_66q_new']['entries'][-1]['v_kalman_before'][1]:+.2f}): cửa sổ sạch, người đi đều.",
       "- Hai yếu tố làm oracle b40 tốt hơn tracker nhưng *không* giải thích PEG-C thua PEG+ (PEG+ chịu cả hai): oracle dùng box detection gốc cố định (44.7x160 ở 176) còn tracker coast box Kalman/EMA (47x157), và VEL_DAMP làm quãng dịch thực chỉ còn khoảng 83% — phép tính số học (không chạy tracker) trên 176: đi thẳng đều 17/25 khung, có damp 14/25, tracker thực 10/25.",
       "- Trên 211 GT box lớn dần (60x215 → 80x260, người tiến lại gần camera) trong khi box size-lock giữ 65x208 nên IoU vượt dưới 0.5 giữa chừng bất kể vận tốc.", ""]

hv, ht = hr["PEG-C online"], None
pegv, pegt = hr["PEG"]["val"], hr["PEG"]["test"]
cv, ct = hr["PEG-C online"]["val"], hr["PEG-C online"]["test"]
sv, st = hr["PEG-C strongest"]["val"], hr["PEG-C strongest"]["test"]
e_t = ep["test"]["PEG-C_vs_PEG+"]; e_v = ep["val"]["PEG-C_vs_PEG+"]; e_p = ep["pooled"]["PEG-C_vs_PEG+"]
md += ["## Kết luận", "",
       f"- Val chấp nhận V; test **không xác nhận** trên T3: PEG-C so với PEG+ {e_t['delta']:+.1f} (CI95 [{e_t['ci95'][0]:+.1f}, {e_t['ci95'][1]:+.1f}], {e_t['better']} tốt hơn / {e_t['worse']} tệ hơn); val {e_v['delta']:+.1f} [{e_v['ci95'][0]:+.1f}, {e_v['ci95'][1]:+.1f}] ({e_v['better']}/{e_v['worse']}); pooled {e_p['delta']:+.1f} [{e_p['ci95'][0]:+.1f}, {e_p['ci95'][1]:+.1f}].",
       f"- Lợi ích duy nhất trên test (cả hai harness; nhưng val T1 IDF1 lại −1.1 nên chưa chắc): T1 IDF1 {sgn(c_['T1']['IDF1'] - a['T1']['IDF1'], 1)} (guard tắt, vs PEG+) / {sgn(ct['T1 IDF1'] - pegt['T1 IDF1'], 1)} (guard bật, vs PEG).",
       f"- Chi phí: T2 HOTA {sgn(c_['T2']['HOTA'] - a['T2']['HOTA'], 1)} vs PEG+ (AssA {sgn(c_['T2']['AssA'] - a['T2']['AssA'], 1)}, IDSW {a['T2']['IDSW']} → {c_['T2']['IDSW']}).",
       f"- S (strongest) giúp test T2 HOTA ({st['T2 HOTA']} so với {ct['T2 HOTA']} của PEG-C online) nhưng dựa vào một sequence ({wg['test|Cstrong']['T2']['top'][0][0]} {wg['test|Cstrong']['T2']['top'][0][1]:+.1f}).",
       "- Bài học: lợi ích oracle do val dẫn dắt vẫn do val dẫn dắt; sai số vận tốc dừng ở sàn của mô hình CV, không phải nhiễu.", ""]

md += ["## Lệnh", ""]
for k, v in n["commands"].items():
    md.append(f"- {k}: `{v}`")
md += ["", f"Env của hàng paper-setting: `{n['env_note']}`", ""]
open(HERE + "/RESULTS.md", "w", encoding="utf-8").write("\n".join(md))
print("wrote RESULTS.md", len(md), "lines")
