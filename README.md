# mecsu-skills

Bộ skill Claude Code nội bộ Mecsu cho công việc dữ liệu sản phẩm. Cài một lần, gọi bằng
`/mecsu-category` và `/mecsu-filter` trong bất kỳ phiên Claude Code nào.

| Skill | Trả lời câu hỏi | Đầu vào | Đầu ra |
|---|---|---|---|
| `/mecsu-category` | *Sản phẩm này có nằm đúng danh mục lá không?* | file Excel có cột mô tả + danh mục đã gán | file đã kiểm + changelog + danh sách cần người quyết |
| `/mecsu-filter` | *Sản phẩm này đã đủ và đúng thông số chưa?* | file Excel có cột filter dạng `Key: Value` | file đã điền + bảng chấm điểm từng ô |

Hai skill bổ trợ nhau: `category` lo **sản phẩm nằm ở đâu**, `filter` lo **sản phẩm có thông số gì**.

---

## Mục lục

1. [Chuẩn bị máy](#1-chuẩn-bị-máy)
2. [Cài plugin](#2-cài-plugin)
3. [Điền key một lần](#3-điền-key-một-lần)
4. [Dùng `/mecsu-category` từng bước](#4-dùng-mecsu-category-từng-bước)
5. [Dùng `/mecsu-filter` từng bước](#5-dùng-mecsu-filter-từng-bước)
6. [Lỗi thường gặp và cách xử](#6-lỗi-thường-gặp-và-cách-xử)
7. [Nguyên tắc không được phá](#7-nguyên-tắc-không-được-phá)
8. [Cho người phát triển skill](#8-cho-người-phát-triển-skill)

---

## 1. Chuẩn bị máy

Cần **Python 3.11 trở lên**. Kiểm tra:

```bash
python --version
```

Cài 3 thư viện:

```bash
pip install openpyxl requests python-dotenv
```

Cần một endpoint tương thích OpenAI. Nội bộ Mecsu dùng 9router:
`https://9router.mspro.io.vn/v1`. Chưa có key thì hỏi người quản trị 9router — **đừng tự đoán
endpoint hay model**.

## 2. Cài plugin

Bản trên GitHub:

```
/plugin marketplace add nhattrung0911/mecsu-skills
/plugin install mecsu-skills@mecsu-skills
```

Bản đang sửa ở máy:

```
/plugin marketplace add d:/test/mecsu-skills
/plugin install mecsu-skills@mecsu-skills
```

Cài xong gõ `/mecsu-category` hoặc `/mecsu-filter` là chạy. Trùng tên với plugin khác thì gọi đầy
đủ: `/mecsu-skills:mecsu-category`.

## 3. Điền key một lần

Ở thư mục gốc plugin:

```bash
copy .env.example .env        # Windows
cp .env.example .env          # macOS/Linux
```

Mở `.env`, điền:

```ini
MECSU_BASE_URL=https://9router.mspro.io.vn/v1
MECSU_API_KEY=<key của bạn>
MECSU_MODELS=ag/gemini-3.7-flash-medium
```

- **Cả hai skill đọc chung file này**, không phải điền lại ở từng skill.
- Thứ tự ưu tiên: biến môi trường của máy → `.env` của skill → `.env` gốc. Nên một skill vẫn dùng
  được key riêng khi cần.
- `.env` nằm trong `.gitignore`. **Không commit file này.**
- `MECSU_MODELS` để nhiều model cách nhau dấu phẩy khi muốn hai model đối chiếu nhau.
  `gemini-3.7-flash-medium` đã đo được 18/18 câu chuẩn và là model rẻ nhất trong nhóm đạt 18/18 —
  đừng đổi sang model đắt hơn nếu chưa đo lại bằng `eval_models.py`.

Chưa có key vẫn chạy được hai tầng đầu của cả hai skill (dò cột, đối chiếu chữ, tra corpus) vì
chúng **không gọi model, không tốn token**. Script tự dừng và in đường dẫn file cần điền khi tới
bước cần key.

## 4. Dùng `/mecsu-category` từng bước

### Bước 1 — Chuẩn bị file Excel

File cần có tối thiểu 3 loại cột (tên cột đặt kiểu gì cũng được, script tự dò):

- mô tả / tên sản phẩm
- danh mục lá đang gán
- danh mục cấp 1

Có thêm cột nào khác cũng không sao — **cột nào script không hiểu thì giữ nguyên, không đụng tới**.

### Bước 2 — Gọi skill

Trong Claude Code:

```
/mecsu-category d:/duong/dan/file.xlsx
```

Hoặc chạy tay:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/audit.py --input <file.xlsx> \
  --models ag/gemini-3.7-flash-medium ag/gemini-3.7-flash-high
```

Một lệnh này chạy cả dây chuyền: dò cột → lọc chữ (0 token) → model thứ nhất chấm → model thứ hai
đối chiếu → dựng file cuối kèm tự kiểm tra.

Các cờ hay dùng:

| Cờ | Nghĩa |
|---|---|
| `--input` | file Excel cần kiểm (bắt buộc) |
| `--sheet` | tên sheet, bỏ trống thì lấy sheet duy nhất hoặc sheet nhiều dòng nhất |
| `--models` | hai model: một chấm, một đối chiếu |
| `--calibrate` | số cặp chấm thử trước, mặc định 50; `0` để bỏ qua |
| `--yes` | bỏ qua chỗ dừng sau lô hiệu chuẩn — **chỉ dùng sau khi đã đọc lô đó** |

### Bước 3 — Đọc lô hiệu chuẩn rồi mới trả tiền cho cả bộ

Sau 50 cặp đầu, script **dừng lại** và in đường dẫn `ai_report_<model>.xlsx`. Mở file đó ra xem
model chấm có hợp lý với nguồn dữ liệu này không. Hợp lý rồi mới chạy lại đúng lệnh cũ kèm `--yes`.

Đây là chỗ rẻ nhất để phát hiện prompt sai. Bỏ qua bước này là trả tiền cho cả bộ rồi mới biết hỏng.

### Bước 4 — Xử ba file cần người

Chạy xong, trong `jobs/oncheck/` sẽ có:

| File | Việc phải làm |
|---|---|
| `changelog.xlsx` | Toàn bộ thay đổi đề xuất. **Người phải duyệt trước khi giao.** |
| `disputes_to_research.json` | Hai model bất đồng. Search đúng mã hàng thật, chỉ ghi lại cái chứng minh được vào `dispute_resolution.json`. |
| `taxonomy_gaps.json` | Sản phẩm không có danh mục hợp lệ nào. **Không phải lỗi phân loại** — đưa cho người quản lý taxonomy. |

Bỏ qua một cặp tranh chấp thì an toàn. Phán bừa một cặp là sai lan ra **mọi dòng** dùng chung cặp đó.

### Bước 5 — Giao file

```bash
python deliver.py --verdicts ai_verdicts_<model>.json \
  --resolutions jobs/oncheck/dispute_resolution.json
```

`deliver.py` **từ chối ghi** vào `jobs/delivered/` khi còn cặp tranh chấp chưa ai quyết. Sự từ chối
đó là tính năng, không phải lỗi. Ba cách qua cửa:

| Cách | Khi nào dùng |
|---|---|
| `--resolutions dispute_resolution.json` | đã tra bằng chứng và ghi phán quyết |
| `--exclude-pairs <file>.json` | chấp nhận bỏ qua các cặp đó, giữ nguyên danh mục cũ |
| `--allow-disputed` | biết là còn tranh chấp và vẫn muốn giao |

## 5. Dùng `/mecsu-filter` từng bước

### Bước 1 — Kiểm tra cột filter

Cột filter phải chứa dạng `Key: Value | Key: Value`. Nếu không, script **dừng ngay** thay vì audit
lên cột sai rồi đẻ ra file rác.

### Bước 2 — Lấy mẫu đo trước (khuyến khích với file lớn)

```bash
python ${CLAUDE_SKILL_DIR}/scripts/make_sample.py --input <file.xlsx> \
  --output <mau.xlsx> --rows 10000
```

Lấy **trọn cụm** (các dòng cùng khung tên) chứ không lấy ngẫu nhiên từng dòng, để số đo phản ánh
đúng lần chạy thật. Không dò được cột thì script dừng và bảo bạn chỉ rõ bằng `--name-col` /
`--filter-col` (đánh số từ 0).

### Bước 3 — Chạy cả dây chuyền

```
/mecsu-filter d:/duong/dan/file.xlsx
```

Hoặc chạy tay:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/run.py --input <file.xlsx> --job <thư mục làm việc>
```

Dây chuyền: rule → tra chính file (corpus) → hỏi model → đối chiếu ngược → ghép + tự kiểm tra →
xuất bảng chấm. **Hai tầng đầu 0 token** — mọi ô phải qua rule và corpus trước, hỏi model thứ file
đã biết là trả tiền cho câu trả lời có sẵn.

Các cờ hay dùng:

| Cờ | Nghĩa |
|---|---|
| `--input` | file Excel (bắt buộc) |
| `--job` | thư mục làm việc, tự đặt (bắt buộc) |
| `--model` | bỏ trống thì lấy model đầu tiên trong `.env` |
| `--calibrate` | số câu hỏi thử trước, mặc định 50 |
| `--yes` | đi tiếp sau lô hiệu chuẩn |
| `--filter-col` / `--name-col` / `--cat-col` | ép cột khi tự dò sai (đánh số từ 0) |
| `--min-confidence` | ngưỡng tin cậy để nhận giá trị model, mặc định 0.8 |

### Bước 4 — Chấm điểm trong `review/cham_diem.xlsx`

Mỗi ô một dòng, đã gom sẵn: giá trị · nguồn · căn cứ · đối chiếu file · điểm lân cận thật · có bảng
tra hay không, xếp theo độ khó chấm.

- Ô đánh dấu `REVIEW` là chỗ **corpus không đồng ý**, KHÔNG phải ô sai. Đối chiếu bảng tra hoặc tra
  web rồi mới quyết.
- **Chính file nguồn cũng sai được.** Đối chiếu DIN 472 gốc từng bắt được 13 dòng sai do lệch một
  dòng khi nhập — có dòng đường kính ngoài nhỏ hơn đường kính rãnh, vô lý về vật lý. Đừng mặc định
  bên nào đúng.
- Job còn ô chưa quyết thì **để nguyên ở `review/`**, không đẩy sang `delivered/`.

### Bước 5 — Thêm bảng tra tiêu chuẩn (khi cần)

`references/standards/*.md` hiện có DIN 471, 472, 912, 931. `run.py` tự nạp đúng bảng của lô hàng
có tiêu chuẩn đó vào prompt.

Thêm bảng mới = thêm một file `.md` đặt tên theo slug tiêu chuẩn, ví dụ `din-933.md`. Mọi máy tìm
kiếm đều chặn script (DuckDuckGo trả `202 anomaly`, Mojeek trả `403`) nên bảng do **người tra một
lần**, dây chuyền dùng lại nhiều lần.

## 6. Lỗi thường gặp và cách xử

| Thông báo | Nghĩa | Cách xử |
|---|---|---|
| `MECSU_BASE_URL chua co` | chưa tạo `.env` | copy `.env.example` thành `.env` rồi điền |
| `... batch(es) failed` + thoát khác 0 | endpoint chết, key sai, hoặc mạng đứt | sửa `.env` rồi **chạy lại đúng lệnh cũ** — nó tự resume, không hỏi lại câu đã trả lời |
| `No verdict files in ...` | chưa có lượt model nào chạy xong | chạy lại từ `audit.py`, xem log xem lượt model có lỗi gì không |
| `Khong nhan ra cot ['name', 'filt']` | header lạ, không đoán được | chỉ rõ `--name-col` / `--filter-col` (đánh số từ 0) |
| `Khong doan duoc cot ten / cot filter` | như trên, ở `make_sample.py` | như trên |
| `Cot filter khong giong filter` | đang trỏ vào cột đếm hoặc cột category | kiểm lại số cột, đừng ép bừa |
| `... pair(s) still disputed` | hai model còn bất đồng | xem [Bước 5 của category](#bước-5--giao-file) |
| `The built workbook failed its own verification` | file dựng ra không khớp file gốc | **KHÔNG giao.** Đọc log xem lệch chỗ nào rồi dựng lại — đừng chạy lại kèm cờ khác để lách |
| Excel mở ra thấy tiếng Việt bị vỡ | console Windows là cp1252 | không ảnh hưởng file, chỉ là hiển thị ở terminal |

**Thoát khác 0 nghĩa là KHÔNG giao.** Không phải "chạy lại kèm cờ khác cho nó qua".

## 7. Nguyên tắc không được phá

Áp cho cả hai skill, mỗi cái sinh ra từ một lỗi đã bắt được thật:

1. **Không bao giờ gọi model theo từng dòng.** Gộp trùng trước — bỏ token có chữ số (size, mã DIN,
   part number) để mọi biến thể của một sản phẩm thu về một cặp. Thấy mình đang lặp qua từng dòng
   để gọi model thì dừng lại.
2. **Không để model bịa danh mục.** Mỗi prompt mang theo nguyên danh sách hợp lệ, và mọi câu trả lời
   được đối chiếu ngược lại danh sách đó.
3. **Không giao thứ mình chưa kiểm.** `build_final.py` tự mở lại output của chính nó và thoát khác 0
   nếu số dòng, dòng không đụng tới, category id, hay bộ ba id/tên/depth không khớp.
4. **Không đoán qua chỗ bất đồng.** Hai model không thống nhất thì dòng đó **giữ nguyên** giá trị
   đang có, trừ khi có bằng chứng thật.
5. **Không rule cứng theo ngành.** Mọi quy ước format đều đo từ chính file đang xử lý. `DIN931` →
   `DIN 931` nghe rất hợp lý, áp vào đẻ ra hàng nghìn lỗi giả.
6. **Không tự chế công thức khi bảng tra thiếu cột.** Bảng không có thì để trống, để người quyết.
7. **Không quote con số mình chưa đo.** `measure.py` sinh lại mọi con số từ artifact trên đĩa.

## 8. Cho người phát triển skill

### Kiểm tra trước khi push

Ba tầng, xếp theo chi phí:

```bash
claude plugin validate .                      # 0 token
python -m pytest skills/*/tests -q            # 0 token — chốt chặn logic
python tools/lint_skills.py                   # 0 token — link chết, cờ không tồn tại, doc lệch
python tools/eval_skills.py                   # token Gemini, KHÔNG phải token Claude
```

`lint_skills.py` bắt: link chết, lệnh trong tài liệu trỏ vào script không có, cờ tài liệu dùng mà
`argparse` không nhận, description quá 500 ký tự, SKILL.md quá 500 dòng, doc dài không có mục lục,
đường dẫn của bản cũ, script in ra stdout mà không đặt utf-8.

`eval_skills.py` đưa SKILL.md + một tình huống thật cho Gemini rồi hỏi *lệnh tiếp theo là gì*, chấm
bằng regex nên tái lập được. Mỗi skill 3 ca, đều là ca đã từng sai thật.

### Thêm skill mới

```
skills/<tên-skill>/
  SKILL.md          # bắt buộc: frontmatter name + description
  scripts/          # tuỳ chọn
  reference.md      # tuỳ chọn, tài liệu dài để SKILL.md gọn
  tests/            # tuỳ chọn nhưng nên có
```

Không cần sửa `plugin.json` — Claude Code tự quét `skills/`.

Quy tắc giữ skill chạy được ở mọi nơi:

- Trong SKILL.md, trỏ script bằng `${CLAUDE_SKILL_DIR}/scripts/...`, **không bao giờ hardcode đường
  dẫn**. Biến này đúng cho cả skill cá nhân, skill theo project, lẫn skill trong plugin.
- Script không được giả định repo nào bao quanh nó. Nhận đường dẫn qua tham số, hoặc qua biến môi
  trường có giá trị mặc định hợp lý.
- `name` trong frontmatter là tên lệnh. Đổi tên = phá lệnh cũ của người đang dùng.
- Bump `version` trong cả `plugin.json` lẫn `marketplace.json` khi phát hành.

### Bố cục repo

```
mecsu-skills/
  .env.example          # key 9router dùng chung cho mọi skill
  .claude-plugin/
    plugin.json         # manifest plugin
    marketplace.json    # catalog, để repo tự làm marketplace luôn
  skills/
    mecsu-category/
      SKILL.md
      reference.md         # chi tiết + mọi số đo
      scripts/audit.py     # một lệnh chạy cả dây chuyền
      scripts/*.py
      tests/*.py
    mecsu-filter/
      SKILL.md
      workflow.md          # từng bước + mọi số đo
      policy.md            # ngân sách token
      TODO.md              # việc còn nợ
      references/standards/*.md
      scripts/run.py       # một lệnh chạy cả dây chuyền
      scripts/*.py
      tests/*.py
  tools/                # lint + eval cho chính các skill
  README.md
```

Mỗi skill có `scripts/skill_env.py` riêng để nạp key — **cố ý trùng lặp**, để copy một thư mục skill
ra ngoài plugin nó vẫn chạy.
