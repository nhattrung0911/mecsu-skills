# AGENTS.md

Hướng dẫn cho agent (Claude Code, Codex, Gemini CLI…) vừa clone repo này về.

Đây là **plugin Claude Code chứa skill soát dữ liệu sản phẩm**. Bạn không cần đọc code để dùng —
mỗi thư mục trong `skills/` là một lệnh, `SKILL.md` bên trong nó là hướng dẫn đầy đủ. Bản cho người
đọc: [README](README.md) · [hướng dẫn chi tiết](docs/huong-dan-su-dung.md).

## Trước khi chạy bất cứ thứ gì

```bash
python --version                                    # cần 3.11 trở lên
pip install openpyxl requests python-dotenv
cp .env.example .env                                # rồi điền, một lần cho mọi skill
```

`.env` cần `MECSU_BASE_URL` (endpoint tương thích OpenAI) và `MECSU_API_KEY`. **Không tự đoán
endpoint hay tên model** — thiếu thì dừng và hỏi người dùng. Mọi skill đọc chung file này; không
skill nào giữ key riêng.

## Lệnh

<!-- skills:bang:start -->
| Lệnh | Trả lời câu hỏi | Cần cột gì trong file |
|---|---|---|
| `/mecsu-category` | Sản phẩm này có nằm đúng danh mục lá không? | mô tả + danh mục đã gán |
| `/mecsu-filter` | Sản phẩm này đã đủ và đúng thông số chưa? | filter dạng `Key: Value` |
| `/mecsu-naming` | Sản phẩm chỉ có mã này tên gì, thông số bao nhiêu? | cột mã hãng (tên và thông số để trống cũng được) |
| `/mecsu-pricelist-claude` | Có data giá rồi, cần bảng giá gửi đối tác? | cột mã hãng, order id, giá Varin (thông số, mô tả, ảnh tuỳ chọn) |
<!-- skills:bang:end -->

<!-- skills:run:start -->
```
/mecsu-category          d:/duong-dan/file.xlsx
/mecsu-filter            d:/duong-dan/file.xlsx
/mecsu-naming            d:/duong-dan/file.xlsx
/mecsu-pricelist-claude  d:/duong-dan/file.xlsx
```
<!-- skills:run:end -->

Trùng tên với plugin khác thì gọi đầy đủ: `/mecsu-skills:mecsu-category`.

## Cách chạy đúng

Skill **cố tình dừng sau lô hiệu chuẩn đầu tiên**. Đó không phải lỗi. Đọc lô mẫu, thấy hợp lý mới
chạy lại kèm `--yes`. Thấy sai thì sửa cột hoặc model rồi chạy lại — đừng `--yes` cho qua.

Bỏ file cần xử lý vào `jobs/inbox/`. Output mỗi lần chạy nằm trong `jobs/`.

## Luật cứng khi bạn vận hành hoặc sửa skill ở đây

Mỗi luật dưới đây sinh ra từ một lỗi đã xảy ra thật, không phải sở thích.

1. **Dò cột từ header.** Không đoán ra được thì **dừng và hỏi**, in header thật kèm tên cờ
   (`--name-col`, `--filter-col`, `--cat-col`, đánh số từ 0). Không bao giờ hardcode chỉ số cột.
2. **Tầng 0 token chạy trước.** rule → tra chính file đang xử lý → *mới* hỏi model → đối chiếu
   ngược. Hỏi model thứ mà file đã tự trả lời được là trả tiền cho câu trả lời có sẵn.
3. **Không gọi model theo từng dòng.** Gộp theo `(nhóm, thuộc tính, bối cảnh tối thiểu)`. Thấy mình
   đang lặp qua từng dòng để gọi model thì dừng lại.
4. **Cache khoá theo nội dung**, không theo số thứ tự. Số thứ tự bị đánh lại khi input đổi, khiến
   câu trả lời cũ gán nhầm sang sản phẩm khác. Đã xảy ra hai lần.
5. **Hỏng thì exit ≠ 0.** Batch chết mà exit 0 là chế độ hỏng tệ nhất: báo xong trong khi chưa kiểm
   gì. Bước sau phải kiểm **nội dung** file, không kiểm sự tồn tại của file.
6. **Không tự sửa dữ liệu nguồn.** Đề xuất ghi sang cột mới hoặc file mới. Dữ liệu gốc là thứ người
   duyệt cần đối chiếu.
7. **Hai model bất đồng thì giữ nguyên giá trị cũ**, trừ khi có bằng chứng thật.
8. **Không quote con số chưa đo.** Mọi số bạn viết vào báo cáo phải sinh lại được từ file trên đĩa.

Kết quả cuối cùng luôn cần **người duyệt**. Skill đề xuất, không tự quyết.

## Chỗ không được đụng

| Chỗ | Vì sao |
|---|---|
| `jobs/` | file thật của người dùng. Không commit, không push, không đưa ra ngoài. |
| `.env` | chứa key. Đã bị `.gitignore` chặn — đừng gỡ. |
| `site/index.html`, `README.md`, `AGENTS.md` ở giữa các mốc `<!-- skills:… -->` | do `tools/sync_site.py` sinh từ `skills/`. Sửa tay sẽ bị ghi đè, và CI báo đỏ. |
| `name` trong frontmatter `SKILL.md` | đó là tên lệnh. Đổi là phá lệnh của người đang dùng. |

CSP trong `site/_headers` cấm inline script/style và tài nguyên ngoài. Thêm CDN vào web sẽ bị chặn
im lặng trên production, không báo lỗi lúc dev.

## Nếu bạn có sửa code trong repo

Chạy đủ bốn lệnh này trước khi báo là xong. Cả bốn đều 0 token:

```bash
claude plugin validate .
python -m pytest -q
python tools/lint_skills.py
python tools/sync_site.py --check
```

Thêm skill mới thì còn một cổng nữa, `python tools/eval_skills.py --skill <tên>` — nó tiêu token
Gemini, không phải token Claude, và chỉ chạy được khi skill đã có ca trong `CASES`.

Xanh nghĩa là *thứ có test thì đúng*, không phải *mọi thứ đều đúng*. Thấy một lỗi lọt lưới thì việc
đầu tiên là viết ca test cho loại lỗi đó, rồi mới vá.

Tên file test phải **duy nhất toàn repo** — pytest gom test theo tên file, không theo đường dẫn.

## Nhánh và Pull Request

| Nhánh | Dùng để |
|---|---|
| `main` | bản phát hành — người dùng cài plugin lấy từ đây. **Được bảo vệ**: chỉ vào qua Pull Request, chủ repo duyệt. |
| `dev` | team sửa ở đây (hoặc nhánh con tách từ `dev`, ví dụ `dev-<tên>-<việc>`). |

1. `git switch dev && git pull` rồi sửa; nhánh con thì `git switch -c dev-<tên>-<việc>`.
2. Chạy đủ cổng ở trên (pytest, lint, `sync_site.py --check`) trước khi push.
3. Push nhánh, mở Pull Request vào `main` (`gh pr create --base main`), ghi rõ sửa gì và vì sao.
4. Đổi hành vi skill thì nâng `version` trong `.claude-plugin/plugin.json` và `marketplace.json` —
   không nâng thì `claude plugin update` không kéo bản mới về máy người dùng.

Không push thẳng `main`. Không commit `.env`, file trong `jobs/`, hay bản nháp trong `lab/`.

## Khi bí

Đọc `skills/<tên-skill>/SKILL.md` — nó là nguồn sự thật cho từng lệnh. Vẫn không rõ thì hỏi người dùng, đừng đoán rồi chạy tiếp. Tài liệu đi kèm khác nhau theo skill, xem
thẳng thư mục của nó: `mecsu-filter` có `workflow.md` + `policy.md`, `mecsu-category` có
`reference.md`, `mecsu-naming` có `references/naming_convention.md`.
