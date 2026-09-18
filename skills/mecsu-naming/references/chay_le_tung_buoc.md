# Chạy lẻ từng bước

Đường chính là `run.py --den-vong N`. Chín lệnh dưới đây để soi một bước cụ thể
khi cần tìm lỗi.

```bash
python ${CLAUDE_SKILL_DIR}/scripts/extract_codes.py --input <file.xlsx> --out codes.json
python ${CLAUDE_SKILL_DIR}/scripts/learn_convention.py --codes codes.json --out convention.json
python ${CLAUDE_SKILL_DIR}/scripts/apply_convention.py --codes codes.json --convention convention.json --out names.json
python ${CLAUDE_SKILL_DIR}/scripts/build_queries.py --codes codes.json --out queries.json
python ${CLAUDE_SKILL_DIR}/scripts/search_sources.py --codes codes.json --queries queries.json --out search.json
python ${CLAUDE_SKILL_DIR}/scripts/fetch_sources.py --sources search.json --out-dir web --limit 20
python ${CLAUDE_SKILL_DIR}/scripts/extract_from_web.py --sources-dir web --search search.json --convention convention.json --out web_facts.json
python ${CLAUDE_SKILL_DIR}/scripts/round3.py --job jobs/naming-01 --out round3.json
python ${CLAUDE_SKILL_DIR}/scripts/build_sheet.py --input <file.xlsx> --job jobs/naming-01 --out ket_qua.xlsx
```
