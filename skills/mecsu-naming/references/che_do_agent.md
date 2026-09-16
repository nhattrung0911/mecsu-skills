# Chế độ agent — khi không có `.env`

`.env` là **tuỳ chọn**: nó mua thêm một model rẻ để làm phần việc nặng, không phải điều kiện để
dùng skill. Không có nó thì chính agent đang chạy (Claude, Codex…) làm phần việc đó.

## Chọn chế độ

| `.env` | `MECSU_CHE_DO` | Chế độ |
|---|---|---|
| đủ `MECSU_BASE_URL` + `MECSU_API_KEY` + `MECSU_MODELS` | trống | `llm` |
| thiếu một trong ba | bất kỳ | `agent` |
| đủ cả ba | `agent` | `agent` |

Có key không có nghĩa là bị bắt xài key.

## Bàn giao qua file

Script Python không gọi ngược được vào agent đang chạy nó. Nên chế độ agent không gọi hàm, mà
bàn giao qua đĩa:

1. `hoi()` tra câu trả lời đã có trong `<job>/hoi_agent/tra_loi.json`. Có thì trả về ngay, y như
   model trả lời.
2. Chưa có thì ghi câu hỏi vào danh sách chờ và ném `ThieuTraLoi`. Call site bỏ qua lô đó rồi
   **chạy tiếp**, để gom hết lô còn thiếu chứ không hỏi từng lô một.
3. Cuối bước, `chot_hoi_dap()` ghi `<job>/hoi_agent/cau_hoi.json` rồi **thoát 4**.
4. Agent điền `tra_loi.json` dạng `{"<khoá>": "<câu trả lời>"}` rồi chạy lại **đúng lệnh cũ**.

Câu hỏi giao cho agent là câu hỏi **đã gộp lô** — cùng prompt model sẽ nhận. Không có chuyện chế độ
agent quay về hỏi từng dòng.

## Khoá theo nội dung

Khoá là `sha256(he_thong + prompt)` cắt 16 ký tự, **không phải số thứ tự**. Số thứ tự bị đánh lại
khi input đổi, khiến câu trả lời cũ gán nhầm sang sản phẩm khác — đã xảy ra hai lần trong repo này.

## Câu trả lời của agent không được ưu ái

Nó đi qua **đúng đường đối chiếu ngược** như của model: tên phải chứa mã gốc, không chứa tiền tố
nội bộ, số đo phải khớp text nguồn. Không khớp thì hạ `REVIEW`. Agent tự trả lời rồi tự chấm mình
đúng là đúng thứ chốt chặn sinh ra để chặn.

## Mã thoát

| Mã | Nghĩa |
|---|---|
| `0` | bước xong |
| `3` | dừng cho **người** soát (sau vòng 0, sau vòng 1) |
| `4` | đang chờ **agent** trả lời |
| khác | hỏng — **không giao** |

`3` và `4` khác nhau vì trộn lẫn thì agent sẽ đi trả lời những câu hỏi không tồn tại.

## Agent giám sát gì khi CÓ `.env`

Mỗi bước xong, đọc **10 dòng mẫu** trong artifact vừa sinh, đối chiếu với nguồn của chính dòng đó,
rồi báo số: bao nhiêu khớp, bao nhiêu lệch, lệch chỗ nào. Không đọc toàn bộ — dây chuyền này sinh
ra để khỏi phải trả tiền đọc từng dòng.
