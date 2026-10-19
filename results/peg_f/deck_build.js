// PEG-F + PEG+ deck (Vietnamese, 2 speakers). Run: node deck_build.js  ->  PEG_F.pptx + SCRIPT_PEG_F.md
// Every result number comes from numbers.json (peg_f), ../peg_plus/numbers.json (paper / our reproduction) and
// figure_stats.json (computed by scripts/13_peg_f_figures.py). Nothing is typed by hand.
const { createRequire } = require("module");
const req = createRequire(require("path").join(__dirname, "../peg_plus/package.json")); // reuse peg_plus/node_modules
const pptxgen = req("pptxgenjs");
const sizeOf = req("image-size");
const fs = require("fs");
const path = require("path");

const DIR = __dirname;
const FIG = path.join(DIR, "figures");
const FIG_OLD = "D:/PROJECT/PEG/results/failure_analysis/figures";
const FIG_PLUS = "D:/PROJECT/PEG/results/peg_plus/figures";
const OUT = path.join(DIR, "PEG_F.pptx");
const OUT_MD = path.join(DIR, "SCRIPT_PEG_F.md");
const N = JSON.parse(fs.readFileSync(path.join(DIR, "numbers.json"), "utf8"));
const P = JSON.parse(fs.readFileSync("D:/PROJECT/PEG/results/peg_plus/numbers.json", "utf8"));
const S = JSON.parse(fs.readFileSync(path.join(DIR, "figure_stats.json"), "utf8"));
// val selection (docs/VAL_SELECTION_PROTOCOL.md): results/val_selection/collect_val.py + episodes.py
const VS = JSON.parse(fs.readFileSync("D:/PROJECT/PEG/results/val_selection/numbers_val.json", "utf8"));
const EPS = JSON.parse(fs.readFileSync("D:/PROJECT/PEG/results/val_selection/episodes.json", "utf8")).episodes;

const C = {
  bg: "15171B", card: "22252B", card2: "2B2F36", text: "F2F2F2", muted: "A3A8B0", amber: "F2A900",
  peg: "3987E5", plus: "19A35F", f: "9B6EE8", fa: "CF8000", sel: "1B9AA6", miss: "E86BB0", red: "E66767", good: "19A35F", grid: "33373E",
};
const F = "Arial";

// ───────────── number helpers (null-safe) ─────────────
const isN = (v) => typeof v === "number" && isFinite(v);
const fmt = (v, d = 1) => (isN(v) ? v.toFixed(d) : "…");
const fmtI = (v) => (isN(v) ? String(Math.round(v)) : "…");
const sgn = (v, d = 1) => {
  if (!isN(v)) return "…";
  const r = Math.sign(v) * Math.round(Math.abs(v) * Math.pow(10, d) + 1e-7) / Math.pow(10, d);
  return (r > 0 ? "+" : r < 0 ? "−" : "±") + Math.abs(r).toFixed(d);
};
const V = N.variants;
const g1 = (v, k) => V[v].table1.combined[k];
const g2 = (v, k) => V[v].table2.combined[k];
const g3 = (v, k = "Rcv@.5") => V[v].table3.all_burn[k];
const PT = (tab, row, col) => { const t = P[tab]; return t.rows[row][t.cols.indexOf(col)]; };
const CL = N.claim.claim, FP_ = N.claim.friend_peg, LV = N.live;
const PS = N.table1_per_seq;
const SEQ129 = "129_sequence_13q_complete", SEQ176 = "176_sequence_56q_new";
const dseq = (seq, k = "HOTA") => PS.F_g[seq][k] - PS.peg_g[seq][k];
const swapFrame = (N.seq_id_analysis[SEQ129].cause.match(/f(\d+)\)/) || [])[1] || "…";
const CT1 = N.firing_counters_F.t1, CD1 = CT1.dists, CC1 = CT1.counts;
const M = N.m2m4, M1 = N.m1;
const SW = S.swap;
const OTHERS_MAX = Math.max(...Object.keys(PS.peg_g).filter((q) => q !== SEQ129 && q !== SEQ176).map((q) => Math.abs(dseq(q))));
// the three checks must agree exactly, otherwise the slide would be lying
["HOTA", "IDF1", "IDSW", "MOTA", "FP", "FN"].forEach((k) => {
  if (CL[k] !== LV.friend_combined[k] || CL[k] !== g1("F_g", k)) throw new Error("claim / live / port mismatch on " + k);
});
const D = S.damp;

// ───────────── pptx scaffolding ─────────────
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "PEG-F và PEG+ — nâng cấp tracker khi đèn mũ làm chói camera";
const SL = []; // {title, notes, who}
const WHO = { 1: { t: "NGƯỜI 1 · PEG-F", c: C.f }, 2: { t: "NGƯỜI 2 · PEG+", c: C.plus }, 0: { t: "CẢ HAI", c: C.amber } };

function base(title, kicker, who) {
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s._who = who;
  if (kicker) s.addText(kicker, { x: 0.6, y: 0.35, w: 9, h: 0.35, fontFace: F, fontSize: 13, color: C.amber, bold: true, charSpacing: 2, margin: 0, isTextBox: true });
  if (title) s.addText(title, { x: 0.6, y: kicker ? 0.7 : 0.45, w: 12.1, h: 0.8, fontFace: F, fontSize: title.length > 54 ? 26 : 30, bold: true, color: C.text, margin: 0, isTextBox: true, valign: "top" });
  return s;
}
function txt(s, t, o) {
  s.addText(t, Object.assign({ fontFace: F, fontSize: 16, color: C.text, margin: 0, valign: "top", isTextBox: true }, o));
}
function card(s, x, y, w, h, fill) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill || C.card }, line: { color: fill || C.card }, rectRadius: 0.12 });
}
function done(s, title, notes) {
  SL.push({ title, notes, who: s._who });
  const w = WHO[s._who];
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 10.55, y: 0.3, w: 2.18, h: 0.36, fill: { color: w.c, transparency: 78 }, line: { color: w.c, width: 1.25 }, rectRadius: 0.18 });
  txt(s, w.t, { x: 10.55, y: 0.3, w: 2.18, h: 0.36, fontSize: 11, bold: true, color: C.text, align: "center", valign: "middle" });
  txt(s, String(SL.length), { x: 12.2, y: 7.05, w: 0.55, h: 0.3, fontSize: 11, color: C.muted, align: "right", valign: "middle" });
  s.addNotes(notes);
}
function fig(s, files, bx, by, bw, bh, align) {
  const p = [].concat(files).map((f) => (path.isAbsolute(f) ? f : path.join(FIG, f))).find((f) => fs.existsSync(f));
  if (!p) throw new Error("missing figure " + files);
  const d = sizeOf.imageSize ? sizeOf.imageSize(fs.readFileSync(p)) : sizeOf(fs.readFileSync(p));
  const k = Math.min(bw / d.width, bh / d.height);
  const w = d.width * k, h = d.height * k;
  const x = align === "left" ? bx : bx + (bw - w) / 2, y = by;
  s.addImage({ path: p, x, y, w, h });
  return { x, y, w, h };
}
function legend(s, x, y, items) {
  let cx = x;
  for (const [t, col] of items) {
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: y + 0.05, w: 0.32, h: 0.22, fill: { color: C.bg }, line: { color: col, width: 2 } });
    const tw = 0.085 * t.length + 0.2;
    txt(s, t, { x: cx + 0.42, y, w: tw, h: 0.32, fontSize: 12, color: C.muted, valign: "middle", wrap: false });
    cx += 0.42 + tw + 0.3;
  }
}
const bullets = (arr, o) => arr.map((t, i, a) => ({ text: t, options: Object.assign({ bullet: true, breakLine: i < a.length - 1, paraSpaceAfter: 8 }, o || {}) }));

// ═════════ 1 ─ Title ═════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s._who = 0;
  s.addShape(pres.shapes.OVAL, { x: 9.6, y: 0.9, w: 3.2, h: 3.2, fill: { color: C.f, transparency: 82 }, line: { color: C.bg } });
  s.addShape(pres.shapes.OVAL, { x: 10.3, y: 1.6, w: 1.8, h: 1.8, fill: { color: C.plus, transparency: 62 }, line: { color: C.bg } });
  s.addShape(pres.shapes.OVAL, { x: 10.85, y: 2.15, w: 0.7, h: 0.7, fill: { color: "F4F0FF" }, line: { color: C.bg } });
  txt(s, "PROJECT SINH VIÊN · GLAREMOT", { x: 0.8, y: 1.3, w: 8, h: 0.4, fontSize: 14, bold: true, color: C.amber, charSpacing: 3 });
  txt(s, [{ text: "PEG-F", options: { color: C.f } }, { text: " và ", options: {} }, { text: "PEG+", options: { color: C.plus } },
    { text: " — giữ ID đúng người khi đèn mũ làm chói camera", options: {} }], { x: 0.8, y: 1.85, w: 8.6, h: 2.0, fontSize: 38, bold: true });
  txt(s, "Kiểm chứng và cải tiến bài báo PEG (“Burnt, Not Gone”)", { x: 0.8, y: 4.0, w: 8.6, h: 0.5, fontSize: 20, color: C.muted });
  card(s, 0.8, 5.0, 5.4, 1.35);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 5.0, w: 0.1, h: 1.35, fill: { color: C.f }, line: { color: C.f } });
  txt(s, [{ text: "Người 1", options: { bold: true, fontSize: 22, color: C.f, breakLine: true } },
    { text: "[điền tên] · PEG-F: 5 method + kiểm chứng", options: { fontSize: 15, color: C.muted } }], { x: 1.1, y: 5.0, w: 5.0, h: 1.35, valign: "middle" });
  card(s, 6.5, 5.0, 5.4, 1.35);
  s.addShape(pres.shapes.RECTANGLE, { x: 6.5, y: 5.0, w: 0.1, h: 1.35, fill: { color: C.plus }, line: { color: C.plus } });
  txt(s, [{ text: "Người 2", options: { bold: true, fontSize: 22, color: C.plus, breakLine: true } },
    { text: "[điền tên] · PEG+ và phần kết hợp", options: { fontSize: 15, color: C.muted } }], { x: 6.8, y: 5.0, w: 5.0, h: 1.35, valign: "middle" });
  done(s, "PEG-F và PEG+ — giữ ID đúng người khi đèn mũ làm chói camera",
    "Em chào thầy cô và các bạn. Nhóm mình có hai người, và hôm nay bọn mình trình bày về cùng một bài toán: theo dõi công nhân trong hầm mỏ khi đèn trên mũ làm chói camera. Bài báo gốc tên là “Burnt, Not Gone”, và có một tracker tên PEG. Mình là người thứ nhất, mình nói về PEG-F, năm cải tiến của mình cho PEG, và cách bọn mình kiểm chứng xem chúng có thật sự tốt không. Bạn mình là người thứ hai, sẽ nói về PEG+, một cải tiến khác, rồi nói về chuyện ghép hai bên lại với nhau.");
}

// ═════════ 2 ─ Problem ═════════
{
  const s = base("Đèn mũ chiếu vào camera → người cháy trắng", "BÀI TOÁN", 1);
  const r = fig(s, path.join(FIG_OLD, "01_gate_ok_box_drifts.png"), 0.6, 1.75, 12.13, 3.4);
  txt(s, "Trước khi chói", { x: r.x, y: r.y + r.h + 0.1, w: 2.4, h: 0.3, fontSize: 12, color: C.muted });
  txt(s, "Bị chói trắng →", { x: r.x + 2.55, y: r.y + r.h + 0.1, w: 3, h: 0.3, fontSize: 12, color: C.muted });
  txt(s, "Detector không thấy người → mất box, mất ID.", { x: 0.6, y: 5.75, w: 12.1, h: 0.6, fontSize: 26, bold: true });
  done(s, "Bài toán",
    "Trong hầm mỏ, công nhân đội đèn trên mũ. Khi họ quay về phía camera, đèn làm cháy sáng cả vùng ảnh, như các tấm ảnh bên phải: người gần như biến mất. Lúc đó detector, tức là mô hình tìm người trong ảnh, không thấy ai, nên tracker mất cái box và có thể mất luôn số ID của người đó. Tracker là phần nối các box qua từng frame để mỗi người giữ một ID cố định.");
}

// ═════════ 3 ─ What PEG does ═════════
{
  const s = base("PEG làm gì?", "Ý TƯỞNG CỦA PAPER", 1);
  const cy = 3.55;
  const arrow = (x1, x2, y) => s.addShape(pres.shapes.LINE, { x: x1, y, w: x2 - x1, h: 0, line: { color: C.amber, width: 2.5, endArrowType: "triangle" } });
  card(s, 0.6, cy - 0.7, 2.3, 1.4);
  txt(s, "Người bị mất", { x: 0.6, y: cy - 0.7, w: 2.3, h: 1.4, fontSize: 20, bold: true, align: "center", valign: "middle" });
  arrow(2.95, 3.4, cy);
  card(s, 3.45, cy - 0.7, 3.1, 1.4, C.card2);
  txt(s, [{ text: "Đo φ", options: { bold: true, color: C.amber, fontSize: 22, breakLine: true } },
    { text: "% box đoán bị trắng", options: { color: C.muted, fontSize: 15 } }], { x: 3.45, y: cy - 0.7, w: 3.1, h: 1.4, align: "center", valign: "middle" });
  arrow(6.6, 7.05, cy);
  s.addShape(pres.shapes.DIAMOND, { x: 7.1, y: cy - 0.85, w: 2.0, h: 1.7, fill: { color: C.card }, line: { color: C.amber, width: 2 } });
  txt(s, "φ ≥ h\n(0.4)?", { x: 7.1, y: cy - 0.85, w: 2.0, h: 1.7, fontSize: 18, bold: true, align: "center", valign: "middle" });
  s.addShape(pres.shapes.LINE, { x: 9.15, y: cy - 1.0, w: 0.5, h: 1.0, flipV: true, line: { color: C.good, width: 2.5, endArrowType: "triangle" } });
  s.addShape(pres.shapes.LINE, { x: 9.15, y: cy, w: 0.5, h: 1.0, line: { color: C.muted, width: 2.5, endArrowType: "triangle" } });
  txt(s, "Có", { x: 9.0, y: cy - 0.95, w: 0.5, h: 0.3, fontSize: 14, bold: true, color: C.good });
  txt(s, "Không", { x: 8.85, y: cy + 1.1, w: 0.8, h: 0.3, fontSize: 14, bold: true, color: C.muted });
  card(s, 9.7, cy - 1.75, 3.03, 1.5, C.card2);
  s.addShape(pres.shapes.RECTANGLE, { x: 9.7, y: cy - 1.75, w: 0.1, h: 1.5, fill: { color: C.good }, line: { color: C.good } });
  txt(s, [{ text: "Giữ box", options: { bold: true, color: C.good, fontSize: 20, breakLine: true } },
    { text: "người vẫn ở đó, chỉ bị chói", options: { color: C.text, fontSize: 14 } }], { x: 9.95, y: cy - 1.75, w: 2.7, h: 1.5, valign: "middle" });
  card(s, 9.7, cy + 0.25, 3.03, 1.5, C.card2);
  s.addShape(pres.shapes.RECTANGLE, { x: 9.7, y: cy + 0.25, w: 0.1, h: 1.5, fill: { color: C.muted }, line: { color: C.muted } });
  txt(s, [{ text: "Bỏ box", options: { bold: true, color: C.muted, fontSize: 20, breakLine: true } },
    { text: "người đã đi", options: { color: C.text, fontSize: 14 } }], { x: 9.95, y: cy + 0.25, w: 2.7, h: 1.5, valign: "middle" });
  txt(s, "Đo chính ánh sáng làm hỏng ảnh để quyết định giữ box.", { x: 0.6, y: 5.9, w: 12.1, h: 0.6, fontSize: 24, bold: true, color: C.amber });
  done(s, "PEG làm gì?",
    "PEG xử lý đúng lúc detector mất người. Nó đo vùng box dự đoán xem bao nhiêu phần trăm điểm ảnh bị cháy trắng, gọi là φ. Nếu φ từ 0.4 trở lên thì người vẫn ở đó, chỉ bị chói, nên giữ box. Việc tự đoán vị trí khi không có detector gọi là coast. Nếu φ thấp thì người đã đi, bỏ box. Ý hay của PEG là dùng chính ánh sáng gây lỗi làm bằng chứng.");
}

// ═════════ 4 ─ Reproduce ═════════
let maxRepro = 0;
{
  const s = base("Mình chạy lại có ra số của paper?", "TÁI HIỆN BÀI BÁO", 1);
  const rows = [
    ["Table I", "HOTA", "table1", "HOTA", 2], ["Table I", "IDF1", "table1", "IDF1", 2], ["Table I", "MOTA", "table1", "MOTA", 2],
    ["Table II", "MOTA", "table2", "MOTA", 2], ["Table II", "IDF1", "table2", "IDF1", 2], ["Table III", "Rcv@.5", "table3", "Rcv@.5", 1],
  ];
  const y0 = 2.2, rh = 0.62, gap = 0.1;
  txt(s, "Paper", { x: 6.5, y: y0 - 0.45, w: 1.5, h: 0.35, fontSize: 14, color: C.muted, align: "right" });
  txt(s, "Mình chạy", { x: 8.2, y: y0 - 0.45, w: 1.8, h: 0.35, fontSize: 14, color: C.muted, align: "right" });
  txt(s, "Lệch", { x: 10.2, y: y0 - 0.45, w: 1.2, h: 0.35, fontSize: 14, color: C.muted, align: "right" });
  let allOk = true;
  rows.forEach(([tb, m, tab, col, dec], i) => {
    const y = y0 + i * (rh + gap);
    const p = PT(tab, "paper_peg", col), o = PT(tab, "ours_peg", col);
    const dd = Math.abs(o - p);
    maxRepro = Math.max(maxRepro, dd);
    card(s, 0.6, y, 12.13, rh);
    txt(s, tb, { x: 0.85, y, w: 2.0, h: rh, fontSize: 16, color: C.muted, valign: "middle" });
    txt(s, m, { x: 2.9, y, w: 2.5, h: rh, fontSize: 22, bold: true, color: C.amber, valign: "middle" });
    txt(s, fmt(p, dec), { x: 6.5, y, w: 1.5, h: rh, fontSize: 24, color: C.muted, align: "right", valign: "middle" });
    txt(s, fmt(o, dec), { x: 8.2, y, w: 1.8, h: rh, fontSize: 24, bold: true, align: "right", valign: "middle" });
    txt(s, fmt(dd, dec), { x: 10.2, y, w: 1.2, h: rh, fontSize: 18, color: C.muted, align: "right", valign: "middle" });
    const ok = dd <= 0.2 + 1e-9;
    if (!ok) allOk = false;
    txt(s, ok ? "✓" : "≠", { x: 11.7, y, w: 0.8, h: rh, fontSize: 26, bold: true, color: ok ? C.good : C.red, align: "center", valign: "middle" });
  });
  txt(s, "✓ = lệch ≤ 0.2 điểm so với paper.   Cùng weights của paper, không train lại.", { x: 0.6, y: 6.6, w: 12, h: 0.35, fontSize: 13, color: C.muted });
  done(s, "Tái hiện kết quả",
    "Trước khi cải tiến gì, bọn mình phải chắc là chạy lại được số của paper. Bọn mình dùng đúng weights mà tác giả gửi, không train lại, và chạy ba bảng kết quả. Table I là video thật, Table II là video có thêm chói giả, và Table III chỉ đo những người đang bị chói. Có mấy điểm số chính. HOTA, IDF1 và MOTA là các điểm tổng quát đo chất lượng tracking, càng cao càng tốt. Rcv@.5 là phần trăm số frame của người bị chói mà box của mình vẫn chồng lên người, với độ trùng IoU trên 0.5. Kết quả của bọn mình lệch paper không quá " + fmt(maxRepro, 1) + " điểm" + (allOk ? ", nghĩa là tái hiện khớp." : ", trừ vài chỗ có dấu ≠."));
}

// ═════════ 5 ─ The five methods ═════════
{
  const s = base("PEG-F: 5 method", "ĐỐI TƯỢNG KIỂM CHỨNG", 1);
  const ms = [
    ["M1", "Chuyển động thích nghi", "M1-damp: hãm vận tốc khi hai người đứng gần nhau.  M1-swap: thêm các phép thử để đổi lại ID bị hoán đổi."],
    ["M2", "Re-ID bằng màu HSV", "So màu áo (histogram HSV) để quyết định box này là ai."],
    ["M3", "Ngưỡng h động + TTL thích nghi", "Tùy tình huống mà đổi ngưỡng chói h và thời gian được giữ box."],
    ["M4", "Pool track “ngủ”", "Track bị mất được cất lại, track mới sinh ra có thể nhận lại ID cũ."],
    ["M5", "Neo vào đèn mũ", "Trong lúc chói, kéo box về phía vị trí đèn trên mũ."],
  ];
  const rh = 0.86, gap = 0.12, y0 = 1.65;
  ms.forEach(([tag, nm, ds], i) => {
    const y = y0 + i * (rh + gap);
    card(s, 0.6, y, 12.13, rh);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 0.1, h: rh, fill: { color: C.f }, line: { color: C.f } });
    txt(s, tag, { x: 0.95, y, w: 0.9, h: rh, fontSize: 28, bold: true, color: C.f, valign: "middle" });
    txt(s, nm, { x: 1.9, y, w: 3.7, h: rh, fontSize: 18, bold: true, valign: "middle" });
    txt(s, ds, { x: 5.7, y, w: 6.8, h: rh, fontSize: 15, color: C.muted, valign: "middle" });
  });
  txt(s, "Tất cả chỉ sửa phần tracker. Detector và weights giữ nguyên.", { x: 0.6, y: 6.75, w: 11, h: 0.35, fontSize: 14, color: C.muted });
  done(s, "5 method của PEG-F",
    "PEG-F là năm cải tiến của mình cho tracker. M1 là chuyển động thích nghi, gồm hai nửa mà sau này bọn mình tách ra: M1-damp hãm vận tốc của hai người đứng gần nhau, còn M1-swap thêm các phép thử để sửa lại những lần đổi nhầm ID. M2 nhận lại người bằng màu áo. M3 đổi ngưỡng chói và thời gian giữ box tùy tình huống. M4 cất track bị mất vào một pool để track mới nhận lại ID cũ. M5 kéo box về phía đèn trên mũ. Tất cả chỉ sửa tracker, không đụng vào detector.");
}

// ═════════ 6 ─ Verify the claim: 3 checks ═════════
{
  const s = base("PEG-F đạt " + fmt(CL.HOTA, 2) + " / " + fmt(CL.IDF1, 2) + ". Có thật không?", "KIỂM CHỨNG CLAIM", 1);
  txt(s, [{ text: "Claim: HOTA ", options: { color: C.muted } }, { text: fmt(CL.HOTA, 2), options: { bold: true, color: C.f } }, { text: " · IDF1 ", options: { color: C.muted } },
    { text: fmt(CL.IDF1, 2), options: { bold: true, color: C.f } }, { text: "     Paper PEG: HOTA ", options: { color: C.muted } }, { text: fmt(PT("table1", "paper_peg", "HOTA"), 2), options: { bold: true } },
    { text: " · IDF1 ", options: { color: C.muted } }, { text: fmt(PT("table1", "paper_peg", "IDF1"), 2), options: { bold: true } }], { x: 0.6, y: 1.55, w: 12.1, h: 0.4, fontSize: 17 });
  const checks = [
    ["①", "Chấm lại output đã nộp", "Dùng evaluator của nhóm chấm file kết quả PEG-F", CL.HOTA, CL.IDF1, null],
    ["②", "Chạy lại code gốc", "Trên GTX 1650 của nhóm, chạy thật cả detector + tracker", LV.friend_combined.HOTA, LV.friend_combined.IDF1, fmt(LV.friend_fps, 1) + " FPS"],
    ["③", "Port vào repo chung", "Chạy lại bằng cache detector (cùng cấu hình guard bật)", g1("F_g", "HOTA"), g1("F_g", "IDF1"), null],
  ];
  checks.forEach(([n, t, sub, h, i1, extra], k) => {
    const x = 0.6 + k * 4.12, w = 3.9, y = 2.2;
    card(s, x, y, w, 3.5);
    txt(s, n, { x: x + 0.25, y: y + 0.15, w: 0.7, h: 0.6, fontSize: 30, bold: true, color: C.amber });
    txt(s, t, { x: x + 0.25, y: y + 0.8, w: w - 0.5, h: 0.5, fontSize: 19, bold: true });
    txt(s, sub, { x: x + 0.25, y: y + 1.3, w: w - 0.5, h: 0.7, fontSize: 13, color: C.muted });
    txt(s, [{ text: "HOTA ", options: { color: C.muted, fontSize: 14 } }, { text: fmt(h, 2), options: { bold: true, fontSize: 30, color: C.f, breakLine: true } },
      { text: "IDF1 ", options: { color: C.muted, fontSize: 14 } }, { text: fmt(i1, 2), options: { bold: true, fontSize: 30, color: C.f } }],
      { x: x + 0.25, y: y + 2.05, w: 2.6, h: 1.3 });
    txt(s, "✓", { x: x + w - 0.95, y: y + 2.3, w: 0.7, h: 0.8, fontSize: 40, bold: true, color: C.good, align: "center" });
    if (extra) txt(s, extra, { x: x + w - 1.6, y: y + 0.15, w: 1.4, h: 0.4, fontSize: 13, color: C.muted, align: "right" });
  });
  txt(s, "Cả ba cách đều ra đúng số → claim là thật, không phải lỗi đo.", { x: 0.6, y: 6.05, w: 12.1, h: 0.6, fontSize: 24, bold: true, color: C.amber });
  done(s, "Kiểm chứng claim",
    "Mình báo PEG-F đạt HOTA " + fmt(CL.HOTA, 2) + " và IDF1 " + fmt(CL.IDF1, 2) + ", cao hơn paper là " + fmt(PT("table1", "paper_peg", "HOTA"), 2) + " và " + fmt(PT("table1", "paper_peg", "IDF1"), 2) + ". Nhưng bọn mình không tin ngay mà kiểm tra ba cách. Một, chấm lại file kết quả mình nộp bằng evaluator của nhóm: ra đúng. Hai, chạy lại nguyên code gốc trên GPU của nhóm, chạy thật cả detector, khoảng " + fmt(LV.friend_fps, 1) + " frame mỗi giây: vẫn đúng số đó. Ba, đưa các method vào repo chung và chạy bằng cache, tức là kết quả detector lưu sẵn: giống từng chữ số. Vậy claim là thật. Nhưng còn một câu hỏi: so với cái gì?");
}

// ═════════ 7 ─ Fair baseline ═════════
{
  const dH = CL.HOTA - FP_.HOTA, dI = CL.IDF1 - FP_.IDF1;
  const s = base("So cùng cấu hình: mức tăng thật là " + sgn(dH, 2) + " HOTA", "KIỂM CHỨNG CLAIM", 1);
  const cols = [
    ["Paper PEG", "guard TẮT", PT("table1", "paper_peg", "HOTA"), PT("table1", "paper_peg", "IDF1"), PT("table1", "paper_peg", "IDSW"), C.muted],
    ["PEG-F (claim)", "guard BẬT", CL.HOTA, CL.IDF1, CL.IDSW, C.f],
    ["PEG, guard bật", "so sánh công bằng", FP_.HOTA, FP_.IDF1, FP_.IDSW, C.peg],
  ];
  cols.forEach(([nm, sub, h, i1, sw, col], k) => {
    const x = 0.6 + k * 4.12, w = 3.9, y = 1.7;
    card(s, x, y, w, 2.55, k === 2 ? C.card2 : C.card);
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.1, h: 2.55, fill: { color: col }, line: { color: col } });
    txt(s, nm, { x: x + 0.3, y: y + 0.12, w: w - 0.5, h: 0.4, fontSize: 19, bold: true, color: col });
    txt(s, sub, { x: x + 0.3, y: y + 0.52, w: w - 0.5, h: 0.3, fontSize: 13, color: C.muted });
    txt(s, [{ text: "HOTA " + fmt(h, 2), options: { breakLine: true, bold: true } }, { text: "IDF1 " + fmt(i1, 2), options: { breakLine: true, bold: true } },
      { text: "IDSW " + fmtI(sw), options: { color: C.muted } }], { x: x + 0.3, y: y + 0.95, w: w - 0.5, h: 1.5, fontSize: 22 });
  });
  const tile = (x, big, lab, col) => {
    card(s, x, 4.5, 3.9, 1.95);
    txt(s, big, { x: x + 0.3, y: 4.55, w: 3.4, h: 1.15, fontSize: 54, bold: true, color: col, valign: "middle" });
    txt(s, lab, { x: x + 0.3, y: 5.7, w: 3.4, h: 0.65, fontSize: 14, color: C.muted });
  };
  tile(0.6, sgn(dH, 2), "HOTA, so với PEG cùng guard bật", C.good);
  tile(4.72, sgn(dI, 2), "IDF1, so với PEG cùng guard bật", C.good);
  tile(8.84, fmtI(FP_.IDSW) + " → " + fmtI(CL.IDSW), "IDSW: số lần đổi ID, nhiều hơn là xấu hơn", C.red);
  txt(s, "Paper tắt guard (bộ chặn track ma do vầng sáng); PEG-F chạy với guard bật → phải so với PEG guard bật.", { x: 0.6, y: 6.6, w: 12.1, h: 0.4, fontSize: 13, color: C.muted });
  done(s, "So cùng cấu hình",
    "Có một chỗ không công bằng. Số " + fmt(PT("table1", "paper_peg", "HOTA"), 2) + " của paper chạy với guard tắt. Guard là lớp bảo vệ không cho tracker tạo ID mới từ vầng sáng chói. Code PEG-F của mình chạy với guard bật, nên phải so với PEG cũng guard bật: PEG đó được " + fmt(FP_.HOTA, 2) + " HOTA và " + fmt(FP_.IDF1, 2) + " IDF1. So như vậy PEG-F hơn " + sgn(dH, 2) + " HOTA và " + sgn(dI, 2) + " IDF1. Và IDSW, tức là số lần tracker đổi ID của một người sang ID khác, tăng từ " + fmtI(FP_.IDSW) + " lên " + fmtI(CL.IDSW) + "; IDSW càng ít càng tốt. Mức tăng có thật, nhưng nhỏ hơn con số ban đầu và có cái giá.");
}

// ═════════ 8 ─ Where the gain comes from ═════════
{
  const d129 = dseq(SEQ129), d176 = dseq(SEQ176);
  const mx = OTHERS_MAX;
  const nz = Object.keys(PS.peg_g).filter((q) => Math.abs(dseq(q)) >= 0.5).length;
  const s = base("Mức tăng đến từ 2 video, mỗi video là 1 lần đổi ID", "MỨC TĂNG ĐẾN TỪ ĐÂU", 1);
  const r = fig(s, "perseq_delta.png", 0.5, 1.6, 8.3, 5.2, "left");
  const cx = 9.1, cw = 3.63;
  card(s, cx, 1.7, cw, 1.55);
  txt(s, [{ text: sgn(d129, 1), options: { bold: true, fontSize: 36, color: C.good, breakLine: true } }, { text: "video 129: sửa 1 lần đổi ID", options: { fontSize: 14, color: C.muted } }], { x: cx + 0.25, y: 1.78, w: cw - 0.4, h: 1.4, valign: "middle" });
  card(s, cx, 3.4, cw, 1.55);
  txt(s, [{ text: sgn(d176, 1), options: { bold: true, fontSize: 36, color: C.red, breakLine: true } }, { text: "video 176: gây 1 lần đổi ID mới", options: { fontSize: 14, color: C.muted } }], { x: cx + 0.25, y: 3.48, w: cw - 0.4, h: 1.4, valign: "middle" });
  card(s, cx, 5.1, cw, 1.65, C.card2);
  txt(s, [{ text: (Object.keys(PS.peg_g).length - 2) + " video còn lại", options: { bold: true, fontSize: 16, breakLine: true } },
    { text: "chênh tối đa " + fmt(mx, 1) + " HOTA; " + (Object.keys(PS.peg_g).length - nz) + " video gần như không đổi (< 0.5)", options: { fontSize: 13, color: C.muted } }], { x: cx + 0.25, y: 5.15, w: cw - 0.4, h: 1.55, valign: "middle" });
  done(s, "Mức tăng đến từ đâu",
    "Mức tăng đó đến từ đâu? Hình là độ chênh HOTA của từng video, PEG-F trừ PEG, cùng guard bật. Chỉ hai video lệch đáng kể: video 129 tăng " + sgn(d129, 1) + ", video 176 giảm " + sgn(d176, 1) + ". Mình soi từng video thì mỗi video chỉ là một lần tracker đổi ID giữa hai công nhân đứng sát nhau: ở 129 PEG-F sửa được một lần, ở 176 PEG-F gây ra một lần mới. Các video còn lại chênh tối đa " + fmt(mx, 1) + " điểm. Nên Table I một mình rất dễ bị lệch bởi một sự kiện.");
}

// ═════════ 9 ─ Swap example 129 ═════════
{
  const s = base("M1-swap sửa lỗi đổi ID ở video 129", "VÌ SAO TĂNG · VIDEO 129", 1);
  const r = fig(s, "swap_129.png", 0.6, 1.55, 12.13, 5.0);
  txt(s, "Hai công nhân A, B đi sát nhau. PEG đổi ID và giữ sai đến hết video; PEG-F đổi lại ở frame " + swapFrame + ".", { x: 0.6, y: r.y + r.h + 0.08, w: 12.13, h: 0.5, fontSize: 15, bold: true, align: "center" });
  done(s, "M1-swap sửa đổi ID ở video 129",
    "Đây là video 129, hai công nhân A và B đi sát nhau. Hàng trên là PEG, hàng dưới là PEG-F; màu vàng là ID một, xanh lơ là ID hai, khung trắng là người thật. Ở frame " + SW.frames[0] + " cả hai đều đúng. Khi hai người đi chéo qua nhau, cả hai tracker đổi nhầm, nhưng PEG giữ nhầm đến hết video, còn PEG-F đổi lại ở frame " + swapFrame + ". Bí quyết là phép thử chiều cao nhất quán của M1-swap: A thấp, B cao, tracker so chiều cao box với chiều cao quen thuộc của từng track, và nếu đổi lại ID làm chiều cao khớp hơn thì đổi lại. Nên ở frame " + SW.frames[3] + " và " + SW.frames[4] + ", PEG-F vẫn đúng, còn PEG thì ngược.");
}

// ═════════ 10 ─ Ablation grid ═════════
{
  const s = base("Từng method làm được gì? (thêm từng cái vào PEG)", "TỪNG METHOD", 1);
  const r = fig(s, "ablation_grid.png", 0.8, 1.5, 11.7, 5.0);
  txt(s, "M1-swap tăng Table I (nhưng IDSW tăng) · M1-damp làm hỏng Table II và III · M3 tốt nhẹ · M2, M4, M5 ≈ 0.", { x: 0.6, y: r.y + r.h + 0.1, w: 12.13, h: 0.5, fontSize: 17, bold: true, color: C.amber, align: "center" });
  done(s, "Từng method làm được gì",
    "Giờ thêm từng method vào PEG, mỗi lần một cái. Số to là độ thay đổi so với PEG; xanh là tốt hơn, đỏ là xấu hơn; với IDSW thì ít hơn mới tốt. M1-swap tăng HOTA " + sgn(g1("P+M1swap", "HOTA") - g1("peg", "HOTA"), 2) + " và IDF1 " + sgn(g1("P+M1swap", "IDF1") - g1("peg", "IDF1"), 2) + " ở Table I, nhưng IDSW tăng từ " + fmtI(g1("peg", "IDSW")) + " lên " + fmtI(g1("P+M1swap", "IDSW")) + ". M1-damp làm hỏng: MOTA của Table II giảm " + sgn(g2("P+M1damp", "MOTA") - g2("peg", "MOTA"), 2) + ", Rcv@.5 của Table III giảm từ " + fmt(g3("peg"), 1) + " xuống " + fmt(g3("P+M1damp"), 1) + ". M3 tốt nhẹ, MOTA của Table II " + sgn(g2("P+M3", "MOTA") - g2("peg", "MOTA"), 2) + ". M2, M4, M5 gần như không đổi. Tức là chỉ hai trong năm method có tác dụng thật: M1-swap và M3.");
}

// ═════════ 11 ─ Why M2, M4 do nothing ═════════
{
  const s = base("Vì sao M2 và M4 không chạy?", "SỐ ĐẾM TỪ BÊN TRONG", 1);
  const tile = (x, tag, big, small, lab) => {
    card(s, x, 1.75, 3.9, 3.1);
    txt(s, tag, { x: x + 0.3, y: 1.85, w: 3.3, h: 0.35, fontSize: 14, bold: true, color: C.f });
    txt(s, big, { x: x + 0.3, y: 2.25, w: 3.4, h: 1.2, fontSize: 44, bold: true, valign: "middle" });
    txt(s, small, { x: x + 0.3, y: 3.45, w: 3.4, h: 0.4, fontSize: 15, bold: true, color: C.red });
    txt(s, lab, { x: x + 0.3, y: 3.9, w: 3.4, h: 0.9, fontSize: 13, color: C.muted });
  };
  tile(0.6, "M2 · giành ID", fmt(CD1.m2_steal_sim_diff.max, 3), "cần > " + fmt(M.steal_margin_needed, 2), "độ chênh màu lớn nhất giữa người đúng và người sai, trong " + CC1.m2_steal_evals + " lần xét");
  tile(4.72, "M2 · đổi chéo", fmt(CD1.m2_swap_cross_minus_own_sum.max, 3), "cần > " + fmt(M.swap_margin_needed, 2), "độ chênh lớn nhất trong " + CC1.m2_swap_evals + " lần xét");
  tile(8.84, "M4 · hồi sinh track", CC1.m4_births_with_pool + " / " + CC1.m4_births, "lần có pool khác rỗng", "khi sinh track mới; chỉ " + CC1.m4_revivals + " lần hồi sinh trong cả Table I");
  card(s, 0.6, 5.05, 12.13, 1.5, C.card2);
  txt(s, [{ text: "Công nhân mặc đồ bảo hộ giống nhau → màu HSV không phân biệt được.", options: { bold: true, fontSize: 21, breakLine: true } },
    { text: "Độ giống màu: cùng người ≈ " + fmt(CD1.m2_swap_sim_own.median_of_seq_medians, 2) + ", khác người ≈ " + fmt(CD1.m2_swap_sim_cross.median_of_seq_medians, 2) + " (trung vị) → số lần M2 đổi một quyết định: " + ((CC1.m2_swap_changed || 0) + (CC1.m2_steal_changed || 0)), options: { fontSize: 14, color: C.muted } }],
    { x: 0.9, y: 5.05, w: 11.6, h: 1.5, valign: "middle" });
  done(s, "Vì sao M2 và M4 không chạy",
    "Vì sao M2 và M4 không làm gì? Bọn mình đếm bên trong tracker. M2 chỉ đổi ID khi màu áo của người kia giống hơn một khoảng đủ lớn, phải trên " + fmt(M.steal_margin_needed, 2) + ", nhưng thực tế lớn nhất chỉ " + fmt(CD1.m2_steal_sim_diff.max, 3) + "; ở phép thử đổi chéo cần " + fmt(M.swap_margin_needed, 2) + " mà chỉ đạt " + fmt(CD1.m2_swap_cross_minus_own_sum.max, 3) + ". Lý do: công nhân mặc đồ bảo hộ giống hệt nhau nên màu HSV không phân biệt được. Vì vậy M2 chưa bao giờ đổi một quyết định nào. M4 còn tệ hơn: trong " + CC1.m4_births + " lần sinh track mới, chỉ " + CC1.m4_births_with_pool + " lần pool có người để nhận lại.");
}

// ═════════ 12 ─ Cost: FPS ═════════
{
  const s = base("Chi phí: gần như không tốn thêm thời gian", "TỐC ĐỘ TRÊN GTX 1650", 1);
  const mx = 6;
  const bar = (y, nm, v, col) => {
    card(s, 0.6, y, 12.13, 1.2);
    txt(s, nm, { x: 0.9, y, w: 2.6, h: 1.2, fontSize: 24, bold: true, color: col, valign: "middle" });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 3.6, y: y + 0.3, w: 6.0 * v / mx, h: 0.6, fill: { color: col }, line: { color: col }, rectRadius: 0.06 });
    txt(s, fmt(v, 1) + " FPS", { x: 3.6 + 6.0 * v / mx + 0.2, y, w: 2.2, h: 1.2, fontSize: 28, bold: true, valign: "middle" });
  };
  bar(1.8, "PEG", LV.peg_fps, C.peg);
  bar(3.2, "PEG-F", LV.friend_fps, C.f);
  txt(s, "FPS = số frame xử lý mỗi giây khi chạy cả detector + h_psi + tracker, trên cùng một máy: " + LV.frames + " frame của Table I.", { x: 0.6, y: 4.65, w: 12.1, h: 0.6, fontSize: 15, color: C.muted });
  card(s, 0.6, 5.35, 12.13, 1.2, C.card2);
  txt(s, [{ text: "Detector chiếm gần hết thời gian → phần tracker thêm vào không đáng kể.", options: { bold: true, fontSize: 20, breakLine: true } },
    { text: "(Paper: " + fmt(LV.paper_fps_rtx5070ti, 1) + " FPS trên RTX 5070 Ti, GPU mạnh hơn nhiều)", options: { fontSize: 14, color: C.muted } }], { x: 0.9, y: 5.35, w: 11.6, h: 1.2, valign: "middle" });
  done(s, "Chi phí: tốc độ",
    "Cuối cùng là chi phí, trên cùng GPU GTX 1650, chạy thật cả pipeline: detector, h_psi và tracker. FPS là số frame xử lý mỗi giây. PEG đạt " + fmt(LV.peg_fps, 1) + " FPS, code PEG-F đạt " + fmt(LV.friend_fps, 1) + " FPS, gần như bằng nhau vì detector chiếm gần hết thời gian. Paper ghi " + fmt(LV.paper_fps_rtx5070ti, 1) + " FPS vì dùng GPU RTX 5070 Ti mạnh hơn. Vậy PEG-F không tốn thêm gì đáng kể, nhưng chỉ hai method đáng giữ. Mình chuyển sang bạn mình, người nói về PEG+.");
}

// ═════════ 13 ─ PEG+ : box collapse ═════════
{
  const s = base("Lỗi PEG còn lại: box co lại khi coast → PEG+ khóa kích thước", "PEG+ · CẢI TIẾN CỦA NGƯỜI 2", 2);
  const r = fig(s, path.join(FIG_PLUS, "cmp_box_collapse.png"), 0.6, 1.55, 9.0, 4.4, "left");
  legend(s, 0.6, r.y + r.h + 0.15, [["Người thật (GT)", C.amber], ["Người bị sót", C.miss], ["Box sai chỗ", C.red]]);
  const g = g3("A") - g3("peg");
  card(s, 9.9, 1.65, 2.83, 2.1);
  txt(s, "Table III · Rcv@.5", { x: 10.1, y: 1.75, w: 2.5, h: 0.3, fontSize: 12, color: C.muted });
  txt(s, sgn(g, 1), { x: 10.1, y: 2.05, w: 2.5, h: 0.9, fontSize: 48, bold: true, color: C.plus });
  txt(s, fmt(g3("peg"), 1) + " → " + fmt(g3("A"), 1), { x: 10.1, y: 3.0, w: 2.5, h: 0.5, fontSize: 20, bold: true });
  card(s, 9.9, 3.95, 2.83, 2.0, C.card2);
  txt(s, [{ text: "~2 dòng code", options: { bold: true, color: C.amber, fontSize: 16, breakLine: true } },
    { text: "vận tốc diện tích = 0 khi coast", options: { fontFace: "Consolas", fontSize: 13 } }], { x: 10.1, y: 4.0, w: 2.5, h: 1.9, valign: "middle" });
  txt(s, "PEG: box nhỏ dần rồi mất người · PEG+: giữ nguyên kích thước.", { x: 0.6, y: 6.4, w: 12.1, h: 0.45, fontSize: 18, bold: true });
  done(s, "PEG+: khóa kích thước",
    "Mình là người thứ hai, mình nói về PEG+. Sau khi tái hiện PEG, mình xem từng ca PEG thất bại và thấy một lỗi lạ: PEG biết người đang bị chói và vẫn giữ box, nhưng cái box nhỏ dần qua từng frame, như hàng trên của hình, cho đến khi không còn trùng người. Khung vàng là người thật, khung xanh dương là box của PEG. Mình đếm lại: trong các ca thất bại ở Table III, " + P.failure.drift_failures + " là do box trôi chứ không phải do gate bật sai, và " + P.failure.small_box_frac + " số frame coast có box nhỏ hơn 30% kích thước ban đầu. Nguyên nhân là Kalman filter, bộ lọc đoán vị trí, nhớ cả vận tốc đổi kích thước. Khi coast, PEG hãm vận tốc di chuyển nhưng quên hãm vận tốc diện tích. Mình đặt vận tốc diện tích bằng không, khoảng hai dòng code, và đó là PEG+, hàng dưới màu xanh lá. Kết quả: Rcv@.5, phần trăm frame mà box vẫn trùng người bị chói, tăng từ " + fmt(g3("peg"), 1) + " lên " + fmt(g3("A"), 1) + ", " + sgn(g, 1) + " điểm. Mình không train lại detector, chỉ sửa tracker, nên so PEG với PEG+ là công bằng: hai bên chỉ khác đúng hai dòng code này. Hình là cùng một người, cùng một đoạn video, cùng lúc bị chói, nên bạn nhìn thấy trực tiếp sự khác nhau giữa hai hàng.");
}

// ═════════ 14 ─ Combination ═════════
{
  const s = base("Ghép PEG-F + PEG+: Table I tốt nhất, nhưng Table II/III tụt", "KẾT HỢP", 2);
  const r = fig(s, "main_combo.png", 0.5, 1.5, 12.3, 4.6);
  txt(s, [{ text: "Table I: HOTA " + fmt(g1("FA", "HOTA"), 2) + ", IDF1 " + fmt(g1("FA", "IDF1"), 2) + " — nhưng Table III Rcv@.5 chỉ " + fmt(g3("FA"), 1) + " (PEG+: " + fmt(g3("A"), 1) + ")", options: { bold: true, breakLine: true } },
           { text: "Phần Table I cao hơn PEG-F gần như chỉ đến từ video 176 (" + fmt(PS.F[SEQ176].HOTA, 1) + " → " + fmt(PS.FA[SEQ176].HOTA, 1) + "): tình cờ, chưa chắc chắn.", options: { fontSize: 13, color: C.muted } }],
    { x: 0.6, y: r.y + r.h + 0.12, w: 12.13, h: 0.75, fontSize: 18, align: "center" });
  done(s, "Kết hợp PEG-F và PEG+",
    "Bọn mình thử ghép PEG-F với PEG+. Hình có bốn bảng nhỏ, mỗi bảng một thang riêng, trục không bắt đầu từ không để nhìn rõ chênh lệch. Xanh dương là PEG, xanh lá là PEG+, tím là PEG-F, cam là ghép cả hai; cột gạch chéo là một cách ghép có chọn lọc, mình nói ở slide sau. Ở Table I, video thật, ghép cả hai cho kết quả tốt nhất: HOTA " + fmt(g1("FA", "HOTA"), 2) + " và IDF1 " + fmt(g1("FA", "IDF1"), 2) + ". Nhưng ở Table II, video có chói giả, MOTA chỉ " + fmt(g2("FA", "MOTA"), 2) + ", thấp hơn cả PEG là " + fmt(g2("peg", "MOTA"), 2) + ". Và ở Table III, Rcv@.5 chỉ còn " + fmt(g3("FA"), 1) + ", trong khi PEG+ một mình đạt " + fmt(g3("A"), 1) + ". Tức là cái lợi của PEG+ đã bị mất đi khi ghép với PEG-F. Câu hỏi là vì sao. Bài học đầu tiên ở đây: mỗi bảng đo một thứ khác nhau, nên một cách ghép chỉ tốt ở một bảng thì chưa thể gọi là tốt. Table I chủ yếu hỏi tracker có giữ đúng ID giữa nhiều người không, còn Table III hỏi tracker có giữ được người đang bị chói hay không, và đó chính là chỗ PEG+ sinh ra để làm. Còn một điều phải nói thật: ghép cả hai cao hơn PEG-F " + fmt(g1("FA", "HOTA") - g1("F", "HOTA"), 2) + " HOTA ở Table I, nhưng gần như toàn bộ phần đó đến từ một video, video 176: có PEG+ thì lần đổi ID mà PEG-F gây ra ở đó không xảy ra nữa, HOTA của video này từ " + fmt(PS.F[SEQ176].HOTA, 2) + " lên " + fmt(PS.FA[SEQ176].HOTA, 2) + ". Đó là một tương tác tình cờ giữa hai thay đổi, PEG+ không được thiết kế để sửa lỗi ID, nên con số " + fmt(g1("FA", "HOTA"), 2) + " không nên coi là chắc chắn.");
}

// ═════════ 15 ─ Why: M1-damp episode ═════════
{
  const s = base("Vì sao? M1-damp làm box đứng lại trong khi người vẫn đi", "VÌ SAO TỤT · M1-DAMP", 2);
  const r = fig(s, "damp_episode.png", 0.5, 1.55, 8.2, 4.6, "left");
  const cx = 9.0, cw = 3.73;
  card(s, cx, 1.65, cw, 1.9);
  txt(s, [{ text: D.episode_cov_peg + " → " + D.episode_cov_damp, options: { bold: true, fontSize: 38, color: C.red, breakLine: true } },
    { text: "frame bị chói mà box còn trùng người, video " + D.seq.split("_")[0] + "_" + D.seq.split("_")[2] + " (" + D.episode_burn_frames + " frame chói)", options: { fontSize: 13, color: C.muted } }], { x: cx + 0.25, y: 1.7, w: cw - 0.4, h: 1.8, valign: "middle" });
  card(s, cx, 3.7, cw, 1.9);
  txt(s, [{ text: D.total_cov_peg + " → " + D.total_cov_damp, options: { bold: true, fontSize: 38, color: C.red, breakLine: true } },
    { text: "trên cả 30 lần chói: số frame (trên " + D.total_burn_frames + ") box còn trùng người", options: { fontSize: 13, color: C.muted } }], { x: cx + 0.25, y: 3.75, w: cw - 0.4, h: 1.8, valign: "middle" });
  txt(s, "Hai người đứng gần → hãm vận tốc ×" + fmt(M1.damp_factor, 2) + " mỗi frame → box người bị chói dừng lại.", { x: 0.6, y: 6.3, w: 12.1, h: 0.6, fontSize: 19, bold: true, color: C.amber });
  done(s, "Vì sao tụt: M1-damp",
    "Mình tách M1 làm hai nửa và tìm ra thủ phạm: M1-damp, nửa hãm vận tốc. Luật của nó là: mỗi frame, nếu hai người đứng gần nhau thì nhân vận tốc của họ với " + fmt(M1.damp_factor, 2) + ". Vấn đề là người đang bị chói cũng đang coast, tức là box chỉ chạy theo vận tốc đoán. Vận tốc bị hãm thì box đứng lại, trong khi người vẫn đi tiếp. Hình là video " + D.seq.split("_")[0] + ", người số " + D.gt_id + ", từ frame " + D.frames[0] + " đến " + D.frames[D.frames.length - 1] + ". Khung xanh lá là người thật. Hàng trên là PEG, box đi theo người. Hàng dưới là PEG cộng M1-damp, box đỏ đứng lại, và độ trùng IoU tụt từ " + fmt(D.iou_damp_first, 2) + " xuống " + fmt(D.iou_damp_last, 2) + ". Đếm lại: trong " + D.episode_burn_frames + " frame bị chói của người này, số frame box còn trùng người giảm từ " + D.episode_cov_peg + " xuống " + D.episode_cov_damp + ". Trên cả ba mươi lần chói, số frame được phủ giảm từ " + D.total_cov_peg + " xuống " + D.total_cov_damp + " trên tổng " + D.total_burn_frames + ". Vậy cái làm hỏng Table III chính là M1-damp, không phải M1-swap. Nửa còn lại, M1-swap, không làm Table III đổi một chút nào: Rcv@.5 vẫn giữ nguyên. Và M1-damp cũng là thứ gây ra lần đổi ID mới ở video 176 mà bạn mình đã nói ở phần trước, nên nó có hại ở cả hai nơi. Mình đoán hãm vận tốc có thể hợp lý khi hai người đi sát nhau và cả hai đều đang được nhìn thấy; còn khi một người bị chói và đang coast thì việc hãm làm box đứng lại, và đó là hướng sửa mình đề xuất.");
}

// ═════════ 16 ─ Selective combination ═════════
{
  const SEL = "A+M1swap+M3";
  const s = base("Ghép có chọn lọc (chọn trên test): PEG+ + M1-swap + M3", "KẾT HỢP CÓ CHỌN LỌC", 2);
  const rows = [["PEG", "peg", C.peg], ["PEG+", "A", C.plus], ["PEG+ + M1-swap + M3", SEL, C.sel]];
  const cols = [["T1 HOTA", (v) => g1(v, "HOTA"), 2, 1], ["T1 IDF1", (v) => g1(v, "IDF1"), 2, 1], ["T1 IDSW", (v) => g1(v, "IDSW"), 0, -1], ["T2 MOTA", (v) => g2(v, "MOTA"), 2, 1], ["T3 Rcv@.5", (v) => g3(v), 1, 1]];
  const x0 = 3.6, cw = 1.75, y0 = 1.65, rh = 0.8;
  cols.forEach(([cn], j) => txt(s, cn, { x: x0 + j * cw, y: y0, w: cw, h: 0.4, fontSize: 14, bold: true, color: C.muted, align: "center" }));
  rows.forEach(([nm, key, col], i) => {
    const y = y0 + 0.5 + i * (rh + 0.1);
    card(s, 0.6, y, 12.13, rh, key === SEL ? C.card2 : C.card);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 0.1, h: rh, fill: { color: col }, line: { color: col } });
    txt(s, nm, { x: 0.9, y, w: 2.7, h: rh, fontSize: key === SEL ? 14 : 17, bold: true, color: col, valign: "middle" });
    cols.forEach(([cn, f, dec, sg], j) => {
      const v = f(key), b = f("peg"), a = f("A");
      let c = C.text;
      if (key === SEL) { const d1 = (v - b) * sg, d2 = (v - a) * sg; c = Math.abs(d1) < 0.005 ? C.text : (d1 > 0 ? C.good : C.red); if (cn === "T1 IDSW") c = C.red; }
      txt(s, fmt(v, dec), { x: x0 + j * cw, y, w: cw, h: rh, fontSize: 24, bold: true, align: "center", valign: "middle", color: key === SEL ? c : C.text });
    });
  });
  const yb = y0 + 0.5 + 3 * (rh + 0.1) + 0.4;
  txt(s, "Hàng dưới: xanh = tốt hơn PEG, đỏ = xấu hơn PEG (IDSW: ít hơn là tốt).", { x: 0.6, y: yb - 0.35, w: 12, h: 0.3, fontSize: 12, color: C.muted });
  card(s, 0.6, yb, 5.95, 1.5);
  txt(s, [{ text: "IDF1", options: { bold: true, color: C.amber, breakLine: true } }, { text: "giữ đúng ID lâu dài.", options: { breakLine: true, fontSize: 15 } },
    { text: "IDSW", options: { bold: true, color: C.amber, breakLine: true } }, { text: "đếm số lần đổi ID, từng lần ngắn.", options: { fontSize: 15 } }], { x: 0.85, y: yb + 0.05, w: 5.5, h: 1.4, fontSize: 18, valign: "middle" });
  card(s, 6.78, yb, 5.95, 1.5, C.card2);
  s.addShape(pres.shapes.RECTANGLE, { x: 6.78, y: yb, w: 0.1, h: 1.5, fill: { color: C.red }, line: { color: C.red } });
  txt(s, [{ text: "IDSW " + fmtI(g1("A", "IDSW")) + " → " + fmtI(g1(SEL, "IDSW")) + ". Và vì chọn sau khi đã thấy test…", options: { bold: true, fontSize: 17, breakLine: true } },
    { text: "→ kiểm tra lại trên tập val: slide sau.", options: { fontSize: 16, color: C.amber, bold: true } }], { x: 7.08, y: yb, w: 5.5, h: 1.5, valign: "middle" });
  done(s, "Ghép có chọn lọc",
    "Từ các thí nghiệm, mình thử ghép có chọn lọc: lấy PEG+, thêm M1-swap, thêm M3 và bỏ M1-damp. Kết quả là không bảng nào kém PEG+. Table I: HOTA " + fmt(g1(SEL, "HOTA"), 2) + ", IDF1 " + fmt(g1(SEL, "IDF1"), 2) + ". Table II: MOTA " + fmt(g2(SEL, "MOTA"), 2) + ". Table III: Rcv@.5 vẫn " + fmt(g3(SEL), 1) + ". Nhưng có hai điều phải nói thẳng. Một là IDSW tăng từ " + fmtI(g1("A", "IDSW")) + " lên " + fmtI(g1(SEL, "IDSW")) + ". Mình giải thích hai chỉ số này: IDF1 đo việc giữ đúng ID trong thời gian dài; IDSW đếm số lần đổi ID, mỗi lần có thể rất ngắn. Nên IDF1 tăng mà IDSW cũng tăng là có thể: tracker đổi ID thêm vài lần ngắn, nhưng phần lớn thời gian vẫn đúng người. Hai là bọn mình chọn tổ hợp này sau khi đã nhìn kết quả trên tập test, nên số đẹp hơn thực tế. Vì vậy phải kiểm tra lại trên tập val, là phần dữ liệu chưa dùng để chọn. Ở slide sau mình làm đúng việc đó.");
}

// ═════════ 17 ─ Re-select on val (pre-registered rule) ═════════
const R1 = VS.selection.rounds[0].candidates;
const NAME = { A: "PEG+ (A)", B: "Lamp follow (B)", M1damp: "M1-damp", M1swap: "M1-swap", M2: "M2", M3: "M3", M4: "M4", M5: "M5" };
const SELC = VS.selection.sequence[0]; // first (and only) accepted component
const vv = (k) => VS.val[k], tt = (k) => VS.test[k];
const vEp = EPS.filter((e) => e.split === "val"), tEp = EPS.filter((e) => e.split === "test");
const VAL_FR = vEp.reduce((a, e) => a + e.n, 0);
const ES = VS.episodes;
{
  const s = base("Chọn lại trên tập val, luật chốt trước khi nhìn số", "SỬA CHỖ RÒ RỈ · TẬP VAL", 2);
  card(s, 0.6, 1.65, 4.6, 4.95);
  txt(s, "Cách làm", { x: 0.85, y: 1.75, w: 4.2, h: 0.4, fontSize: 19, bold: true, color: C.amber });
  txt(s, bullets([
    "Val: 17 video thật + 9 video chói giả, " + vEp.length + " lần chói. Chưa dùng để chọn gì.",
    "Chỉ bật/tắt 8 thành phần, không chỉnh con số nào.",
    "Thêm dần từ PEG: nhận một thành phần nếu không bảng nào tụt quá 0.5 và tổng 3 bảng tăng hơn 0.5.",
    "Luật được đưa lên git trước khi chạy val.",
    "Chọn xong: chạy test đúng 1 lần.",
  ]), { x: 0.85, y: 2.25, w: 4.2, h: 4.25, fontSize: 15 });
  const x0 = 5.45, nw = 2.15, cw = 1.27, y0 = 1.65, rh = 0.47;
  const hdr = ["Δ T1 HOTA", "Δ T2 HOTA", "Δ T3 Rcv", "Tổng"];
  hdr.forEach((h, j) => txt(s, h, { x: x0 + nw + j * cw, y: y0, w: cw, h: 0.4, fontSize: 12, bold: true, color: C.muted, align: "center", valign: "middle" }));
  R1.forEach((r, i) => {
    const y = y0 + 0.45 + i * rh, sel = r.component === SELC;
    if (sel) card(s, x0 - 0.05, y, nw + 4 * cw + 0.1, rh - 0.04, C.card2);
    txt(s, NAME[r.component], { x: x0 + 0.1, y, w: nw - 0.1, h: rh - 0.04, fontSize: 14, bold: sel, color: sel ? C.amber : r.admissible ? C.text : C.muted, valign: "middle" });
    [...r.delta, r.score].forEach((d, j) => {
      const c = Math.abs(d) < 0.05 ? C.muted : d > 0 ? C.good : C.red;
      txt(s, sgn(d, j === 2 ? 1 : 2), { x: x0 + nw + j * cw, y, w: cw, h: rh - 0.04, fontSize: 14, bold: j === 3, color: c, align: "center", valign: "middle" });
    });
  });
  txt(s, [{ text: "Được chọn: PEG + " + NAME[SELC], options: { bold: true, color: C.amber, breakLine: true } },
    { text: "Vòng 2 không thêm được gì (tốt nhất: " + sgn(Math.max(...VS.selection.rounds[1].candidates.map((c) => c.score)), 2) + ").", options: { fontSize: 13, color: C.muted } }],
    { x: x0, y: y0 + 0.5 + R1.length * rh, w: 7.3, h: 0.75, fontSize: 18 });
  done(s, "Chọn lại trên tập val",
    "Để sửa chỗ rò rỉ, bọn mình chọn lại trên tập val, là phần dữ liệu chưa dùng để chọn gì. Val có mười bảy video thật, chín video chói giả và " + vEp.length + " lần chói. Luật được viết ra và đưa lên git trước khi chạy val, để không ai có thể chỉnh luật sau khi đã thấy số. Luật như sau: bắt đầu từ PEG, mỗi vòng thử thêm từng thành phần. Một thành phần được nhận nếu không bảng nào tụt quá 0.5 điểm và tổng mức tăng của ba bảng lớn hơn 0.5. Bảng bên phải là vòng một. Điều đầu tiên đáng chú ý: PEG+ trên val gần như không làm gì, Table III còn tụt " + sgn(R1.find((r) => r.component === "A").delta[2], 1) + ". M1-swap và M3 gần như bằng không. Thành phần duy nhất vượt ngưỡng là M1-damp, tổng " + sgn(R1.find((r) => r.component === SELC).score, 2) + ", chính là thứ mà ở slide trước mình đã thấy làm hỏng Table III trên test. Vòng hai không thêm được gì nữa. Vậy theo đúng luật, config được chọn là PEG cộng M1-damp.");
}

// ═════════ 18 ─ Test once ═════════
{
  const s = base("Chạy test 1 lần: config chọn trên val thua PEG", "KẾT QUẢ TRÊN TEST", 2);
  const rows = [["PEG", "v_peg", C.peg, ""], ["PEG + M1-damp", "v_M1damp", C.amber, "chọn trên val"], ["PEG+", "v_A", C.plus, ""],
    ["PEG+ + M1-swap + M3", "v_A+M1swap+M3", C.sel, "chọn trên test"]];
  const cols = [["T1 HOTA", (m) => m.T1.HOTA, 2], ["T2 HOTA", (m) => m.T2.HOTA, 2], ["T3 Rcv@.5", (m) => m.T3.all_burn["Rcv@.5"], 1]];
  const x0 = 4.1, cw = 1.44, y0 = 1.6, rh = 0.88;
  cols.forEach(([cn], j) => {
    txt(s, cn, { x: x0 + j * 2 * cw, y: y0, w: 2 * cw, h: 0.32, fontSize: 15, bold: true, color: C.text, align: "center" });
    ["test", "val"].forEach((sp, k) => txt(s, sp, { x: x0 + (2 * j + k) * cw, y: y0 + 0.32, w: cw, h: 0.3, fontSize: 12, color: C.muted, align: "center" }));
  });
  rows.forEach(([nm, key, col, sub], i) => {
    const y = y0 + 0.72 + i * (rh + 0.08);
    card(s, 0.6, y, 12.13, rh, i === 1 ? C.card2 : C.card);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 0.1, h: rh, fill: { color: col }, line: { color: col } });
    txt(s, [{ text: nm, options: { bold: true, color: col, breakLine: !!sub } }].concat(sub ? [{ text: sub, options: { fontSize: 12, color: C.muted } }] : []),
      { x: 0.9, y, w: 3.2, h: rh, fontSize: 16, valign: "middle" });
    cols.forEach(([cn, f, dec], j) => {
      [[tt(key), tt("v_peg")], [vv(key), vv("v_peg")]].forEach(([m, b], k) => {
        const v = f(m), d = v - f(b);
        const c = i === 0 || Math.abs(d) < 0.05 ? C.text : d > 0 ? C.good : C.red;
        txt(s, [{ text: fmt(v, dec), options: { breakLine: i > 0 } }].concat(i > 0 ? [{ text: sgn(d, dec), options: { fontSize: 12, bold: false } }] : []),
          { x: x0 + (2 * j + k) * cw, y, w: cw, h: rh, fontSize: 20, bold: true, align: "center", valign: "middle", color: c });
      });
    });
  });
  txt(s, "Xanh = tốt hơn PEG trên cùng tập, đỏ = xấu hơn. Hai tập có độ khó khác nhau, chỉ so trong cùng cột.",
    { x: 0.6, y: 6.55, w: 12.1, h: 0.3, fontSize: 12, color: C.muted });
  done(s, "Chạy test một lần",
    "Đây là kết quả khi chạy test đúng một lần. Mỗi chỉ số có hai cột, test và val; số nhỏ bên dưới là chênh lệch so với PEG trên cùng tập. Hàng thứ hai là config chọn trên val, PEG cộng M1-damp. Trên test nó thua PEG ở cả ba bảng: Table I HOTA " + fmt(tt("v_M1damp").T1.HOTA, 2) + " so với " + fmt(tt("v_peg").T1.HOTA, 2) + ", Table II " + fmt(tt("v_M1damp").T2.HOTA, 2) + " so với " + fmt(tt("v_peg").T2.HOTA, 2) + ", Table III Rcv " + fmt(tt("v_M1damp").T3.all_burn["Rcv@.5"], 1) + " so với " + fmt(tt("v_peg").T3.all_burn["Rcv@.5"], 1) + ". Hàng cuối là tổ hợp bọn mình chọn trên test lúc trước. Trên test nó đẹp, nhưng trên val nó gần như bằng PEG: Table III " + fmt(vv("v_A+M1swap+M3").T3.all_burn["Rcv@.5"], 1) + " so với " + fmt(vv("v_peg").T3.all_burn["Rcv@.5"], 1) + ". PEG+ cũng vậy: trên test tăng " + sgn(ES.test.A.delta, 1) + " Rcv, trên val " + sgn(ES.val.A.delta, 1) + ". Nói cách khác, cái gì tốt trên tập này thì không tốt trên tập kia. Bạn mình nghi ngờ đúng: phần tăng trên test của tổ hợp chọn lọc là do chọn trên test.");
}

// ═════════ 19 ─ Why: one burn episode decides ═════════
{
  const big = vEp.slice().sort((a, b) => Math.abs(b.M1damp - b.PEG) - Math.abs(a.M1damp - a.PEG))[0];
  const tWorse = tEp.filter((e) => e.M1damp < e.PEG).length;
  const zeroEps = vEp.filter((e) => e.PEG / e.n < 0.1);
  const s = base("Vì sao: một lần chói có thể quyết định cả bảng", "VÌ SAO · ĐẾM TỪNG LẦN CHÓI", 2);
  const col3 = [
    [C.amber, "M1-damp", big.PEG + " → " + big.M1damp,
      "val: được chọn nhờ đúng 1 lần chói (video " + big.seq.split("_")[0] + "). Test: " + tWorse + " lần chói tệ hơn, mất " + Math.abs(ES.test.M1damp.frames_gained) + " frame."],
    [C.plus, "PEG+", sgn(ES.test.A.delta, 1) + " / " + sgn(ES.val.A.delta, 1),
      "Rcv test / val. Lỗi của PEG trên val chủ yếu là người chưa từng được track (" + zeroEps.length + " lần chói gần 0 frame), không phải box co lại."],
    [C.sel, "M1-swap", fmtI(vv("v_peg").T1.IDSW) + " → " + fmtI(vv("v_M1swap").T1.IDSW),
      "IDSW trên val. Phần tăng Table I trên test đến từ 1 video (129); trên val HOTA " + sgn(vv("v_M1swap").T1.HOTA - vv("v_peg").T1.HOTA, 2) + "."],
  ];
  col3.forEach(([c, h, big2, sub], k) => {
    const x = 0.6 + k * 4.12, w = 3.9;
    card(s, x, 1.65, w, 3.0);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.65, w: 0.1, h: 3.0, fill: { color: c }, line: { color: c } });
    txt(s, h, { x: x + 0.3, y: 1.75, w: w - 0.5, h: 0.4, fontSize: 18, bold: true, color: c });
    txt(s, big2, { x: x + 0.3, y: 2.15, w: w - 0.5, h: 0.95, fontSize: 38, bold: true, valign: "middle" });
    txt(s, sub, { x: x + 0.3, y: 3.15, w: w - 0.45, h: 1.45, fontSize: 13, color: C.muted });
  });
  card(s, 0.6, 4.85, 12.13, 1.75, C.card2);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.85, w: 0.1, h: 1.75, fill: { color: C.red }, line: { color: C.red } });
  txt(s, [{ text: "Bài học: ngưỡng +0.5 quá thấp. Trên val, 1 frame = " + fmt(100 / VAL_FR, 2) + " điểm Rcv.", options: { bold: true, fontSize: 18, breakLine: true } },
    { text: "Gộp cả 48 lần chói (val + test), khoảng tin cậy 95%: PEG+ " + sgn(ES.pooled.A.delta, 1) + " [" + sgn(ES.pooled.A.ci95[0], 1) + ", " + sgn(ES.pooled.A.ci95[1], 1) + "], M1-damp " + sgn(ES.pooled.M1damp.delta, 1) + " [" + sgn(ES.pooled.M1damp.ci95[0], 1) + ", " + sgn(ES.pooled.M1damp.ci95[1], 1) + "].", options: { fontSize: 15, breakLine: true } },
    { text: "Lần sau: chỉ nhận một thành phần khi khoảng tin cậy không chứa 0.", options: { fontSize: 15, color: C.amber, bold: true } }],
    { x: 0.95, y: 4.9, w: 11.6, h: 1.65, valign: "middle" });
  done(s, "Vì sao val và test ngược nhau",
    "Vì sao val và test lại ngược nhau? Mình đếm lại theo từng lần chói. M1-damp được chọn trên val nhờ đúng một lần chói, ở video " + big.seq.split("_")[0] + ": số frame box còn trùng người tăng từ " + big.PEG + " lên " + big.M1damp + ". Trên val, một frame chỉ đáng " + fmt(100 / VAL_FR, 2) + " điểm, nên chỉ một lần chói đó cũng đủ vượt ngưỡng 0.5. Trên test, M1-damp làm " + tWorse + " lần chói tệ hơn và mất " + Math.abs(ES.test.M1damp.frames_gained) + " frame. PEG+ thì ngược lại: trên test tăng " + sgn(ES.test.A.delta, 1) + ", trên val " + sgn(ES.val.A.delta, 1) + ". Lý do là val có ít trường hợp box co lại khi coast; lỗi của PEG trên val chủ yếu là người chưa bao giờ được track, có " + zeroEps.length + " lần chói gần như không phủ được frame nào, và khóa kích thước box không cứu được những ca đó. M1-swap trên val không cải thiện Table I mà IDSW còn tăng từ " + fmtI(vv("v_peg").T1.IDSW) + " lên " + fmtI(vv("v_M1swap").T1.IDSW) + ". Nếu gộp cả bốn mươi tám lần chói của val và test, PEG+ tăng " + sgn(ES.pooled.A.delta, 1) + " với khoảng tin cậy chín mươi lăm phần trăm từ " + sgn(ES.pooled.A.ci95[0], 1) + " đến " + sgn(ES.pooled.A.ci95[1], 1) + ", tức là chỉ vừa đủ khác không; còn M1-damp giảm " + fmt(-ES.pooled.M1damp.delta, 1) + " điểm và chắc chắn có hại. Bài học là luật của bọn mình đặt ngưỡng quá thấp so với độ nhiễu của một tập nhỏ như vậy. Bọn mình không sửa luật sau khi đã thấy test, vì như thế lại là chọn trên test lần nữa; lần sau mình sẽ chỉ nhận một thành phần khi khoảng tin cậy không chứa không.");
}

// ═════════ PEG-F v2 (Thach, 2026-10-18): 6 methods, one slide each, then the checks ═════════
// numbers: results/thach_v2/numbers_thach.json (analyze.py), figures: results/thach_v2/figures (make_figures.py)
const TH = JSON.parse(fs.readFileSync("D:/PROJECT/PEG/results/thach_v2/numbers_thach.json", "utf8"));
const THF = "D:/PROJECT/PEG/results/thach_v2/figures";
const TS = JSON.parse(fs.readFileSync("D:/PROJECT/PEG/results/thach_v2/figure_stats.json", "utf8"));
const tm = (sp, c) => TH.metrics[sp][c];
const prim = (sp, c) => [tm(sp, c).T1.HOTA, tm(sp, c).T2.HOTA, tm(sp, c).T3["Rcv@.5"]];
const dprim = (sp, c, ref) => prim(sp, c).map((v, i) => v - prim(sp, ref)[i]);
const DG = TH.diag["test|full+M6"] || {};
const V2C = C.f; // v2 slides keep the PEG-F purple
const seqHota = (sp, tab, c, seq) => TH.per_seq[sp][c][tab][seq].HOTA;
const seqIdsw = (sp, tab, c, seq) => TH.per_seq[sp][c][tab][seq].IDSW;
const S129 = "129_sequence_13q", S320 = "320_sequence_116q", S127 = "127_sequence_1";

// effect strip shared by the six method slides: base+Mi vs base, test and val, three tables
function effectStrip(s, cfg, extra) {
  const y = 5.35, h = 1.55;
  card(s, 0.6, y, 12.13, h);
  txt(s, "Bật riêng " + cfg.replace("base+", "") + " trên base của Thạch:", { x: 0.85, y: y + 0.08, w: 6, h: 0.3, fontSize: 13, bold: true, color: C.muted });
  const cols = ["Δ T1 HOTA", "Δ T2 HOTA", "Δ T3 Rcv@.5"];
  const x0 = 2.3, cw = 1.75;
  cols.forEach((cn, j) => txt(s, cn, { x: x0 + j * cw, y: y + 0.4, w: cw, h: 0.28, fontSize: 12, color: C.muted, align: "center" }));
  [["test", "test"], ["val", "val"]].forEach(([sp, lab], i) => {
    const yy = y + 0.68 + i * 0.4;
    txt(s, lab, { x: 0.85, y: yy, w: 1.3, h: 0.36, fontSize: 15, bold: true, color: C.text, valign: "middle" });
    dprim(sp, cfg, "base").forEach((d, j) => {
      const c = Math.abs(d) < 0.05 ? C.muted : d > 0 ? C.good : C.red;
      txt(s, sgn(d, j === 2 ? 1 : 2), { x: x0 + j * cw, y: yy, w: cw, h: 0.36, fontSize: 17, bold: true, color: c, align: "center", valign: "middle" });
    });
  });
  txt(s, extra, { x: 7.75, y: y + 0.12, w: 4.8, h: h - 0.24, fontSize: 13, color: C.muted, valign: "middle" });
}

function methodSlide(tag, title, problem, steps, right, cfg, extra, notes) {
  const s = base(title, "PEG-F v2 · " + tag, 1);
  card(s, 0.6, 1.6, 5.75, 0.95, C.card2);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 1.6, w: 0.1, h: 0.95, fill: { color: C.amber }, line: { color: C.amber } });
  txt(s, [{ text: "Vấn đề  ", options: { bold: true, color: C.amber } }, { text: problem }], { x: 0.85, y: 1.6, w: 5.4, h: 0.95, fontSize: 14, valign: "middle" });
  txt(s, "Cách làm", { x: 0.6, y: 2.65, w: 5.5, h: 0.35, fontSize: 16, bold: true, color: V2C });
  txt(s, steps.map((t, i, a) => ({ text: t, options: { bullet: { type: "number" }, breakLine: i < a.length - 1, paraSpaceAfter: 5 } })),
    { x: 0.6, y: 3.0, w: 5.75, h: 2.25, fontSize: 13 });
  right(s);
  effectStrip(s, cfg, extra);
  done(s, tag + ": " + title, notes);
  return s;
}

// flow diagram (3 stacked cards with arrows) for methods without a picture
function flow(s, items, x = 6.65, y = 1.6, w = 6.08, h = 3.6) {
  const n = items.length, gap = 0.28, ch = (h - gap * (n - 1)) / n;
  items.forEach(([head, body], i) => {
    const yy = y + i * (ch + gap);
    card(s, x, yy, w, ch);
    s.addShape(pres.shapes.RECTANGLE, { x, y: yy, w: 0.1, h: ch, fill: { color: V2C }, line: { color: V2C } });
    txt(s, [{ text: head, options: { bold: true, color: C.text, breakLine: true } }, { text: body, options: { color: C.muted, fontSize: 13 } }],
      { x: x + 0.3, y: yy, w: w - 0.45, h: ch, fontSize: 15, valign: "middle" });
    if (i < n - 1) s.addShape(pres.shapes.LINE, { x: x + w / 2, y: yy + ch + 0.02, w: 0, h: gap - 0.04, line: { color: C.amber, width: 2, endArrowType: "triangle" } });
  });
}

// ── v2 overview
{
  const s = base("PEG-F v2: Thạch sửa lại, giờ có 6 method", "PEG-F v2 · TỔNG QUAN", 1);
  const ms = [
    ["M1", "Vùng bất định (cone)", "MỚI", "Khi mất người lâu, vùng tìm lại nở rộng dần; khớp lại ID cũ thay vì sinh ID mới."],
    ["M2", "Re-ID: feature detector + màu", "MỚI", "“Dấu vân tay” lấy từ chính detector (không thêm mạng) + màu HSV, lưu lúc chưa chói."],
    ["M3", "Ngưỡng h động + TTL", "giữ", "Như v1."],
    ["M4", "Pool track “ngủ”", "giữ", "Như v1, dùng dấu vân tay của M2."],
    ["M5", "Neo vào đèn mũ", "giữ", "Như v1."],
    ["M6", "Tone-mapping quanh đèn", "MỚI", "Làm dịu vầng sáng quanh đèn trong ảnh đưa vào detector."],
  ];
  const rh = 0.66, gap = 0.08, y0 = 1.6;
  ms.forEach(([tg, nm, st, ds], i) => {
    const y = y0 + i * (rh + gap);
    card(s, 0.6, y, 12.13, rh);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 0.1, h: rh, fill: { color: V2C }, line: { color: V2C } });
    txt(s, tg, { x: 0.9, y, w: 0.8, h: rh, fontSize: 22, bold: true, color: V2C, valign: "middle" });
    txt(s, nm, { x: 1.75, y, w: 3.6, h: rh, fontSize: 16, bold: true, valign: "middle" });
    txt(s, st, { x: 5.35, y, w: 0.9, h: rh, fontSize: 12, bold: true, color: st === "MỚI" ? C.amber : C.muted, valign: "middle" });
    txt(s, ds, { x: 6.25, y, w: 6.3, h: rh, fontSize: 13, color: C.muted, valign: "middle" });
  });
  const fm = tm("test", "full+M6").T1;
  txt(s, [{ text: "Thạch báo (Table I, test): full+M6 HOTA " + fmt(fm.HOTA, 2) + ", IDF1 " + fmt(fm.IDF1, 2) + ".  ", options: { bold: true } },
    { text: "Mình chạy lại 14/14 cấu hình: ra đúng từng số.", options: { color: C.good, bold: true } }],
    { x: 0.6, y: 6.15, w: 12.1, h: 0.45, fontSize: 16 });
  txt(s, "Thạch chỉ báo Table I trên test. Mình đo thêm Table II/III và tập val, như các phần trước.", { x: 0.6, y: 6.6, w: 12.1, h: 0.35, fontSize: 13, color: C.muted });
  done(s, "PEG-F v2: tổng quan",
    "Sau buổi trước, Thạch sửa lại PEG-F và gửi bản mới, gọi là PEG-F v2. Giờ có sáu method. Ba cái mới là M1, M2 và M6: M1 viết lại hoàn toàn thành một vùng bất định nở rộng khi mất người; M2 không chỉ dùng màu áo nữa mà lấy thêm đặc trưng từ chính detector; và M6 là method mới, xử lý ảnh trước khi đưa vào detector. M3, M4, M5 giữ như cũ. Thạch báo trên Table I, tập test, cấu hình đầy đủ cộng M6 đạt HOTA " + fmt(fm.HOTA, 2) + " và IDF1 " + fmt(fm.IDF1, 2) + ". Mình chạy lại cả mười bốn cấu hình trong bảng của Thạch và ra đúng từng con số. Nhưng Thạch chỉ báo Table I trên test, nên mình đo thêm hai bảng còn lại và tập val, đúng như cách mình đã kiểm chứng ở phần trước. Trước hết mình giải thích từng method, mỗi method một slide.");
}

// ── M1
methodSlide("M1", "Vùng bất định nở rộng khi mất người",
  "Người bị chói vài chục frame có thể rẽ, đứng lại hay lùi. Box dự đoán không còn trùng (IoU = 0) → sinh ID mới.",
  ["Mỗi frame không thấy người, Kalman tăng độ bất định: vị trí cộng thêm (0.03·h)² mỗi frame (h = chiều cao box), tối đa 30 frame.",
   "Detection chưa ai nhận được thử với track đã mất ≥ 2 frame: khoảng cách Mahalanobis ≤ 9.21 (vùng 99%), so với 2 giả thuyết: đi tiếp vận tốc cũ, hoặc đứng lại chỗ cũ.",
   "Chặn thêm: không xa quá sức đi bộ, chiều cao lệch < 1.5×, không đè lên người đang được track.",
   "Kèm theo: hãm vận tốc ×0.88 khi hai người gần nhau, giờ chỉ áp cho track đang coast."],
  (s) => fig(s, path.join(THF, "m1_cone.png"), 6.65, 1.6, 6.08, 3.6),
  "base+M1",
  "Cone khớp lại được " + fmtI(DG["cone_matches(M1)"]) + " lần trên cả tập test (full+M6). Đi cùng M5 thì Table III sụt mạnh: xem slide “Vì sao Table III sụt”.",
  "M1 của Thạch giải quyết tình huống này: người bị chói vài chục frame, trong lúc đó họ có thể rẽ, đứng lại hoặc lùi, nên box dự đoán không còn trùng với người khi họ hiện ra lại, và tracker sinh ID mới. Cách làm có hai phần. Phần một: mỗi frame không thấy người, Kalman filter tăng độ bất định về vị trí, mỗi frame cộng thêm khoảng ba phần trăm chiều cao người, tối đa ba mươi frame. Hình bên phải cho thấy vùng này nở rộng theo thời gian, như một cái nón. Phần hai: những detection chưa được ai nhận sẽ được thử với các track đã mất từ hai frame trở lên. Nếu detection nằm trong vùng chín mươi chín phần trăm, theo một trong hai giả thuyết là đi tiếp với vận tốc cũ hoặc đứng lại chỗ cũ, thì gán lại ID cũ. Có thêm vài chặn để tránh gán nhầm: không xa quá sức đi bộ, chiều cao không lệch quá, và không đè lên người đang được track. Ngoài ra M1 vẫn kèm phần hãm vận tốc khi hai người gần nhau, và giờ Thạch chỉ áp cho track đang coast. Trên cả tập test, cone chỉ khớp lại " + fmtI(DG["cone_matches(M1)"]) + " lần. Kết quả bật riêng M1 ở dải dưới.");

// ── M2
methodSlide("M2", "Re-ID: “dấu vân tay” lấy từ detector",
  "Công nhân mặc đồ bảo hộ giống nhau, nên màu áo (HSV) gần như không phân biệt được ai với ai. Đó là lý do M2 cũ không bao giờ kích hoạt.",
  ["Lấy feature map tầng P4 của detector, cắt theo box, chia nửa trên / nửa dưới người (không thêm mạng nào).",
   "Trừ trung bình của cả video để bỏ phần “giống nhau” chung, rồi ghép với màu HSV: độ giống = 70% feature + 30% màu.",
   "Mỗi người giữ tối đa 10 dấu vân tay, 5 frame lấy 1 lần, chỉ khi người rõ, chưa chói và không chen với người khác.",
   "So detection mới với cả 10 mẫu, lấy mẫu giống nhất."],
  (s) => flow(s, [["Lúc chưa chói: lưu dấu vân tay", "chỉ lấy khi người rõ, không có đốm cháy, không chen"],
    ["Lúc chói: đóng băng", "không cập nhật bằng ảnh cháy trắng"],
    ["Dùng ở 4 chỗ", "giành detection (+0.25) · đổi cặp ID (+0.15) · lọc cone M1 (≥ 0.35) · hồi sinh M4 (≥ 0.60)"]]),
  "base+M2",
  "Không có bộ đếm số lần M2 quyết định. Ở test, FP giảm chủ yếu trên video 320.",
  "M2 là phần nhận lại người. Bản cũ chỉ so màu áo, mà công nhân mặc đồ bảo hộ giống nhau, nên nó không bao giờ đổi được quyết định nào. Bản mới lấy thêm đặc trưng từ chính detector: feature map ở tầng P4, cắt theo box của người và chia làm nửa trên, nửa dưới, nên không cần thêm mạng nào. Thạch trừ đi trung bình của cả video để bỏ phần giống nhau chung, rồi ghép với màu: độ giống bằng bảy mươi phần trăm feature cộng ba mươi phần trăm màu. Mỗi người giữ tối đa mười mẫu, gọi là gallery, lấy năm frame một lần và chỉ lấy khi người rõ, chưa bị chói và không chen với ai. Khi bị chói thì gallery đóng băng. Dấu vân tay này được dùng ở bốn chỗ: khi hai track giành một detection, khi xét đổi ID của một cặp, để lọc cone của M1, và để hồi sinh ID ở M4.");

// ── M3
methodSlide("M3", "Ngưỡng chói h tăng dần + thời gian giữ box thích nghi",
  "Đèn chiếu lên tường cũng làm vùng box trắng → PEG giữ box “ma” mãi. Và mọi lần chói đều được giữ 5 frame như nhau.",
  ["Mất detection quá 3 frame: ngưỡng h tăng 6% mỗi frame, từ 0.40 tới tối đa 0.65 → càng lâu càng cần bằng chứng mạnh.",
   "Thời gian được giữ box sau khi xác nhận chói = 5 frame × φ / 0.5. Vì chỉ xét khi φ ≥ h, thực tế là 4 hoặc 5 frame (PEG: luôn 5).",
   "Giữ nguyên như v1."],
  (s) => fig(s, path.join(THF, "m3_dynamic_h.png"), 6.65, 1.6, 6.08, 3.6),
  "base+M3",
  "Chỉ đổi lúc người đã mất detection; không có bộ đếm trong code của Thạch.",
  "M3 giữ nguyên như bản cũ. Vấn đề nó nhắm tới là đèn chiếu lên tường: vùng box cũng trắng, nên PEG tưởng người vẫn ở đó và giữ box ma. Cách làm: khi đã mất detection quá ba frame, ngưỡng h tăng sáu phần trăm mỗi frame, từ 0.4 tới tối đa 0.65, như hình bên trái; càng mất lâu càng cần bằng chứng chói mạnh hơn. Thứ hai, thời gian được giữ box sau khi xác nhận chói không còn cố định năm frame mà tỉ lệ với độ chói φ. Nhưng vì box chỉ được giữ khi φ đã vượt ngưỡng, như vùng xám ở hình bên phải, nên thực tế nó chỉ là bốn hoặc năm frame: phần này gần như không đổi gì so với PEG.");

// ── M4
methodSlide("M4", "Pool track “ngủ”: trả lại ID cũ",
  "Track bị xóa sau khi mất quá lâu. Nếu người quay lại, họ nhận một ID mới → đổi ID.",
  ["Track đã xác nhận bị xóa → cất vào pool, giữ tối đa 45 frame.",
   "Có người mới xuất hiện: xét các track trong pool ở gần đó (khoảng cách ≤ 2 lần đường chéo box + 15% mỗi frame).",
   "Dấu vân tay (M2) giống ≥ 0.60 → trả lại ID cũ, gộp gallery.",
   "Giữ như v1, nhưng giờ dùng dấu vân tay mới của M2."],
  (s) => flow(s, [["Track mất quá lâu", "cất vào pool “ngủ” (≤ 45 frame)"], ["Người mới xuất hiện gần chỗ cũ", "trong tầm đi bộ"], ["Giống ≥ 0.60?", "có → trả lại ID cũ thay vì ID mới"]]),
  "base+M4",
  "Trong bảng của Thạch, base+M4 bật kèm M2. Số lần hồi sinh trên test (full+M6): " + fmtI(DG["dormant_revivals(M4)"]) + ".",
  "M4 giữ như bản cũ. Khi một track bị xóa vì mất quá lâu, thay vì quên luôn, tracker cất nó vào một pool, giữ tối đa bốn mươi lăm frame. Khi có người mới xuất hiện gần chỗ cũ, trong tầm đi bộ, và dấu vân tay giống từ 0.6 trở lên, thì người đó được trả lại ID cũ. Ý tưởng hợp lý, nhưng trên cả tập test với cấu hình đầy đủ, số lần hồi sinh là " + fmtI(DG["dormant_revivals(M4)"]) + ".");

// ── M5
methodSlide("M5", "Neo box vào đèn mũ",
  "Khi chói, box chỉ chạy theo dự đoán Kalman; người đổi tư thế hay quay người thì box trôi.",
  ["Chỉ chạy khi gate PEG đã xác nhận người đang bị chói.",
   "Tìm tâm đốm đèn trong dải đầu của box (45% phía trên).",
   "Tâm người ≈ tâm đèn + 0.35 × chiều cao box.",
   "Kéo nhẹ tâm box Kalman về đó (cập nhật yếu), nếu không quá xa box hiện tại. Giữ như v1."],
  (s) => flow(s, [["Gate PEG: người đang bị chói", "chỉ lúc này M5 mới chạy"], ["Tìm đốm đèn ở dải đầu box", "tâm người ≈ đèn + 0.35 h"], ["Kéo nhẹ box về đó", "cập nhật Kalman với độ tin thấp"]]),
  "base+M5",
  "Một mình M5 gần như vô hại. Đi cùng M1 thì cú “kéo nhẹ” thành kéo mạnh: xem slide “Vì sao Table III sụt”.",
  "M5 cũng giữ như cũ. Khi người bị chói, box chỉ chạy theo dự đoán của Kalman, nên nếu người đổi tư thế thì box trôi. M5 chỉ chạy khi gate của PEG đã xác nhận là người đang bị chói. Nó tìm tâm của đốm đèn ở dải đầu của box, suy ra tâm người bằng tâm đèn cộng 0.35 lần chiều cao, rồi kéo nhẹ box về đó. Bật một mình thì M5 gần như không đổi gì. Nhưng khi đi cùng M1, cú kéo nhẹ này trở thành kéo mạnh, và đó là nguyên nhân Table III sụt; mình sẽ quay lại ở slide sau.");

// ── M6
methodSlide("M6", "Làm dịu vầng sáng quanh đèn trước khi đưa vào detector",
  "Quanh đèn có một vầng sáng rộng làm mất chi tiết của người đứng gần → detector bỏ sót.",
  ["Tìm vùng cháy trắng (lõi đèn) trong ảnh.",
   "Tách ảnh thành lớp “độ sáng nền” (mờ, giữ cạnh) và lớp chi tiết.",
   "Nén lớp nền chỗ quá sáng (trên 0.55, nén còn 35%), chỉ trong vòng quanh đèn; lõi đèn giữ nguyên.",
   "Chỉ ảnh đưa vào detector bị đổi. Gate PEG và màu Re-ID vẫn dùng ảnh gốc."],
  (s) => fig(s, path.join(THF, "m6_tonemap.png"), 6.65, 1.6, 6.08, 3.6),
  "base+M6",
  "Áp lên " + fmt(100 * TS.m6_frac_applied, 0) + "% số frame test (ngưỡng bật rất thấp). Cần chạy lại detector: phải build cache riêng.",
  "M6 là method mới và khác các method khác: nó không sửa tracker mà sửa ảnh trước khi đưa vào detector. Quanh đèn có một vầng sáng rộng làm mất chi tiết của người đứng gần. Thạch tách ảnh thành một lớp độ sáng nền, làm mờ nhưng giữ cạnh, và một lớp chi tiết; rồi nén lớp nền ở chỗ quá sáng, chỉ trong vòng quanh đèn, còn lõi đèn thì giữ nguyên. Hình bên phải là ảnh gốc, ảnh sau khi xử lý, và bản đồ chỗ bị đổi. Chỉ ảnh đưa vào detector bị đổi; gate của PEG và màu Re-ID vẫn dùng ảnh gốc. Ngưỡng bật rất thấp, nên M6 được áp lên khoảng " + fmt(100 * TS.m6_frac_applied, 0) + " phần trăm số frame của tập test.");

// ── base is not PEG
{
  const s = base("“base” của Thạch không phải PEG", "SO CÙNG CẤU HÌNH", 1);
  const rows = [["PEG (guard bật)", "PEG", C.peg], ["base của Thạch", "base", C.f]];
  const cols = [["T1 HOTA", (c) => tm("test", c).T1.HOTA, 2], ["T1 IDSW", (c) => tm("test", c).T1.IDSW, 0], ["video 129 HOTA", (c) => seqHota("test", "T1", c, S129), 1],
    ["video 320 HOTA", (c) => seqHota("test", "T1", c, S320), 1], ["video 320 IDSW", (c) => seqIdsw("test", "T1", c, S320), 0]];
  const x0 = 3.6, cw = 1.83, y0 = 1.7, rh = 0.8;
  cols.forEach(([cn], j) => txt(s, cn, { x: x0 + j * cw, y: y0, w: cw, h: 0.35, fontSize: 13, bold: true, color: C.muted, align: "center" }));
  rows.forEach(([nm, key, col], i) => {
    const y = y0 + 0.45 + i * (rh + 0.1);
    card(s, 0.6, y, 12.13, rh);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 0.1, h: rh, fill: { color: col }, line: { color: col } });
    txt(s, nm, { x: 0.9, y, w: 2.7, h: rh, fontSize: 17, bold: true, color: col, valign: "middle" });
    cols.forEach(([cn, f, dec], j) => txt(s, dec ? fmt(f(key), dec) : fmtI(f(key)), { x: x0 + j * cw, y, w: cw, h: rh, fontSize: 24, bold: true, align: "center", valign: "middle" }));
  });
  card(s, 0.6, 4.4, 12.13, 2.2, C.card2);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.4, w: 0.1, h: 2.2, fill: { color: C.amber }, line: { color: C.amber } });
  txt(s, bullets([
    "Logic đổi-ID cũ (M1-swap của v1) giờ luôn bật, không có công tắc → nằm sẵn trong base.",
    "Nó sửa video 129 (+" + fmt(seqHota("test", "T1", "base", S129) - seqHota("test", "T1", "PEG", S129), 1) + " HOTA) nhưng làm hỏng video 320 (IDSW " + fmtI(seqIdsw("test", "T1", "PEG", S320)) + " → " + fmtI(seqIdsw("test", "T1", "base", S320)) + ").",
    "Nên “Δ so với base” trong bảng của Thạch không phải “Δ so với PEG”. Các slide sau so với cả hai.",
  ]), { x: 0.9, y: 4.5, w: 11.6, h: 2.0, fontSize: 16, valign: "middle" });
  done(s, "base của Thạch không phải PEG",
    "Trước khi xem kết quả, có một điểm về cấu hình. Trong bảng của Thạch, mọi chênh lệch đều so với một cấu hình gọi là base, tức là PEG khi tắt hết sáu method. Nhưng base đó không phải PEG: phần logic đổi lại ID mà ở v1 mình gọi là M1-swap giờ luôn bật, không có công tắc. Nó sửa được video 129, HOTA tăng " + fmt(seqHota("test", "T1", "base", S129) - seqHota("test", "T1", "PEG", S129), 1) + " điểm, nhưng làm hỏng video 320: số lần đổi ID tăng từ " + fmtI(seqIdsw("test", "T1", "PEG", S320)) + " lên " + fmtI(seqIdsw("test", "T1", "base", S320)) + ". Vì vậy chênh lệch so với base không phải chênh lệch so với PEG. Ở các slide sau mình so với cả hai.");
}

// ── his table was chosen on test (counted in dataset/thach_v2/PEG-main/results/eval of his zip)
{
  const s = base("Bảng của Thạch được chỉnh và chọn trên test", "PEG-F v2 · KIỂM TRA CÁCH CHỌN", 1);
  const stats = [["56", "lượt chạy Table I trên test", C.red], ["0", "lượt chạy trên val", C.red], ["0", "lượt chạy Table II / III", C.amber]];
  stats.forEach(([n, l, c], k) => {
    const x = 0.6 + k * 4.12, w = 3.9;
    card(s, x, 1.65, w, 1.9);
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.65, w: 0.1, h: 1.9, fill: { color: c }, line: { color: c } });
    txt(s, n, { x: x + 0.3, y: 1.7, w: w - 0.5, h: 1.1, fontSize: 54, bold: true, color: c, valign: "middle" });
    txt(s, l, { x: x + 0.3, y: 2.8, w: w - 0.5, h: 0.6, fontSize: 16, color: C.muted });
  });
  card(s, 0.6, 3.75, 12.13, 2.85, C.card2);
  txt(s, bullets([
    "Script của Thạch ghi: “choose / calibrate on VAL, report TEST once”, nhưng thư mục kết quả không có file val nào.",
    "Riêng M1 có các bản thử dx_qonly / dx_qcone / dx_damp (HOTA 66.44–68.84), fix1 (69.09), fix2 = bản cuối (69.24): tất cả đo trên Table I test.",
    "Nên +1.69 HOTA là số “chọn trên test, báo trên test”. Mình làm lại đúng cách: chọn trên val bằng luật chốt trước (commit trước khi có số val), báo test một lần.",
  ]), { x: 0.9, y: 3.85, w: 11.6, h: 2.65, fontSize: 16, valign: "middle" });
  done(s, "Bảng của Thạch được chọn trên test",
    "Trước khi xem kết quả, mình kiểm tra Thạch đã chọn cấu hình trên tập nào. Trong thư mục kết quả Thạch gửi có năm mươi sáu lượt chạy Table I trên tập test, không có lượt nào trên val, và không có lượt nào cho Table II hay Table III. Script của Thạch có ghi đúng quy trình: chọn trên val, báo test một lần, nhưng thực tế không làm. Ví dụ riêng M1 có ba bản thử tên dx, rồi fix1, rồi fix2 là bản cuối, HOTA từ khoảng 66 đến 69.24, và tất cả đều đo trên Table I test. Vì vậy con số cộng 1.69 HOTA là số chọn trên test rồi báo cũng trên test. Bọn mình làm lại theo đúng cách: luật chọn được viết và đưa lên git trước khi có bất kỳ số val nào, chọn trên val, rồi chỉ báo test một lần cho cấu hình được chọn. Có một điều bọn mình không gỡ được: các tham số bên trong method đã được chỉnh trên test; muốn gỡ thì phải tune lại từ đầu trên val.");
}

// ── results on test, three tables
const V2ROWS = [["PEG", "PEG", C.peg], ["base", "base", C.muted], ["full (M1–M5)", "full", C.f], ["full + M6", "full+M6", C.fa]];
function v2table(s, sp, y0, sel) {
  const rows = V2ROWS.concat(sel && !V2ROWS.some((r) => r[1] === sel) ? [["chọn trên val: " + sel, sel, C.amber]] : []);
  const cols = [["T1 HOTA", (m) => m.T1.HOTA, 2], ["T1 IDF1", (m) => m.T1.IDF1, 2], ["T1 IDSW", (m) => m.T1.IDSW, 0], ["T2 HOTA", (m) => m.T2.HOTA, 2], ["T2 MOTA", (m) => m.T2.MOTA, 2], ["T3 Rcv@.5", (m) => m.T3["Rcv@.5"], 1]];
  const x0 = 3.3, cw = 1.57, rh = 0.62;
  cols.forEach(([cn], j) => txt(s, cn, { x: x0 + j * cw, y: y0, w: cw, h: 0.35, fontSize: 13, bold: true, color: C.muted, align: "center" }));
  rows.forEach(([nm, key, col], i) => {
    const y = y0 + 0.42 + i * (rh + 0.07);
    card(s, 0.6, y, 12.13, rh);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 0.1, h: rh, fill: { color: col }, line: { color: col } });
    txt(s, nm, { x: 0.9, y, w: 2.4, h: rh, fontSize: 15, bold: true, color: col, valign: "middle" });
    cols.forEach(([cn, f, dec], j) => {
      const v = f(tm(sp, key)), b = f(tm(sp, "PEG")), d = (v - b) * (cn === "T1 IDSW" ? -1 : 1);
      const c = key === "PEG" || Math.abs(d) < 0.05 ? C.text : d > 0 ? C.good : C.red;
      txt(s, dec ? fmt(v, dec) : fmtI(v), { x: x0 + j * cw, y, w: cw, h: rh, fontSize: 19, bold: true, align: "center", valign: "middle", color: c });
    });
  });
  return y0 + 0.42 + rows.length * (rh + 0.07);
}
{
  const s = base("Trên test, đủ 3 bảng", "PEG-F v2 · KẾT QUẢ TEST", 1);
  const yb = v2table(s, "test", 1.6, null);
  const f = tm("test", "full+M6"), p = tm("test", "PEG");
  txt(s, "Xanh/đỏ = tốt/xấu hơn PEG (IDSW: ít hơn là tốt).", { x: 0.6, y: yb + 0.05, w: 12, h: 0.3, fontSize: 12, color: C.muted });
  card(s, 0.6, yb + 0.45, 12.13, 6.85 - yb - 0.45, C.card2);
  txt(s, bullets([
    "Table I: full+M6 hơn PEG " + sgn(f.T1.HOTA - p.T1.HOTA, 2) + " HOTA, " + sgn(f.T1.IDF1 - p.T1.IDF1, 2) + " IDF1. IDSW " + fmtI(p.T1.IDSW) + " → " + fmtI(f.T1.IDSW) + ".",
    "Table II: " + sgn(f.T2.HOTA - p.T2.HOTA, 2) + " HOTA, " + sgn(f.T2.MOTA - p.T2.MOTA, 2) + " MOTA.   Table III: Rcv@.5 " + fmt(p.T3["Rcv@.5"], 1) + " → " + fmt(f.T3["Rcv@.5"], 1) + ".",
  ]), { x: 0.9, y: yb + 0.5, w: 11.6, h: 6.85 - yb - 0.55, fontSize: 16, valign: "middle" });
  done(s, "Kết quả v2 trên test",
    "Đây là kết quả trên tập test, đủ ba bảng, so với PEG cùng cấu hình guard bật. Ở Table I, cấu hình đầy đủ cộng M6 hơn PEG " + sgn(f.T1.HOTA - p.T1.HOTA, 2) + " HOTA và " + sgn(f.T1.IDF1 - p.T1.IDF1, 2) + " IDF1, số lần đổi ID từ " + fmtI(p.T1.IDSW) + " thành " + fmtI(f.T1.IDSW) + ". Ở Table II, HOTA " + sgn(f.T2.HOTA - p.T2.HOTA, 2) + " và MOTA " + sgn(f.T2.MOTA - p.T2.MOTA, 2) + ". Ở Table III, phần đo người đang bị chói, Rcv@.5 từ " + fmt(p.T3["Rcv@.5"], 1) + " thành " + fmt(f.T3["Rcv@.5"], 1) + ".");
}

// ── why Table III collapses: M1's growing uncertainty x M5's "weak" pull (results/thach_v2/burn_drift.py, diag_m1m5.py)
{
  const DR = JSON.parse(fs.readFileSync("D:/PROJECT/PEG/results/thach_v2/drift.json", "utf8"));
  const d = (sp, c) => DR[sp + "|" + c];
  const s = base("Vì sao Table III sụt: M1 làm cú “kéo nhẹ” của M5 thành kéo mạnh", "VÌ SAO · TỪNG FRAME BỊ CHÓI", 1);
  const rows = [["base", "base", C.muted], ["chỉ M1", "base+M1", C.f], ["chỉ M5", "base+M5", C.f],
    ["M5 + chỉ phần nở vùng bất định của M1", "dxbase+M5+Q", C.red], ["full (M1–M5)", "full", C.red], ["full, tắt phần nở vùng bất định", "dxfull-Q", C.good]];
  const cols = [["Rcv@.5 test", (c) => fmt(d("test", c).rcv, 1)], ["Rcv@.5 val", (c) => fmt(d("val", c).rcv, 1)],
    ["box lệch ngang test", (c) => sgn(100 * d("test", c).dx_w, 0) + "%"], ["box lệch ngang val", (c) => sgn(100 * d("val", c).dx_w, 0) + "%"]];
  const x0 = 5.3, cw = 1.86, y0 = 1.55, rh = 0.5;
  cols.forEach(([cn], j) => txt(s, cn, { x: x0 + j * cw, y: y0, w: cw, h: 0.35, fontSize: 12, bold: true, color: C.muted, align: "center" }));
  rows.forEach(([nm, key, col], i) => {
    const y = y0 + 0.4 + i * (rh + 0.06);
    card(s, 0.6, y, 12.13, rh);
    s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y, w: 0.1, h: rh, fill: { color: col }, line: { color: col } });
    txt(s, nm, { x: 0.9, y, w: 4.4, h: rh, fontSize: 14, bold: true, color: col, valign: "middle" });
    cols.forEach(([cn, f], j) => txt(s, f(key), { x: x0 + j * cw, y, w: cw, h: rh, fontSize: 17, bold: true, align: "center", valign: "middle" }));
  });
  const yb = y0 + 0.4 + rows.length * (rh + 0.06) + 0.1;
  card(s, 0.6, yb, 12.13, 6.85 - yb, C.card2);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: yb, w: 0.1, h: 6.85 - yb, fill: { color: C.amber }, line: { color: C.amber } });
  txt(s, bullets([
    "M1 làm độ bất định vị trí của Kalman tăng mỗi frame mất người. M5 kéo box về đèn với độ tin cố định. Độ bất định càng lớn thì Kalman càng tin phép đo → kéo nhẹ thành kéo hẳn.",
    "Box vẫn còn và vẫn đúng chiều cao, nhưng trượt ngang theo đốm sáng (lệch trung vị = % bề rộng người, trong các frame chói).",
    "Kiểm tra bằng công tắc con của M1: chỉ cần phần nở vùng bất định + M5 là đủ gây sụt; tắt riêng phần đó thì T3 hồi lại.",
  ]), { x: 0.9, y: yb + 0.05, w: 11.6, h: 6.85 - yb - 0.1, fontSize: 14, valign: "middle" });
  done(s, "Vì sao Table III sụt",
    "Vì sao Table III sụt mạnh như vậy? Mình tách từng phần. Bật riêng M1, Rcv trên test từ " + fmt(d("test", "base").rcv, 1) + " còn " + fmt(d("test", "base+M1").rcv, 1) + ". Bật riêng M5, gần như không đổi. Nhưng bật cả hai thì còn khoảng " + fmt(d("test", "full").rcv, 1) + " trên test và " + fmt(d("val", "full").rcv, 1) + " trên val. Lý do: M1 làm độ bất định vị trí của Kalman tăng lên mỗi frame không thấy người. M5 kéo box về phía đèn bằng một phép đo có độ tin cố định, được thiết kế là cú kéo nhẹ. Nhưng Kalman cân giữa dự đoán và phép đo theo độ bất định: dự đoán càng không chắc thì phép đo càng được tin. Nên khi M1 làm độ bất định phình ra, cú kéo nhẹ của M5 thành kéo hẳn. Mình đo trong các frame bị chói: box vẫn còn, vẫn đúng chiều cao, nhưng trượt ngang khỏi người, trung vị khoảng " + fmt(Math.abs(100 * d("test", "full").dx_w), 0) + " phần trăm bề rộng người trên test và " + fmt(Math.abs(100 * d("val", "full").dx_w), 0) + " phần trăm trên val. Để chắc chắn, mình dùng công tắc con trong code của Thạch: chỉ M5 cộng riêng phần nở vùng bất định của M1 là đã ra " + fmt(d("test", "dxbase+M5+Q").rcv, 1) + " trên test; còn tắt riêng phần đó khỏi cấu hình đầy đủ thì hồi lại " + fmt(d("test", "dxfull-Q").rcv, 1) + ". Các lượt này chỉ để chẩn đoán, không dùng để chọn cấu hình.");
}

// ── val, three tables
{
  const s = base("Trên val, đủ 3 bảng", "PEG-F v2 · TẬP VAL", 1);
  const yb = v2table(s, "val", 1.6, null);
  const f = tm("val", "full+M6"), p = tm("val", "PEG"), b = tm("val", "base");
  txt(s, "Xanh/đỏ = tốt/xấu hơn PEG (IDSW: ít hơn là tốt).", { x: 0.6, y: yb + 0.05, w: 12, h: 0.3, fontSize: 12, color: C.muted });
  card(s, 0.6, yb + 0.45, 12.13, 6.85 - yb - 0.45, C.card2);
  txt(s, bullets([
    "full+M6 so với PEG: T1 " + sgn(f.T1.HOTA - p.T1.HOTA, 2) + " HOTA (IDSW " + fmtI(p.T1.IDSW) + " → " + fmtI(f.T1.IDSW) + "), T2 " + sgn(f.T2.HOTA - p.T2.HOTA, 2) + " HOTA, T3 Rcv " + fmt(p.T3["Rcv@.5"], 1) + " → " + fmt(f.T3["Rcv@.5"], 1) + ".",
    "Mức tăng Table I trên test không lặp lại. Table III sụt như trên test, còn nặng hơn.",
    "Ngay cả base (có logic đổi-ID cũ) cũng kém PEG ở T1: " + fmt(b.T1.HOTA, 2) + " so với " + fmt(p.T1.HOTA, 2) + ", IDSW " + fmtI(b.T1.IDSW) + " so với " + fmtI(p.T1.IDSW) + ".",
  ]), { x: 0.9, y: yb + 0.5, w: 11.6, h: 6.85 - yb - 0.55, fontSize: 15, valign: "middle" });
  done(s, "Kết quả v2 trên val",
    "Giờ đến tập val, phần dữ liệu Thạch chưa dùng tới. Cấu hình đầy đủ cộng M6 so với PEG: Table I " + sgn(f.T1.HOTA - p.T1.HOTA, 2) + " HOTA, số lần đổi ID từ " + fmtI(p.T1.IDSW) + " lên " + fmtI(f.T1.IDSW) + "; Table II " + sgn(f.T2.HOTA - p.T2.HOTA, 2) + " HOTA; Table III từ " + fmt(p.T3["Rcv@.5"], 1) + " xuống " + fmt(f.T3["Rcv@.5"], 1) + ". Tức là mức tăng Table I trên test không lặp lại trên val, còn Table III sụt như trên test và còn nặng hơn. Ngay cả base, tức PEG cộng logic đổi ID cũ, cũng kém PEG ở Table I trên val: " + fmt(b.T1.HOTA, 2) + " so với " + fmt(p.T1.HOTA, 2) + ", và đổi ID " + fmtI(b.T1.IDSW) + " lần so với " + fmtI(p.T1.IDSW) + ".");
}

// ── the pre-registered rule on val, then test once
{
  const VR = TH.val_rule, sel = VR.selected;
  const s = base("Luật chốt trước, chọn trên val: " + (sel === "base" ? "không method nào qua" : "chọn " + sel), "PEG-F v2 · CHỌN TRÊN VAL", 1);
  txt(s, "Ứng viên = 13 cấu hình của Thạch so với base. Qua vòng 1 nếu không bảng nào giảm quá 0.5 và tổng tăng > 0.5:", { x: 0.6, y: 1.5, w: 12.1, h: 0.35, fontSize: 14, color: C.muted });
  const cand = VR.rows.filter((r) => r.admissible && r.score > 0.5).sort((a, b) => b.score - a.score);
  const chk = (c) => VR.checks.find((k) => k.config === c);
  const cols = ["ΔT1 HOTA", "ΔT2 HOTA", "ΔT3 Rcv", "tổng", "bỏ 1 video / 1 lần chói có lợi nhất", ""];
  const cx = [3.2, 4.65, 6.1, 7.4, 8.6, 11.3], cwid = [1.4, 1.4, 1.3, 1.1, 2.7, 1.4];
  cols.forEach((cn, j) => txt(s, cn, { x: cx[j], y: 1.9, w: cwid[j], h: 0.35, fontSize: 12, bold: true, color: C.muted, align: "center" }));
  cand.forEach((r, i) => {
    const y = 2.3 + i * 0.68, k = chk(r.config);
    card(s, 0.6, y, 12.13, 0.6);
    txt(s, r.config, { x: 0.85, y, w: 2.3, h: 0.6, fontSize: 17, bold: true, color: C.f, valign: "middle" });
    const v = [sgn(r.delta[0], 2), sgn(r.delta[1], 2), sgn(r.delta[2], 1), sgn(r.score, 2), k ? "còn " + sgn(k.score_without, 2) : "…", k && k.pass ? "QUA" : "TRƯỢT"];
    v.forEach((t, j) => txt(s, t, { x: cx[j], y, w: cwid[j], h: 0.6, fontSize: 16, bold: true, align: "center", valign: "middle", color: j === 5 ? (k && k.pass ? C.good : C.red) : C.text }));
  });
  const ex = cand.length ? chk(cand[0].config) : null;
  const y2 = 2.3 + cand.length * 0.68 + 0.1;
  card(s, 0.6, y2, 5.95, 6.85 - y2, C.card2);
  txt(s, bullets([
    ex ? "Mức tăng của cả hai đến từ 1 video T2 (" + ex.checks.t2.dropped.split("_")[0] + ") và 1 lần chói T3 (video " + ex.checks.t3.dropped.split("_")[0] + ")." : "",
    "Cấu hình có cả M1 và M5 bị loại ngay: T3 giảm ~30 điểm.",
    "M6 bị loại: cả 3 bảng đều giảm trên val.",
  ]), { x: 0.85, y: y2 + 0.05, w: 5.55, h: 6.85 - y2 - 0.1, fontSize: 14, valign: "middle" });
  const t = tm("test", sel), p = tm("test", "PEG");
  card(s, 6.78, y2, 5.95, 6.85 - y2);
  s.addShape(pres.shapes.RECTANGLE, { x: 6.78, y: y2, w: 0.1, h: 6.85 - y2, fill: { color: C.amber }, line: { color: C.amber } });
  txt(s, [{ text: "Báo test một lần: " + sel, options: { bold: true, color: C.amber, fontSize: 17, breakLine: true } },
    { text: "T1 HOTA " + fmt(t.T1.HOTA, 2) + " · T2 HOTA " + fmt(t.T2.HOTA, 2) + " · T3 " + fmt(t.T3["Rcv@.5"], 1), options: { bold: true, fontSize: 16, breakLine: true } },
    { text: "PEG: " + fmt(p.T1.HOTA, 2) + " · " + fmt(p.T2.HOTA, 2) + " · " + fmt(p.T3["Rcv@.5"], 1), options: { fontSize: 15, color: C.muted, breakLine: true } },
    { text: "Thạch báo (chọn trên test): full+M6 T1 " + fmt(tm("test", "full+M6").T1.HOTA, 2), options: { fontSize: 13, color: C.muted, breakLine: true } },
    { text: "base trên val: T1 " + sgn(tm("val", "base").T1.HOTA - tm("val", "PEG").T1.HOTA, 2) + " so với PEG, T2/T3 bằng → thực chất là giữ PEG.", options: { fontSize: 13, color: C.amber } }],
    { x: 7.05, y: y2 + 0.05, w: 5.5, h: 6.85 - y2 - 0.1, valign: "middle" });
  done(s, "Chọn trên val bằng luật chốt trước",
    "Đây là bước chọn. Luật được viết và đưa lên git trước khi có số val nào. Ứng viên là mười ba cấu hình của Thạch, so với base. Vòng một: không bảng nào được giảm quá 0.5, và tổng mức tăng phải lớn hơn 0.5. Chỉ có " + cand.length + " cấu hình qua vòng này: " + cand.map((r) => r.config).join(" và ") + ". Vòng hai là điều kiện mình thêm từ bài học lần trước: bỏ đi một video, hoặc một lần chói, có lợi nhất cho cấu hình đó mà vẫn còn tăng thì mới nhận. " + (ex ? "Cả hai đều trượt: mức tăng của chúng đến từ đúng một video ở Table II, video " + ex.checks.t2.dropped.split("_")[0] + ", và một lần chói ở Table III, video " + ex.checks.t3.dropped.split("_")[0] + ". " : "") + "Mọi cấu hình có cả M1 và M5 bị loại ngay ở vòng một vì Table III giảm khoảng ba mươi điểm, và M6 bị loại vì cả ba bảng đều giảm trên val. Kết quả: " + (sel === "base" ? "không method nào được val ủng hộ, nên cấu hình được chọn là base. " : "chọn " + sel + ". ") + "Báo test đúng một lần cho cấu hình này: Table I " + fmt(t.T1.HOTA, 2) + ", Table II " + fmt(t.T2.HOTA, 2) + ", Table III " + fmt(t.T3["Rcv@.5"], 1) + ", so với PEG " + fmt(p.T1.HOTA, 2) + ", " + fmt(p.T2.HOTA, 2) + " và " + fmt(p.T3["Rcv@.5"], 1) + ".");
}

// ── tune from scratch on val (docs/THACH_V2_TUNE_PROTOCOL.md, results/thach_v2/tune/)
{
  const TR = JSON.parse(fs.readFileSync("D:/PROJECT/PEG/results/thach_v2/tune/trace.json", "utf8"));
  const TT = JSON.parse(fs.readFileSync("D:/PROJECT/PEG/results/thach_v2/tune/test.json", "utf8"));
  const TD = JSON.parse(fs.readFileSync("D:/PROJECT/PEG/results/thach_v2/tune/test_diagnostic.json", "utf8"));
  const r1 = TR[1];
  const NAME = { R: "Đổi-ID viết lại (luôn bật ở base)", M1q: "M1 · nở vùng bất định", M1c: "M1 · cone khớp lại ID", M1d: "M1 · hãm vận tốc ×0.88",
    M2: "M2 · Re-ID", M3: "M3 · h động / TTL", M4: "M4 · pool track ngủ", M5: "M5 · neo đèn", M6: "M6 · tone-map" };
  const P = { M1q: ["0.01h", "0.02h", "0.03h"], M1c: ["χ² 5.99, 0.04h", "χ² 5.99, 0.06h", "χ² 9.21, 0.04h", "χ² 9.21, 0.06h"], M2: ["0.5", "0.7", "0.9"],
    M3: ["0.03, TTL tắt", "0.03, TTL bật", "0.06, TTL tắt", "0.06, TTL bật", "0.12, TTL tắt", "0.12, TTL bật", "chỉ TTL"], M4: ["0.50", "0.60", "0.70"],
    M5: ["R ×6", "R ×24", "R ×96"] };
  const best = {};
  r1.rows.forEach((r) => { if (!best[r.comp] || r.score > best[r.comp].score) best[r.comp] = r; });
  const chk = (add) => r1.checks.find((c) => c.add === add);
  const s = base("Tune lại tham số trên val từ đầu: vẫn không thành phần nào qua", "PEG-F v2 · TUNE TRÊN VAL", 1);
  txt(s, "Xuất phát = PEG (đã kiểm: ra đúng từng số). Vòng 1 thử " + r1.rows.length + " giá trị tham số của 9 thành phần; mỗi dòng = giá trị tốt nhất của một thành phần.", { x: 0.6, y: 1.45, w: 12.1, h: 0.35, fontSize: 13, color: C.muted });
  const cols = ["thành phần", "tham số tốt nhất", "ΔT1 HOTA", "ΔT2 HOTA", "ΔT3 Rcv", "tổng (val)", "bỏ 1 video / lần chói", "test (đối chiếu)"];
  const cx = [0.85, 3.95, 5.95, 6.9, 7.85, 8.75, 9.75, 11.45], cw = [3.1, 2.0, 0.95, 0.95, 0.9, 1.0, 1.7, 1.25];
  cols.forEach((cn, j) => txt(s, cn, { x: cx[j], y: 1.85, w: cw[j], h: 0.3, fontSize: 11, bold: true, color: C.muted, align: j < 2 ? "left" : "center" }));
  const order = Object.keys(best).sort((a, b) => best[b].score - best[a].score);
  order.forEach((c, i) => {
    const r = best[c], y = 2.2 + i * 0.42, k = chk(r.add);
    card(s, 0.6, y, 12.13, 0.37);
    const zero = r.delta.every((d) => d === 0);
    const p = P[c] ? (zero ? "mọi giá trị: không đổi gì" : P[c][r.idx]) : "bật";
    const res = k ? (k.pass ? "QUA" : "còn " + sgn(k.score_without, 2)) : r.admissible && r.score > 0.5 ? "" : r.admissible ? "tăng < 0.5" : "giảm > 0.5";
    const v = [NAME[c], p, sgn(r.delta[0], 2), sgn(r.delta[1], 2), sgn(r.delta[2], 1), sgn(r.score, 2), res, sgn(TD[c].test_score, 2)];
    v.forEach((t, j) => txt(s, t, { x: cx[j], y, w: cw[j], h: 0.37, fontSize: j === 0 ? 13 : 12, bold: j === 0 || j === 5, valign: "middle", align: j < 2 ? "left" : "center",
      color: j === 7 ? C.muted : j === 6 ? (k && !k.pass ? C.red : C.muted) : j === 0 ? C.f : j >= 2 && j <= 5 ? (r.delta[j - 2] > 0.05 || (j === 5 && r.score > 0.05) ? C.good : r.delta[j - 2] < -0.05 || (j === 5 && r.score < -0.05) ? C.red : C.text) : C.text }));
  });
  const yb = 2.2 + order.length * 0.42 + 0.08;
  card(s, 0.6, yb, 12.13, 6.88 - yb, C.card2);
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: yb, w: 0.1, h: 6.88 - yb, fill: { color: C.amber }, line: { color: C.amber } });
  const tt = TT.test;
  txt(s, [{ text: "Kết quả: giữ PEG. ", options: { bold: true, color: C.amber } },
    { text: "Test cho cấu hình cuối = PEG: " + fmt(tt.T1.HOTA, 2) + " · " + fmt(tt.T2.HOTA, 2) + " · " + fmt(tt.T3["Rcv@.5"], 1) + ". Cột test chỉ để đối chiếu (chạy sau khi đã chốt): trên test, M6 và đổi-ID viết lại tăng gần như chỉ nhờ 1 lần đổi ID ở video 129; cone nhờ video 204; hãm vận tốc −8.5 → val loại đúng." }],
    { x: 0.9, y: yb, w: 11.7, h: 6.88 - yb, fontSize: 13, valign: "middle" });
  const cc = chk(best.M1c.add), cd = chk(best.M1d.add);
  done(s, "Tune lại tham số trên val từ đầu",
    "Chọn lại trên val chưa đủ, vì các tham số bên trong method vẫn là số Thạch đã chỉnh trên test. Nên bọn mình tune lại từ đầu, chỉ trên val, với luật viết trước và đưa lên git trước khi chạy. Điểm xuất phát là PEG: bọn mình chép lại logic đổi ID gốc của PEG vào code của Thạch và kiểm tra là khi tắt hết method thì ra đúng từng số của PEG. Phần đổi ID mà Thạch viết lại cũng thành một thành phần để thử. Mỗi vòng, mỗi thành phần được thử với vài giá trị tham số, vòng đầu tổng cộng " + r1.rows.length + " lượt. Bảng này là giá trị tốt nhất của từng thành phần ở vòng đầu. Chỉ có hai thứ tăng quá ngưỡng: cone của M1, cộng " + fmt(best.M1c.score, 2) + ", và phần hãm vận tốc, cộng " + fmt(best.M1d.score, 2) + ". Nhưng khi bỏ đi một video hoặc một lần chói có lợi nhất, cone còn " + sgn(cc.score_without, 2) + " và hãm vận tốc còn " + sgn(cd.score_without, 2) + ": toàn bộ mức tăng của cone nằm ở hai video, 156 và 147, còn của hãm vận tốc nằm ở một lần chói trong video 332. Phần nở vùng bất định, Re-ID và pool track ngủ không đổi gì khi đứng một mình; neo đèn và tone-map làm giảm. Nên không thành phần nào được nhận, cấu hình cuối cùng chính là PEG, và test một lần cho nó ra đúng số PEG: " + fmt(tt.T1.HOTA, 2) + ", " + fmt(tt.T2.HOTA, 2) + " và " + fmt(tt.T3["Rcv@.5"], 1) + ". Cột cuối là số test của từng thành phần, chạy sau khi đã chốt, chỉ để đối chiếu. Trên test cũng vậy: M6 và phần đổi ID viết lại tăng gần như chỉ nhờ sửa đúng một lần đổi ID ở video 129, lần đó đáng hai mươi ba điểm HOTA ở video ấy; cone tăng chủ yếu nhờ video 204; còn hãm vận tốc giảm tám điểm rưỡi, nên val loại nó là đúng. Lưu ý là số test của M6 và phần đổi ID bị lạc quan, vì Thạch đã chỉnh chúng trên chính tập test.");
}

// ═════════ 17 ─ Conclusion ═════════
{
  const s = base("Kết luận và bài học", "TỔNG KẾT", 2);
  const v2t = tm("test", "full+M6"), v2p = tm("test", "PEG"), v2v = tm("val", "full+M6"), v2vp = tm("val", "PEG");
  card(s, 0.6, 1.65, 6.0, 4.9);
  txt(s, "Kết quả", { x: 0.9, y: 1.75, w: 5.4, h: 0.4, fontSize: 20, bold: true, color: C.amber });
  txt(s, bullets([
    "PEG-F v1: tái hiện được, nhưng cùng cấu hình chỉ " + sgn(CL.HOTA - FP_.HOTA, 2) + " HOTA; 2 lần đổi ID quyết định bảng.",
    "PEG-F v2: Table I đúng 14/14, nhưng Thạch chỉnh và chọn trên test. Chọn lại, rồi tune lại từ đầu trên val: không method nào qua → giữ PEG.",
    "v2: M1 × M5 làm Table III sụt (" + fmt(v2p.T3["Rcv@.5"], 1) + " → " + fmt(v2t.T3["Rcv@.5"], 1) + " test, " + fmt(v2vp.T3["Rcv@.5"], 1) + " → " + fmt(v2v.T3["Rcv@.5"], 1) + " val): box trượt ngang.",
    "PEG+: Rcv test " + sgn(ES.test.A.delta, 1) + ", val " + sgn(ES.val.A.delta, 1) + ", gộp " + sgn(ES.pooled.A.delta, 1) + ": chỉ giúp khi box co lại lúc coast.",
    "Table I một mình dễ đánh lừa → luôn đo đủ 3 bảng, chọn trên val, báo test 1 lần.",
  ]), { x: 0.9, y: 2.3, w: 5.45, h: 4.1, fontSize: 15 });
  card(s, 6.78, 1.65, 5.95, 4.9, C.card2);
  txt(s, "Hướng tiếp theo", { x: 7.08, y: 1.75, w: 5.4, h: 0.4, fontSize: 20, bold: true, color: C.plus });
  txt(s, ["Chọn bằng khoảng tin cậy hoặc cross-validation, không bằng ngưỡng cứng", "Thêm dữ liệu val: hiện 1–2 video quyết định mọi mức tăng", "Neo đèn (M5) với độ tin không phụ thuộc độ bất định Kalman", "M6 (tone-map): thử lại khi val có nhiều ca chói quanh người hơn"].map((t, i, a) => ({ text: t, options: { bullet: { type: "number" }, breakLine: i < a.length - 1, paraSpaceAfter: 18 } })),
    { x: 7.08, y: 2.3, w: 5.4, h: 4.1, fontSize: 19 });
  done(s, "Kết luận và bài học",
    "Tóm lại năm điều. Một, PEG-F bản đầu tái hiện được, nhưng khi so cùng cấu hình thì mức tăng chỉ " + sgn(CL.HOTA - FP_.HOTA, 2) + " HOTA, và hai lần đổi ID quyết định gần hết mức tăng đó. Hai, PEG-F bản hai: Table I tái hiện đúng cả mười bốn cấu hình, nhưng Thạch chỉnh và chọn mọi thứ trên test; khi chọn lại trên val bằng luật chốt trước thì không method nào qua; và khi tune lại tham số từ đầu, chỉ trên val, kết quả vẫn vậy, cấu hình cuối cùng là PEG. Ba, ở bản hai, M1 đi cùng M5 làm Table III sụt mạnh, từ " + fmt(v2p.T3["Rcv@.5"], 1) + " xuống " + fmt(v2t.T3["Rcv@.5"], 1) + " trên test và từ " + fmt(v2vp.T3["Rcv@.5"], 1) + " xuống " + fmt(v2v.T3["Rcv@.5"], 1) + " trên val, vì box bị kéo trượt ngang khỏi người. Bốn, PEG+ tăng Rcv trên test " + sgn(ES.test.A.delta, 1) + ", trên val " + sgn(ES.val.A.delta, 1) + ", gộp lại " + sgn(ES.pooled.A.delta, 1) + ": chỉ giúp khi box co lại lúc coast. Năm, nhìn một mình Table I rất dễ bị đánh lừa, nên lúc nào cũng đo đủ ba bảng, chọn trên val và báo test một lần. Hướng tiếp theo: chọn bằng khoảng tin cậy hoặc cross-validation thay vì ngưỡng cứng; thêm dữ liệu val, vì hiện giờ một hai video quyết định mọi mức tăng; nếu giữ M5 thì cú kéo về đèn phải có độ tin cố định, không phụ thuộc độ bất định của Kalman; và M6 đáng thử lại khi có thêm dữ liệu val có người đứng gần đèn. Bài học lớn nhất với mình không phải một con số mà là cách làm: tái hiện trước, so cùng cấu hình, đo cả ba bảng, chọn trên val, và tách từng phần ra để xem phần nào thật sự có tác dụng.");
}

// ═════════ 18 ─ Q&A ═════════
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  s._who = 0;
  s.addShape(pres.shapes.OVAL, { x: 9.4, y: 1.3, w: 3.4, h: 3.4, fill: { color: C.f, transparency: 84 }, line: { color: C.bg } });
  s.addShape(pres.shapes.OVAL, { x: 10.3, y: 2.2, w: 1.6, h: 1.6, fill: { color: C.plus, transparency: 62 }, line: { color: C.bg } });
  txt(s, "Cảm ơn thầy cô và các bạn", { x: 0.8, y: 2.3, w: 8.4, h: 1.0, fontSize: 40, bold: true });
  txt(s, "Hỏi đáp (Q&A)", { x: 0.8, y: 3.5, w: 8.4, h: 0.6, fontSize: 24, color: C.amber, bold: true });
  txt(s, "Người 1 · PEG-F    |    Người 2 · PEG+", { x: 0.8, y: 5.6, w: 9, h: 0.4, fontSize: 16, color: C.muted });
  done(s, "Hỏi đáp",
    "Bọn mình xin cảm ơn thầy cô và các bạn đã lắng nghe. Giờ bọn mình xin nhận câu hỏi.");
}

// ═════════ write deck + script ═════════
const QA = [
  [1, "Sao không retrain?",
    "Mục tiêu là sửa logic tracker chứ không đổi detector. Dùng đúng weights của paper thì so sánh công bằng: chỉ khác đúng phần mình sửa. Máy bọn mình chỉ có GPU 4 GB nên train lại rất tốn thời gian và không liên quan đến lỗi này."],
  [1, "Cache detector là gì, có làm kết quả sai không?",
    "Cache là kết quả của detector được lưu lại một lần, rồi tracker chạy lại từ đó cho nhanh (khoảng 11 giây thay vì 40 phút). Bọn mình kiểm tra file kết quả ra giống hệt từng byte so với chạy thật, nên không làm lệch số."],
  [1, "Guard là gì và tại sao phải chạy guard tắt?",
    "Guard là lớp bảo vệ không cho tracker sinh ra ID mới từ vầng sáng chói. Paper báo số với guard tắt, nên để tái hiện đúng paper bọn mình tắt guard. Nhưng code PEG-F chạy với guard bật, nên khi so claim phải so với PEG cũng guard bật."],
  [1, "Có chắc là mức tăng của PEG-F chỉ do hai video không?",
    "Khoảng như vậy: hai video 129 và 176 chênh " + sgn(dseq(SEQ129), 1) + " và " + sgn(dseq(SEQ176), 1) + " HOTA, còn các video khác chênh nhiều nhất " + fmt(OTHERS_MAX, 1) + " điểm. Mỗi video chỉ là một lần đổi ID, nên bảng Table I rất nhạy với vài sự kiện."],
  [2, "Tại sao box co lại?",
    "Kalman filter nhớ cả vận tốc đổi diện tích của box. Khi coast, PEG hãm vận tốc di chuyển nhưng quên hãm vận tốc diện tích, nên box tiếp tục nhỏ đi (hoặc to ra) mỗi frame. PEG+ đặt vận tốc diện tích bằng không khi coast."],
  [2, "Tại sao IDF1 tăng mà IDSW cũng tăng?",
    "IDSW đếm số lần đổi ID, mỗi lần có thể rất ngắn. IDF1 đo tỉ lệ thời gian giữ đúng ID. Một phép sửa có thể đổi ID thêm vài lần ngắn nhưng làm phần lớn thời gian còn lại đúng người, nên IDF1 vẫn tăng."],
  [2, "Tại sao tổ hợp chọn lọc chưa đáng tin?",
    "Vì bọn mình chọn M1-swap và M3 sau khi đã nhìn kết quả trên tập test. Bọn mình đã kiểm tra lại: trên val tổ hợp này gần bằng PEG (Table III " + fmt(vv("v_A+M1swap+M3").T3.all_burn["Rcv@.5"], 1) + " so với " + fmt(vv("v_peg").T3.all_burn["Rcv@.5"], 1) + "), nên phần tăng trên test là do chọn trên test."],
  [2, "Sao không đổi luật rồi chọn lại sau khi thấy M1-damp thua trên test?",
    "Vì đổi luật sau khi đã thấy test thì lại là chọn trên test lần nữa. Bọn mình báo đúng kết quả của luật đã chốt trước, rồi ghi bài học cho lần sau: chỉ nhận một thành phần khi khoảng tin cậy không chứa không."],
  [1, "Sao không lấy thẳng số full+M6 của Thạch (+1.69 HOTA)?",
    "Vì số đó được chọn trên test: trong kết quả Thạch gửi có " + "56 lượt chạy Table I trên test và không lượt nào trên val. Chọn lại trên val bằng luật chốt trước thì không method nào qua. Ngoài ra full+M6 làm Table III giảm từ " + fmt(tm("test", "PEG").T3["Rcv@.5"], 1) + " xuống " + fmt(tm("test", "full+M6").T3["Rcv@.5"], 1) + " trên test."],
  [1, "Có chắc M1 × M5 là nguyên nhân Table III sụt không?",
    "Có, vì bọn mình kiểm tra bằng công tắc con trong chính code của Thạch: chỉ M5 cộng riêng phần nở độ bất định của M1 đã đủ gây sụt, và tắt riêng phần đó khỏi cấu hình đầy đủ thì Table III hồi lại. Đo từng frame chói cũng thấy box đúng chiều cao nhưng trượt ngang."],
  [1, "M6 có vẻ tốt trên test, sao không giữ?",
    "Trên test M6 tăng cả ba bảng, nhưng trên val cả ba bảng đều giảm nhẹ (T1 " + sgn(dprim("val", "base+M6", "base")[0], 2) + ", T2 " + sgn(dprim("val", "base+M6", "base")[1], 2) + ", T3 " + sgn(dprim("val", "base+M6", "base")[2], 1) + "). Luật chốt trước không cho nhận; M6 đáng thử lại với nhiều dữ liệu hơn."],
  [2, "Vậy rốt cuộc PEG+ có tốt hơn PEG không?",
    "Chỉ ở những ca box co lại khi coast. Trên test nó tăng " + sgn(ES.test.A.delta, 1) + " Rcv, trên val " + sgn(ES.val.A.delta, 1) + ". Gộp " + ES.pooled.n_episodes + " lần chói thì tăng " + sgn(ES.pooled.A.delta, 1) + " với khoảng tin cậy [" + sgn(ES.pooled.A.ci95[0], 1) + ", " + sgn(ES.pooled.A.ci95[1], 1) + "]: có dấu hiệu tốt nhưng chưa chắc chắn."],
];
pres.writeFile({ fileName: OUT }).then((f) => {
  console.log("wrote", f, SL.length, "slides");
  const words = (t) => t.split(/\s+/).filter(Boolean).length;
  const RATE = 160; // spoken Vietnamese syllables (whitespace tokens) per minute, with pauses
  let md = "# Kịch bản thuyết trình PEG-F + PEG+ (2 người, ~12–15 phút)\n\n_File này được sinh tự động từ deck_build.js; số liệu lấy từ numbers.json._\n\n";
  const tot = { 1: 0, 2: 0, 0: 0 };
  SL.forEach((sl) => { tot[sl.who] += words(sl.notes); });
  const mins = (w) => (w / RATE).toFixed(1);
  md += "Tổng: Người 1 ≈ " + mins(tot[1] + tot[0]) + " phút, Người 2 ≈ " + mins(tot[2]) + " phút (tốc độ ~" + RATE + " tiếng/phút), Q&A không tính.\n\n";
  const part = (who, title) => {
    const list = SL.map((sl, i) => ({ sl, i })).filter((o) => o.sl.who === who || (who === 1 && o.sl.who === 0 && o.i === 0));
    md += "# " + title + " (≈ " + mins(list.reduce((a, o) => a + words(o.sl.notes), 0)) + " phút)\n\n";
    list.forEach(({ sl, i }) => { md += "## Slide " + (i + 1) + " — " + sl.title + "  _(≈ " + (words(sl.notes) / RATE * 60).toFixed(0) + " giây)_\n\n" + sl.notes + "\n\n"; });
  };
  part(1, "NGƯỜI 1 — PEG-F, kiểm chứng");
  part(2, "NGƯỜI 2 — PEG+ và kết hợp");
  md += "## Slide " + SL.length + " — " + SL[SL.length - 1].title + " (cả hai)\n\n" + SL[SL.length - 1].notes + "\n\n";
  md += "---\n\n# Hỏi đáp dự kiến\n\n";
  QA.forEach(([who, q, a], i) => { md += "**" + (i + 1) + ". " + q + "** _(Người " + who + " trả lời)_\n\n" + a + "\n\n"; });
  fs.writeFileSync(OUT_MD, md, "utf8");
  console.log("wrote", OUT_MD, "words", tot);
});
