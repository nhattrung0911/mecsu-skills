# Số liệu đo được — `on_web_filter.xlsx`

> **Cảnh báo**: file này đo trên `on_web_filter.xlsx` bằng **code trước các bản vá**
> (chưa có chốt thẻ kinh doanh / tên phủ định / khóa cụ thể hơn, và vốn từ còn ràng
> buộc cứng thuộc tính đo lường). Phần **quy ước format cột tên vẫn đúng** và vẫn dùng
> được. Phần **tỉ lệ lấp đầy và chi phí token đã lỗi thời** — số hiện hành nằm ở
> [SKILL.md](../SKILL.md) và [workflow.md](../workflow.md), đo trên `Fas+Hand_check_all.xlsx`.
> Muốn số mới cho file này thì phải chạy lại cả chuỗi.

Mọi con số dưới đây đo từ file thật, không phải ước lượng. Chạy lại tool để sinh lại;
đừng trích dẫn theo trí nhớ.

## Hình dạng file

67.563 dòng, 5 cột: `part_id | ma_san_pham | ten_san_pham | so_luong_filter | danh_sach_filter_mapping`.

Cột E dạng `Key: Value | Key: Value`. Nhóm hàng nằm ngay trong key: `<Thuộc tính> Of <Nhóm>`
(biến thể `Của <Nhóm>` cho Ren Cấy, Bulong Ép — 2.113 lần so với 512.806 lần `Of`).
`Brand of Group Home`, `Original`, `Ngành Hàng` là key toàn cục, không phải nhóm.

126 nhóm hàng. Gom theo skeleton tên (số → `#`): 9.256 cụm, 95% dòng có ≥2 peer.

## Quy ước format thật của cột C

| Quy ước | Đa số | Thiểu số | Kết luận |
|---|---|---|---|
| `DIN931` viết dính | 8.396 | 0 | **đúng, không sửa** — cột E lại dùng `DIN 931`, hai cột khác quy ước có chủ đích |
| `M8x27` không space (hệ mét) | 25.738 | 463 | sửa thiểu số |
| `3/8-24 x 1` có space (hệ inch) | 2.228 | 141 | **ngược hệ mét** |
| `55 mm` có space | 11.700 | 2.477 | sửa thiểu số, đúng cho cả hai hệ |
| `inch` có space | 735 | 17 | sửa thiểu số |

Dấu hiệu hệ inch học được từ token, không đoán bằng phân số: `unc`, `unf`, `bsw`, `gr`,
`a193`, `a325`, phân số, `#10`. Tên như `UNC 1-8 x 4` và `#10-32 x 3` là hệ inch mà
**không** chứa phân số — dùng phân số làm dấu hiệu là sai.

Token `x` phải bị loại khỏi bộ dấu hiệu: nó chỉ tồn tại khi đã tách, nên rò rỉ nhãn.

## Kết quả audit toàn file (tầng 1)

| Vấn đề | Số dòng |
|---|---|
| Cột E rỗng hoàn toàn (`N/A:`) trong khi cột D ghi 11-14 filter | 437 |
| Cột D sai số lượng filter | 437 |
| Tên C đề xuất sửa | 2.583 |
| Mâu thuẫn C ↔ E | 35 |
| Dòng thiếu filter so với peer | 913 |
| Filter nghi thừa/sai | 1.225 |
| Cả cụm thiếu filter mà ≥80% cụm khác cùng nhóm đều có | 10.382 dòng / 788 cụm |
| Key trùng y hệt | 0 |

Loại lỗi tên: `×`→`x` 1.088, hoa/thường lệch majority 663, space thừa 614,
thiếu space trước đơn vị 278.

## Lỗi dữ liệu ở nguồn (không sửa được từ đây)

- **`Đường Kính Rãnh Sử Dụng Of Retaining Ring` sai hệ thống.** Đối chiếu bảng DIN 472
  gốc: lỗ 46 phải là 48.5 (file ghi 49.5), lỗ 48 phải là 50.5 (file ghi 53.0),
  lỗ 50 phải là 53.0 (file ghi 54.0). File đang lưu đường kính ngoài vòng găng thay
  cho đường kính rãnh, lệch một dòng. Lỗ 44, 45, 52 lại đúng — nên không phải lệch đều.
- **Sản phẩm ở size không tồn tại trong chuẩn**: `Phe Gài Lỗ ... DIN472 D49`, `D51`
  — DIN 472 nhảy từ lỗ 48 sang 50.
- **Giá trị lẻ mâu thuẫn với hàng trăm dòng cùng tổ hợp**: `(M10, DIN 931) → Size Khóa 16 mm`
  (1 dòng) trong khi 123 dòng ghi 17 mm; `(M12, DIN 933) → 18 mm` (1 dòng) / 177 dòng ghi 19 mm.
  Cẩn thận: một số "bất thường" kiểu `M20 → Bước Ren 1.5 mm` lại **đúng** (ren nhuyễn),
  chỉ là bộ xác định thiếu `Loại Ren`. Phải kiểm theo từng dòng, không kết luận theo bảng.
- **`Ngành Hàng` là multi-value**: `Tổ Lắp Ráp | CNC` trên cùng một dòng là hợp lệ.

## Chi phí đo được (mẫu 10.009 dòng, 246 cụm, 127 nhóm)

| Bước | Kết quả | Token |
|---|---|---|
| audit tầng 1 | — | 0 |
| corpus tra ô thiếu | 92/158 ô (58%) | 0 |
| gom hàng đợi | 57 câu hỏi | 0 |
| Gemini `ag/gemini-3.7-flash-medium` | 41 trả lời được, 16 tự bỏ trống | 899/câu |
| verify bằng corpus | 4 nghi sai, 8 hợp lý, 28 không có tham chiếu | 0 |
| ghép + tự kiểm tra | 505 ô bổ sung / 74 dòng | 0 |

Batch theo `(nhóm, thuộc tính)`: 2.838 token/câu. Batch theo nhóm: 899 token/câu.
