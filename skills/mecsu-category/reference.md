# mecsu-category — chi tiết

> Đi kèm skill `mecsu-category`. `$CLAUDE_SKILL_DIR` là thư mục chứa `SKILL.md`;
> `$ONCHECK_JOBS` là thư mục chứa `jobs/` của công việc đang chạy (mặc định: thư mục cha
> gần nhất có `jobs/`, hoặc thư mục hiện tại).
>
> **Mọi con số trong file này đo trên job `On_web_category` (67.526 dòng, 16 nhóm lv1,
> 740 leaf).** Nguồn khác thì số khác — chạy `measure.py` để sinh lại, đừng chép sang.

Kiểm tra cột mô tả sản phẩm có khớp cột danh mục lá đang gán không, nhóm theo danh mục cấp 1.
Ba vai trò đó do `detect_schema.py` tự dò theo tên cột; không phụ thuộc vị trí cột. Không ghi
đè file gốc.

## Mục lục

- [Một lệnh](#một-lệnh)
- [Từng bước](#từng-bước)
- [Chạy](#chạy)
- [Verdict](#verdict)
- [File cuối](#file-cuối)
- [Phân xử chỗ 2 model bất đồng](#phân-xử-chỗ-2-model-bất-đồng)
- [Giao hàng](#giao-hàng)
- [Lần sau chạy nhanh](#lần-sau-chạy-nhanh)
- [Dọn dẹp](#dọn-dẹp)
- [Vấn đề dữ liệu phát hiện được](#vấn-đề-dữ-liệu-phát-hiện-được-ở-nguồn-không-sửa-được-từ-đây)
- [Kết quả đo được](#kết-quả-đo-được)

## Một lệnh

```bash
python ${CLAUDE_SKILL_DIR}/scripts/audit.py --input <file.xlsx> --models ag/gemini-3.7-flash-medium ag/gemini-3.7-flash-high
```

Chạy hết: dò cột → lọc chữ → model chấm → model 2 đối chiếu → dựng file + tự kiểm tra. Dừng lại
sau mẫu 50 cặp để bạn xem chất lượng; xem xong chạy lại kèm `--yes`.

**Không phụ thuộc cấu trúc file.** `detect_schema.py` khớp tên cột miễn phí trước, chỉ gọi model
cho vai trò tên không quyết được. Cột nào pipeline không hiểu thì **giữ nguyên, không đụng**. Chỉ
cần 3 vai trò có mặt: mô tả sản phẩm, danh mục đã gán, danh mục cấp 1.

Đã kiểm chứng trên file 8 cột, header tiếng Việt, thứ tự khác, thiếu cột id, thừa 2 cột lạ: model
map đúng `Mã DM`→leaf_id, `Cấp`→leaf_depth, trả null đúng cho 3 vai trò không tồn tại, và 2 cột
`Ghi chú`/`Giá bán` giữ nguyên 100%.

## Từng bước

| bước | script | chi phí đo được |
|---|---|---|
| dò cột → `schema.json` | `detect_schema.py` | 0 nếu tên cột khớp |
| tách theo lv1 (tùy chọn, để tự xem) | `split_by_level1.py` | 0 |
| đối chiếu chữ, lọc dòng hiển nhiên đúng | `rule_check.py` | 0 |
| LLM chấm các cặp nghi vấn | `ai_check.py` | 337 token/cặp (medium) |
| model thứ hai đối chiếu | `ai_check.py --model <khác>` | 439 token/cặp (high) |
| ma trận đồng thuận + danh sách bất đồng | `compare_models.py` | 0 |
| worklist tranh chấp, ưu tiên theo số dòng | `list_disputes.py` | 0 |
| trải verdict về đủ 67k dòng + bảng sửa | `apply_fixes.py` (tùy chọn, `audit.py` không chạy) | 0 |
| file cuối + tự kiểm tra | `build_final.py` | 0 |
| đo lại mọi con số trong tài liệu | `measure.py` | 0 |

### Vì sao rẻ

Rule-check lọc sạch 63.7% dòng khớp chữ. Phần còn lại được **gộp trùng**: bỏ token có chữ số
(size, mã DIN, part number) khỏi mô tả → 24,487 dòng nghi vấn thu về 2,696 cặp duy nhất.
LLM chỉ chấm 2,696 cặp, `apply_fixes.py` trải verdict ngược lại đủ 24,487 dòng. Giảm ~9x số lần
gọi model. Đừng bao giờ gọi LLM theo từng dòng.

### Vì sao chính xác

Mỗi request chỉ chứa sản phẩm của **một lv1**, kèm nguyên danh sách leaf hợp lệ của lv1 đó
(nhiều nhất 291 leaf ≈ 8k ký tự). Model buộc phải chọn `suggested_category` từ danh sách có thật;
`ai_check.py` đối chiếu lại lần nữa và đánh dấu `NOT_IN_CATALOG` nếu model vẫn bịa. Không có bước
này model gợi ý danh mục không tồn tại ("Bộ Điều Áp Khí Nén" thay vì "Van Giảm Áp Khí Nén").

## Chạy

```bash
cd $CLAUDE_SKILL_DIR/scripts

python split_by_level1.py
python rule_check.py

copy .env.example .env      # rồi dán key + model
python ai_check.py --limit 50                     # thử 50 cặp, xem chất lượng
python ai_check.py --level1 "Dụng Cụ Cầm Tay"     # chạy 1 nhóm
python ai_check.py                                # chạy hết

python apply_fixes.py --verdicts $ONCHECK_JOBS/jobs/oncheck/ai_verdicts_ag-gemini-3-7-flash-medium.json
```

`ai_check.py` resume được: verdict đã có nằm trong `ai_verdicts_<model>.json`, chạy lại chỉ làm
phần thiếu, `--restart` mới làm lại từ đầu. Đổi `--model` sinh file riêng nên so sánh nhiều model
trên cùng bộ cặp được.

## Verdict

Rule (`rule_report.xlsx`):

| verdict | nghĩa | vào hàng đợi AI |
|---|---|---|
| `EXACT` | tên leaf xuất hiện nguyên cụm trong mô tả | không |
| `ALL_WORDS` | đủ mọi từ nội dung của leaf, khác thứ tự | không |
| `PARTIAL` | khớp một phần | có |
| `NO_OVERLAP` | không từ nào chung | có |

`NO_OVERLAP` **không đồng nghĩa sai**. Nguồn này đặt nhiều leaf bằng tiếng Anh trong khi mô tả
tiếng Việt — "Vít Bi Nhún" → `Ball Plunger`, "Chốt Định Vị" → `Locating Pins`, "Bulong Vặn Tay" →
`Knurled Knob`. Rule-check mù các case đó; đấy chính là việc của LLM ở bước 2.

AI (`ai_report_<model>.xlsx`): `correct` / `wrong` / `unsure` kèm `ai_reason`,
`ai_suggested_leaf_name`, `ai_suggested_leaf_id`, `ai_suggested_valid`. Sắp xếp `wrong` lên đầu
rồi theo `row_count` giảm dần — sửa từ trên xuống là chạm nhiều dòng nhất trước.

Trạng thái cuối (`annotated_<model>.xlsx`, cột `status`):

| status | nghĩa |
|---|---|
| `PASS_RULE` | rule-check khớp, không cần LLM |
| `AI_OK` | LLM xác nhận đúng |
| `FIX` | LLM bác bỏ, có leaf thay thế hợp lệ, confidence ≥ `--min-confidence` (mặc định 0.8) |
| `REVIEW_LOW_CONFIDENCE` | LLM bác bỏ nhưng không đủ chắc |
| `REVIEW_WRONG_NO_TARGET` | LLM bác bỏ nhưng không có leaf nào phù hợp trong lv1 → thiếu danh mục |
| `REVIEW_AMBIGUOUS_TARGET` | tên leaf đích tồn tại dưới nhiều id, không biết chọn id nào |
| `REVIEW_GENERIC_TARGET` | leaf đích là danh mục hứng chung — không hạ một leaf cụ thể xuống đó |
| `REVIEW_UNSURE` | LLM không quyết được |
| `NOT_CHECKED` | lọt lưới (chỉ xảy ra nếu verdict thiếu) |

Chỉ `FIX` mới vào `fixes_<model>.xlsx`. **Không có bước nào tự ghi đè file gốc** — bảng `fixes` là
thứ để người duyệt trước khi áp.

## File cuối

`build_final.py` chỉ đổi một dòng khi **mọi** nguồn verdict cùng chỉ một leaf thay thế
(`--accept-single-model` nới điều kiện này). Sau khi ghi, nó tự mở lại file và kiểm tra; sai bất kỳ
mục nào là exit code 1 chứ không im lặng giao file hỏng:

- số dòng vào == số dòng ra
- số dòng đổi == số dòng trong changelog
- dòng không nằm trong changelog phải giống hệt nguồn, mọi cột
- mọi `leaf_category_id` phải có thật
- bộ ba (id, tên, depth) phải là bộ ba nguồn đã dùng — bắt trường hợp đổi leaf mà quên đổi `depth`
- một id không được ứng với nhiều tên

Chạy `--exclude-pairs <file.json>` với danh sách `pair_id` người duyệt đã bác để giữ nguyên các
dòng đó.

## Phân xử chỗ 2 model bất đồng

`build_final.py` mặc định **không sửa** khi 2 model không thống nhất. Muốn giải quyết chúng thì
tra mã sản phẩm thật:

```bash
python list_disputes.py --verdicts $ONCHECK_JOBS/jobs/oncheck/ai_verdicts_*.json
```

In ra worklist xếp theo số dòng ảnh hưởng, kèm mã hãng đã trích sẵn để search, và tách riêng nhóm
**thiếu danh mục** (`taxonomy_gaps.json`) — nhóm đó search vô ích, taxonomy chưa có chỗ chứa,
phải người quyết.

Tự search bằng web search tool, đi từ trên xuống. Bảng "rows covered if you search the top N" cho
biết dừng ở đâu là đủ: với job `On_web_category`, top 10 cặp phủ 50% số dòng tranh chấp.

Có bằng chứng rồi thì ghi `jobs/oncheck/dispute_resolution.json`:

```json
{"895": {"decision": "change", "new_leaf_name": "Đầu Nối Nhanh Khí Nén Chữ Y",
         "new_leaf_id": 7246, "confidence": 0.95,
         "reason": "Catalog Pisco/MISUMI: PVU = Tripod Union, 1 cổng ra 3 ống"}}
```

rồi truyền vào:

```bash
python build_final.py --verdicts ...json --resolutions $ONCHECK_JOBS/jobs/oncheck/dispute_resolution.json
```

Phán quyết thắng luật đồng thuận, vì nó dựa trên bằng chứng về mã thật chứ không phải 2 model
đoán từ mô tả. Guard vẫn giữ hiệu lực.

**Cặp nào không có bằng chứng thì để trống** — nó giữ nguyên danh mục cũ. Bỏ sót một cặp là an
toàn; phán quyết sai bị áp lên mọi dòng của cặp đó. Job `On_web_category`: 3/73 cặp có bằng chứng
đủ chắc, 70 cặp còn lại giữ nguyên.

> Đừng scrape công cụ tìm kiếm từ script. Đã thử: bị chặn IP, 73/73 lượt tra về rỗng, và vòng
> retry còn nhân ba số request làm mọi thứ tệ hơn. Vài lượt search có chủ đích vào nhóm nhiều
> dòng nhất ăn đứt quét tự động bị bóp cổ đến câm.

## Giao hàng

`deliver.py` ghi sang `jobs/delivered/<tên>_categorized_<ngày>_<giờ>.xlsx`: **giữ nguyên 9 cột gốc**
rồi nối thêm 4 cột review.

| cột thêm | nội dung |
|---|---|
| `new_leaf_category_id` | id sau kiểm tra (bằng id cũ nếu không đổi) |
| `new_leaf_category_name` | tên sau kiểm tra |
| `is_changed` | `YES` / `NO` |
| `confidence_pct` | 0-100. **Trống = rule filter xử lý, không model nào chấm** — không bịa 100% |

`deliver.py` **từ chối chạy khi 2 model còn bất đồng**, vì `jobs/delivered/` theo SKILL.md chỉ chứa
file đã duyệt xong. Ba cách qua cửa, đưa thẳng cho `deliver.py` chính file người duyệt đã làm:

```bash
python deliver.py --verdicts ...json --resolutions $ONCHECK_JOBS/jobs/oncheck/dispute_resolution.json
python deliver.py --verdicts ...json --exclude-pairs <danh sách pair_id đã bác>.json
python deliver.py --verdicts ...json --allow-disputed
```

Cặp nào có trong `--resolutions` hoặc `--exclude-pairs` là đã có người quyết, không tính là
tranh chấp nữa. Trước đây `deliver.py` tính lại tranh chấp thẳng từ verdict thô nên giải quyết
đúng cách vẫn không giao được.

## Lần sau chạy nhanh

Nguồn mới, một mạch:

```bash
cd $CLAUDE_SKILL_DIR/scripts
python rule_check.py --input $ONCHECK_JOBS/jobs/inbox/<file>.xlsx
python ai_check.py --limit 50            # xem chất lượng trước khi trả tiền cho cả bộ
python ai_check.py
python ai_check.py --model ag/gemini-3.7-flash-high
python compare_models.py --a $ONCHECK_JOBS/jobs/oncheck/ai_verdicts_ag-gemini-3-7-flash-medium.json --b $ONCHECK_JOBS/jobs/oncheck/ai_verdicts_ag-gemini-3-7-flash-high.json
python build_final.py --verdicts $ONCHECK_JOBS/jobs/oncheck/ai_verdicts_*.json
python deliver.py --verdicts $ONCHECK_JOBS/jobs/oncheck/ai_verdicts_*.json
```

Mẹo tiết kiệm:

- **Đừng bao giờ `--restart` nếu chỉ sửa code sau bước gọi model.** Verdict nằm trong
  `ai_verdicts_*.json`; `build_final.py`, `apply_fixes.py`, `compare_models.py`, `measure.py`,
  `deliver.py` đều đọc lại từ đó, chạy free. Job này sửa 3 lỗi và build lại 3 lần, tốn 0 token.
- Chỉ `--restart` khi **prompt hoặc queue đổi**. Đổi schema `ai_queue.json` thì chạy lại
  `rule_check.py` là đủ, verdict vẫn dùng được vì khoá theo (mẫu mô tả, tên leaf).
- Chạy 1 lv1 trước cho nguồn lạ: `ai_check.py --level1 "<tên>"`.
- `--limit 50` luôn rẻ hơn phát hiện prompt sai sau khi chạy hết.

## Dọn dẹp

**Giữ** — đã trả tiền model hoặc do người làm ra, không sinh lại được:

| file | vì sao |
|---|---|
| `ai_verdicts_*.json` | nguồn sự thật, mọi thứ khác derive từ đây |
| `ai_verdicts_*__nocatalog.json` | nhánh đối chứng của A/B; xoá là `measure.py` mất mục 3 |
| `ai_queue.json` | cần để đọc verdict theo pair_id |
| `dispute_resolution.json` | phán quyết thủ công dựa trên bằng chứng web |
| `taxonomy_gaps.json`, `dispute_research.json` | danh sách chờ người review |
| `*_FINAL.xlsx` + `_changelog.xlsx` | vết sửa để đối chiếu |
| `jobs/delivered/*` | bản giao |

**Xoá được** — sinh lại miễn phí, **0 lần gọi model** (`ai_check.py` thấy đủ verdict thì báo
`todo=0, batches=0` rồi vẫn xuất report):

- `split/`, `rule_report.xlsx`, `annotated_*.xlsx`, `fixes_*.xlsx`, `disagreements_*.xlsx`,
  `ai_report_*.xlsx`

```bash
cd $ONCHECK_JOBS/jobs/oncheck
Remove-Item -Recurse -Force split
Remove-Item rule_report.xlsx, annotated_*.xlsx, fixes_*.xlsx, disagreements_*.xlsx, ai_report_*.xlsx
```

Job `On_web_category` dọn theo cách này: 18.9 MB → 5.6 MB, giữ lại 9 file.

Sau khi giao: file gốc ở `jobs/inbox/` chuyển sang `jobs/history/`, `jobs/inbox/` chỉ chứa việc
đang chờ. Job còn cặp chưa giải quyết thì để ở `jobs/review/`, không được đẩy vào `jobs/delivered/`.

## Vấn đề dữ liệu phát hiện được (ở nguồn, không sửa được từ đây)

- **5 tên leaf ứng với 2 id khác nhau trong cùng một lv1**: `Bộ Tua Vít` (4078 và 6860),
  `Bộ Cờ Lê` (4071, 6852), `Bộ Lục Giác` (1330, 6853), `Rivet Inox` (639, 6445),
  `Rivet Inox Chân Thép` (669, 6444). 168 dòng mang id "thứ hai". Tool từ chối sửa vào các tên này
  vì không có cách chọn đúng id.
- 11 tên leaf thừa khoảng trắng đầu/cuối (`'Đầu Nối Nhanh Khí Nén Thẳng '`, `'Mũi Khoét '`, ...).
- 2 tên leaf trùng ở nhiều lv1: `Other` (3 lv1), `Chưa Phân Loại` (2 lv1) — cần root để phân biệt.
- lv1 `Đang Xử Lý` (7 dòng) và `Ốc Vít Inox 316` (6 dòng) trông như rác cần dọn ở nguồn.
- Thiếu danh mục cho các nhóm sản phẩm có thật: van xả nhanh khí nén (~45 dòng), đầu nối ren
  đực-cái / cái-cái (~20 dòng), dao cạo sơn, cọ quét sơn, gripper pad. Cả hai model đều báo
  "không có danh mục phù hợp" ở các cụm này.

## Kết quả đo được

Đo trên job **`On_web_category`, 67.526 dòng, 16 nhóm lv1, 740 leaf**. Chạy `measure.py` để
sinh lại cho nguồn khác.

| Hạng mục | Đo được |
|---|---|
| dòng khớp chữ, không cần model | 63.7% |
| dòng nghi vấn | 24.487 |
| sau khi gộp trùng (bỏ token có chữ số) | 2.696 cặp duy nhất — giảm ~9x số lần gọi model |
| token/cặp, model chấm | 337 (`ag/gemini-3.7-flash-medium`) |
| token/cặp, model đối chiếu | 439 (`ag/gemini-3.7-flash-high`) |
| leaf nhiều nhất trong một prompt | 291 leaf ≈ 8k ký tự |
| lượt tra web từ script | 0/73 thành công — IP bị chặn, đã bỏ hướng này |

Kiểm chứng khả năng dò cột: file 8 cột, header tiếng Việt, thứ tự khác, thiếu cột id, thừa
2 cột lạ → model map đúng `Mã DM`→leaf_id, `Cấp`→leaf_depth, trả null đúng cho 3 vai trò
không tồn tại, 2 cột `Ghi chú`/`Giá bán` giữ nguyên 100%.
