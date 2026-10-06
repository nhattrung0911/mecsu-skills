# Khung bảng giá Varin — số đo chuẩn

Đo từ 7 file: form, pricelist_example, SKF, ASAHI, Sata, Bosi, Stanley. Mọi giá trị nằm trong `config/theme.json`; file này giải thích nguồn gốc và cách sửa.

## Trang
- 1 sheet in A4 dọc, lề 0.2 in mọi phía, view `pageLayout`, không fit-to-page (in 100%).
- 1 trang = 77 dòng × 56 cột (A..BD). Cột rộng `1.77734375` (~12.8 px), dòng cao `10.35` pt (~13.8 px) → lưới ô vuông nhỏ, mọi thứ dàn bằng merge.
- Trang k (từ 0) bắt đầu ở dòng `77k+1`. Ngắt trang thủ công sau mỗi 77 dòng (các file cũ thiếu ngắt in dễ lệch — chuẩn mới luôn có).
- Vùng thân: dòng 5–74, cột C..BC. A:B và BD để trống làm lề.

## Header trang (dòng 1–3)
| Vùng | Nội dung | Kiểu |
|---|---|---|
| D1 (ảnh) | Logo hãng, oneCellAnchor offset 99060×15240 EMU, khung tối đa 1226820×366127 EMU | giữ tỉ lệ |
| `S1:AL3` | `BẢNG GIÁ {HÃNG}` | Calibri 16 đậm, giữa |
| `AM2:AY3` | `100% sản phẩm có xuất VAT` | Calibri 9 nghiêng, trái |
| AY1 (ảnh) | Logo Varin 150×63, offset 83724×64401, ext 624936×263259 EMU | |

## Footer (dòng 75–77)
| Vùng | Nội dung | Kiểu |
|---|---|---|
| `A75:BD76` | `LƯU Ý GIÁ DÀNH CHO ĐỐI TÁC VARIN` | nền đỏ FF0000, Calibri 14 đậm trắng, giữa |
| `A77:U77` | `Đặt hàng trên: app.varin.vn` | 8 nghiêng xám 7F7F7F, trái |
| `AA77:AD77` | `{CODE} - {NN}` (2 chữ số) | 9 đậm nghiêng, giữa |
| `AH77:BD77` | `sử dụng mã đặt hàng 7 chữ số để kiểm tra tồn kho và đặt hàng` | 8 nghiêng xám, phải |

## Làn (lane) cho card
| Độ rộng | Vị trí cột bắt đầu | Dùng khi |
|---|---|---|
| 17 | C, U, AM | bảng ≤ 4 cột ngắn (mặc định Stanley) |
| 26 | C, AD | 5–6 cột hoặc nhãn dài |
| 35 | C, U | 6–7 cột |
| 53 | C | bảng rất rộng |

## Card (từ trên xuống)
1. Tiêu đề: 2 dòng merge, Calibri 9 đậm IN HOA, trái-trên.
2. Mô tả: `desc_rows` dòng (tối thiểu 3), Calibri 8, thụt 1 cột; ảnh nằm nửa phải, cao tối đa 7 dòng.
3. `VAT: 8%`: 1 dòng, Calibri 8, canh phải trên cột giá.
4. Header: 2 dòng merge mỗi cột, Calibri 8 đậm giữa, xuống dòng.
5. Dữ liệu: 1 dòng/sản phẩm (hoặc 3 cho card 1 sản phẩm), Calibri 8; Mã Hãng trái, thông số giữa, Mã Đặt Hàng đậm text `@`, Giá đỏ nghiêng `#,##0` = `VLOOKUP(mã,Sheet2!$A:$B,2,0)`.
6. Viền: mọi ô bảng + khung ngoài card, mảnh, màu E7E6E6. Không tô nền, không sọc.
7. Cách card dưới 1 dòng.

## Sheet2
`Mã Đặt Hàng` (text 7 số) | `varin_price` (số). Một dòng cho mỗi mã đặt hàng xuất hiện trong bảng.

## Điểm lệch của file cũ đã chuẩn hoá
- Sata/Stanley mã trang không có số 0 (`SAT - 1`) → chuẩn `SAT - 01`.
- Bosi thiếu logo + dòng VAT → chuẩn luôn có.
- Sata không có ngắt trang thủ công → chuẩn luôn có.
- SKF dùng định dạng giá accounting, Bosi `#,##0` → chuẩn `#,##0`.
