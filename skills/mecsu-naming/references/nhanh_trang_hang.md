# Nhánh trang hãng — có sẵn, chưa nối vào `run.py`


Dùng cho file mà **mã suy thẳng ra URL trang hãng** (đo 2026-09-11: SATA 62,1% và Anex 3,1% của
một file 5.730 mã). Rẻ và chính xác hơn tìm kiếm, nhưng chỉ áp được khi hãng có mẫu URL.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/vendor_url.py --codes codes.json --out sources.json --check 12
python ${CLAUDE_SKILL_DIR}/scripts/fetch_sources.py --sources sources.json --out-dir sources --luu html
python ${CLAUDE_SKILL_DIR}/scripts/parse_vendor.py --sources-dir sources --codes codes.json --out facts.json
python ${CLAUDE_SKILL_DIR}/scripts/ai_extract.py --facts facts.json --out ai.json
```

`--check` thử thật bằng HTTP xem mẫu URL còn đúng không — nó là **giả định về một trang web bên
ngoài**, gãy lúc nào không ai báo. `--luu html` vì bước này cần cấu trúc bảng, không chỉ chữ.

`skill_env.py` là lớp dùng chung: đọc `.env` ở gốc plugin và gọi model. Không script nào giữ key
riêng. Nó parse **SSE** vì endpoint luôn stream kể cả khi không xin — `json.load()` chết ngay.
