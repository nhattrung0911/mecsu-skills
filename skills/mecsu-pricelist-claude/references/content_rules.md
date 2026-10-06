# Quy tắc nội dung card (cho người viết nội dung)

Rút ra từ 5 bảng giá chuẩn: SKF (67 card), ASAHI (23), Bosi (78), Sata (153), Stanley (113). Số đếm dưới đây là số card có nhãn đó.
Mục tiêu: mỗi card = 1 bảng nhỏ đọc được trong 5 giây, giống Stanley: tiêu đề IN HOA, vài dòng mô tả ngắn, ảnh, bảng.

## Mục lục
- 1. Cấu trúc một card (thứ tự in)
- 2. Title
- 3. Dòng mô tả (`lines`, 0–5 dòng, mỗi dòng ≤ 28 ký tự)
- 4. Từ vựng tiêu đề cột (header)
- 5. Legend (chú giải ký hiệu)
- 6. Nhóm và tách card
- 7. Ghi chú (`note`)
- 8. Dữ liệu dòng
- 9. Ví dụ card (hợp lệ theo `config/doc.schema.json`)
- 10. Tự kiểm tra trước khi giao doc.json

## 1. Cấu trúc một card (thứ tự in)
1. `title` (2 dòng đầu, Calibri 9 đậm).
2. `lines` mô tả (0–5 dòng, Calibri 8) rồi `legend` (chú giải ký hiệu), cùng khu vực bên trái ảnh.
3. `VAT: 8%` (builder tự thêm), hàng tiêu đề 2 dòng, các dòng dữ liệu.
4. `note` (nếu có) in nghiêng đậm dưới bảng.

Cột luôn là: `Mã Hãng` | các cột thông số | `Mã Đặt Hàng` | `Giá/Cái\nChưa VAT`. Không tự thêm cột khác ngoài thông số.

## 2. Title
- IN HOA, tiếng Việt, có dấu: `{LOẠI SẢN PHẨM}` + `{biến thể chính}` + (tuỳ chọn) `{dòng/series}`. Không ghi tên hãng (đã có ở tiêu đề trang), không ghi mã sản phẩm riêng lẻ.
- Mẫu thật: `KÌM MỎ NHỌN`, `KÌM CẮT CÁCH ĐIỆN`, `MỎ LẾT CÓ ĐIỀU CHỈNH`, `BỘ KÌM 3 CHI TIẾT`, `CỜ LÊ MIỆNG HỞ - TUÝP LẮC LÉO`, `VÒNG BI CẦU 1 DÃY KHÔNG NẮP DÒNG 6200`, `VÒNG BI CẦU 1 DÃY 2 PHỚT CAO SU DÒNG 6000`.
- Biến thể chính = đặc điểm làm các sản phẩm trong card khác card khác: có/không nắp, loại phớt, cách điện, loại đầu. Chỉ chọn 1–2 đặc điểm.
- Dài tối đa ~40 ký tự (title chiếm 2 dòng × bề rộng card; card 17 cột ≈ 30 ký tự/dòng).
- Nếu gốc data viết Title Case (Bosi/ASAHI: `Cờ Lê 2 Đầu Miệng Cao Cấp`) vẫn chuyển sang IN HOA.
- Không dấu hai chấm, không dấu chấm cuối, không emoji.

## 3. Dòng mô tả (`lines`, 0–5 dòng, mỗi dòng ≤ 28 ký tự)
Thứ tự ưu tiên (bỏ dòng nào không có dữ liệu thật; không bịa):
1. Vật liệu / chất liệu: `Vật Liệu: Thép`, `Vật Liệu: Thép Crom-Vanadium`.
2. Đặc điểm cấu tạo nổi bật: `Tay Cầm Bọc Nhựa`, `Hàm Kẹp Cong`, `Có Cách Điện 1000V`.
3. Công dụng: `Dùng Cắt Dây Thông Dụng`.
4. Tiêu chuẩn / bề mặt: `Mạ Crom`, `Theo Tiêu Chuẩn DIN`.
5. Chú giải ký hiệu — đặt ở `legend`, KHÔNG để trong `lines` (xem mục 5).

Quy tắc: Title Case tiếng Việt, đầu dòng viết hoa, không dấu chấm cuối; dạng `Nhãn: Giá Trị` khi là thuộc tính, cụm danh từ khi là đặc điểm. Dòng dài hơn 28 ký tự phải rút gọn hoặc chia 2 dòng, không để builder cắt chữ. Card chỉ có 1 sản phẩm: 2–3 dòng là đủ. Mục tiêu đồng nhất: mọi card có 1–3 dòng có nguồn; chỉ để trống khi thật sự không có nguồn (ghi review.md).

## 4. Từ vựng tiêu đề cột (header)
Quy tắc đơn vị: nhãn viết `"<Tên>\n(<đơn vị>)"` với ký tự xuống dòng thật `\n` trong JSON, đơn vị luôn trong ngoặc, đơn vị viết thường: `(mm)`, `(inch)`, `(kN)`, `(rpm)`, `(N.m)`, `(kg)`, `(g)`. Không dùng `mm` trần, `(Inch)`, `(in)`, `(cm)` nếu đổi được sang mm. Nhãn không có đơn vị (số lượng, loại): không xuống dòng. **Ngoại lệ cột chữ cái hẹp (vòng bi d/D/B, card 26 cột):** dùng `"d\nmm"` không ngoặc như bản FBJ/SKF chuẩn để cột chỉ cần 2 ô. Chữ cái kích thước (d, D, B, L, A…) chỉ được dùng khi có dòng chú giải/ảnh bản vẽ cùng chữ đó (mục 5); nếu không có bản vẽ, dùng tên đầy đủ.

| Nhãn (xuất hiện) | Ý nghĩa | Khi dùng |
|---|---|---|
| `Mã Hãng` (mọi card) | mã nhà sản xuất | luôn, cột đầu tiên, role `code` |
| `Mã Đặt Hàng` (mọi card) | mã Varin 7 chữ số | luôn, cột cuối trước giá, role `order_code` |
| `Giá/Cái\nChưa VAT` (mọi card) | giá, VLOOKUP | luôn, cột cuối. ASAHI cũ dùng `(Chưa VAT)`, chuẩn mới bỏ ngoặc |
| `d\n(mm)` (67 SKF, 25 ASAHI) | đường kính trong vòng bi / lỗ | vòng bi; cần legend `d: Đường Kính Trong` |
| `D\n(mm)` (68) | đường kính ngoài | vòng bi; legend `D: Đường Kính Ngoài` |
| `B\n(mm)` (73) | độ dày / bề rộng vòng bi | vòng bi; legend `B: Độ Dày Vòng Bi`. Stanley dùng `B` = chiều rộng tay cầm: phải có legend riêng |
| `C\n(kN)` (67) | tải trọng động | vòng bi SKF; legend `C: Tải Trọng Động` |
| `C₀\n(kN)` (67) | tải trọng tĩnh | cùng bộ với C; legend `C0: Tải Trọng Tĩnh` |
| `N\n(rpm)` (49) | tốc độ quay tối đa | khi có dữ liệu; legend `N: Tốc Độ Quay Tối Đa (vòng/phút)` |
| `Nắp Chắn` | loại nắp/phớt | bảng FBJ gộp nhiều loại nắp trong một card (xem mục 6) |
| `Size\n(mm)` / `Size\n(inch)` (Bosi 12/31) | cỡ danh nghĩa | cờ lê, tuýp, mỏ lết, kìm: cỡ miệng/vuông/lục giác. Dùng `Size\n(mm)` cho hệ mét, `Size\n(inch)` cho hệ inch, cả hai khi có |
| `Chiều Dài\n(mm)` / `Tổng Chiều Dài\n(mm)` (Bosi 17/9, Sata 7) | chiều dài toàn bộ | khi không có bản vẽ. Có bản vẽ + legend → `L\n(mm)` (Sata 27, Stanley 6) |
| `Chiều Dài\n(inch)` (Stanley 16) | chiều dài hệ inch | hãng ghi inch (kìm Stanley); chuẩn hoá thành `(inch)` |
| `A\n(mm)`, `C\n(mm)`, `DL\n(mm)`, `PD\n(mm)`, `OH\n(mm)` (Sata) | kích thước theo bản vẽ | chỉ khi có legend/bản vẽ ghi đúng chữ; đổi cm → mm khi có thể |
| `S\n(mm)` (Stanley 6) | cỡ miệng/đầu | khi legend `S: ...` |
| `Số Chi Tiết` (Stanley 20) | số món trong bộ | mọi card "BỘ …"; số nguyên không đơn vị |
| `Bấm Cos\n(mm²)` (Bosi 27) | phạm vi cos bấm được | kìm bấm cos; đơn vị lên nhãn, ô chỉ ghi số `0.5-6` |
| `Lực Siết\n(N.m)` (Bosi 4) | lực siết | cần siết lực |
| `Chuôi Gài\n(inch)` (Bosi 4) | cỡ đầu vuông gài | cần siết lực, khẩu |
| `Loại Cán`, `Quy Cách`, `Sai Số`, `Khoảng Đo`, `Độ Chia Nhỏ Nhất` (Sata 3–5) | thuộc tính chữ | khi thông số là chữ ngắn, không là số |
| `Dùng Cho Dây\n(mm²)` (Stanley 3) | tiết diện dây | kìm tuốt dây, bấm cos |

Giới hạn: 0–4 cột thông số (chuẩn Stanley); tối đa 6 khi bắt buộc (vòng bi SKF). Quá nhiều cột → xem quy tắc tách ở mục 6. Hai nhãn đồng nghĩa trong cùng một file chuẩn không được trộn (chọn `Chiều Dài` hoặc `L`, không cả hai).

## 5. Legend (chú giải ký hiệu)
- Mỗi chữ cái làm nhãn cột (d, D, B, L, S, A…) cần một dòng `legend`, đúng định dạng `Chữ: Tên Tiếng Việt` (có thể thêm đơn vị khi nhãn cột không có): `d: Đường Kính Trong`, `L: Chiều Dài Kìm`, `T: Độ Dày Đầu`, `B: Chiều Rộng Tay Cầm`, `C0: Tải Trọng Tĩnh` (ký hiệu `C₀` ở cột ↔ `C0` ở legend).
- Thứ tự legend = thứ tự cột. Mỗi dòng ≤ 28 ký tự nếu có thể; dài hơn (như `N: Tốc Độ Quay Tối Đa (vòng/phút)`) vẫn chấp nhận nhưng QA cảnh báo.
- Nếu có ảnh bản vẽ kỹ thuật ghi chữ L/B/T thì legend phải khớp chữ trên bản vẽ. Không bản vẽ, không legend: dùng nhãn đầy đủ thay vì chữ cái.
- Legend nằm trong `legend[]`, không trộn vào `lines[]`.
- Ký hiệu cho phép: 1–4 ký tự Latin hoặc Φ/Ø/Δ, có thể kèm chỉ số (`C₀`, `AVM`, `ØQ`). Chữ hoa/thường ở legend phải trùng nhãn cột.
- Card có `drawing` (bản vẽ ghi chữ kích thước) thì legend là tuỳ chọn; KHÔNG sinh legend chung chung kiểu `X: Kích Thước X` — hoặc ghi nghĩa thật, hoặc để bản vẽ giải thích.

## 6. Nhóm và tách card
Một card = một nhóm sản phẩm có cùng bộ cột và cùng loại. Tách thành nhiều card khi:
1. Khác bộ cột hoặc khác đơn vị (ví dụ cờ lê Size mm vs Size inch).
2. Khác biến thể chính đáng ghi lên title: nắp chắn/phớt/độ hở C3 (SKF tách `KHÔNG NẮP`, `2 PHỚT CAO SU`, `2 NẮP CHẮN THÉP`), cách điện/không cách điện, đầu cắt/đầu nhọn.
3. Khác dòng bearing có kích thước ngoài khác hẳn (dòng 6000, 6200, 6300 → 3 card).
4. Quá 25–30 dòng dữ liệu → tách theo khoảng kích thước (`… DÒNG 6200 (d 10–40)`) hoặc để builder tự tách (title/VAT/header lặp lại); chỉ tách tay khi ranh giới có nghĩa.
5. Một sản phẩm đơn lẻ có ảnh riêng → card riêng 1 dòng, `data_row_height: 3`.

**Ưu tiên số 1 — data của user:** nếu data có cột `Tên Bảng Giá`, đó là tiêu đề (IN HOA, giữ nguyên chữ). Quy tắc C và "Nguồn của biến thể" bên dưới chỉ dùng khi user yêu cầu Claude tự đặt tên. Cùng tên + cùng bộ cột → 1 card (pl_draft tự gộp); cùng tên khác bộ cột → giữ nguyên, báo user.

**Quy tắc C (bắt buộc, lint chặn):** một tiêu đề = một loại sản phẩm. Hai card không được trùng tiêu đề.
- Cùng loại + cùng ảnh + cùng bộ cột → GỘP thành 1 card nhiều dòng.
- Khác loại (ảnh khác, kết cấu khác: cos trần / cos cách điện / cos ống, thủy lực / cơ…) → card riêng, tiêu đề ghi biến thể: `KÌM BẤM COS CÁCH ĐIỆN`, `KÌM BẤM COS ỐNG`. Biến thể phải tra từ nguồn thật (skill `naming-handtools`), không đoán; tra không ra → dùng đặc điểm thấy được (dải bấm `0.25-6 MM²`) và báo user.

**Nguồn của biến thể (bắt buộc):** chỉ lấy từ (a) snippet tìm kiếm có nhắc đúng mã, hoặc (b) cột/legend/ảnh có sẵn trong data. CẤM suy từ định dạng mã (vd "chữ số đầu = cỡ đầu vuông"), CẤM đổi loại sản phẩm dựa trên snippet bị cắt. Mọi tiêu đề không có nguồn (a) ghi vào `<W>/review.md` (card, cũ → mới, căn cứ) để user duyệt.

Gộp khi: cùng bộ cột, sản phẩm chỉ khác 1 cột thông số (ví dụ cùng loại nắp, khác kích thước) → một card, không tách theo cột thứ yếu. Thứ tự dòng: tăng dần theo cột thông số chính (Size, d, Chiều Dài), không theo mã.
Mỗi card ≤ 1 ảnh. Card ≥ 2 dòng nên có ảnh; card 1 dòng nên có ảnh.

## 7. Ghi chú (`note`)
- Chỉ dùng cho thông tin áp dụng cả card mà không đưa được vào cột: ý nghĩa hậu tố (`Ký Hiệu 2RS Là Phớt Cao Su Hai Bên`), quan hệ dòng (`Dòng 6300 Có Đường Kính Ngoài Và Độ Dày Lớn Hơn 6200`), điều kiện (`Giá Theo Cái`).
- Một câu, tối đa ~100 ký tự, Title Case như `lines`, không dấu chấm cuối. SKF có 24 ghi chú loại này; Stanley/Bosi gần như không có.
- Không ghi giá, tồn kho, khuyến mãi, nguồn.

## 8. Dữ liệu dòng
- Mã Hãng: chuỗi giữ nguyên như hãng (`84-623`, `6204-2RS`), không thêm dấu cách.
- Mã Đặt Hàng: chuỗi đúng 7 chữ số (`"0927517"`), không để số.
- Số kích thước: số hoặc chuỗi; dùng `.` làm dấu thập phân, bỏ `.0` thừa (`164.6`, `20`).
- Trống: để `""`, không ghi `N/A`, `-`.

## 9. Ví dụ card (hợp lệ theo `config/doc.schema.json`)

### 9.1 Vòng bi cầu 1 dãy (nhiều loại nắp, legend khớp bản vẽ)
```json
{"id":"vong-bi-6200-2rs","group":"VÒNG BI CẦU 1 DÃY 2 PHỚT CAO SU DÒNG 6200","title":"VÒNG BI CẦU 1 DÃY 2 PHỚT CAO SU DÒNG 6200","lines":["Phớt Cao Su Hai Bên","Vòng Cách Thép Dập"],"legend":["d: Đường Kính Trong","D: Đường Kính Ngoài","B: Độ Dày Vòng Bi"],"note":"Ký Hiệu 2RS Là Phớt Cao Su Hai Bên","image":{"path":null,"status":"missing"},"columns":[{"key":"code"},{"key":"d","label":"d\n(mm)"},{"key":"D","label":"D\n(mm)"},{"key":"B","label":"B\n(mm)"},{"key":"order"},{"key":"price"}],"rows":[{"code":"6200-2RS","d":10,"D":30,"B":9,"order":"0102001"},{"code":"6201-2RS","d":12,"D":32,"B":10,"order":"0102002"},{"code":"6202-2RS","d":15,"D":35,"B":11,"order":"0102003"}]}
```

### 9.2 Kìm (Stanley: dòng mô tả + legend theo bản vẽ)
```json
{"id":"kim-mo-nhon","group":"Kìm Mỏ Nhọn","title":"KÌM MỎ NHỌN","lines":["Vật Liệu: Thép","Tay Cầm Bọc Nhựa"],"legend":["L: Chiều Dài Kìm","B: Chiều Rộng Tay Cầm","T: Độ Dày Đầu"],"note":null,"image":{"path":"img/kim-mo-nhon.png","status":"ok"},"columns":[{"key":"code"},{"key":"L","label":"L\n(mm)"},{"key":"B","label":"B\n(mm)"},{"key":"T","label":"T\n(mm)"},{"key":"order"},{"key":"price"}],"rows":[{"code":"84-000","L":150,"B":44,"T":8,"order":"0120001"},{"code":"84-002","L":200,"B":55,"T":10,"order":"0120002"}]}
```

### 9.3 Bộ tuýp (bộ có "Số Chi Tiết", không bản vẽ → nhãn đầy đủ, không legend)
```json
{"id":"bo-tuyp-1-2","group":"Bộ Tuýp","title":"BỘ ĐẦU TUÝP 1/2 INCH","lines":["Vật Liệu: Thép Crom-Vanadium","Mạ Crom Bóng","Kèm Hộp Nhựa"],"legend":[],"note":null,"image":{"path":null,"status":"missing"},"columns":[{"key":"code"},{"key":"pieces","label":"Số Chi Tiết"},{"key":"size","label":"Size\n(mm)"},{"key":"order"},{"key":"price"}],"rows":[{"code":"STMT72-001","pieces":12,"size":"10-24","order":"0130001"},{"code":"STMT72-002","pieces":24,"size":"8-32","order":"0130002"}],"data_row_height":1}
```

## 10. Tự kiểm tra trước khi giao doc.json
- Title IN HOA; mỗi `lines` ≤ 28 ký tự và ≤ 5 dòng; `legend` chỉ chứa `Chữ: Tên`.
- Mọi nhãn cột đơn vị có `\n`; mọi chữ cái kích thước có mặt trong legend hoặc bản vẽ.
- Mọi `order` là 7 chữ số dạng chuỗi; mọi `code` không trống.
- Không có hai card cùng title và cùng bộ cột (gộp lại hoặc phân biệt bằng biến thể).
