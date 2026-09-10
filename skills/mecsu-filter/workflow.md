# Quy trình chuẩn hóa tên + filter

Đường chạy bình thường là **một lệnh** `run.py` (xem [SKILL.md](SKILL.md)). File này giải
thích từng bước bên trong nó, và cách gọi lẻ từng script khi cần gỡ lỗi hoặc chạy lại
một khúc. Đọc [policy.md](policy.md) trước khi gọi model. Mọi bước không gọi model đều
miễn phí và chạy lại được bao nhiêu lần cũng được.

Quy ước đường dẫn trong file này:

```bash
S=${CLAUDE_SKILL_DIR}/scripts     # thư mục script của skill
J=<thư mục job>                   # tự đặt, ở đâu cũng được
IN=<file Excel đầu vào>
```

## Mục lục

- [0. Trích mẫu trước, đừng chạy cả file](#0-trích-mẫu-trước-đừng-chạy-cả-file)
- [1. Audit — tầng 1](#1-audit--tầng-1)
- [2. Học phụ thuộc hàm — tầng 2](#2-học-phụ-thuộc-hàm--tầng-2)
- [3. Gom hàng đợi](#3-gom-hàng-đợi--tầng-2-tra-corpus-phần-còn-lại-mới-hỏi)
- [4. Hỏi model — tầng 3](#4-hỏi-model--tầng-3)
- [5. Kiểm tra giá trị bằng chính file — tầng 4a](#5-kiểm-tra-giá-trị-bằng-chính-file--tầng-4a)
- [6. Ghép và tự kiểm tra](#6-ghép-và-tự-kiểm-tra)
- [6b. Xuất bảng chấm](#6b-xuất-bảng-chấm)
- [7. Claude duyệt trước khi giao](#7-claude-duyệt-trước-khi-giao)
- [Kết quả đo được](#kết-quả-đo-được)

## 0. Trích mẫu trước, đừng chạy cả file

```bash
python $S/make_sample.py --input $IN --output $J/sample.xlsx --rows 10000
```

Lấy **trọn cụm**, không lấy ngẫu nhiên từng dòng. Schema filter được học từ peer cùng
cụm; cắt đôi cụm thì mọi con số đo được đều không phản ánh lần chạy thật.

## 1. Audit — tầng 1

```bash
python $S/filter_audit.py $IN --out $J/audit --xlsx-out $J/audit.xlsx
```

Việc nó làm:

- gom cụm theo skeleton tên (số → `#`), 4 mức peer L1→L4 (L4 = cứu bằng peer toàn corpus
  khi cả cụm rỗng filter)
- học quy ước format **theo cụm**, không theo corpus toàn cục
- điền filter suy được chắc chắn: hằng số trong cụm, hoặc lấy từ số trong chính tên
- báo: lỗi tên, mâu thuẫn C↔E, filter thiếu, filter nghi thừa, cả-cụm-thiếu

Tự nhận cột theo header; ép bằng `--name-col/--filter-col/--cat-col` nếu nhận sai.
Có cột category (`ten_cate_leaf`) thì dùng làm nhóm hàng — chính xác hơn suy từ hậu tố
`Of <Nhóm>`, và cứu được dòng có cột filter rỗng.

**Chốt chặn đã cài**: giá trị hằng số nào vốn được viết trong tên ở các peer thì chỉ
áp khi tên dòng đó cũng chứa giá trị ấy. Không có chốt này thì
`Cùm U ... Nhúng Nóng Kẽm` bị gán `Xử Lý Bề Mặt: Mạ Kẽm` chép từ peer khác loại mạ.

## 2. Học phụ thuộc hàm — tầng 2

```bash
python $S/learn_deps.py --audit $J/audit.pkl --out $J/deps.json
```

Tìm quan hệ kiểu `(Size Ren, Tiêu Chuẩn) → Size Khóa`. Ba điều đã phải sửa vì đo thấy sai:

1. **Xếp hạng theo độ dùng được × nhất quán**, không theo nhất quán đơn thuần.
   `Size Khóa ← Kích Thước (C)` đạt nhất quán 1.0 nhưng `Kích Thước (C)` chỉ phủ 15%
   số dòng nên gần như không bao giờ tra được; nó đẩy quan hệ hữu ích ra khỏi top.
   Sửa xong: tỷ lệ tra được 2.8% → 10.5% trên file đầy đủ.
2. **Độ tin xét theo từng tổ hợp**, không theo cả quan hệ. Một quan hệ nhất quán 91%
   vẫn có tổ hợp sạch tuyệt đối; loại cả quan hệ là đi hỏi model giá trị file đã có.
3. **Tổ hợp phải có ≥3 dòng làm chứng** (`--min-key-rows`, mặc định 3). Một dòng là không đủ — đã bắt được sai thật:
   `DIN2093 M36` bị suy thành `Dùng Cho Bulong: M35` từ đúng 1 dòng.

## 3. Gom hàng đợi — tầng 2 tra corpus, phần còn lại mới hỏi

```bash
python $S/build_ai_queue.py --audit $J/audit.pkl --deps $J/deps.json \
                            --out $J/queue.json --filled-out $J/corpus.json
```

Đo trên `Fas+Hand_check_all.xlsx` (37.569 dòng): **1.836 ô thiếu → corpus tra 742 → còn 899 câu hỏi.**

Khóa gom là `(nhóm, thuộc tính, bối cảnh quyết định tối thiểu)`. Lấy **hợp** mọi bộ xác
định làm bối cảnh thì mỗi dòng thành một câu hỏi riêng, gom được 1.0x — vô dụng.

`NO_AI_ATTRS` chặn `Ngành Hàng`, `Brand of Group Home`, `Original`: đó là thẻ phân
ngành/kinh doanh, suy được thì tầng 1-2 đã suy; model từng tự điền `Ngành Hàng: CNC`
cho một mũi khoan.

## 4. Hỏi model — tầng 3

```bash
# key điền một lần ở .env gốc plugin, xem README
python $S/ai_fill.py --queue $J/queue.json --audit $J/audit.pkl --output-dir $J/ai \
                     --standards ${CLAUDE_SKILL_DIR}/references/standards --limit 50
python $S/ai_fill.py --queue $J/queue.json --audit $J/audit.pkl --output-dir $J/ai \
                     --standards ${CLAUDE_SKILL_DIR}/references/standards
```

**Kho bảng tra tiêu chuẩn** (`references/standards/*.md`) được nạp vào prompt cho đúng
lô có tiêu chuẩn đó. Mọi máy tìm kiếm đều chặn script (DDG `202 anomaly`, Mojeek `403`)
nên bảng do người tra một lần, pipeline dùng lại nhiều lần. Thêm bảng mới = thêm 1 file
`.md` đặt tên theo slug tiêu chuẩn (`din-912.md`).

Cờ hữu ích:

- `--retry-empty` hỏi lại những câu model từng bỏ trống (dùng sau khi thêm bảng tra)
- `--need-standard` chỉ hỏi câu có bảng tra tương ứng — tiết kiệm
- `--model` đổi model; chọn model bằng `eval_models.py`, đừng chọn bằng tên

Luôn chạy `--limit` trước. Rẻ hơn nhiều so với phát hiện prompt sai sau khi chạy hết.

Hai thứ quyết định chất lượng và chi phí:

- **Vốn từ giá trị có thật đưa vào prompt**, rồi đối chiếu lại câu trả lời với vốn từ đó.
  Thuộc tính có ≤40 giá trị khác nhau thì đưa cả danh sách và bắt sao chép nguyên văn;
  nhiều hơn thì đưa 10 ví dụ làm mẫu định dạng và kiểm tra bằng khuôn số.
- **Một request = một nhóm hàng, nhiều thuộc tính.** Gom theo `(nhóm, thuộc tính)` làm
  8 câu hỏi vỡ thành 6 request: đo được **2838 token/câu**. Gom theo nhóm: **555 token/câu**
  (820 khi prompt có kèm bảng tra tiêu chuẩn).

**Vốn từ chỉ ràng buộc thuộc tính PHÂN LOẠI.** Thuộc tính đo lường (giá trị là số +
đơn vị) chỉ được gợi ý định dạng. Ràng buộc cứng cả hai loại khiến model phải chọn trong
tập giá trị *đã có trong file*; giá trị đúng chưa từng xuất hiện (`56 mm`) thì nó bỏ
trống. Đo được: **300 ô bỏ trống, bỏ ràng buộc thì 12/12 ô thử nghiệm trả lời đúng**,
tổng lấp đầy 73% → 87%.

**Cache khóa theo nội dung, không theo thứ tự.** `ask_id` đánh số từ 1; hàng đợi đổi
là câu trả lời cũ gắn nhầm sang câu hỏi khác — đã xảy ra thật, 21/58 câu sai
(`NOT_IN_VOCAB` 16 + `BAD_FORMAT` 5). Sau khi khóa bằng `key_hash`: 0 sai.

## 5. Kiểm tra giá trị bằng chính file — tầng 4a

```bash
python $S/verify_values.py --audit $J/audit.pkl --queue $J/queue.json \
                           --values $J/ai/ai_values_*.json --out $J/ai/verify.json
```

Học các cặp `(x, y)` đơn điệu trong từng nhóm rồi kẹp giá trị model trả về giữa hai
điểm kề bên trong corpus, **tách theo lát cắt** (tiêu chuẩn) để không trộn DIN 127 với
DIN 7980.

**Đây là cờ bất đồng, không phải phán quyết — và nó KHÔNG tự loại giá trị nữa.**
Đo trên 15 ca bị bác: **ít nhất 11 ca là bác oan giá trị đúng**. `Chiều Dài Ren` phụ
thuộc (size, dải chiều dài) mà đường cong chỉ có một trục, nên `M22x180 → 56 mm` (đúng
công thức `2d+12`) bị coi là ngoài khoảng vì corpus chỉ có bulong M22 ngắn. Độ chính xác
4/15 → hạ xuống cảnh báo, đánh dấu `REVIEW`.

Chốt còn tự loại: **model tự mâu thuẫn** (`AI_TU_MAU_THUAN`) và **tên sản phẩm phủ
định**. Đã kiểm chứng bằng bảng DIN 472 gốc:

| Lỗ | Chuẩn (G) | Corpus | AI |
|---|---|---|---|
| 46 | 48.5 | 49.5 ✗ | — |
| 48 | 50.5 | 53.0 ✗ | — |
| 49 | không có trong chuẩn | — | 51.5 ✗ |
| 51 | 54.0 | — | 54.0 ✓ |

Corpus đang lưu đường kính ngoài vòng găng thay cho đường kính rãnh. Cả hai phía đều
sai được — người/web phân xử, đừng mặc định bên nào đúng.

## 6. Ghép và tự kiểm tra

```bash
python $S/apply_fills.py --input $IN --audit $J/audit.pkl --queue $J/queue.json \
                         --corpus-filled $J/corpus.json --ai-values $J/ai/ai_values_*.json \
                         --ai-verify $J/ai/verify.json --out-dir $J/review
```

Giá trị model chỉ được nhận khi: đúng định dạng, confidence ≥ `--min-confidence`
(mặc định 0.8), không bị tên sản phẩm phủ định, và không tự mâu thuẫn. Corpus không đồng
ý thì **giữ giá trị, đánh dấu `REVIEW`** chứ không loại. Không bao giờ đè lên giá trị đã
có; chỉ điền ô trống.

Ghi xong tự mở lại file kiểm tra bằng code khác với code vừa ghi, sai thì exit 1:

- đủ số dòng, cột gốc nguyên vẹn từng ô
- không có filter trùng y hệt (key lặp với value **khác** là multi-value hợp lệ, không phải lỗi)
- key thêm vào phải là key nhóm hàng đó thật sự dùng

Đo trên `Fas+Hand`: **4.166 ô bổ sung / 638 dòng**; AI nhận 701, model tự bỏ trống 172,
15 ô bị tên phủ định, 10 ô model tự mâu thuẫn, 3 key lạ bị chặn.

## 6b. Xuất bảng chấm

```bash
python $S/build_review.py --audit $J/audit.pkl --queue $J/queue.json --corpus-filled $J/corpus.json \
                          --ai-values $J/ai/ai_values_*.json --ai-verify $J/ai/verify.json \
                          --standards ${CLAUDE_SKILL_DIR}/references/standards \
                          --out $J/review/cham_diem.xlsx
```

Mỗi ô một dòng, gom đủ bằng chứng, xếp theo độ khó chấm. Trên `Fas+Hand`: 1.469 ô, trong
đó **1.189 ô "RẤT KHÓ"** — không đối chiếu được gì và không có bảng tra. Đó là hàng theo
catalog hãng (NBK, SATA...), bảng DIN/GB không cứu được.

## 7. Claude duyệt trước khi giao

Bắt buộc, không script hóa được. Xem mục "Cái gì cần người" trong [SKILL.md](SKILL.md).
Job còn ô chưa quyết được thì để `$J/review/`, không đẩy sang `delivered/`.

## Kết quả đo được

Mọi con số dưới đây đo trên job **`Fas+Hand_check_all.xlsx`, 37.569 dòng**. Chạy file khác
thì số khác — đừng chép sang job mới, đo lại.

| Hạng mục | Đo được |
|---|---|
| ô filter thiếu | 1.836 |
| tầng 2 (tra chính file) lấp được | 742 / 1.836, **0 token** |
| còn phải hỏi model | 899 câu hỏi duy nhất |
| tầng 3 (Gemini + bảng tra) lấp được | 841 ô |
| tổng lấp đầy | **86%** |
| tổng token cả file | 790k |
| token/câu, gom theo nhóm hàng | 555 (820 khi prompt kèm bảng tra) |
| token/câu, gom theo `(nhóm, thuộc tính)` | 2.838 — đắt gấp 5 |
| tỷ lệ tra được của tầng 2, trước/sau khi xếp hạng lại | 2.8% → 10.5% |
| lấp đầy trước/sau khi bỏ ràng buộc vốn từ cho thuộc tính đo lường | 73% → 87% |
| ô bổ sung khi ghép | 4.166 ô / 638 dòng |
| model tự bỏ trống / tên phủ định / tự mâu thuẫn / key lạ | 172 / 15 / 10 / 3 |
| bảng chấm | 1.469 ô, trong đó 1.189 "RẤT KHÓ" (hàng theo catalog hãng, DIN/GB không cứu được) |

Đo bằng eval 18 câu có đáp án xác minh từ bảng tiêu chuẩn (`eval_models.py`):

| Model | Đúng | Token | Thời gian |
|---|---|---|---|
| `ag/gemini-3.7-flash-medium` | **18/18** | **4.570** | 4s |
| `ag/gemini-3.7-flash-high` | 18/18 | 7.561 | 12s |
| `ag/gemini-3.1-pro-low` | 18/18 | 7.606 | 32s |
| `ag/claude-sonnet-4-6` | 12/18 | 4.8k | — (đo lần trước) |

Cả ba model Gemini đều đúng hết phần thông số. Cái phân biệt chúng là **có bám skill
không** — đo bằng `tools/eval_skills.py`:

| Model | Ca hành vi đúng | Token |
|---|---|---|
| `ag/gemini-3.7-flash-medium` | **6/6** | 26.455 |
| `ag/gemini-3.7-flash-high` | 6/6 | 30.489 |
| `ag/gemini-3.1-pro-low` | 3/6 | 33.899 |

`ag/gemini-3.1-pro-low` trượt vì dừng lại hỏi về `.env` thay vì chạy hai tầng 0 token, và
vì gặp lỗi dò cột thì dừng thay vì ép `--filter-col`. Đắt hơn, chậm hơn, bám skill kém hơn.

Job nhỏ để so sánh — `Handtools-check-cate-filter.xlsx`, 5.730 dòng: 26 ô thiếu, corpus tra
được 1, còn **25 câu hỏi**. Số dòng không quyết định kích thước job; số câu hỏi duy nhất mới
quyết định.
