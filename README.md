# mecsu-skills

Skill Claude Code nội bộ Mecsu cho dữ liệu sản phẩm. Cài một lần, gọi bằng `/...` ở mọi phiên.

| Skill | Trả lời | Đầu vào |
|---|---|---|
| `/mecsu-category` | Sản phẩm có nằm **đúng danh mục lá** không? | Excel có cột mô tả + danh mục đã gán |
| `/mecsu-filter` | Sản phẩm đã **đủ và đúng thông số** chưa? | Excel có cột filter dạng `Key: Value` |

## Cài

```bash
pip install openpyxl requests python-dotenv      # cần Python 3.11+
```

```
/plugin marketplace add nhattrung0911/mecsu-skills
/plugin install mecsu-skills@mecsu-skills
```

Điền key **một lần** ở gốc plugin — mọi skill đọc chung:

```bash
cp .env.example .env      # rồi điền MECSU_BASE_URL + MECSU_API_KEY
```

`.env` nằm trong `.gitignore`. **Không commit.**

## Chạy

```
/mecsu-category d:/duong/dan/file.xlsx
/mecsu-filter   d:/duong/dan/file.xlsx
```

Mỗi lệnh chạy cả dây chuyền và **dừng lại sau lô hiệu chuẩn 50 câu** — đọc lô đó rồi mới chạy lại
kèm `--yes`. Chưa có key vẫn chạy được các tầng đầu vì chúng không gọi model, **0 token**.

Kết quả cần người duyệt: `changelog.xlsx` (category) và `review/cham_diem.xlsx` (filter). Thoát
khác 0 nghĩa là **không giao**, không phải "chạy lại kèm cờ khác".

## Tài liệu

| Cần gì | Đọc |
|---|---|
| Hướng dẫn dùng chi tiết, từng bước, bảng lỗi thường gặp | [docs/huong-dan-su-dung.md](docs/huong-dan-su-dung.md) |
| Luật và cách vận hành `/mecsu-category` | [skills/mecsu-category/SKILL.md](skills/mecsu-category/SKILL.md) · [reference.md](skills/mecsu-category/reference.md) |
| Luật và cách vận hành `/mecsu-filter` | [skills/mecsu-filter/SKILL.md](skills/mecsu-filter/SKILL.md) · [workflow.md](skills/mecsu-filter/workflow.md) · [policy.md](skills/mecsu-filter/policy.md) |

## Phát triển

```bash
claude plugin validate .                # 0 token
python -m pytest skills/*/tests -q      # 0 token
python tools/lint_skills.py             # 0 token
python tools/eval_skills.py             # token Gemini, không phải token Claude
```

Thêm skill mới: tạo `skills/<tên>/SKILL.md`, Claude Code tự quét. Trong SKILL.md trỏ script bằng
`${CLAUDE_SKILL_DIR}/scripts/...`, **không hardcode đường dẫn**. `name` trong frontmatter là tên
lệnh — đổi là phá lệnh của người đang dùng. Chi tiết ở
[docs/huong-dan-su-dung.md](docs/huong-dan-su-dung.md#8-cho-người-phát-triển-skill).
