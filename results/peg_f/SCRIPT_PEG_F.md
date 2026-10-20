# Kịch bản thuyết trình PEG-F + PEG+ (2 người, ~12–15 phút)

_File này được sinh tự động từ deck_build.js; số liệu lấy từ numbers.json._

Tổng: Người 1 ≈ 22.9 phút, Người 2 ≈ 19.9 phút (tốc độ ~160 tiếng/phút), Q&A không tính.

# NGƯỜI 1 — PEG-F, kiểm chứng (≈ 22.7 phút)

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

## Slide 20 — PEG-F v2: tổng quan  _(≈ 57 giây)_

Sau buổi trước, Thạch sửa lại PEG-F và gửi bản mới, gọi là PEG-F v2. Giờ có sáu method. Ba cái mới là M1, M2 và M6: M1 viết lại hoàn toàn thành một vùng bất định nở rộng khi mất người; M2 không chỉ dùng màu áo nữa mà lấy thêm đặc trưng từ chính detector; và M6 là method mới, xử lý ảnh trước khi đưa vào detector. M3, M4, M5 giữ như cũ. Thạch báo trên Table I, tập test, cấu hình đầy đủ cộng M6 đạt HOTA 70.03 và IDF1 87.03. Mình chạy lại cả mười bốn cấu hình trong bảng của Thạch và ra đúng từng con số. Nhưng Thạch chỉ báo Table I trên test, nên mình đo thêm hai bảng còn lại và tập val, đúng như cách mình đã kiểm chứng ở phần trước. Trước hết mình giải thích từng method, mỗi method một slide.

## Slide 21 — M1: Vùng bất định nở rộng khi mất người  _(≈ 82 giây)_

M1 của Thạch giải quyết tình huống này: người bị chói vài chục frame, trong lúc đó họ có thể rẽ, đứng lại hoặc lùi, nên box dự đoán không còn trùng với người khi họ hiện ra lại, và tracker sinh ID mới. Cách làm có hai phần. Phần một: mỗi frame không thấy người, Kalman filter tăng độ bất định về vị trí, mỗi frame cộng thêm khoảng ba phần trăm chiều cao người, tối đa ba mươi frame. Hình bên phải cho thấy vùng này nở rộng theo thời gian, như một cái nón. Phần hai: những detection chưa được ai nhận sẽ được thử với các track đã mất từ hai frame trở lên. Nếu detection nằm trong vùng chín mươi chín phần trăm, theo một trong hai giả thuyết là đi tiếp với vận tốc cũ hoặc đứng lại chỗ cũ, thì gán lại ID cũ. Có thêm vài chặn để tránh gán nhầm: không xa quá sức đi bộ, chiều cao không lệch quá, và không đè lên người đang được track. Ngoài ra M1 vẫn kèm phần hãm vận tốc khi hai người gần nhau, và giờ Thạch chỉ áp cho track đang coast. Trên cả tập test, cone chỉ khớp lại 10 lần. Kết quả bật riêng M1 ở dải dưới.

## Slide 22 — M2: Re-ID: “dấu vân tay” lấy từ detector  _(≈ 62 giây)_

M2 là phần nhận lại người. Bản cũ chỉ so màu áo, mà công nhân mặc đồ bảo hộ giống nhau, nên nó không bao giờ đổi được quyết định nào. Bản mới lấy thêm đặc trưng từ chính detector: feature map ở tầng P4, cắt theo box của người và chia làm nửa trên, nửa dưới, nên không cần thêm mạng nào. Thạch trừ đi trung bình của cả video để bỏ phần giống nhau chung, rồi ghép với màu: độ giống bằng bảy mươi phần trăm feature cộng ba mươi phần trăm màu. Mỗi người giữ tối đa mười mẫu, gọi là gallery, lấy năm frame một lần và chỉ lấy khi người rõ, chưa bị chói và không chen với ai. Khi bị chói thì gallery đóng băng. Dấu vân tay này được dùng ở bốn chỗ: khi hai track giành một detection, khi xét đổi ID của một cặp, để lọc cone của M1, và để hồi sinh ID ở M4.

## Slide 23 — M3: Ngưỡng chói h tăng dần + thời gian giữ box thích nghi  _(≈ 49 giây)_

M3 giữ nguyên như bản cũ. Vấn đề nó nhắm tới là đèn chiếu lên tường: vùng box cũng trắng, nên PEG tưởng người vẫn ở đó và giữ box ma. Cách làm: khi đã mất detection quá ba frame, ngưỡng h tăng sáu phần trăm mỗi frame, từ 0.4 tới tối đa 0.65, như hình bên trái; càng mất lâu càng cần bằng chứng chói mạnh hơn. Thứ hai, thời gian được giữ box sau khi xác nhận chói không còn cố định năm frame mà tỉ lệ với độ chói φ. Nhưng vì box chỉ được giữ khi φ đã vượt ngưỡng, như vùng xám ở hình bên phải, nên thực tế nó chỉ là bốn hoặc năm frame: phần này gần như không đổi gì so với PEG.

## Slide 24 — M4: Pool track “ngủ”: trả lại ID cũ  _(≈ 30 giây)_

M4 giữ như bản cũ. Khi một track bị xóa vì mất quá lâu, thay vì quên luôn, tracker cất nó vào một pool, giữ tối đa bốn mươi lăm frame. Khi có người mới xuất hiện gần chỗ cũ, trong tầm đi bộ, và dấu vân tay giống từ 0.6 trở lên, thì người đó được trả lại ID cũ. Ý tưởng hợp lý, nhưng trên cả tập test với cấu hình đầy đủ, số lần hồi sinh là 0.

## Slide 25 — M5: Neo box vào đèn mũ  _(≈ 41 giây)_

M5 cũng giữ như cũ. Khi người bị chói, box chỉ chạy theo dự đoán của Kalman, nên nếu người đổi tư thế thì box trôi. M5 chỉ chạy khi gate của PEG đã xác nhận là người đang bị chói. Nó tìm tâm của đốm đèn ở dải đầu của box, suy ra tâm người bằng tâm đèn cộng 0.35 lần chiều cao, rồi kéo nhẹ box về đó. Bật một mình thì M5 gần như không đổi gì. Nhưng khi đi cùng M1, cú kéo nhẹ này trở thành kéo mạnh, và đó là nguyên nhân Table III sụt; mình sẽ quay lại ở slide sau.

## Slide 26 — M6: Làm dịu vầng sáng quanh đèn trước khi đưa vào detector  _(≈ 47 giây)_

M6 là method mới và khác các method khác: nó không sửa tracker mà sửa ảnh trước khi đưa vào detector. Quanh đèn có một vầng sáng rộng làm mất chi tiết của người đứng gần. Thạch tách ảnh thành một lớp độ sáng nền, làm mờ nhưng giữ cạnh, và một lớp chi tiết; rồi nén lớp nền ở chỗ quá sáng, chỉ trong vòng quanh đèn, còn lõi đèn thì giữ nguyên. Hình bên phải là ảnh gốc, ảnh sau khi xử lý, và bản đồ chỗ bị đổi. Chỉ ảnh đưa vào detector bị đổi; gate của PEG và màu Re-ID vẫn dùng ảnh gốc. Ngưỡng bật rất thấp, nên M6 được áp lên khoảng 100 phần trăm số frame của tập test.

## Slide 27 — base của Thạch không phải PEG  _(≈ 40 giây)_

Trước khi xem kết quả, có một điểm về cấu hình. Trong bảng của Thạch, mọi chênh lệch đều so với một cấu hình gọi là base, tức là PEG khi tắt hết sáu method. Nhưng base đó không phải PEG: phần logic đổi lại ID mà ở v1 mình gọi là M1-swap giờ luôn bật, không có công tắc. Nó sửa được video 129, HOTA tăng 23.5 điểm, nhưng làm hỏng video 320: số lần đổi ID tăng từ 4 lên 25. Vì vậy chênh lệch so với base không phải chênh lệch so với PEG. Ở các slide sau mình so với cả hai.

## Slide 28 — Bảng của Thạch được chọn trên test  _(≈ 70 giây)_

Trước khi xem kết quả, mình kiểm tra Thạch đã chọn cấu hình trên tập nào. Trong thư mục kết quả Thạch gửi có năm mươi sáu lượt chạy Table I trên tập test, không có lượt nào trên val, và không có lượt nào cho Table II hay Table III. Script của Thạch có ghi đúng quy trình: chọn trên val, báo test một lần, nhưng thực tế không làm. Ví dụ riêng M1 có ba bản thử tên dx, rồi fix1, rồi fix2 là bản cuối, HOTA từ khoảng 66 đến 69.24, và tất cả đều đo trên Table I test. Vì vậy con số cộng 1.69 HOTA là số chọn trên test rồi báo cũng trên test. Bọn mình làm lại theo đúng cách: luật chọn được viết và đưa lên git trước khi có bất kỳ số val nào, chọn trên val, rồi chỉ báo test một lần cho cấu hình được chọn. Có một điều bọn mình không gỡ được: các tham số bên trong method đã được chỉnh trên test; muốn gỡ thì phải tune lại từ đầu trên val.

## Slide 29 — Kết quả v2 trên test  _(≈ 24 giây)_

Đây là kết quả trên tập test, đủ ba bảng, so với PEG cùng cấu hình guard bật. Ở Table I, cấu hình đầy đủ cộng M6 hơn PEG +1.69 HOTA và +4.35 IDF1, số lần đổi ID từ 15 thành 29. Ở Table II, HOTA −0.20 và MOTA −4.00. Ở Table III, phần đo người đang bị chói, Rcv@.5 từ 76.2 thành 53.6.

## Slide 30 — Vì sao Table III sụt  _(≈ 81 giây)_

Vì sao Table III sụt mạnh như vậy? Mình tách từng phần. Bật riêng M1, Rcv trên test từ 76.2 còn 70.1. Bật riêng M5, gần như không đổi. Nhưng bật cả hai thì còn khoảng 55.6 trên test và 37.7 trên val. Lý do: M1 làm độ bất định vị trí của Kalman tăng lên mỗi frame không thấy người. M5 kéo box về phía đèn bằng một phép đo có độ tin cố định, được thiết kế là cú kéo nhẹ. Nhưng Kalman cân giữa dự đoán và phép đo theo độ bất định: dự đoán càng không chắc thì phép đo càng được tin. Nên khi M1 làm độ bất định phình ra, cú kéo nhẹ của M5 thành kéo hẳn. Mình đo trong các frame bị chói: box vẫn còn, vẫn đúng chiều cao, nhưng trượt ngang khỏi người, trung vị khoảng 10 phần trăm bề rộng người trên test và 39 phần trăm trên val. Để chắc chắn, mình dùng công tắc con trong code của Thạch: chỉ M5 cộng riêng phần nở vùng bất định của M1 là đã ra 53.6 trên test; còn tắt riêng phần đó khỏi cấu hình đầy đủ thì hồi lại 69.5. Các lượt này chỉ để chẩn đoán, không dùng để chọn cấu hình.

## Slide 31 — Kết quả v2 trên val  _(≈ 36 giây)_

Giờ đến tập val, phần dữ liệu Thạch chưa dùng tới. Cấu hình đầy đủ cộng M6 so với PEG: Table I −0.39 HOTA, số lần đổi ID từ 15 lên 48; Table II −3.09 HOTA; Table III từ 67.6 xuống 37.1. Tức là mức tăng Table I trên test không lặp lại trên val, còn Table III sụt như trên test và còn nặng hơn. Ngay cả base, tức PEG cộng logic đổi ID cũ, cũng kém PEG ở Table I trên val: 69.98 so với 70.24, và đổi ID 28 lần so với 15.

## Slide 32 — Chọn trên val bằng luật chốt trước  _(≈ 72 giây)_

Đây là bước chọn. Luật được viết và đưa lên git trước khi có số val nào. Ứng viên là mười ba cấu hình của Thạch, so với base. Vòng một: không bảng nào được giảm quá 0.5, và tổng mức tăng phải lớn hơn 0.5. Chỉ có 2 cấu hình qua vòng này: full-M5 và base+M1. Vòng hai là điều kiện mình thêm từ bài học lần trước: bỏ đi một video, hoặc một lần chói, có lợi nhất cho cấu hình đó mà vẫn còn tăng thì mới nhận. Cả hai đều trượt: mức tăng của chúng đến từ đúng một video ở Table II, video 147, và một lần chói ở Table III, video 332. Mọi cấu hình có cả M1 và M5 bị loại ngay ở vòng một vì Table III giảm khoảng ba mươi điểm, và M6 bị loại vì cả ba bảng đều giảm trên val. Kết quả: không method nào được val ủng hộ, nên cấu hình được chọn là base. Báo test đúng một lần cho cấu hình này: Table I 68.84, Table II 62.18, Table III 76.2, so với PEG 68.34, 61.41 và 76.2.

## Slide 33 — Tune lại tham số trên val từ đầu  _(≈ 127 giây)_

Chọn lại trên val chưa đủ, vì các tham số bên trong method vẫn là số Thạch đã chỉnh trên test. Nên bọn mình tune lại từ đầu, chỉ trên val, với luật viết trước và đưa lên git trước khi chạy. Điểm xuất phát là PEG: bọn mình chép lại logic đổi ID gốc của PEG vào code của Thạch và kiểm tra là khi tắt hết method thì ra đúng từng số của PEG. Phần đổi ID mà Thạch viết lại cũng thành một thành phần để thử. Mỗi vòng, mỗi thành phần được thử với vài giá trị tham số, vòng đầu tổng cộng 26 lượt. Bảng này là giá trị tốt nhất của từng thành phần ở vòng đầu. Chỉ có hai thứ tăng quá ngưỡng: cone của M1, cộng 1.73, và phần hãm vận tốc, cộng 1.32. Nhưng khi bỏ đi một video hoặc một lần chói có lợi nhất, cone còn −0.01 và hãm vận tốc còn −0.60: toàn bộ mức tăng của cone nằm ở hai video, 156 và 147, còn của hãm vận tốc nằm ở một lần chói trong video 332. Phần nở vùng bất định, Re-ID và pool track ngủ không đổi gì khi đứng một mình; neo đèn và tone-map làm giảm. Nên không thành phần nào được nhận, cấu hình cuối cùng chính là PEG, và test một lần cho nó ra đúng số PEG: 68.34, 61.41 và 76.2. Cột cuối là số test của từng thành phần, chạy sau khi đã chốt, chỉ để đối chiếu. Trên test cũng vậy: M6 và phần đổi ID viết lại tăng gần như chỉ nhờ sửa đúng một lần đổi ID ở video 129, lần đó đáng hai mươi ba điểm HOTA ở video ấy; cone tăng chủ yếu nhờ video 204; còn hãm vận tốc giảm tám điểm rưỡi, nên val loại nó là đúng. Lưu ý là số test của M6 và phần đổi ID bị lạc quan, vì Thạch đã chỉnh chúng trên chính tập test.

## Slide 34 — Full metrics trên test  _(≈ 69 giây)_

Đây là bảng đầy đủ trên test: mỗi dòng là PEG cộng một thành phần, với tham số tốt nhất chọn trên val, cộng hai bản mạnh nhất và bản của Thạch. Xanh là tốt hơn PEG, đỏ là kém hơn, cột cuối ghi video quyết định mức tăng. Bản mạnh nhất mà để val chọn hết, gồm cone và hãm vận tốc, chỉ ra Table III 70.0, kém PEG, vì phần hãm vận tốc. Bản tốt nhất là PEG+ cộng cone: Table I 68.44, Table II HOTA 63.14, Table III 83.1, tốt hơn PEG ở cả ba bảng, và hơn PEG+ một mình +0.81 HOTA ở Table II và +0.9 ở Table III. Phần tăng Table III của nó không phụ thuộc một video: bỏ lần chói có lợi nhất thì vẫn còn khoảng cộng bốn điểm rưỡi. Bản của Thạch có Table I cao nhất, nhưng Table III chỉ 53.6. Bốn dòng PEG-C ở cuối: PEG-C online, T1 IDF1 84.26, T3 80.4; bản có S, T2 HOTA 62.67 nhưng nhờ một video; ALL cộng cone của Thạch. Chi tiết ở slide PEG-C.

## Slide 35 — Full metrics trên val  _(≈ 35 giây)_

Đây là cùng bảng trên val, tập dùng để chọn. Trên val các mức chênh nhỏ hơn và gần như mức nào cũng nằm ở một hai video: cone nhờ video 156 và 147, hãm vận tốc nhờ một lần chói ở video 332. PEG+ trên val gần như bằng PEG, vì val hầu như không có ca box bị co lại khi coast. Bốn dòng PEG-C ở cuối: trên val PEG-C online tăng Table III lên 75.8 so với 67.3 của PEG+, đó là phần V được chọn; dòng fixed-lag chỉ có val.

# NGƯỜI 2 — PEG+ và kết hợp (≈ 19.9 phút)

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

## Slide 36 — PEG-O: dùng chính vùng chói để đo box dời bao xa  _(≈ 60 giây)_

PEG: ánh sáng phá hủy quyết định giữ box. PEG-O: cùng ánh sáng đó đo box đã dời bao xa — không giả định đèn ở đâu trên người, và chỉ tin khi đỉnh tương quan đủ nhọn. Đi qua bốn dòng. Một, tâm đĩa chói gắn cứng với người, nên độ dời của đĩa chính là độ dời của người, không cần biết đèn nằm đâu. Hai, lọc đĩa trên thành phần bão hòa để tìm tâm đĩa. Ba, độ nhọn của đỉnh là độ tin cậy: đỉnh phẳng thì không cập nhật. Bốn, đưa độ dời vào Kalman chỉ cho tâm, kích thước giữ như PEG+. Sau thử nghiệm trên video 135, bọn mình đã đổi một lần: với nhiễu đo tuyệt đối của kế hoạch ban đầu, gain gần như bằng không nên box không nhúc nhích; đổi sang nhiễu tương đối theo độ nhọn, và ghi thay đổi này vào protocol trước khi chạy val.

## Slide 37 — PEG-O trên val và test: không qua  _(≈ 47 giây)_

Kết quả thẳng thắn: PEG-O không qua. Trên val, cả chín điểm của lưới tau và gamma đều làm Table III sụt, mất từ 13.5 đến 41.2 điểm, nên theo luật viết trước, cấu hình cuối vẫn là PEG+. Test chạy đúng một lần, ở điểm val tốt nhất để báo cáo cho đủ: Table III Rcv 73.6 so với 82.2 của PEG+, và Table I, II gần như không đổi. Gộp 48 lần chói, PEG-O thấp hơn PEG+ 10.6 điểm, khoảng tin cậy không chứa không. Một chi tiết thú vị: tỉ lệ ID bị tắt giảm, 9.5 phần trăm so với 15.5, vì box sống lâu hơn; nhưng phần lớn các box đó bị lệch khỏi người nên không tính là trúng.

## Slide 38 — Vì sao thua: đĩa chói không cứng  _(≈ 71 giây)_

Hai video cho hai kết cục. Ở video 135 trên test, người đi khoảng 111 pixel và box rộng 264: với cấu hình tau 0,06 gamma 1, box bám theo người, 41 trên 43 frame trúng, đúng bằng cận trên nếu căn tâm hoàn hảo. Nhưng chính cấu hình đó không phải điểm val chọn; điểm báo cáo tau 0,08 gamma 4 chỉ được 11 trên 43. Ở video 187 trên val thì ngược lại: người gần như đứng yên, box chỉ rộng 30 pixel, nhưng đỉnh của bộ lọc đĩa trôi mười đến hai mươi pixel khi độ chói tăng rồi giảm, vì vùng bão hòa đổi hình chứ không dời theo người. Với box hẹp như vậy, sai số đó đủ để mất box. Bọn mình kiểm tra lại là không phải lỗi code: ước lượng offline với mốc là đúng vị trí thật cũng thua, không có anchor cũ, và độ lệch trung vị của cập nhật là 9.7 pixel so với bề rộng box 41. Ngoài ra anchor lấy đúng lúc chói đang tăng, và vận tốc bị bơm vào Kalman nên box tiếp tục trôi.

## Slide 39 — Coast chưa được thiết kế  _(≈ 92 giây)_

Phần này là phân tích oracle, chưa phải tracker. Câu hỏi: PEG giữ box cho người đang bị chói, nhưng box giữ như thế nào là tốt nhất. Mình lấy bốn mươi ba lần chói mà PEG+ đang theo dõi người, rồi thử áp một vận tốc không đổi từ khung cuối có detection. Nếu cứ đứng yên thì Rcv@.5 là 72.9 khi gộp. Nếu đoán vận tốc từ năm khung gần nhất thì chỉ 62.9, tệ hơn đứng yên, vì năm khung là nhiễu. Nếu đoán từ bốn mươi khung thì lên 87.8, trên val 86.6 và trên test 88.5, cao hơn cả PEG+ thực tế là 84.2. Trần lý thuyết nếu biết vận tốc thật là 96.0, và nếu biết cả tâm thật thì 99.9. Hình bên phải trả lời vì sao cửa sổ dài thắng: nét đứt xám là sai số nếu chỉ có nhiễu trắng, σ bằng 2.21 pixel, rơi theo K mũ trừ một phẩy năm. Đường xanh là sai số đo được, và nó dừng ở khoảng 0.28 pixel mỗi frame, bằng khoảng 54 phần trăm tốc độ thật. Đường cam là sai số khi lấy vận tốc từ chính ground truth quá khứ, cũng dừng ở khoảng 0.30. Vậy phần sai còn lại là do người đổi nhịp, tức là do mô hình vận tốc không đổi, không phải do nhiễu. Hàm ý: đi bộ dự đoán được từ cửa sổ dài, còn năm khung thì không.

## Slide 40 — PEG-C: PEG quyết định có giữ, PEG-C thiết kế giữ thế nào  _(≈ 115 giây)_

PEG trả lời câu hỏi có nên giữ box hay không, bằng cổng phi lớn hơn hoặc bằng h. PEG-C trả lời câu hỏi giữ như thế nào, bằng một mô hình duy nhất: vận tốc không đổi. Mô hình này dùng theo hai cách. Cách thứ nhất là bộ lọc online, gồm ba thành phần. V: lúc bắt đầu coast, vận tốc lấy từ độ dốc bình phương tối thiểu của K tâm detection gần nhất, thay vì vận tốc Kalman bị chói làm sai; trục nào có độ dốc nhỏ hơn t lần sai số chuẩn thì đặt bằng không. C: cổng chỉ được arm khi track đã mất không quá N khung. S: nếu ngay sau khi hết chói có một detection định sinh ID mới mà nằm sát box dự đoán của một track vừa cháy, thì nối lại thay vì sinh ID mới, chỉ khi ghép một đối một. Cách thứ hai là bộ làm mượt fixed-lag, cho phép sửa các hàng đã ghi tới L khung trước. B: khi một track cháy được bắt lại sau M khung, nối đường thẳng giữa hai detection hai đầu và điền vào khoảng trống; chế độ hidden chỉ thêm hàng còn thiếu, chế độ all thay luôn box coast. BB: nếu một track đã cháy ngay lúc sinh thì thêm hàng ngược về trước. Mỗi thành phần chỉ có một núm, lưới viết trước trong protocol, và val chọn. Có hai lưu ý ghi ở khung dưới. Một, dữ liệu chói giả đặt đĩa chói theo đúng ground truth box, nên bất cứ thứ gì đọc hình đĩa là rò rỉ; PEG-C chỉ đọc cổng phi lớn hơn h, giống PEG. Hai, B và BB sửa quá khứ nên không phải online; mọi hàng của chúng luôn gắn nhãn fixed-lag và báo riêng.

## Slide 41 — PEG-C trên val và test: val nhận V, test không xác nhận  _(≈ 100 giây)_

Kết quả thẳng thắn. Trên val, luật chốt trước chấp nhận V, vận tốc từ bốn mươi khung với t bằng hai: Table III tăng +8.5, Table I và II gần như không đổi. Thành phần S, nối lại ID sau chói, tăng Table II trên val nhưng chỉ nhờ một video, nên luật chặt không nhận. C và B hidden không đổi gì; B all làm Table III val giảm. Test chạy đúng một lần: Table III −1.7 so với PEG+, Table II HOTA −1.4, và Table I IDF1 +1.0. Theo từng lần chói, test −1.8 với khoảng tin cậy từ −7.7 đến +3.6, 4 tốt hơn và 5 tệ hơn; val +8.6 với 9 tốt hơn và 1 tệ hơn; gộp +2.4, khoảng tin cậy từ −2.1 đến +6.8, còn chứa không. Hàng nhỏ màu hồng là fixed-lag chín mươi khung: không được val chọn, và trên Table III trùng online. Hai hình dưới là hai đầu: video 187 trên val, người đi đều, cửa sổ sạch, PEG+ 19 lên 35 trên 35 khung; video 211 trên test, 25 xuống 13 trên 25. Phân tích sau test, không dùng để chọn: ở hai video thua trên test, vận tốc Kalman sẵn có của PEG+ lúc vào coast gần vận tốc thật hơn độ dốc bốn mươi khung: ở 211, Kalman (-0.33, 1.42), OLS (0.53, 1.08), thật (-0.08, 1.96); cửa sổ bốn mươi khung bắc qua một khoảng trống bốn mươi khung trước đó. Nền dài chỉ thắng khi người đi đều. Lợi ích nhất quán duy nhất trên test là IDF1 Table I, +1.0.

## Slide 42 — Kết luận và bài học  _(≈ 152 giây)_

Tóm lại bảy điều. Một, PEG-F bản đầu tái hiện được, nhưng khi so cùng cấu hình thì mức tăng chỉ +0.49 HOTA, và hai lần đổi ID quyết định gần hết mức tăng đó. Hai, PEG-F bản hai: Table I tái hiện đúng cả mười bốn cấu hình, nhưng Thạch chỉnh và chọn mọi thứ trên test; khi chọn lại trên val bằng luật chốt trước thì không method nào qua; và khi tune lại tham số từ đầu, chỉ trên val, kết quả vẫn vậy, cấu hình cuối cùng là PEG. Ba, ở bản hai, M1 đi cùng M5 làm Table III sụt mạnh, từ 76.2 xuống 53.6 trên test và từ 67.6 xuống 37.1 trên val, vì box bị kéo trượt ngang khỏi người. Bốn, PEG+ tăng Rcv trên test +5.6, trên val −0.4, gộp lại +3.2: chỉ giúp khi box co lại lúc coast. Năm, PEG-O, thử đo vị trí bằng chính vùng chói: đúng ở video 135 nơi người đi xa, nhưng so với PEG+ trên val −13.5 và trên test −8.6 Rcv, nên không nhận, vì đĩa chói đổi hình chứ không cứng. Sáu, PEG-C, thiết kế lại cách coast bằng vận tốc đo từ cửa sổ quá khứ dài: val nhận V và Table III tăng +8.6, nhưng test không xác nhận, −1.8 với khoảng tin cậy từ −7.7 đến +3.6, chỉ IDF1 Table I tăng +1.0; bài học là lợi ích oracle do val dẫn dắt thì vẫn do val dẫn dắt, và sàn sai số của vận tốc là mô hình vận tốc không đổi, không phải nhiễu. Bảy, nhìn một mình Table I rất dễ bị đánh lừa, nên lúc nào cũng đo đủ ba bảng, chọn trên val và báo test một lần. Hướng tiếp theo: chọn bằng khoảng tin cậy hoặc cross-validation thay vì ngưỡng cứng; thêm dữ liệu val, vì hiện giờ một hai video quyết định mọi mức tăng; đo vị trí từ vùng chói chỉ khi đĩa đã ổn định và box đủ lớn so với nhiễu đo khoảng 10 pixel; và M6 đáng thử lại khi có thêm dữ liệu val có người đứng gần đèn. Bài học lớn nhất với mình không phải một con số mà là cách làm: tái hiện trước, so cùng cấu hình, đo cả ba bảng, chọn trên val, và tách từng phần ra để xem phần nào thật sự có tác dụng.

## Slide 43 — Hỏi đáp (cả hai)

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

**9. Sao không lấy thẳng số full+M6 của Thạch (+1.69 HOTA)?** _(Người 1 trả lời)_

Vì số đó được chọn trên test: trong kết quả Thạch gửi có 56 lượt chạy Table I trên test và không lượt nào trên val. Chọn lại trên val bằng luật chốt trước thì không method nào qua. Ngoài ra full+M6 làm Table III giảm từ 76.2 xuống 53.6 trên test.

**10. Có chắc M1 × M5 là nguyên nhân Table III sụt không?** _(Người 1 trả lời)_

Có, vì bọn mình kiểm tra bằng công tắc con trong chính code của Thạch: chỉ M5 cộng riêng phần nở độ bất định của M1 đã đủ gây sụt, và tắt riêng phần đó khỏi cấu hình đầy đủ thì Table III hồi lại. Đo từng frame chói cũng thấy box đúng chiều cao nhưng trượt ngang.

**11. M6 có vẻ tốt trên test, sao không giữ?** _(Người 1 trả lời)_

Trên test M6 tăng cả ba bảng, nhưng trên val cả ba bảng đều giảm nhẹ (T1 −0.10, T2 −0.73, T3 −0.7). Luật chốt trước không cho nhận; M6 đáng thử lại với nhiều dữ liệu hơn.

**12. B và M5 thua, PEG-O khác gì mà vẫn thua?** _(Người 2 trả lời)_

B và M5 giả định đèn nằm cách tâm người 0.35 lần chiều cao nên lệch có hệ thống. PEG-O chỉ đo độ dời nên không cần offset, và đúng ở video 135 (41/43 frame với τ .06 γ 1). Nhưng đĩa chói không cứng: khi độ chói tăng hay giảm thì đỉnh lọc dịch 10–20 px dù người không đi, và với người rộng khoảng 30 px thì đủ mất box. Kết quả: val −13.5, test −8.6 Rcv so với PEG+.

**13. Khi nào PEG-O không giúp?** _(Người 2 trả lời)_

Khi người đứng yên hoặc hẹp (val: 187, 203, 210); khi vùng chói phẳng (nửa khung hình trắng, như video 325): đỉnh chỉ nhọn ở cuối lần chói nên PEG-O gần như không đổi gì (bằng PEG+); và khi mục tiêu chưa bao giờ được track trước lúc chói (312, 305): không cách coast nào cứu được. PEG-O chỉ có ích khi quãng người đi lớn so với nhiễu đo khoảng 10 px.

**14. Fixed-lag có phải ăn gian không?** _(Người 2 trả lời)_

Không phải ăn gian, nhưng cũng không phải online: B và BB sửa hoặc thêm các hàng đã ghi tới L khung trước, nên có độ trễ tối đa L khung. Vì vậy bọn mình báo riêng, luôn gắn nhãn fixed-lag L, không trộn với hàng online. Ở đây val không chọn nó: B hidden không thêm hàng nào ở Table III, còn B all làm Table III val giảm.

**15. Synth rò rỉ GT thì PEG cũng rò rỉ?** _(Người 2 trả lời)_

Synth đặt đĩa chói theo đúng GT box nên mọi phương pháp đọc hình hay vị trí đĩa đều rò rỉ GT. PEG và PEG-C chỉ đọc phi lớn hơn h, tức là cổng tồn tại: phần rò rỉ chỉ là có cháy hay không, giống nhau cho mọi phương pháp dùng cổng. Table I trên video thật là phép kiểm tra không rò rỉ.

**16. Vì sao PEG-C val tăng mà test không?** _(Người 2 trả lời)_

Val nhỏ, mười tám lần chói, và các thành phần được chọn từ phân tích oracle đã gộp cả val lẫn test. Trên test vận tốc từ cửa sổ dài sai ở hai video người đổi nhịp hoặc cửa sổ bắc qua một khoảng trống: Kalman sẵn có của PEG+ lúc vào coast gần vận tốc thật hơn. Đây là phân tích sau test, không dùng để chọn.

**17. Vậy rốt cuộc PEG+ có tốt hơn PEG không?** _(Người 2 trả lời)_

Chỉ ở những ca box co lại khi coast. Trên test nó tăng +5.6 Rcv, trên val −0.4. Gộp 48 lần chói thì tăng +3.2 với khoảng tin cậy [+0.1, +7.3]: có dấu hiệu tốt nhưng chưa chắc chắn.

