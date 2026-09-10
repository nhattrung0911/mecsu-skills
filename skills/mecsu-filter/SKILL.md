---
name: mecsu-filter
description: Audits and completes the filter/spec set on a product workbook - catches name-format errors, name-vs-filter contradictions and missing filters, then fills each empty cell with a concrete value backed by evidence. Use when product filters or technical specs are missing, wrong or unverified in an Excel file of industrial goods (fasteners, bearings, hand tools, pneumatics), or when a spec column needs QC before it goes live.
argument-hint: "[path/to/workbook.xlsx]"
license: MIT
---

# mecsu-filter — kiểm tra & bổ sung filter sản phẩm

Đề xuất filter **luôn kèm giá trị cụ thể**. "Thiếu Size Khóa" là báo cáo dở dang;
`Size Khóa Of Bulong: 32 mm (DIN 931 M22, 59 dòng trong file xác nhận)` mới là kết quả.

Bổ trợ cho `mecsu-category`: category trả lời *sản phẩm này thuộc danh mục nào*,
skill này trả lời *sản phẩm này có đủ và đúng thông số chưa*.

## Chạy

```bash
python ${CLAUDE_SKILL_DIR}/scripts/run.py --input <file.xlsx> --job <thư mục làm việc>
```

Đó là cả pipeline: rule → tra chính file → hỏi model → đối chiếu ngược → ghép + tự kiểm tra →
xuất bảng chấm. Hai tầng đầu **0 token**. Nó dừng lại sau lô hiệu chuẩn 50 câu; đọc lô đó
xong mới chạy lại kèm `--yes`.

Tự nhận cột theo header. Nhận sai thì ép bằng `--filter-col` / `--name-col` / `--cat-col`
(0-based) — nhưng nếu cột filter không chứa `Key: Value` thì script **dừng ngay**, không
audit tiếp rồi ghi ra file rác.

Cứ chạy trước — hai tầng đầu **không cần key**, và script tự dừng kèm đường dẫn file cần
điền nếu thiếu. Lúc đó mới hỏi người dùng endpoint 9router + key + model, đừng tự đoán. Cần Python 3.11+ với `openpyxl`,
`requests`, `python-dotenv`.

## Luật không được phá

1. **Không rule cứng theo ngành.** Mọi quy ước format đều đo từ chính file đang xử lý.
   `DIN931`→`DIN 931` và `M8 x 27`→`M8x27` nghe rất hợp lý, áp vào đẻ ra hàng nghìn lỗi giả
   vì file viết dính, và hệ inch lại tách. Gom sản phẩm thành **cụm cùng skeleton tên**
   (số → `#`), mọi kết luận đều so trong cụm. Không có bằng chứng trong cụm thì không sửa gì.
2. **Không hỏi model thứ file đã biết.** Mọi ô phải qua tầng rule rồi tầng corpus trước.
   Đảo thứ tự là trả tiền cho câu trả lời file đã có sẵn.
3. **Không hỏi model theo từng dòng.** Gom thành `(nhóm hàng, thuộc tính, bối cảnh quyết
   định tối thiểu)`. Một request = một nhóm hàng, nhiều thuộc tính — gom theo cặp
   `(nhóm, thuộc tính)` đắt gấp 5 lần.
4. **Vốn từ chỉ ràng buộc thuộc tính PHÂN LOẠI.** Thuộc tính đo lường (số + đơn vị) chỉ
   được gợi ý định dạng. Ràng buộc cứng cả hai loại thì giá trị đúng chưa từng xuất hiện
   trong file sẽ bị model bỏ trống.
5. **Luôn chạy lô hiệu chuẩn trước.** Rẻ hơn nhiều so với phát hiện prompt sai sau khi đã
   trả tiền cho cả bộ. `--calibrate 0` chỉ dùng khi đã chạy file cùng schema.
6. **Đối chiếu corpus là cờ cảnh báo, không phải phán quyết.** Nó bác oan giá trị đúng
   nhiều hơn bác trúng, nên không tự loại nữa — chỉ đánh dấu `REVIEW`.
7. **Không tự chế công thức khi bảng tra thiếu cột.** Bảng không có thì để trống, để người
   quyết.
8. **Không quote con số mình chưa đo.** Số trong tài liệu đều kèm tên job đã đo.

## Chốt chặn — mỗi cái ra đời từ một lỗi đã bắt được

| Chốt | Ca đã bắt |
|---|---|
| Tổ hợp tra cứu phải có ≥3 dòng làm chứng | `DIN2093 M36 → M35` suy từ 1 dòng |
| Thẻ kinh doanh (`Ngành Hàng`, `Brand`, `Original`) không được làm bộ xác định | `Vít Col Inox 316 → Vật Liệu Inox 304` |
| Tên sản phẩm phủ định giá trị điền | `Cùm U Nhúng Nóng Kẽm → Xử Lý Bề Mặt: Mạ Kẽm` |
| Khóa cụ thể hơn thắng khóa tổng quát | `M14x1.5 Ren Nhuyễn → Bước Ren 2 mm` (phải 1.5) |
| Model tự mâu thuẫn → bỏ cả hai | `DIN 7980 M14` ra 24.4 chỗ này, 21.1 chỗ kia |
| Bảng tra thiếu cột → cấm tự chế công thức | `DIN912 b=2d+24` (không tồn tại) |
| Cache khóa theo nội dung câu hỏi, không theo thứ tự | hàng đợi đổi → 21/58 câu trả lời gắn nhầm |
| Cột filter không giống filter → dừng ngay | audit chạy trên cột đếm, exit 0, ra file rác |

## Cái gì cần người

- `review/cham_diem.xlsx` — mỗi ô một dòng, gom sẵn giá trị · nguồn · căn cứ · đối chiếu
  file · điểm lân cận thật · có bảng tra hay không, xếp theo độ khó chấm.
- Ô `REVIEW` — corpus không đồng ý. Đối chiếu bảng tra hoặc tra web rồi mới quyết.
- **Chính file nguồn cũng sai được.** Đối chiếu DIN 472 gốc bắt được 13 dòng sai do lệch
  một dòng khi nhập, có dòng đường kính ngoài nhỏ hơn đường kính rãnh — vô lý vật lý.
  Đừng mặc định bên nào đúng.

Job còn ô chưa quyết thì để `review/`, không đẩy sang `delivered/`.

## Kho bảng tra tiêu chuẩn

`references/standards/*.md` — hiện có DIN 471, 472, 912, 931. `run.py` nạp đúng bảng của lô
có tiêu chuẩn đó vào prompt. Thêm bảng mới = thêm một file `.md` đặt tên theo slug tiêu chuẩn
(`din-933.md`). Mọi máy tìm kiếm đều chặn script (DuckDuckGo `202 anomaly`, Mojeek `403`)
nên bảng do người tra một lần, pipeline dùng lại nhiều lần.

## Chọn model bằng đo đạc, đừng chọn bằng tên

```bash
python ${CLAUDE_SKILL_DIR}/scripts/eval_models.py --models "model-a,model-b"
```

18 câu có đáp án đã xác minh từ bảng tiêu chuẩn. Model rẻ nhất trong nhóm đạt 18/18 đã là
tối ưu — đừng đổi sang model đắt hơn nếu chưa đo lại.

---

- Từng bước, lý do thiết kế, và mọi số đo: [workflow.md](workflow.md)
- Ngân sách token và ngưỡng phải xin phép: [policy.md](policy.md)
- Việc còn nợ: [TODO.md](TODO.md)
