# Nặng bao nhiêu

Đo trên file thật 20 sản phẩm, 2026-09-11:

| | |
|---|---|
| Cả tầng 0 token chạy lại | **~1 giây** |
| Thư viện ngoài stdlib | chỉ `ddgs`, nạp khi cần |
| Nguồn tải về, mỗi trang | HTML thô ~366 KB → **text nén ~7 KB** |
| Cả job 20 sản phẩm | **128 KB** |

Mặc định lưu **text đã lọc, nén gzip** — 1,2% HTML thô. Suy ra file 5.730 sản phẩm: ~24 MB thay vì
~2 GB. Cần cấu trúc bảng (trang hãng SATA/Anex) thì `fetch_sources.py --luu html`.

Cache giữ lại vì bỏ nó là trả bằng giờ: 5.730 trang × 1 giây nghỉ ≈ 1,6 tiếng mỗi lần chạy lại.
