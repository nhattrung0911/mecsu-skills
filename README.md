# mecsu-skills

Skill Claude Code nội bộ Mecsu cho dữ liệu sản phẩm.

```mermaid
flowchart LR
    F["📄 File Excel<br/>sản phẩm"] --> Q{Hỏi gì?}
    Q -->|"Danh mục gán<br/>đúng chưa?"| C["/mecsu-category"]
    Q -->|"Thông số<br/>đủ &amp; đúng chưa?"| T["/mecsu-filter"]
    C --> R1["📋 changelog.xlsx<br/><i>người duyệt</i>"]
    T --> R2["📋 cham_diem.xlsx<br/><i>người chấm</i>"]

    style F fill:#e8f0fe,stroke:#4285f4
    style C fill:#fef7e0,stroke:#f9ab00
    style T fill:#fef7e0,stroke:#f9ab00
    style R1 fill:#e6f4ea,stroke:#34a853
    style R2 fill:#e6f4ea,stroke:#34a853
```

## Dây chuyền — LLM là tầng cuối

```mermaid
flowchart LR
    A["1️⃣ Dò cột<br/>+ lọc chữ"] --> B["2️⃣ Tra chính<br/>file đang xử lý"]
    B --> C["3️⃣ Hỏi model"]
    C --> D["4️⃣ Đối chiếu<br/>ngược"]
    D --> E["5️⃣ Dựng file<br/>+ tự kiểm tra"]
    E --> F["👤 Người duyệt"]

    style A fill:#e6f4ea,stroke:#34a853
    style B fill:#e6f4ea,stroke:#34a853
    style C fill:#fce8e6,stroke:#ea4335
    style D fill:#e6f4ea,stroke:#34a853
    style E fill:#e6f4ea,stroke:#34a853
    style F fill:#e8f0fe,stroke:#4285f4
```

🟢 **0 token** · 🔴 tốn tiền · rule lọc sạch **63.7%** dòng, phần còn lại gộp trùng **9×** trước khi gọi model

## Cài

```bash
pip install openpyxl requests python-dotenv        # Python 3.11+
```

```
/plugin marketplace add nhattrung0911/mecsu-skills
/plugin install mecsu-skills@mecsu-skills
```

```bash
cp .env.example .env      # điền MECSU_BASE_URL + MECSU_API_KEY, một lần cho mọi skill
```

## Chạy

```
/mecsu-category  d:/file.xlsx
/mecsu-filter    d:/file.xlsx
```

```mermaid
flowchart LR
    R["Chạy"] --> S["⏸ Dừng sau<br/>50 câu hiệu chuẩn"]
    S --> K{"Lô mẫu<br/>hợp lý?"}
    K -->|Có| Y["Chạy lại kèm --yes"]
    K -->|Không| N["Sửa cột / model<br/>rồi chạy lại"]

    style S fill:#fef7e0,stroke:#f9ab00
    style Y fill:#e6f4ea,stroke:#34a853
    style N fill:#fce8e6,stroke:#ea4335
```

> ⚠️ Thoát khác 0 = **không giao**. Không phải "chạy lại kèm cờ khác cho qua".

## Đọc thêm

| | |
|---|---|
| 📘 Hướng dẫn chi tiết, bảng lỗi | [docs/huong-dan-su-dung.md](docs/huong-dan-su-dung.md) |
| ⚙️ Luật của `/mecsu-category` | [SKILL.md](skills/mecsu-category/SKILL.md) · [reference.md](skills/mecsu-category/reference.md) |
| ⚙️ Luật của `/mecsu-filter` | [SKILL.md](skills/mecsu-filter/SKILL.md) · [workflow.md](skills/mecsu-filter/workflow.md) |
| 🧪 Kiểm tra trước khi push | `claude plugin validate .` · `pytest -q` · `python tools/lint_skills.py` |
