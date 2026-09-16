# Quy ước đặt tên sản phẩm — chuẩn Mecsu

Chuẩn này **đi kèm skill**, không hỏi lại ở mỗi lần chạy. Người dùng không cần biết công thức
trước khi dùng skill.

Mọi con số trong tài liệu này đo trên `samples/Handtools-check-cate-filter.xlsx` (5.730 dòng đã
đặt tên) ngày 2026-09-11, sinh lại được bằng script.

## Mục lục

- [Công thức](#công-thức)
- [1. Khoảng cách đơn vị](#1-khoảng-cách-đơn-vị)
- [2. Hoa thường của đơn vị](#2-hoa-thường-của-đơn-vị)
- [3. Tên hãng](#3-tên-hãng)
- [4. Kích thước](#4-kích-thước)
- [Thứ tự áp dụng](#thứ-tự-áp-dụng)

## Công thức

```
{Loại sản phẩm} {Đặc trưng} {Thông số quan trọng để khách lựa chọn} {Hãng} {Mã}
```

Ví dụ thật từ dữ liệu Mecsu:

| Loại | Đặc trưng | Thông số | Hãng | Mã |
|---|---|---|---|---|
| Đầu Tuýp | 6 Cạnh | Chuôi 1/2 Inch Khẩu 13 mm | SATA | 13304 |
| Cờ Lê Vòng Miệng | Lắc Léo Tự Động Có Khóa | 13 mm | SATA | 46806 |
| Bộ Mũi Vít | — | 4 Chi Tiết | ANEX | AK-51P-B4 |

Mã trong tên phải **đúng nguyên văn** mã ở cột mã. Không viết lại, không bỏ dấu gạch.

## 1. Khoảng cách đơn vị

| Nhóm | Cách viết | Ví dụ |
|---|---|---|
| **Điện** — `W` `V` `A` | **liền** | `20W` · `12V` · `16A` |
| Mọi đơn vị còn lại | **cách** | `13 mm` · `1/2 Inch` · `100 Nm` · `200 kg` · `36 x 17.5 x 18 cm` |

Đo được: `mm` cách 3.698/3.921 · `inch` cách 1.472/1.506 · `Nm` `kg` `g` `cm` cách 100%.

> **Bẫy: `A` vừa là ampe vừa là đuôi mã.** `16A` là 16 ampe; `KST2000A` và `09014 A` là mã sản
> phẩm. Phân biệt: đơn vị điện đi sau **một con số đứng riêng**; đuôi mã dính vào một token đã có
> chữ cái. Đo được 311 lần xuất hiện của `A`, phần lớn là đuôi mã — nhận nhầm là đổi mã hàng.

## 2. Hoa thường của đơn vị

| Đơn vị | Viết | Ghi chú |
|---|---|---|
| `Inch` | **hoa chữ đầu** | dữ liệu đang 50/50 (`inch` 703 · `Inch` 769) — chốt dùng `Inch` |
| `mm` `cm` `m` `kg` `g` | thường | |
| `W` `V` `A` `Nm` | theo chuẩn SI | `Nm` hoa N thường m |

## 3. Tên hãng

**Không có luật suy ra được.** `SATA` và `PICUS` viết in hoa hết nhưng không phải từ viết tắt;
`Anex` `Bosi` `Stanley` viết hoa chữ đầu. Nhìn chuỗi không biết được hãng nào thuộc nhóm nào.

Vì vậy skill **hỏi người dùng một lần cho mỗi hãng mới**, rồi nhớ vào `references/brands.json`.
Hãng đã có trong danh sách thì không hỏi lại.

Cùng một hãng đang có hai kiểu viết trong dữ liệu thì skill sửa về kiểu đã chốt:

| Hãng | Trong dữ liệu | |
|---|---|---|
| SATA | `SATA` 3.466 · `Sata` 92 | sửa `Sata` → `SATA` |
| Anex | `Anex` 154 · `ANEX` 25 | sửa `ANEX` → `Anex` |
| Tsunoda | `Tsunoda` 121 · `TSUNODA` 11 | sửa `TSUNODA` → `Tsunoda` |

## 4. Kích thước

Hai con số kèm đơn vị trong cùng một tên rơi vào **một trong hai loại**, và chỉ model đọc hiểu mới
phân biệt được — không hardcode.

**Cùng một thứ, ghi hai đơn vị → bỏ một, giữ đơn vị hợp với loại sản phẩm.**

```
Mỏ Lết Trắng 8 Inch/200 mm Bosi BS361208
   -> Mỏ Lết Trắng 200 mm Bosi BS361208
```

**MỌI số đo trong tên phải có nhãn.** Số đứng trần thì khách không biết nó đo cái gì.

```
Kéo Thu Hoạch Lưỡi Cong 165 mm Saboten AG-1 Nhật Bản
   -> Kéo Thu Hoạch Lưỡi Cong Dài 165 mm Lưỡi 63 mm Saboten AG-1 Nhật Bản
```

**Trần 80 ký tự.** Đo trên 5.730 tên Mecsu đang dùng: trung bình 45, p90 là 59, dài nhất 80.
Vượt trần thì bỏ bớt thông số ÍT quan trọng nhất, không cắt cụt giữa chừng.

Thông số đã nằm trong mã thì **không lặp lại bằng chữ**: mã `C-2 450x16x21` đã mang 450×16×21,
nên tên chỉ cần số đo nào mã không nói.

**Đưa nhiều thông số vào tên, không chỉ một.** Lấy các thông số **khách dùng để chọn hàng** từ
dòng thông số có sẵn: chiều dài tổng, chiều dài lưỡi, đường kính, cỡ khẩu, số chi tiết, vật liệu
nếu là điểm phân biệt. Hai đến ba thông số là vừa; đừng nhồi hết cả bảng.

Nhãn lấy đúng chữ khách đang dùng trong dòng thông số (`Tổng chiều dài:` → `Dài`,
`Chiều dài lưỡi:` → `Lưỡi`), viết gọn lại cho lọt vào tên.

**Hai thứ khác nhau → GỌI TÊN từng số đo.** Để trần thì khách đọc không hiểu số nào là gì.

```
Đầu Tuýp Lục Giác Dài 1/2 Inch 19 mm Bosi BS365119A
   -> Đầu Tuýp Lục Giác Dài Chuôi 1/2 Inch Khẩu 19 mm Bosi BS365119A

Đục Gỗ Cầm Tay 1 Inch Dài 258 mm Bosi BS490081
   -> Đục Gỗ Cầm Tay Bản Rộng 1 Inch Dài 258 mm Bosi BS490081
```

Đo trên 18 dòng mẫu có cả inch lẫn mm: 12 dòng là hai thứ khác nhau, 6 dòng là cùng một thứ.
Toàn file có 832/5.730 dòng chứa cả hai đơn vị.

## Thứ tự áp dụng

1. Tách tên hiện có thành 5 thành phần của công thức.
2. Chuẩn hoá đơn vị theo mục 1 và 2.
3. Chuẩn hoá tên hãng theo `brands.json`; gặp hãng mới thì **dừng lại hỏi**.
4. Xử lý kích thước theo mục 4 — bước này cần model đọc hiểu.
5. Ghép lại theo công thức, giữ mã đúng nguyên văn.
6. Đối chiếu ngược: tên mới phải chứa đúng mã gốc. Không khớp thì `REVIEW`.
