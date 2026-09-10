# jobs/ — vùng làm việc của bạn (KHÔNG push)

Chỗ để file thật của bạn và mọi thứ skill sinh ra. Chỉ file README này lên GitHub, **toàn bộ nội
dung còn lại bị `.gitignore` chặn** — dữ liệu sản phẩm không rời khỏi máy bạn.

```
jobs/
  inbox/        ← BỎ FILE EXCEL CẦN XỬ VÀO ĐÂY
  oncheck/      ← skill tự tạo: hàng đợi, verdict, changelog, file đã dựng
  delivered/    ← file đã duyệt xong, sẵn sàng giao
```

## Dùng

```bash
# 1. chép file cần xử vào jobs/inbox/
# 2. gọi skill, trỏ thẳng vào file đó
```

```
/mecsu-category  jobs/inbox/file-cua-ban.xlsx
/mecsu-filter    jobs/inbox/file-cua-ban.xlsx
```

Script tự tìm thư mục này (thư mục cha nào chứa `jobs/` thì đó là gốc). Muốn để chỗ khác thì đặt
biến `ONCHECK_JOBS` trỏ tới thư mục cha của `jobs/`.

## Luật

- **`delivered/` chỉ chứa file đã có người duyệt.** `deliver.py` từ chối ghi vào đây khi còn cặp
  tranh chấp chưa ai quyết — sự từ chối đó là tính năng.
- Còn ô `REVIEW` chưa quyết thì để nguyên ở `oncheck/`, đừng đẩy sang `delivered/`.
- Muốn xem file mẫu đi kèm repo thì vào [`samples/`](../samples) — đó là dữ liệu demo được commit,
  khác với dữ liệu thật của bạn nằm ở đây.
