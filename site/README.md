# Website giới thiệu Mecsu Skills

Static site public. Không nhận file, không gọi API, không chứa dữ liệu nghiệp vụ.

## Xem thử ở máy

```bash
python -m http.server 4173 --directory site
python -m pytest tests/test_site.py -q
```

## Deploy — Cloudflare Pages

| Cấu hình | Giá trị |
|---|---|
| Production branch | `main` |
| Build command | *(để trống — static)* |
| Build output directory | `site` |

> ⚠️ Trước 10/09/2026 production branch là nhánh `website`. Nhánh đó đã bị xoá (repo giữ đúng một
> nhánh `main`), nên **phải đổi production branch sang `main`** trong dashboard Cloudflare Pages,
> nếu không lần deploy tới sẽ hỏng.

Cloudflare, DNS, secret đều là thiết lập bên ngoài; repo không tự đổi chúng.

## Thêm skill mới lên trang

`tests/test_site.py` chặn việc trang lệch với thư mục `skills/` — đúng lỗi đã xảy ra: trang quảng
cáo skill `category-auto` sau khi skill đó không còn tồn tại. Ba chỗ phải khớp nhau:

1. `site/public-skill-catalog.json` — thêm một mục, `skill_id` **trùng tên thư mục** trong `skills/`.
2. `site/index.html` — thêm `<section id="<website_section>">` và `<template id="prompt-<skill_id>">`.
3. Nút bấm `data-copy-prompt="<skill_id>"` — `app.js` tự tìm template theo id, không cần sửa.

## Bảo mật

`_headers` đặt CSP `default-src 'self'` — **không có** inline script, inline style hay tài nguyên
ngoài. Thêm CDN hay `<script>` nội tuyến sẽ bị chặn im lặng trên production.
