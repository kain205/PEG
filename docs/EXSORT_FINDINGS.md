# ExSORT trên cache YOLOX fix2: tái lập, phát hiện "coast mù", bản sửa chọn trên val

Ngày 18/11/2026. Gửi Minh (và cả nhóm). Tất cả số liệu dưới đây chạy trên **cùng một pipeline**: cache detection YOLOX-X
fix2 dùng chung, mask chói của ExSORT, nhãn GlareMOT2 đã sửa 2 lần, 48 video test (118 632 frame, 114 097 box GT)
và 71 video val_half, chấm bằng TrackEval (HOTA, CLEAR, Identity). Code và lệnh chạy lại ở mục 8.

## TL;DR

1. **Box ma (FP) của ExSORT đến từ "coast mù"**: khi mất detection, ExSORT vẫn xuất box dự đoán của Kalman. Box này
   chỉ đúng **17,6 % trên test, 26,8 % trên val**, dưới ngưỡng hòa vốn của HOTA (≈ 37 %) và MOTA (50 %).
   Các baseline (trừ DIP) **không** coast mù: track không có detection ở frame hiện tại thì không xuất box.
2. **Bỏ coast mù, giữ nguyên toàn bộ phần nhớ track và giải thích bằng mask chói** (`COAST_MODE=none`, có sẵn
   trong code, 0 tham số mới): test **HOTA 61.39 → 62.30, IDF1 79.69 → 81.50, MOTA 72.50 → 77.07, FP 13 041 → 6 435**.
   Mọi quyết định lấy từ val; test chấm một lần.
3. **Luật 1/2 giây (commit b2bca1b) gần như không giảm FP** trên cache chung (13 102) vì đồng hồ của nó bị detection
   điểm thấp reset; nó giảm FN chứ không giảm FP (đúng như README của repo ghi).
4. **Không tái lập được HOTA 59.50** của bảng báo cáo: đúng code b2bca1b trên cache chung cho **61.54**. Cần output
   MOT của lượt 59.50 để chấm lại (mục 3).
5. Baseline đều chạy code repo gốc, cấu hình MOT17 mặc định; các method vốn dùng ReID đều được cấp FastReID (mục 2).

## 1. Pipeline chung

| Thành phần | Chi tiết |
|---|---|
| Detector | YOLOX-X run 3 (khởi tạo TrackTrack MOT20, epoch 15 chọn theo AP50 trên val không morongmo) |
| Cache box | `det_nms0.95.txt` (mọi box điểm ≥ 0.1, native pixel), mỗi tracker chạy lại NMS của chính nó (ExSORT 0.65, top 100) |
| Mask chói ExSORT | chép `exsort/cache.py:77-79`: stretch frame về 512×512, HSV, `V ≥ 235 & S ≤ 89`; test + val_half |
| ReID | FastReID SBS-S50 MOT20 (bản BoT-SORT/DiffMOT phát hành), crop 128×384, L2; cho mọi box trong cache |
| GMC | sparseOptFlow (downscale 2) cho BoT-SORT, Deep-OC-SORT, TrackTrack, DIP |
| Chấm | TrackEval, GT `mark=0` bị loại, mọi frame của 48 video test |

Kiểm chứng cache: ExSORT 0c25ef3 `selected.json` trên cache chung **61.39**; Long chạy cùng config trên cache riêng của
ExSORT **61.48**. Chênh do cache ≈ 0.1 HOTA.

Dữ liệu trên Drive (thư mục nhóm, `ExSORT_bo_sung_cache_fix2 (2026-11-17)`): mask ExSORT test + val_half, biểu đồ, phân
tích, output train detector. Cache box: `glaremot2_yolox_dets_fix2.zip`.

## 2. Baseline: code gốc, có ReID khi repo gốc có

| Baseline | Repo @ commit | ReID trong repo gốc | Lượt chạy |
|---|---|---|---|
| ByteTrack | ifzhang/ByteTrack @ d1bf019 | không | không |
| OC-SORT | noahcao/OC_SORT @ 8462e7e | không | không |
| Deep-OC-SORT | GerardMaggiolino/Deep-OC-SORT @ 6bb51d0 | có | FastReID, w_emb 0.75 |
| BoT-SORT | NirAharon/BoT-SORT @ 2519854 | có (`--with-reid`) | FastReID + GMC |
| HybridSORT | ymzis69/HybridSORT @ 396f8d3 | có (bản ReID) | FastReID |
| TrackTrack | kamkyu94/TrackTrack @ ee7f1c5 | có | FastReID + GMC |
| DiffMOT | Kroery/DiffMOT @ eada72e | có | FastReID, w_emb 2.2 |
| DIP | tarashakhurana/detecting-invisible-people @ 3b01416 | có (cosine) | FastReID + GMC + MegaDepth; code gốc không chạy, dựng lại |

Cấu hình từng method và nguồn file:dòng: `configs/baselines/README.md`, docstring của `glaremot/baselines/t_*.py`.
FastReID là bản công khai MOT20, chưa fine-tune trên video mỏ (weight fine-tune của paper không công bố).

Luật xuất box của baseline (đã đọc code): OC-SORT / Deep-OC-SORT / HybridSORT xuất khi `time_since_update < 1`;
ByteTrack / BoT-SORT / TrackTrack chỉ xuất `tracked_stracks` (track mất được chuyển sang `lost_stracks`, vẫn nhớ để nối
lại nhưng không xuất). Chỉ DIP cố ý xuất box cho người không thấy.

## 3. Tái lập ExSORT và con số 59.50

| Ai chạy | Bản | Cache | HOTA | MOTA | FP | FN |
|---|---|---|---|---|---|---|
| Thành | 0c25ef3 (`budget`) | chung | 61.39 | 72.50 | 13 041 | 18 309 |
| Long | 0c25ef3 (`budget`) | riêng ExSORT | 61.48 | | | |
| Thành | **b2bca1b (`fps_budget`)** | chung | **61.54** | 72.95 | 13 102 | 17 726 |
| Minh, bảng báo cáo | b2bca1b? | ? | 59.50 | 76.09 | 7 865 | 19 374 |
| Minh, README b2bca1b | trước / sau luật 1/2 giây | "cache YOLOX-X epoch 15" | 56.52 / 56.43 | 76.63 / 75.95 | 7 006 / 8 380 | 19 621 / 19 034 |

Cùng code nhưng 59.50 / 56.4 khác 61.5. Cache không giải thích được (≈ 0.1). Cần: cache, phiên bản GT và lệnh chấm
của lượt 59.50, hoặc gửi thư mục `trackers/exsort/data/` của lượt đó để chấm lại bằng cùng pipeline. Nếu chấm lại ra
61.5 thì lệch do cách chấm/GT; nếu vẫn 59.5 thì lệch do cách chạy tracker. **Không ghép 59.50 vào bảng cùng 8 baseline**
trước khi rõ nguồn.

## 4. Phát hiện: FP đến từ việc xuất box, không đến từ việc giữ ID

Replay có ghi đặc trưng từng box (`scripts/exsort_diag/replay.py`; output trùng từng dòng với lượt chạy 0c25ef3), ghép
với GT bằng Hungarian IoU ≥ 0.5 mỗi frame. Test, 13 042 FP (các nhóm chồng nhau):

| Nguồn | Box | FP | Ghi chú |
|---|---|---|---|
| Box coast (dự đoán, không có detection) | 7 996 | 6 588 (51 %) | precision 17,6 %; sau 25 frame chỉ 34 TP / 2 590 box. Val: 5 318 box, precision 26,8 % |
| Track không bao giờ trùng GT ("track ma") | 30 / 171 track | 7 784 (60 %) | 7 471 ở video 401; ID 149 = 2 666 FP, ID 24 (đèn trần) = 1 932 |
| Ghép với detection điểm thấp (0.10–0.25) | 3 610 | 2 150 | precision 40 % (val 51 %) |
| Ghép với detection điểm cao | 97 223 | 4 304 | |

**Cơ chế của track ma.** Một lần ghép với detection điểm thấp reset cả `time_since_update` lẫn `unexplained`, nên ngân
sách 160 frame được làm mới mãi. ID 149 có 2 387 box coast, điểm detection cuối trung vị 0.16.

**Phép thử vùng đầu gần như không phân biệt được.** 75 % box đã ghép detection có vùng đầu chạm mask (đèn đầu nằm trên
đầu), và 98 % box coast có vùng đầu chạm mask ở lần ghép cuối.

**Biến phân biệt tốt nhất: τ = số frame từ lần ghép detection điểm cao (≥ DET) cuối cùng.** Cùng hình dạng trên val và test:

| τ | 0 | 1–5 | 6–25 | 26–100 | > 100 |
|---|---|---|---|---|---|
| precision, test | 95,6 % | 49 % | 27 % | 9 % | 0,4 % |
| precision, val | 94,5 % | 54 % | 37 % | 13 % | 0 % |

**Ngưỡng hòa vốn.** DetA = TP / (GT + FP), GT cố định. Xuất thêm một box đúng với xác suất p: tử số tăng p, mẫu số tăng
(1 − p). Box có lợi cho DetA khi p > DetA / (1 + DetA) ≈ 0,37; cho MOTA = 1 − (FN + FP + IDSW)/GT khi p > 0,5.
Box coast có p = 0,18 (test) / 0,27 (val): xuất ra là lỗ cả hai chỉ số. AssA gần như không đổi khi bỏ chúng, vì ID được
giữ bằng track trong bộ nhớ: người hiện lại thì được ghép vào track cũ dù trong lúc mất không xuất box.

**Luật 1/2 giây (b2bca1b)** đếm `time_since_update`, cũng bị detection điểm thấp reset, nên gần như không chạm được track
ma; nó thêm 1 giây coast cả khi không có chói, nên giảm FN và tăng nhẹ FP.

Những hướng đã kiểm tra và **không** dùng: phát hiện đèn tĩnh (track đứng yên trên vùng chói kéo dài: test 83 % FP
nhưng val 88 % TP, thợ mỏ đứng yên trông như đèn trần); chói xuất hiện lúc mất detection (val precision 0,43 so với
0,45, không có tín hiệu); chặn sinh track trong vùng chói lâu (chỉ 4/31 track ma sinh ra ở đó).

## 5. Bản sửa và quy trình chọn trên val

Chỉ đổi **phần xuất box**; trạng thái tracker (Kalman, ghép, ngân sách sống theo mask, khôi phục ID) giữ nguyên, nên luật
xuất box chấm được như một bộ lọc output.

Ứng viên và luật chọn chốt trước khi chạy val:
- `ex_old`: 0c25ef3 `budget`; `ex_minh`: b2bca1b `fps_budget`; `ex_none`: `COAST_MODE=none`;
  `ex_tauK`: xuất box khi τ ≤ K, K ∈ {3, 6, 12, 25}.
- Luật: HOTA val ≥ HOTA `ex_old` − 0.1 và IDSW ≤ `ex_old`; trong số đó lấy MOTA cao nhất, hòa thì ít FP hơn.

Val_half (71 video):

| Bản | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | FP | FN |
|---|---|---|---|---|---|---|---|---|
| ex_old | 53.61 | 58.36 | 50.08 | 70.14 | 74.76 | 59 | 14 339 | 32 991 |
| ex_minh | 53.68 | 58.44 | 50.15 | 70.27 | 74.69 | 55 | 15 728 | 31 746 |
| ex_none | 53.83 | 58.85 | 50.06 | 70.63 | 76.14 | 59 | 10 385 | 34 355 |
| ex_tau3 | 53.80 | 58.88 | 49.98 | 70.59 | **76.26** | 57 | 9 891 | 34 625 |
| ex_tau6 | 53.85 | 58.92 | 50.04 | 70.59 | 76.21 | 57 | 10 490 | 34 132 |
| ex_tau12 | 53.87 | 58.92 | 50.08 | 70.55 | 76.07 | 57 | 11 222 | 33 663 |
| ex_tau25 | 53.84 | 58.84 | 50.11 | 70.49 | 75.81 | 57 | 12 129 | 33 231 |

Luật chọn ra `ex_tau3`. HOTA val của mọi ứng viên chỉ chênh 0.26, nên chọn theo HOTA là chọn theo nhiễu. Nếu áp luật
"hòa về HOTA thì lấy bản đơn giản nhất" thì ra `ex_none` (0 tham số, cùng luật xuất box với baseline). Đề xuất dùng
`ex_none` làm hàng chính, `ex_tau3` làm hàng phụ.

Test (48 video, mỗi bản chấm một lần):

| Bản | HOTA | DetA | AssA | IDF1 | MOTA | IDSW | FP | FN | HOTA bỏ 401 | MOTA bỏ 401 |
|---|---|---|---|---|---|---|---|---|---|---|
| ex_old | 61.39 | 58.32 | 65.28 | 79.69 | 72.50 | 31 | 13 041 | 18 309 | 63.92 | 79.11 |
| ex_minh | 61.54 | 58.68 | 65.18 | 79.88 | 72.95 | 31 | 13 102 | 17 726 | 63.75 | 78.58 |
| **ex_none** | **62.30** | 60.38 | 64.94 | 81.50 | 77.07 | 33 | 6 435 | 19 699 | 63.88 | 79.44 |
| ex_tau3 | 62.49 | 60.72 | 64.97 | 81.75 | 77.70 | 32 | 5 603 | 19 803 | 63.87 | 79.46 |
| ex_tau6 | 62.56 | 60.73 | 65.11 | 81.72 | 77.54 | 32 | 6 281 | 19 312 | 63.95 | 79.48 |
| ex_tau12 | 62.54 | 60.59 | 65.20 | 81.54 | 77.08 | 30 | 7 214 | 18 910 | 63.99 | 79.36 |
| ex_tau25 | 62.37 | 60.24 | 65.23 | 81.23 | 76.29 | 30 | 8 420 | 18 604 | 63.94 | 79.19 |

So từng video (paired bootstrap 10 000 lần, trung bình HOTA theo video):
- `ex_none` − `ex_old`: test −0.06 [−0.25, +0.10], val −0.05 [−0.19, +0.08]: không video nào bị hại đáng kể; lợi ích
  dồn vào video 401 (HOTA 57.2 → 59.3, MOTA 62.9 → 73.6, FP 9 607 → 3 815).
- `ex_none` − TrackTrack: test −0.75 [−3.36, +1.54], thắng 29/48 video. Lợi thế ở bảng tổng (theo frame) đến từ các
  video dài, đông người (401, 199), nơi giữ ID qua đoạn chói có giá trị nhất.

## 6. Công bằng và minh bạch

- Phát hiện được nhìn thấy đầu tiên khi phân tích lỗi trên test, rồi xác nhận độc lập trên val (precision coast 26,8 %,
  cùng đường cong τ). Toàn bộ kết luận có thể rút ra chỉ từ val.
- Trước lượt chọn trên val, đã xem trước 3 hàng test (`none`, τ ≤ 3, τ ≤ 12). Lưới K và luật chọn lấy từ đường cong val.
- ExSORT được tune 9 tham số trên val (SMAC); baseline dùng tham số mặc định của repo gốc. So sánh chặt nhất cần tune mỗi
  baseline trên val với cùng ngân sách. Ghi câu này dưới bảng.
- Luật 1/2 giây: README b2bca1b ghi "được chọn làm cấu hình chính thức sau khi xem kết quả test".

## 7. Bảng đề xuất cho báo cáo (mọi hàng cùng một lượt chạy)

| Tracker | HOTA↑ | DetA↑ | AssA↑ | IDF1↑ | MOTA↑ | IDSW↓ | FP↓ | FN↓ |
|---|---|---|---|---|---|---|---|---|
| **Ex-Sort** | **62.30** | 60.38 | **64.94** | **81.50** | 77.07 | **33** | 6 435 | 19 699 |
| TrackTrack | 58.88 | **62.29** | 56.59 | 72.83 | **80.20** | 56 | 3 038 | 19 492 |
| HybridSORT | 57.59 | 61.63 | 54.76 | 70.76 | 79.28 | 87 | 3 393 | 20 161 |
| BoT-SORT | 56.28 | 62.12 | 52.01 | 68.50 | 79.72 | 95 | 2 618 | 20 422 |
| ByteTrack | 56.22 | 61.65 | 52.29 | 68.89 | 79.21 | 72 | 2 814 | 20 832 |
| DiffMOT | 56.01 | 61.97 | 51.64 | 67.97 | 79.53 | 111 | 3 210 | 20 037 |
| Deep-OC-SORT | 53.28 | 59.02 | 49.12 | 65.23 | 75.57 | 89 | **1 598** | 26 185 |
| OC-SORT | 53.27 | 58.93 | 49.17 | 65.50 | 75.55 | 97 | 1 603 | 26 194 |
| DIP | 51.28 | 61.15 | 44.25 | 58.05 | 77.10 | 258 | 7 028 | **18 845** |

Ex-Sort = 0c25ef3 `selected.json` với `COAST_MODE=none` (cùng luật xuất box với baseline). Câu gợi ý cho báo cáo:
"Phân tích lỗi trên val cho thấy box dự đoán khi mất detection chỉ đúng 27 %, dưới ngưỡng hòa vốn DetA/(1+DetA) ≈ 0.37.
Ex-Sort vì vậy dùng mask chói để giữ ID trong bộ nhớ nhưng không xuất box dự đoán. Ex-Sort được tune trên val; các
baseline dùng tham số mặc định của repo gốc."

## 8. Chạy lại

```bash
PY=.venv/bin/python
# mask ExSORT (stream ảnh từ zip GlareMOT2; val cần overlay ảnh sửa của 400_morongmo, 98 frame cuối)
GDRIVE_TOKEN_FILE=... $PY scripts/29_cache_peg_photometric.py --kind exsort --splits val_half,test \
    --dets results/baselines_t1/dets --out results/baselines_t1/exsat --tmp results/baselines_t1/stream \
    --overlay results/baselines_t1/overlay
# ReID + GMC cho baseline (Colab): configs/baselines/colab_feats.sh  (scripts/27_cache_reid_gmc.py)
# một tracker
$PY scripts/28_run_baselines.py --tracker <bytetrack|ocsort|deepocsort|botsort|hybridsort|tracktrack|diffmot|dip|exsort> --split test
# ma trận ExSORT (mục 5)
bash configs/baselines/run_exsort_matrix.sh val_half
bash configs/baselines/run_exsort_matrix.sh test
# chẩn đoán FP (mục 4)
$PY scripts/exsort_diag/replay.py test <out_dir>
```

Biến môi trường của adapter ExSORT (`glaremot/baselines/t_exsort.py`):
- `EXSORT_ROOT`: checkout ExSORT khác (mặc định `results/baselines_t1/repos/exsort` @ 0c25ef3).
- `EXSORT_COAST`: ghi đè `COAST_MODE` (`budget` | `fps_budget` | `none`); `fps_budget` nhận FPS từ `meta/DONE.json`.
- `EXSORT_TAU=K`: chỉ xuất box của track có τ ≤ K (bộ lọc output, không đổi trạng thái tracker).

| File | Nội dung |
|---|---|
| `glaremot/baselines/adapters.py`, `t_*.py` | adapter từng tracker, gọi code repo gốc không sửa |
| `scripts/27_cache_reid_gmc.py` | FastReID + GMC + disparity cho mọi box của cache |
| `scripts/28_run_baselines.py` | harness: đọc cache, chạy tracker, ghi MOT, chấm TrackEval |
| `scripts/29_cache_peg_photometric.py` | mask chói (`--kind exsort`) |
| `configs/baselines/README.md` | repo, commit, cấu hình của từng baseline |
| `configs/baselines/run_exsort_matrix.sh` | ma trận luật xuất box của ExSORT |
| `scripts/exsort_diag/replay.py`, `filt.py` | replay có ghi đặc trưng từng box; bộ lọc output + TrackEval |

## 9. Bước tiếp theo (chưa chạy)

1. **Detection điểm thấp không được reset `unexplained`** (`Track.observe`, chỉ reset khi `row[4] >= DET`; 0 tham số).
   Nhắm vào track ma (60 % FP). Đổi trạng thái tracker nên cần replay val thật; rủi ro ở AssA. Phân tích và chọn chỉ trên val.
2. **Log-odds tồn tại kiểu SPRT** (1 tham số: ngưỡng kẹp B): cộng logit độ chính xác theo điểm detection khi ghép, cộng
   log(1 − recall(chói)) khi mất; xuất khi σ(L) ≥ ½. Thay phép thử "chạm 1 pixel" bằng likelihood; lợi thêm dự kiến nhỏ.
