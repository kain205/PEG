# Kịch bản thuyết trình PEG-F + PEG+ (2 người, ~12–15 phút)

_File này được sinh tự động từ deck_build.js; số liệu lấy từ numbers.json._

Tổng: Người 1 ≈ 7.5 phút, Người 2 ≈ 10.9 phút (tốc độ ~160 tiếng/phút), Q&A không tính.

# NGƯỜI 1 — PEG-F, kiểm chứng (≈ 7.4 phút)

## Slide 1 — PEG-F và PEG+ — giữ ID đúng người khi đèn mũ làm chói camera  _(≈ 39 giây)_

Em chào thầy cô và các bạn. Nhóm mình có hai người, và hôm nay bọn mình trình bày về cùng một bài toán: theo dõi công nhân trong hầm mỏ khi đèn trên mũ làm chói camera. Bài báo gốc tên là “Burnt, Not Gone”, và có một tracker tên PEG. Mình là người thứ nhất, mình nói về PEG-F, năm cải tiến của mình cho PEG, và cách bọn mình kiểm chứng xem chúng có thật sự tốt không. Bạn mình là người thứ hai, sẽ nói về PEG+, một cải tiến khác, rồi nói về chuyện ghép hai bên lại với nhau.

## Slide 2 — Bài toán  _(≈ 30 giây)_

Trong hầm mỏ, công nhân đội đèn trên mũ. Khi họ quay về phía camera, đèn làm cháy sáng cả vùng ảnh, như các tấm ảnh bên phải: người gần như biến mất. Lúc đó detector, tức là mô hình tìm người trong ảnh, không thấy ai, nên tracker mất cái box và có thể mất luôn số ID của người đó. Tracker là phần nối các box qua từng frame để mỗi người giữ một ID cố định.

## Slide 3 — PEG làm gì?  _(≈ 30 giây)_

PEG xử lý đúng lúc detector mất người. Nó đo vùng box dự đoán xem bao nhiêu phần trăm điểm ảnh bị cháy trắng, gọi là φ. Nếu φ từ 0.4 trở lên thì người vẫn ở đó, chỉ bị chói, nên giữ box. Việc tự đoán vị trí khi không có detector gọi là coast. Nếu φ thấp thì người đã đi, bỏ box. Ý hay của PEG là dùng chính ánh sáng gây lỗi làm bằng chứng.

## Slide 4 — Tái hiện kết quả  _(≈ 45 giây)_

Trước khi cải tiến gì, bọn mình phải chắc là chạy lại được số của paper. Bọn mình dùng đúng weights mà tác giả gửi, không train lại, và chạy ba bảng kết quả. Table I là video thật, Table II là video có thêm chói giả, và Table III chỉ đo những người đang bị chói. Có mấy điểm số chính. HOTA, IDF1 và MOTA là các điểm tổng quát đo chất lượng tracking, càng cao càng tốt. Rcv@.5 là phần trăm số frame của người bị chói mà box của mình vẫn chồng lên người, với độ trùng IoU trên 0.5. Kết quả của bọn mình lệch paper không quá 0.1 điểm, nghĩa là tái hiện khớp.

## Slide 5 — 5 method của PEG-F  _(≈ 38 giây)_

PEG-F là năm cải tiến của mình cho tracker. M1 là chuyển động thích nghi, gồm hai nửa mà sau này bọn mình tách ra: M1-damp hãm vận tốc của hai người đứng gần nhau, còn M1-swap thêm các phép thử để sửa lại những lần đổi nhầm ID. M2 nhận lại người bằng màu áo. M3 đổi ngưỡng chói và thời gian giữ box tùy tình huống. M4 cất track bị mất vào một pool để track mới nhận lại ID cũ. M5 kéo box về phía đèn trên mũ. Tất cả chỉ sửa tracker, không đụng vào detector.

## Slide 6 — Kiểm chứng claim  _(≈ 37 giây)_

Mình báo PEG-F đạt HOTA 68.82 và IDF1 84.42, cao hơn paper là 68.20 và 82.30. Nhưng bọn mình không tin ngay mà kiểm tra ba cách. Một, chấm lại file kết quả mình nộp bằng evaluator của nhóm: ra đúng. Hai, chạy lại nguyên code gốc trên GPU của nhóm, chạy thật cả detector, khoảng 4.3 frame mỗi giây: vẫn đúng số đó. Ba, đưa các method vào repo chung và chạy bằng cache, tức là kết quả detector lưu sẵn: giống từng chữ số. Vậy claim là thật. Nhưng còn một câu hỏi: so với cái gì?

## Slide 7 — So cùng cấu hình  _(≈ 39 giây)_

Có một chỗ không công bằng. Số 68.20 của paper chạy với guard tắt. Guard là lớp bảo vệ không cho tracker tạo ID mới từ vầng sáng chói. Code PEG-F của mình chạy với guard bật, nên phải so với PEG cũng guard bật: PEG đó được 68.33 HOTA và 82.68 IDF1. So như vậy PEG-F hơn +0.49 HOTA và +1.74 IDF1. Và IDSW, tức là số lần tracker đổi ID của một người sang ID khác, tăng từ 15 lên 27; IDSW càng ít càng tốt. Mức tăng có thật, nhưng nhỏ hơn con số ban đầu và có cái giá.

## Slide 8 — Mức tăng đến từ đâu  _(≈ 35 giây)_

Mức tăng đó đến từ đâu? Hình là độ chênh HOTA của từng video, PEG-F trừ PEG, cùng guard bật. Chỉ hai video lệch đáng kể: video 129 tăng +23.5, video 176 giảm −19.9. Mình soi từng video thì mỗi video chỉ là một lần tracker đổi ID giữa hai công nhân đứng sát nhau: ở 129 PEG-F sửa được một lần, ở 176 PEG-F gây ra một lần mới. Các video còn lại chênh tối đa 4.0 điểm. Nên Table I một mình rất dễ bị lệch bởi một sự kiện.

## Slide 9 — M1-swap sửa đổi ID ở video 129  _(≈ 46 giây)_

Đây là video 129, hai công nhân A và B đi sát nhau. Hàng trên là PEG, hàng dưới là PEG-F; màu vàng là ID một, xanh lơ là ID hai, khung trắng là người thật. Ở frame 330 cả hai đều đúng. Khi hai người đi chéo qua nhau, cả hai tracker đổi nhầm, nhưng PEG giữ nhầm đến hết video, còn PEG-F đổi lại ở frame 339. Bí quyết là phép thử chiều cao nhất quán của M1-swap: A thấp, B cao, tracker so chiều cao box với chiều cao quen thuộc của từng track, và nếu đổi lại ID làm chiều cao khớp hơn thì đổi lại. Nên ở frame 420 và 560, PEG-F vẫn đúng, còn PEG thì ngược.

## Slide 10 — Từng method làm được gì  _(≈ 37 giây)_

Giờ thêm từng method vào PEG, mỗi lần một cái. Số to là độ thay đổi so với PEG; xanh là tốt hơn, đỏ là xấu hơn; với IDSW thì ít hơn mới tốt. M1-swap tăng HOTA +0.50 và IDF1 +2.05 ở Table I, nhưng IDSW tăng từ 17 lên 36. M1-damp làm hỏng: MOTA của Table II giảm −2.98, Rcv@.5 của Table III giảm từ 76.6 xuống 66.4. M3 tốt nhẹ, MOTA của Table II +0.82. M2, M4, M5 gần như không đổi. Tức là chỉ hai trong năm method có tác dụng thật: M1-swap và M3.

## Slide 11 — Vì sao M2 và M4 không chạy  _(≈ 37 giây)_

Vì sao M2 và M4 không làm gì? Bọn mình đếm bên trong tracker. M2 chỉ đổi ID khi màu áo của người kia giống hơn một khoảng đủ lớn, phải trên 0.25, nhưng thực tế lớn nhất chỉ 0.052; ở phép thử đổi chéo cần 0.15 mà chỉ đạt 0.096. Lý do: công nhân mặc đồ bảo hộ giống hệt nhau nên màu HSV không phân biệt được. Vì vậy M2 chưa bao giờ đổi một quyết định nào. M4 còn tệ hơn: trong 81 lần sinh track mới, chỉ 1 lần pool có người để nhận lại.

## Slide 12 — Chi phí: tốc độ  _(≈ 30 giây)_

Cuối cùng là chi phí, trên cùng GPU GTX 1650, chạy thật cả pipeline: detector, h_psi và tracker. FPS là số frame xử lý mỗi giây. PEG đạt 4.4 FPS, code PEG-F đạt 4.3 FPS, gần như bằng nhau vì detector chiếm gần hết thời gian. Paper ghi 26.4 FPS vì dùng GPU RTX 5070 Ti mạnh hơn. Vậy PEG-F không tốn thêm gì đáng kể, nhưng chỉ hai method đáng giữ. Mình chuyển sang bạn mình, người nói về PEG+.

# NGƯỜI 2 — PEG+ và kết hợp (≈ 10.9 phút)

## Slide 13 — PEG+: khóa kích thước  _(≈ 86 giây)_

Mình là người thứ hai, mình nói về PEG+. Sau khi tái hiện PEG, mình xem từng ca PEG thất bại và thấy một lỗi lạ: PEG biết người đang bị chói và vẫn giữ box, nhưng cái box nhỏ dần qua từng frame, như hàng trên của hình, cho đến khi không còn trùng người. Khung vàng là người thật, khung xanh dương là box của PEG. Mình đếm lại: trong các ca thất bại ở Table III, 9/12 là do box trôi chứ không phải do gate bật sai, và 33% số frame coast có box nhỏ hơn 30% kích thước ban đầu. Nguyên nhân là Kalman filter, bộ lọc đoán vị trí, nhớ cả vận tốc đổi kích thước. Khi coast, PEG hãm vận tốc di chuyển nhưng quên hãm vận tốc diện tích. Mình đặt vận tốc diện tích bằng không, khoảng hai dòng code, và đó là PEG+, hàng dưới màu xanh lá. Kết quả: Rcv@.5, phần trăm frame mà box vẫn trùng người bị chói, tăng từ 76.6 lên 82.2, +5.6 điểm. Mình không train lại detector, chỉ sửa tracker, nên so PEG với PEG+ là công bằng: hai bên chỉ khác đúng hai dòng code này. Hình là cùng một người, cùng một đoạn video, cùng lúc bị chói, nên bạn nhìn thấy trực tiếp sự khác nhau giữa hai hàng.

## Slide 14 — Kết hợp PEG-F và PEG+  _(≈ 104 giây)_

Bọn mình thử ghép PEG-F với PEG+. Hình có bốn bảng nhỏ, mỗi bảng một thang riêng, trục không bắt đầu từ không để nhìn rõ chênh lệch. Xanh dương là PEG, xanh lá là PEG+, tím là PEG-F, cam là ghép cả hai; cột gạch chéo là một cách ghép có chọn lọc, mình nói ở slide sau. Ở Table I, video thật, ghép cả hai cho kết quả tốt nhất: HOTA 70.03 và IDF1 86.94. Nhưng ở Table II, video có chói giả, MOTA chỉ 71.54, thấp hơn cả PEG là 73.26. Và ở Table III, Rcv@.5 chỉ còn 68.4, trong khi PEG+ một mình đạt 82.2. Tức là cái lợi của PEG+ đã bị mất đi khi ghép với PEG-F. Câu hỏi là vì sao. Bài học đầu tiên ở đây: mỗi bảng đo một thứ khác nhau, nên một cách ghép chỉ tốt ở một bảng thì chưa thể gọi là tốt. Table I chủ yếu hỏi tracker có giữ đúng ID giữa nhiều người không, còn Table III hỏi tracker có giữ được người đang bị chói hay không, và đó chính là chỗ PEG+ sinh ra để làm. Còn một điều phải nói thật: ghép cả hai cao hơn PEG-F 1.20 HOTA ở Table I, nhưng gần như toàn bộ phần đó đến từ một video, video 176: có PEG+ thì lần đổi ID mà PEG-F gây ra ở đó không xảy ra nữa, HOTA của video này từ 45.68 lên 65.53. Đó là một tương tác tình cờ giữa hai thay đổi, PEG+ không được thiết kế để sửa lỗi ID, nên con số 70.03 không nên coi là chắc chắn.

## Slide 15 — Vì sao tụt: M1-damp  _(≈ 97 giây)_

Mình tách M1 làm hai nửa và tìm ra thủ phạm: M1-damp, nửa hãm vận tốc. Luật của nó là: mỗi frame, nếu hai người đứng gần nhau thì nhân vận tốc của họ với 0.88. Vấn đề là người đang bị chói cũng đang coast, tức là box chỉ chạy theo vận tốc đoán. Vận tốc bị hãm thì box đứng lại, trong khi người vẫn đi tiếp. Hình là video 183, người số 240, từ frame 448 đến 482. Khung xanh lá là người thật. Hàng trên là PEG, box đi theo người. Hàng dưới là PEG cộng M1-damp, box đỏ đứng lại, và độ trùng IoU tụt từ 0.84 xuống 0.22. Đếm lại: trong 35 frame bị chói của người này, số frame box còn trùng người giảm từ 35 xuống 15. Trên cả ba mươi lần chói, số frame được phủ giảm từ 651 xuống 564 trên tổng 850. Vậy cái làm hỏng Table III chính là M1-damp, không phải M1-swap. Nửa còn lại, M1-swap, không làm Table III đổi một chút nào: Rcv@.5 vẫn giữ nguyên. Và M1-damp cũng là thứ gây ra lần đổi ID mới ở video 176 mà bạn mình đã nói ở phần trước, nên nó có hại ở cả hai nơi. Mình đoán hãm vận tốc có thể hợp lý khi hai người đi sát nhau và cả hai đều đang được nhìn thấy; còn khi một người bị chói và đang coast thì việc hãm làm box đứng lại, và đó là hướng sửa mình đề xuất.

## Slide 16 — Ghép có chọn lọc  _(≈ 60 giây)_

Từ các thí nghiệm, mình thử ghép có chọn lọc: lấy PEG+, thêm M1-swap, thêm M3 và bỏ M1-damp. Kết quả là không bảng nào kém PEG+. Table I: HOTA 68.81, IDF1 84.56. Table II: MOTA 73.90. Table III: Rcv@.5 vẫn 82.2. Nhưng có hai điều phải nói thẳng. Một là IDSW tăng từ 17 lên 36. Mình giải thích hai chỉ số này: IDF1 đo việc giữ đúng ID trong thời gian dài; IDSW đếm số lần đổi ID, mỗi lần có thể rất ngắn. Nên IDF1 tăng mà IDSW cũng tăng là có thể: tracker đổi ID thêm vài lần ngắn, nhưng phần lớn thời gian vẫn đúng người. Hai là bọn mình chọn tổ hợp này sau khi đã nhìn kết quả trên tập test, nên số đẹp hơn thực tế. Vì vậy phải kiểm tra lại trên tập val, là phần dữ liệu chưa dùng để chọn. Ở slide sau mình làm đúng việc đó.

## Slide 17 — Chọn lại trên tập val  _(≈ 65 giây)_

Để sửa chỗ rò rỉ, bọn mình chọn lại trên tập val, là phần dữ liệu chưa dùng để chọn gì. Val có mười bảy video thật, chín video chói giả và 18 lần chói. Luật được viết ra và đưa lên git trước khi chạy val, để không ai có thể chỉnh luật sau khi đã thấy số. Luật như sau: bắt đầu từ PEG, mỗi vòng thử thêm từng thành phần. Một thành phần được nhận nếu không bảng nào tụt quá 0.5 điểm và tổng mức tăng của ba bảng lớn hơn 0.5. Bảng bên phải là vòng một. Điều đầu tiên đáng chú ý: PEG+ trên val gần như không làm gì, Table III còn tụt −0.3. M1-swap và M3 gần như bằng không. Thành phần duy nhất vượt ngưỡng là M1-damp, tổng +0.96, chính là thứ mà ở slide trước mình đã thấy làm hỏng Table III trên test. Vòng hai không thêm được gì nữa. Vậy theo đúng luật, config được chọn là PEG cộng M1-damp.

## Slide 18 — Chạy test một lần  _(≈ 55 giây)_

Đây là kết quả khi chạy test đúng một lần. Mỗi chỉ số có hai cột, test và val; số nhỏ bên dưới là chênh lệch so với PEG trên cùng tập. Hàng thứ hai là config chọn trên val, PEG cộng M1-damp. Trên test nó thua PEG ở cả ba bảng: Table I HOTA 67.38 so với 68.19, Table II 57.84 so với 61.70, Table III Rcv 66.4 so với 76.6. Hàng cuối là tổ hợp bọn mình chọn trên test lúc trước. Trên test nó đẹp, nhưng trên val nó gần như bằng PEG: Table III 67.3 so với 67.6. PEG+ cũng vậy: trên test tăng +5.6 Rcv, trên val −0.4. Nói cách khác, cái gì tốt trên tập này thì không tốt trên tập kia. Bạn mình nghi ngờ đúng: phần tăng trên test của tổ hợp chọn lọc là do chọn trên test.

## Slide 19 — Vì sao val và test ngược nhau  _(≈ 93 giây)_

Vì sao val và test lại ngược nhau? Mình đếm lại theo từng lần chói. M1-damp được chọn trên val nhờ đúng một lần chói, ở video 332: số frame box còn trùng người tăng từ 3 lên 13. Trên val, một frame chỉ đáng 0.18 điểm, nên chỉ một lần chói đó cũng đủ vượt ngưỡng 0.5. Trên test, M1-damp làm 9 lần chói tệ hơn và mất 87 frame. PEG+ thì ngược lại: trên test tăng +5.6, trên val −0.4. Lý do là val có ít trường hợp box co lại khi coast; lỗi của PEG trên val chủ yếu là người chưa bao giờ được track, có 3 lần chói gần như không phủ được frame nào, và khóa kích thước box không cứu được những ca đó. M1-swap trên val không cải thiện Table I mà IDSW còn tăng từ 15 lên 22. Nếu gộp cả bốn mươi tám lần chói của val và test, PEG+ tăng +3.2 với khoảng tin cậy chín mươi lăm phần trăm từ +0.1 đến +7.3, tức là chỉ vừa đủ khác không; còn M1-damp giảm 5.6 điểm và chắc chắn có hại. Bài học là luật của bọn mình đặt ngưỡng quá thấp so với độ nhiễu của một tập nhỏ như vậy. Bọn mình không sửa luật sau khi đã thấy test, vì như thế lại là chọn trên test lần nữa; lần sau mình sẽ chỉ nhận một thành phần khi khoảng tin cậy không chứa không.

## Slide 20 — Kết luận và bài học  _(≈ 95 giây)_

Tóm lại bốn điều. Một, claim của PEG-F tái hiện được, nhưng chỉ khi so cùng cấu hình: guard bật, mức tăng thật là +0.49 HOTA. Hai, nhìn một mình Table I rất dễ bị đánh lừa, vì hai lần đổi ID ở hai video quyết định gần hết mức tăng; nên phải đo cả ba bảng. Ba, M1-swap và M3 giúp trên test nhưng không lặp lại trên val; M1-damp làm hại; M2, M4, M5 gần như bằng không. Bốn, PEG+ nâng Rcv@.5 trên test từ 76.6 lên 82.2, nhưng trên val thì không; gộp cả hai tập nó tăng +3.2, vừa đủ khác không. Nó chỉ giúp khi box co lại lúc coast, và val có ít trường hợp như vậy. Năm, khi chọn lại trên val với luật chốt trước, config được chọn là PEG cộng M1-damp, và nó thua PEG trên test; nghĩa là val quá nhỏ để chọn bằng một ngưỡng cứng. Hướng tiếp theo: chọn bằng khoảng tin cậy hoặc cross-validation thay vì ngưỡng cứng; thay màu HSV bằng một Re-ID học được, vì màu không phân biệt được hai công nhân; và sửa M1-damp để chỉ hãm vận tốc của track đang được thấy, không hãm track đang coast. Bài học lớn nhất với mình không phải một con số, mà là cách làm: tái hiện trước, so cùng cấu hình, đo cả ba bảng, tách từng phần ra để xem phần nào thật sự có tác dụng, và nói rõ chỗ nào chưa kiểm chứng.

## Slide 21 — Hỏi đáp (cả hai)

Bọn mình xin cảm ơn thầy cô và các bạn đã lắng nghe. Giờ bọn mình xin nhận câu hỏi.

---

# Hỏi đáp dự kiến

**1. Sao không retrain?** _(Người 1 trả lời)_

Mục tiêu là sửa logic tracker chứ không đổi detector. Dùng đúng weights của paper thì so sánh công bằng: chỉ khác đúng phần mình sửa. Máy bọn mình chỉ có GPU 4 GB nên train lại rất tốn thời gian và không liên quan đến lỗi này.

**2. Cache detector là gì, có làm kết quả sai không?** _(Người 1 trả lời)_

Cache là kết quả của detector được lưu lại một lần, rồi tracker chạy lại từ đó cho nhanh (khoảng 11 giây thay vì 40 phút). Bọn mình kiểm tra file kết quả ra giống hệt từng byte so với chạy thật, nên không làm lệch số.

**3. Guard là gì và tại sao phải chạy guard tắt?** _(Người 1 trả lời)_

Guard là lớp bảo vệ không cho tracker sinh ra ID mới từ vầng sáng chói. Paper báo số với guard tắt, nên để tái hiện đúng paper bọn mình tắt guard. Nhưng code PEG-F chạy với guard bật, nên khi so claim phải so với PEG cũng guard bật.

**4. Có chắc là mức tăng của PEG-F chỉ do hai video không?** _(Người 1 trả lời)_

Khoảng như vậy: hai video 129 và 176 chênh +23.5 và −19.9 HOTA, còn các video khác chênh nhiều nhất 4.0 điểm. Mỗi video chỉ là một lần đổi ID, nên bảng Table I rất nhạy với vài sự kiện.

**5. Tại sao box co lại?** _(Người 2 trả lời)_

Kalman filter nhớ cả vận tốc đổi diện tích của box. Khi coast, PEG hãm vận tốc di chuyển nhưng quên hãm vận tốc diện tích, nên box tiếp tục nhỏ đi (hoặc to ra) mỗi frame. PEG+ đặt vận tốc diện tích bằng không khi coast.

**6. Tại sao IDF1 tăng mà IDSW cũng tăng?** _(Người 2 trả lời)_

IDSW đếm số lần đổi ID, mỗi lần có thể rất ngắn. IDF1 đo tỉ lệ thời gian giữ đúng ID. Một phép sửa có thể đổi ID thêm vài lần ngắn nhưng làm phần lớn thời gian còn lại đúng người, nên IDF1 vẫn tăng.

**7. Tại sao tổ hợp chọn lọc chưa đáng tin?** _(Người 2 trả lời)_

Vì bọn mình chọn M1-swap và M3 sau khi đã nhìn kết quả trên tập test. Bọn mình đã kiểm tra lại: trên val tổ hợp này gần bằng PEG (Table III 67.3 so với 67.6), nên phần tăng trên test là do chọn trên test.

**8. Sao không đổi luật rồi chọn lại sau khi thấy M1-damp thua trên test?** _(Người 2 trả lời)_

Vì đổi luật sau khi đã thấy test thì lại là chọn trên test lần nữa. Bọn mình báo đúng kết quả của luật đã chốt trước, rồi ghi bài học cho lần sau: chỉ nhận một thành phần khi khoảng tin cậy không chứa không.

**9. Vậy rốt cuộc PEG+ có tốt hơn PEG không?** _(Người 2 trả lời)_

Chỉ ở những ca box co lại khi coast. Trên test nó tăng +5.6 Rcv, trên val −0.4. Gộp 48 lần chói thì tăng +3.2 với khoảng tin cậy [+0.1, +7.3]: có dấu hiệu tốt nhưng chưa chắc chắn.

