# mecsu-skills

Skill Claude Code nội bộ Mecsu cho dữ liệu sản phẩm. · **[Xem bản đồ kho trên web →](https://mecsu-skills.pages.dev)**

```mermaid
flowchart LR
    F["📄 File Excel<br/>sản phẩm"] --> Q{Hỏi gì?}
    Q -->|"Danh mục gán<br/>đúng chưa?"| C["/mecsu-category"]
    Q -->|"Thông số<br/>đủ &amp; đúng chưa?"| T["/mecsu-filter"]
    Q -->|"Chỉ có mã,<br/>chưa có tên?"| N["/mecsu-naming"]
    C --> R1["📋 changelog.xlsx<br/><i>người duyệt</i>"]
    T --> R2["📋 cham_diem.xlsx<br/><i>người chấm</i>"]
    N --> R3["📋 ket_qua.xlsx<br/><i>người soát</i>"]

    style F fill:#e8f0fe,stroke:#4285f4
    style C fill:#fef7e0,stroke:#f9ab00
    style T fill:#fef7e0,stroke:#f9ab00
    style N fill:#fef7e0,stroke:#f9ab00
    style R1 fill:#e6f4ea,stroke:#34a853
    style R2 fill:#e6f4ea,stroke:#34a853
    style R3 fill:#e6f4ea,stroke:#34a853
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

🟢 **0 token** · 🔴 tốn tiền · gộp trùng trước khi gọi model, và mọi giá trị model trả về đều bị
đối chiếu lại với chính nguồn — không khớp thì thành `REVIEW`, không đi vào file giao như thật.

Đo trên 100 dòng thật, 2026-09-18 — mỗi số dưới đây sinh lại được bằng một lệnh trong `tools/`:

| Skill | Số đo | Sinh lại bằng |
|---|---|---|
| `/mecsu-category` | bắt **15/15** dòng gán sai, **0** báo động giả trên 87 dòng còn nguyên | `tools/cham_cate.py` |
| `/mecsu-filter` | điền đúng **41,8%** trong 134 cặp bị xoá trắng | `tools/cham_holdout.py` |
| `/mecsu-naming` | tên để lọt tiền tố nội bộ bị hạ `REVIEW`, không giao thẳng | [test canh luật này](skills/mecsu-naming/tests/test_naming_vong2d_tien_to.py) |

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

<!-- skills:run:start -->
```
/mecsu-category  d:/file.xlsx
/mecsu-filter    d:/file.xlsx
/mecsu-naming    d:/file.xlsx
```
<!-- skills:run:end -->

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

## Skill trong kho

<!-- skills:bang:start -->
| Skill | Trả lời câu hỏi | Ra file | Luật |
|---|---|---|---|
| `/mecsu-category` | Sản phẩm này có nằm đúng danh mục lá không? | `changelog.xlsx` | [SKILL.md](skills/mecsu-category/SKILL.md) |
| `/mecsu-filter` | Sản phẩm này đã đủ và đúng thông số chưa? | `cham_diem.xlsx` | [SKILL.md](skills/mecsu-filter/SKILL.md) |
| `/mecsu-naming` | Sản phẩm chỉ có mã này tên gì, thông số bao nhiêu? | `ket_qua.xlsx` | [SKILL.md](skills/mecsu-naming/SKILL.md) |
<!-- skills:bang:end -->

Bỏ file cần xử lý vào `jobs/inbox/`. Output mỗi lần chạy nằm trong `jobs/` và **không** lên GitHub.

## Đọc thêm

| | |
|---|---|
| 🤖 Bạn là AI agent vừa clone repo này? | [AGENTS.md](AGENTS.md) |
| 📘 Hướng dẫn chi tiết, bảng lỗi thường gặp | [docs/huong-dan-su-dung.md](docs/huong-dan-su-dung.md) |
| ⚙️ Luật của từng skill | cột **Luật** ở bảng trên |
