# doc.json — đặc tả

`doc.json` là nguồn sự thật cho một bảng giá. Mọi thay đổi bố cục/nội dung = sửa file này rồi build lại.
Schema máy đọc: `config/doc.schema.json` (pl_build/pl_layout validate trước khi chạy).

## meta
| Trường | Bắt buộc | Ý nghĩa |
|---|---|---|
| `brand` | ✔ | Tên hãng in trên title: `BẢNG GIÁ {brand}` |
| `page_code` | ✔ | 3 chữ cái cho mã trang: `STA` → `STA - 01` |
| `title` | | Ghi đè toàn bộ title |
| `brand_logo` | | Đường dẫn logo hãng (tương đối thư mục doc hoặc skill). Thiếu → bỏ trống ô logo + cảnh báo |
| `theme_overrides` | | Ghi đè theme cho riêng bảng giá này, ví dụ `{"card":{"vat_text":"VAT: 10%"}}` |
| `page_count` | | Do pl_layout điền |

## prices
`[{ "order_code": "0927517", "price": 41300 }]` → Sheet2. `order_code` luôn 7 chữ số dạng text. `price` số; giá trị chữ (ví dụ `"checking"`) vẫn ghi nhưng pl_qa cảnh báo.

## cards[]
| Trường | Mặc định | Ý nghĩa |
|---|---|---|
| `id` | bắt buộc | Duy nhất. Card bị tách sẽ thành `id#2`, `id#3` |
| `group` | | Nhóm gốc trong data (truy vết) |
| `title` | bắt buộc | IN HOA, xem `content_rules.md` |
| `title_source` | | `data` = tên lấy từ cột Tên Bảng Giá của user (không được đổi, kể cả pl_kb), `kb`, `research` |
| `lines` | `[]` | 0–5 dòng mô tả, mỗi dòng ≤ 28 ký tự |
| `legend` | `[]` | Dòng chú giải ký hiệu (`d: Đường Kính Trong`) — in sau `lines` |
| `note` | `null` | Ghi chú in nghiêng đậm dưới bảng |
| `image` | `null` | `{path, status: ok|review|missing, url?}` — `url` khi data cho link ảnh (chưa tải) |
| `drawing` | `null` | Bản vẽ kích thước (ảnh nét, nền trắng) cùng dạng `image`. Có cả `image` + `drawing` → ảnh chụp bên trái, bản vẽ bên phải trong vùng ảnh. Cột chữ cái (A, B, L…) hợp lệ khi có bản vẽ hoặc legend |
| `columns` | bắt buộc | Thứ tự cột. Mỗi cột `{key, label?, role?, span?, align?}` |
| `rows` | bắt buộc | Mỗi dòng là object theo `key` của cột |
| `width` | `auto` | `auto` hoặc 17 / 26 / 35 / 53 cột |
| `data_row_height` | 1 | 3 cho card chỉ 1 sản phẩm muốn dòng cao |
| `place` | `null` | `{page, col, row, locked:true}` khoá vị trí (page từ 0, row tương đối trang) |
| `split` | `allow` | `keep_together` cấm tách |

**role của cột:** `code` (Mã Hãng), `spec` (thông số), `order_code` (Mã Đặt Hàng), `price` (Giá). Nếu không ghi, suy từ `key`: `code`, `order`/`order_code`, `price`; còn lại là `spec`. Nhãn mặc định của `code/order_code/price` lấy từ theme. Cột `price` không cần dữ liệu trong `rows` — builder tự viết VLOOKUP theo ô mã đặt hàng.

## free[] — lối thoát cho trường hợp một lần
`{type:"text", page:2, range:"AD11:AL13", text:"...", style:{size:8, italic:true, bold:false, color:"red", align:"left", border:"left"}}`
`{type:"image", page:0, range:"M20", path:"img/x.png"}`
`shape` chưa hỗ trợ (openpyxl không ghi shape) — builder bỏ qua và cảnh báo.

## _geo / _warnings
Do pl_layout sinh, không sửa tay (muốn ép vị trí → dùng `place`).

## Ví dụ tối thiểu
```json
{
 "meta": {"brand": "STANLEY", "page_code": "STA", "brand_logo": "assets/logos/stanley.png"},
 "prices": [{"order_code": "0120316", "price": 145300}],
 "cards": [{
   "id": "kim-dien", "title": "KÌM ĐIỆN",
   "lines": ["Vật Liệu: Thép", "Tay Cầm Bọc Nhựa"],
   "image": {"path": "img/84-623.png", "status": "ok"},
   "columns": [{"key": "code"}, {"key": "len_mm", "label": "Chiều Dài\n(mm)"}, {"key": "order"}, {"key": "price"}],
   "rows": [{"code": "84-623", "len_mm": 164.6, "order": "0120316"}]
 }]
}
```

## Cột tuỳ chọn trong data (pl_read → pl_draft)
Mẫu: `assets/templates/data_template.xlsx` (sheet "Hướng dẫn" bị bỏ qua khi đọc).
| Cột data | Vào card |
|---|---|
| `Tên Bảng Giá` | `title` (IN HOA), `title_source: "data"`; cùng tên + cùng bộ cột (kể cả khác sheet) → 1 card |
| `Mô Tả`, `Mô Tả 1..5`, `Dòng Mô Tả 1..5` | `lines` |
| `Chú Giải`, `Chú Giải 1..5` | `legend` |
| `Ghi Chú` | `note` |
| `Ảnh` / `Hình Ảnh` / `Image` | `image` (đường dẫn tương đối file data, hoặc URL) |
| `Bản Vẽ` / `Drawing` | `drawing` |
Mọi cột khác ngoài 4 cột cố định (Mã Hãng, Tên Bảng Giá, Order ID, Varin Price) là cột thông số; đơn vị ghi trên tiêu đề cột.
