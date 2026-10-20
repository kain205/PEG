# PEG-O: photometric odometry (kết quả)

Commit: `4b13dc3` (protocol), `bab4795` (code + addendum). Mọi số dưới đây sinh bởi `results/peg_o/collect.py` từ report/ledger (không gõ tay), trừ `PLAN_19` (số của plan).

## Ý tưởng
PEG dùng vùng bão hòa để *quyết định* giữ box (phi >= h). PEG-O dùng cùng vùng đó để *đo* box đã dời bao xa: lọc đĩa (disc matched filter) trên thành phần bão hòa, đo dịch chuyển của tâm đĩa từ một mốc (anchor) và đưa vào Kalman như pseudo-measurement chỉ cho tâm; chỉ tin khi đỉnh nhọn (độ cong k >= tau). Kích thước vẫn khóa (PEG+). Fusion cuối: R tương đối = gamma·(tau/k)·P (gain = 1/(1+gamma·tau/k)), cổng nhảy 0.5·đường chéo.

## Bảng test, guard tắt (setting của paper), O[8] = tau .08, gamma 4 — *không được val chọn*

| | T1 HOTA | DetA | AssA | IDF1 | MOTA | IDSW | FP | FN |
|---|---|---|---|---|---|---|---|---|
| paper PEG | 68.20 | – | – | 82.30 | 80.62 | 17 | 1425 | 2611 |
| PEG | 68.19 | 65.88 | 71.62 | 82.30 | 80.62 | 17 | 1425 | 2611 |
| PEG+ | 68.23 | 65.96 | 71.62 | 82.24 | 80.52 | 17 | 1440 | 2618 |
| PEG-O | 68.15 | 65.79 | 71.62 | 82.15 | 80.36 | 17 | 1479 | 2612 |

| | T2 HOTA | MOTA | FP | Rcll | IDF1 | IDSW |
|---|---|---|---|---|---|---|
| paper PEG | – | 73.24 | 2024 | 85.61 | 75.29 | – |
| PEG | 61.70 | 73.26 | 2022 | 85.62 | 75.30 | 19 |
| PEG+ | 62.54 | 73.37 | 2113 | 86.26 | 77.95 | 16 |
| PEG-O | 61.73 | 73.06 | 2100 | 85.88 | 77.26 | 16 |

| | T3 clear | Rcv@.5 | heavy | total | ID-off % | survived |
|---|---|---|---|---|---|---|
| paper PEG | 93.0 | 76.5 | 74.1 | 77.6 | 18.5 | – |
| PEG | 93.0 | 76.6 | 74.1 | 77.8 | 18.5 | 19/30 |
| PEG+ | 93.3 | 82.2 | 78.9 | 85.1 | 15.5 | 21/30 |
| PEG-O | 93.3 | 73.6 | 72.1 | 74.5 | 9.5 | 19/30 |

Val T3 Rcv@.5 (guard tắt): PEG 67.6, PEG+ 67.3, PEG-O 53.8.

## Chọn trên val (Thach harness, guard bật, pre-registered)

Bắt đầu S0+P: val T1 70.11 / T2 76.3 / T3 67.3.

| thêm | tau | gamma | Δ T1 | Δ T2 | Δ T3 | score | admissible |
|---|---|---|---|---|---|---|---|
| O[0] | 0.04 | 0.25 | -0.01 | -4.80 | -41.2 | -46.01 | không |
| O[1] | 0.04 | 1 | -0.01 | -1.75 | -34.6 | -36.36 | không |
| O[2] | 0.04 | 4 | -0.01 | -1.22 | -22.8 | -24.03 | không |
| O[3] | 0.06 | 0.25 | +0.00 | -1.76 | -29.3 | -31.06 | không |
| O[4] | 0.06 | 1 | +0.00 | -1.55 | -24.9 | -26.45 | không |
| O[5] | 0.06 | 4 | +0.00 | -2.20 | -23.3 | -25.50 | không |
| O[6] | 0.08 | 0.25 | +0.00 | -0.98 | -27.5 | -28.48 | không |
| O[7] | 0.08 | 1 | +0.00 | -1.71 | -22.1 | -23.81 | không |
| O[8] | 0.08 | 4 | +0.00 | -1.55 | -13.5 | -15.05 | không |
| S[0] |  |  | +0.00 | +0.00 | +0.0 | +0.00 | có (score <= 0.5: không chọn) |

Final = `P[0]` (không O, không S). `tune_O/test.json` = S0+P test: T1 68.41 / T2 62.33 / T3 82.2. S (armed survival) byte-identical với PEG+ trên val (không bao giờ kích hoạt).

## Theo episode (T3)

- test: 30 ep. — Rcv PEG 76.6 / PEG+ 82.2 / PEG-O 73.6; PEG-O so với PEG+ Δ -8.6 CI95 [-19.8, +1.0], tốt hơn 6 / tệ hơn 5 (+26 / −99 frame); so với PEG Δ -2.9 CI95 [-16.1, +9.1].
- val: 18 ep. — Rcv PEG 67.6 / PEG+ 67.3 / PEG-O 53.8; PEG-O so với PEG+ Δ -13.5 CI95 [-29.0, -0.8], tốt hơn 3 / tệ hơn 5 (+10 / −87 frame); so với PEG Δ -13.8 CI95 [-30.2, -0.2].
- pooled: 48 ep. — Rcv PEG 73.0 / PEG+ 76.2 / PEG-O 65.7; PEG-O so với PEG+ Δ -10.6 CI95 [-19.5, -2.7], tốt hơn 9 / tệ hơn 10 (+36 / −186 frame); so với PEG Δ -7.3 CI95 [-17.3, +2.0].

Episode khác PEG+ (test): seq g<id> frames: covered PEG+ → PEG-O (n) | sai số tâm px PEG+ → PEG-O

- 135_sequence_19q_new g53 409-451: 4 → 11 (43) | 70.5 → 48.2
- 145_sequence_28q_new g84 1094-1130: 31 → 36 (37) | 6.7 → 7.7
- 176_sequence_56q_new g204 331-355: 25 → 11 (25) | 11.9 → 15.4
- 183_sequence_62q_new g240 448-482: 35 → 12 (35) | 9.6 → 18.3
- 192_sequence_70q_complete g265 673-711: 39 → 22 (39) | 5.0 → 8.4
- 204_sequence_81q_complete g300 102-141: 38 → 39 (40) | 2.6 → 2.7
- 204_sequence_81q_complete g300 342-383: 25 → 28 (42) | 13.6 → 11.3
- 204_sequence_81q_complete g300 400-432: 26 → 30 (33) | 20.5 → 12.7
- 211_sequence_88q_new g319 376-411: 35 → 6 (36) | 16.6 → 36.4
- 211_sequence_88q_new g320 436-460: 25 → 9 (25) | 20.3 → 31.9
- 316_sequence_112q_new g6 2000-2034: 22 → 28 (35) | 31.6 → 28.6

Episode khác PEG+ (val): seq g<id> frames: covered PEG+ → PEG-O (n) | sai số tâm px PEG+ → PEG-O

- 133_sequence_17q_new g117 3239-3275: 17 → 12 (37) | 20.3 → 19.5
- 141_sequence_24q_new g71 161-184: 12 → 13 (24) | 12.8 → 12.2
- 147_sequence_3q_new g79 497-541: 38 → 45 (45) | 7.6 → 8.7
- 187_sequence_66q_new g247 141-173: 33 → 16 (33) | 5.4 → 10.1
- 187_sequence_66q_new g247 201-235: 19 → 3 (35) | 9.1 → 28.9
- 203_sequence_80q_new g299 104-146: 42 → 7 (43) | 5.9 → 23.0
- 203_sequence_80q_new g299 306-340: 33 → 35 (35) | 11.1 → 8.7
- 210_sequence_87q_complete g317 192-209: 16 → 2 (18) | 5.8 → 17.5

## Estimator pin (scripts/19_peg_o_check.py, tau .05, sai số tâm trung bình, px)

| episode | frozen (PEG+) | MF-odo (ours) | plan (nhập tay từ plan) |
|---|---|---|---|
| 204 g300 | 28.3 | 25.8 | 21.5 |
| 135 g53 | 76.2 | 30.4 | 30.4 |
| 325 g3 | 82.5 | 83.7 | 82.5 |
| 176 g204 | 16.5 | 28.9 | 28.9 |
| 320 g1 | 9.0 | 6.8 | 6.8 |

tau .06 / .08 (MF-odo): 204 g300: 25.8 / 14.5; 135 g53: 26.9 / 26.9; 325 g3: 54.5 / 79.4; 176 g204: 28.8 / 20.0; 320 g1: 6.8 / 7.0

## Smoke 135_19q g53 409–451 (test, một sequence)

- PEG+ 4/43, sai số tâm 70.5 px (max 101.2).
- Fusion cũ (R tuyệt đối, tau .06 gamma 4): 4/43, 65.1 px — gain ≈ 0.01, không làm gì.
- Fusion R tương đối (tau .06 gamma 1): 41/43, 31.6 px (max 52.1); cận trên oracle (box PEG+ căn đúng tâm GT) 41/43.
- Episode 815–834 giữ 20/20.

## Vì sao val thất bại

D1 — estimator offline (anchor = GT, thay trực tiếp) trên các episode val bị mất >= 5 frame với O[8]: sai số tâm trung bình (px)

| episode | box | frozen | MF-odo tau .06 | MF-odo tau .08 |
|---|---|---|---|---|
| 133_sequence_17q g117 f3239 | 32x113 | 12.8 | 14.8 | 16.3 |
| 187_sequence_66q g247 f141 | 30x102 | 10.0 | 18.8 | 12.8 |
| 187_sequence_66q g247 f201 | 34x121 | 11.3 | 11.4 | 14.6 |
| 203_sequence_80q g299 f104 | 28x92 | 6.9 | 15.2 | 18.2 |
| 210_sequence_87q g317 f192 | 32x112 | 5.8 | 8.7 | 9.4 |

D2 — tracker O[4] trên val: 216 update (10 track), median |z−c| 9.7 px (max 57.9), gain 0.5–0.71, anchor cũ (stale) 0, update ngoài vùng GT cháy nặng 73; box median 41×147 px.

Cơ chế: đĩa bão hòa đổi hình khi độ cháy tăng/giảm (và dính hàng xóm/tường), nên đỉnh lọc dịch 10–20 px dù người gần như đứng yên; anchor lấy đúng lúc đang tăng; gain ≈ 0.6 mỗi update và vận tốc bị bơm vào Kalman nên box tiếp tục trôi. Với box rộng 28–41 px sai số đó làm mất IoU .5; với 135_19q (box 264 px, người đi 108 px) thì không đáng kể.

## Lệnh

- estimator_pin: `.venv/Scripts/python.exe scripts/19_peg_o_check.py > results/peg_o/check_19.txt`
- byte_identity (flags unset, guard off, cached): `GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 [GPEG_SIZE_LOCK=1] scripts/06_eval_mot.py / 07_eval_recovery.py --percep_cache results/percep_cache/{real,synth} --tracker_name bi_*`
- smoke 135 (relative-R): `GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_ODO=1 GPEG_ODO_TAU=0.06 GPEG_ODO_GAMMA=1 .venv/Scripts/python.exe scripts/07_eval_recovery.py --split test --percep_cache results/percep_cache/synth --tracker_name smoke_pego2_135 --seqs 135_sequence_19q_new`
- val search (Thach harness, guard on): `.venv/Scripts/python.exe results/thach_v2/tune_val.py --peg_o ; --peg_o --strong ; --peg_o --test`
- test T1: `GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_ODO=1 GPEG_ODO_TAU=0.08 GPEG_ODO_GAMMA=4 .venv/Scripts/python.exe scripts/06_eval_mot.py --split test --percep_cache results/percep_cache/real --tracker_name pego_test`
- test T2: `GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_ODO=1 GPEG_ODO_TAU=0.08 GPEG_ODO_GAMMA=4 .venv/Scripts/python.exe scripts/06_eval_mot.py --split test --data_root datasets/synth --results_subdir eval_synthfs --percep_cache results/percep_cache/synth --tracker_name pego_fs`
- test T3: `GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_ODO=1 GPEG_ODO_TAU=0.08 GPEG_ODO_GAMMA=4 .venv/Scripts/python.exe scripts/07_eval_recovery.py --split test --percep_cache results/percep_cache/synth --tracker_name pego_rcv`
- val T3 (ours, guard off): `GMOT_TRACKER=beacon GMOT_BIRTH_SIZE_GUARD=0 GPEG_SIZE_LOCK=1 GPEG_ODO=1 GPEG_ODO_TAU=0.08 GPEG_ODO_GAMMA=4 .venv/Scripts/python.exe scripts/07_eval_recovery.py --split val --percep_cache results/percep_cache/synth --tracker_name v_pego_rcv`
- episodes: `.venv/Scripts/python.exe results/peg_o/episodes.py`
