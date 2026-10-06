# Chạy theo đội: leader điều phối, worker Sonnet làm

## Mục lục
1. Vì sao
2. Ngưỡng giao việc
3. Luật chung cho worker
4. Mẫu giao việc A · B · C · D
5. Leader gộp và chấm

## 1. Vì sao
Leader (phiên đang nói với user, thường là model mạnh) giữ phán đoán. Việc đọc nhiều — tra catalog,
xem contact sheet, soi trang render — giao worker Sonnet chạy song song: nhanh hơn, rẻ hơn, và
context của leader không bị lấp bởi ảnh/JSON. Leader nhận tóm tắt ngắn + đường dẫn file kết quả.

## 2. Ngưỡng giao việc
| Tình huống | Giao khi | Số worker | Mẫu |
|---|---|---|---|
| `STOP 4 data` | ≥ 3 mã trong `items_warnings.txt` | 1 | A |
| `STOP 4 images` | ≥ 2 file `img_work/sheet_*.png` | 1 / sheet, tối đa 3 | B |
| `STOP 4 images-review` | ≥ 2 file `img_work/chosen_sheet*.png` | 1 / sheet, tối đa 3 | B' |
| `STOP 4 lint` | ≥ 10 card lỗi trong `lint_report.md` | tối đa 3, chia theo card | C |
| Soát render | có `team/review_batches.json` (> 4 trang) | theo file đó, tối đa 3 | D |

Dưới ngưỡng: leader tự làm.

## 3. Luật chung cho worker
- Agent tool, `model: "sonnet"`, `run_in_background: true`; mọi worker của một bước gửi trong
  **cùng một lượt** để chạy song song. Không đoán kết quả trước khi có thông báo xong.
- Prompt tự đủ: đường dẫn tuyệt đối, đúng phần việc, file được đọc, **một** file được ghi.
- Worker chỉ ghi `<out>/team/<file của nó>`. Không sửa `doc.json`, `plan.json`, data của user,
  không chạy `run.py`. Hai worker không bao giờ ghi cùng một file.
- Không bịa: giá trị mới phải có `source` (URL, cột data, ảnh số mấy). Không chắc → bỏ qua + nêu lý do.
- Trả lời ≤ 120 từ: đã làm gì, file kết quả, điểm không chắc. Không dán nội dung file.

## 4. Mẫu giao việc
Thay `<...>` bằng giá trị thật trước khi gửi.

### A — Tra catalog cho data nghi sai
```
Đọc <out>/items_warnings.txt (mỗi dòng: MÃ | order id | sheet!dòng | cảnh báo). Xử lý TỪNG mã, không
suy từ vài mã ra cả nhóm. Với mỗi mã: mở https://mecsu.vn/x/i/<order_id> (catalog chính thức),
đọc tiêu đề và bảng thông số. Ghi <out>/team/patches_A.json: danh sách thao tác của pl_patch
({"op":"set_spec","code","label","value","source"} · {"op":"rename_label","group","from","to","source"}
· {"op":"set_brand","group"|"code","brand","source"}); "source" là URL + câu trích. "value" của set_spec là SỐ TRẦN theo đơn vị của cột (vd 20, không «20 lb»); khác đơn vị thì không đưa vào patch. Mã không xác minh
được thì KHÔNG đưa vào file — liệt kê trong câu trả lời. Không sửa file nào khác.
```

### B — Chọn ảnh
```
Xem <out>/img_work/sheet_<k>.png: mỗi hàng là một card (card_id ở đầu hàng), ảnh đánh số.
Chọn cho mỗi card ảnh: đúng sản phẩm, đúng hãng <BRAND>, nền trơn, không watermark/banner/chữ.
Không ảnh nào đạt → ghi 0 (card để trống, leader quyết). Ghi <out>/team/picks_<k>.json =
{"<card_id>": <số thứ tự hoặc 0>}. Không sửa file nào khác.
```

### B' — Soát ảnh catalog
```
Xem <out>/img_work/chosen_sheet_<k>.png: mỗi ô là ảnh đã chọn của một card (card_id + nguồn).
Loại ảnh: không đúng sản phẩm, logo/chữ của hãng khác, ảnh quảng cáo nhiều chữ, ảnh chụp bao bì.
Ghi <out>/team/reject_<k>.json = ["<card_id>", ...] (rỗng [] nếu ổn hết). Không sửa file nào khác.
```

### C — Sửa nội dung card theo lint
```
Đọc <SKILL>/references/content_rules.md và <out>/lint_report.md. Chỉ xử lý các card: <id1, id2...>.
Ghi <out>/team/edits_<n>.json = [{"card": "<id>", "set": {"lines": [...], "legend": [...],
"note": "...", "width": 26}, "source": "<lý do / cột data>"}]. Tiêu đề lấy từ data KHÔNG được đổi.
Mô tả chỉ lấy từ data hoặc catalog có URL. Không sửa file nào khác.
```

### D — Soát trang render
```
Đọc <SKILL>/references/qa_checklist.md. Mở lần lượt <out>/renders/page_<a>.png … page_<b>.png
(các trang trong team/review_batches.json phần worker <i>). Ghi <out>/team/review_<i>.json =
[{"page": 3, "card_id": "...", "item": 8, "severity": "chan"|"tham-my", "fix": "sửa gì"}].
Trang không lỗi thì không ghi. Không sửa file nào khác.
```

## 5. Leader gộp và chấm
1. Chờ đủ thông báo xong của mọi worker trong bước.
2. Gộp bằng script, không chép tay:
   - A → chạy lại toàn bộ lệnh `run.py` với `--patches <out>/team/patches_A.json`.
   - B → `run.py ... --resume` (tự gộp `team/picks_*.json`; file sau thắng, xung đột được báo).
   - B' → `run.py ... --resume` (tự gộp `team/reject_*.json`; thẻ bị loại sẽ tìm ảnh web → STOP images → B).
   - C → `pl_docedit.py <out>/doc.json <out>/team/edits_1.json ...` rồi `run.py ... --resume`.
   - D → leader đọc các `review_*.json`, mở đúng trang có mức "chan", sửa `doc.json`/theme, `--from layout`.
3. Trọng tài là lint + QA của lần chạy kế. Còn lỗi → giao lại đúng worker đó kèm lỗi cụ thể.
4. Báo user những gì worker không xác minh được — user quyết, không đoán thay.
