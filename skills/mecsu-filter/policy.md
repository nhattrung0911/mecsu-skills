# Chính sách token cho job chuẩn hóa filter

Ngăn tiêu token trước khi tiêu, không phải đếm sau khi tiêu. Áp cho mọi agent
(Claude, Codex, Gemini CLI...).

## Luật cứng

- **Một agent chính.** Không tạo subagent / worker song song / agent nền trừ khi
  người dùng cho phép cho đúng file đang làm.
- **Không bao giờ hỏi model theo từng dòng.** Gom thành câu hỏi duy nhất theo
  `(nhóm hàng, thuộc tính, bối cảnh quyết định)` rồi trải kết quả ngược lại.
- **Không hỏi thứ file đã biết.** Mọi ô đều phải qua tầng rule và tầng corpus trước.
  Đo trên mẫu 10k: **58% ô thiếu được corpus tra ra, 0 token.**
- **Không nạp cả file vào context.** Script đọc Excel; agent chỉ đọc số liệu tổng hợp
  và các ô cần phân xử.
- **Không tra web khi tên sản phẩm + corpus đã đủ căn cứ.** Web chỉ dành cho ô mà
  corpus và model bất đồng, hoặc mã lạ không nhóm nào biết.

## Đo bằng ô duy nhất, không đo bằng dòng

Kích thước job = **số câu hỏi duy nhất sau khi gom**, không phải số dòng.

| | dòng | ô filter thiếu | câu hỏi cho model |
|---|---|---|---|
| mẫu 10.009 dòng | 10.009 | 158 | **57** |

Một file 67k dòng vẫn có thể là job nhỏ. Một file 300 dòng toàn sản phẩm lạ thì không.

## Bậc ngân sách

Tính theo **câu hỏi duy nhất**:

| Số câu hỏi | Kế hoạch | Tra web | Dừng trước khi |
|---|---|---|---|
| 1-100 | `--limit 10` thử, rồi chạy hết 1 model | tối đa 5 lượt | chạy model thứ 2 |
| 101-500 | `--limit 10` thử, chạy hết, model 2 chỉ cho ô bị `OUT_OF_RANGE` | tối đa 10 lượt | chạy model 2 trên toàn bộ |
| >500 | chạy 100 câu đầu, báo phân bố confidence và xin duyệt | 0 trước khi duyệt | chạy phần còn lại |

## Chạy lại thì miễn phí, đừng `--restart`

Verdict nằm trong `ai_values_<model>.json`. `verify_values.py`, `apply_fills.py` đều
đọc lại từ đó — sửa code sau bước gọi model rồi build lại tốn **0 token**.

Chỉ `--restart` khi **prompt hoặc hàng đợi đổi**. Vì cache khóa theo `key_hash` nội
dung, hàng đợi đổi mà câu hỏi cũ vẫn còn thì câu trả lời cũ vẫn dùng được — không cần
`--restart`.

## Ngưỡng phải xin phép

- tạo subagent / chạy song song
- chạy model thứ hai trên **toàn bộ** hàng đợi (chỉ ô bất đồng thì không cần xin)
- tra web quá số lượt của bậc
- quá 20% dòng bị đánh `REVIEW` sau khi đã chạy đủ các tầng

## Thứ tự phải giữ

1. rule (0 token) → 2. corpus (0 token) → 3. model → 4. verify bằng corpus (0 token)
→ 5. Claude/web cho phần bất đồng.

Đảo thứ tự là trả tiền cho câu trả lời mà file đã có sẵn.

Không app nào đếm token chính xác tuyệt đối. Đây là giới hạn hành vi chủ động; muốn
chặn cứng theo quota thì phải đi qua gateway có đo.
