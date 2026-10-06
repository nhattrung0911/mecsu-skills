# Checklist soát ảnh render (pl_render → PNG)

Dùng cho leader hoặc agent soát trang. Mở PNG từng trang bằng Read, đối chiếu mẫu chuẩn Stanley (trang 1) và đánh dấu từng mục. Báo lỗi theo dạng: `trang N · card <id> · mục X · mô tả · sửa gì trong doc.json`.

## A. Khung trang (mọi trang)
1. Logo hãng góc trái trên, logo Varin góc phải trên, không méo, không đè title.
2. Title "BẢNG GIÁ <HÃNG>" giữa, to, đậm; dòng "100% sản phẩm có xuất VAT" nghiêng bên phải.
3. Thanh đỏ footer chữ trắng "LƯU Ý GIÁ DÀNH CHO ĐỐI TÁC VARIN" sát đáy, đủ chiều ngang.
4. Dòng cuối: "Đặt hàng trên: app.varin.vn" trái, mã trang `XXX - NN` giữa, hướng dẫn mã 7 số phải.
5. Mã trang tăng liên tục, không nhảy số.

## B. Card
6. Mỗi card có viền xám mảnh bao quanh; các card không chạm/chồng nhau; khoảng cách đều.
7. Tiêu đề in hoa, đậm, không bị ảnh che, không bị cắt chữ.
8. Ảnh sản phẩm nằm góc phải phần mô tả, đúng sản phẩm, rõ, nền trắng/trong, không tràn sang card khác, không đè bảng.
9. Dòng mô tả căn lề thẳng, không đè ảnh, không bị cắt.
10. "VAT: 8%" nằm ngay trên header, phía cột giá.
11. Header 2 dòng, chữ không bị cắt (đặc biệt "Giá/Cái Chưa VAT", "Mã Đặt Hàng"); đơn vị đúng.
12. Mã Hãng không bị cắt; số liệu canh giữa; mã đặt hàng đậm 7 số.
13. Giá đỏ nghiêng, có dấu phân cách nghìn, không hiện `#N/A`, `####`, hay `0`.
14. Card bị tách sang trang/làn khác có lặp lại tiêu đề và header.

## C. Tổng thể
15. Mật độ: không còn khoảng trắng lớn bất thường (> 1/4 trang) trừ trang cuối.
16. Nhóm hàng liên quan đứng gần nhau, đọc theo thứ tự hợp lý.
17. Chất lượng đồng đều giữa các trang (cỡ ảnh, cỡ chữ, số dòng mô tả).

## Mức độ
- **Lỗi chặn** (phải sửa trước khi bàn giao): 1–5, 6 (chồng), 8 (sai sản phẩm), 11–13, 14.
- **Lỗi thẩm mỹ** (sửa nếu còn vòng): 7, 9, 10, 15–17.
