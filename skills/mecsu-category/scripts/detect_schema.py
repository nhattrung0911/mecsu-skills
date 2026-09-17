"""Work out which column plays which role in an unfamiliar workbook, and write schema.json.

Header names are matched literally first, because that is free and exact. The model is called only
for roles that survive unmatched - on a workbook whose headers are already known, this costs nothing
and makes no network call.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import openpyxl

from common import OPTIONAL_ROLES, REQUIRED_ROLES, ROLES, fold, job_root
import sys

if hasattr(sys.stdout, 'reconfigure'):      # console Windows mac dinh la cp1252
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = job_root()
DEFAULT_DIR = ROOT / "jobs" / "oncheck"

# Header spellings seen in the wild, per role. Matched on the folded (accent-free) form.
ALIASES = {
    "part_id": ["part id", "id", "product id", "sku id", "ma dong", "row id", "item id"],
    "part_number": ["part number", "part no", "ma hang", "ma san pham", "product code", "model"],
    "description": [
        "part description", "description", "product name", "ten san pham", "mo ta",
        "ten hang hoa", "product description", "item name", "name",
    ],
    "sku": ["part sku code", "sku", "sku code", "ma sku", "barcode"],
    "leaf_id": ["leaf category id", "category id", "cate id", "ma danh muc", "leaf id"],
    "leaf_name": [
        "leaf category name", "category", "category name", "danh muc", "cate", "cate leaf",
        "danh muc la", "leaf category", "leaf name",
    ],
    "leaf_depth": ["leaf depth", "depth", "cap do", "level"],
    "level1_id": ["level1 category id", "level 1 id", "root category id", "cate lv1 id"],
    "level1_name": [
        "level1 category name", "level 1 category", "level1", "root category", "cate lv1",
        "danh muc cap 1", "nganh hang", "level 1 name", "parent category",
        "category lv1", "category level1", "cap 1", "lv1",
    ],
}

ROLE_HELP = {
    "part_id": "unique identifier of the row/product",
    "part_number": "manufacturer part number",
    "description": "product name or description text - the thing being checked",
    "sku": "internal SKU or barcode",
    "leaf_id": "id of the assigned leaf category",
    "leaf_name": "name of the assigned leaf category - the thing being checked against",
    "leaf_depth": "depth of the leaf in the category tree",
    "level1_id": "id of the top-level category",
    "level1_name": "name of the top-level category - used to group products for review",
}

SYSTEM_PROMPT = """Bạn ánh xạ cột của một file Excel sản phẩm sang các vai trò cố định.

Bạn nhận: tên các cột (kèm chỉ số) và vài dòng dữ liệu mẫu.
Nhiệm vụ: mỗi vai trò còn thiếu, chọn CHỈ SỐ cột phù hợp nhất, hoặc null nếu file không có.

Nguyên tắc:
- Nhìn dữ liệu mẫu, đừng chỉ nhìn tên cột. Tên cột có thể mơ hồ hoặc bằng tiếng Việt.
- description là cột chứa TÊN/MÔ TẢ sản phẩm dài, không phải mã.
- leaf_name là danh mục CỤ THỂ NHẤT được gán cho sản phẩm.
- level1_name là danh mục CẤP CAO NHẤT, ít giá trị phân biệt hơn leaf_name, lặp lại nhiều.
- Nếu hai cột cùng trông giống một vai trò, chọn cột có dữ liệu đầy đủ hơn.
- Thà trả null còn hơn đoán sai. Vai trò không có thật thì để null.

Trả về DUY NHẤT một object JSON:
{"<role>": {"index": <int hoặc null>, "confidence": <0.0-1.0>, "why": "<ngắn gọn>"}}

Không thêm chữ nào ngoài JSON."""


def pick_sheet(workbook, requested: str | None) -> str:
    if requested:
        return requested
    if len(workbook.sheetnames) == 1:
        return workbook.sheetnames[0]
    # Otherwise the sheet with the most rows is the data; the rest are usually notes or lookups.
    return max(workbook.sheetnames, key=lambda name: workbook[name].max_row or 0)


def sample(path: Path, sheet: str, count: int) -> tuple[list[str], list[list]]:
    workbook = openpyxl.load_workbook(path, data_only=True, read_only=True)
    worksheet = workbook[sheet]
    headers: list[str] = []
    rows: list[list] = []
    for index, values in enumerate(worksheet.iter_rows(min_row=1, values_only=True)):
        if index == 0:
            headers = [str(v).strip() if v is not None else "" for v in values]
            continue
        rows.append([("" if v is None else str(v))[:70] for v in values[: len(headers)]])
        if len(rows) >= count:
            break
    workbook.close()
    return headers, rows


def match_by_name(headers: list[str]) -> dict[str, int]:
    folded = [fold(h) for h in headers]
    found: dict[str, int] = {}
    for role, aliases in ALIASES.items():
        for alias in aliases:
            target = fold(alias)
            if target in folded:
                index = folded.index(target)
                if index not in found.values():
                    found[role] = index
                    break
    return found


def ask_model(headers: list[str], rows: list[list], missing: list[str], model: str | None) -> dict:
    from ai_check import load_config, read_completion  # imported late: only needed on this path
    import requests

    config = load_config()
    model = model or config["models"][0]
    payload = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "columns": [{"index": i, "header": h} for i, h in enumerate(headers)],
                        "sample_rows": rows,
                        "roles_needed": {role: ROLE_HELP[role] for role in missing},
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }
    response = requests.post(
        f"{config['base_url']}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"},
        timeout=180,
    )
    response.raise_for_status()
    content, _ = read_completion(response)
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end < 0:
        raise SystemExit(f"Model did not return JSON:\n{content[:400]}")
    return json.loads(content[start : end + 1]), model


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--sheet", help="Defaults to the only sheet, else the one with most rows.")
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR / "schema.json")
    parser.add_argument("--model", help="Override the model used when names alone are not enough.")
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--no-model", action="store_true", help="Name matching only; fail if short.")
    args = parser.parse_args()

    workbook = openpyxl.load_workbook(args.input, data_only=True, read_only=True)
    sheet = pick_sheet(workbook, args.sheet)
    workbook.close()

    headers, rows = sample(args.input, sheet, args.samples)
    if not headers:
        raise SystemExit(f"{args.input.name} sheet {sheet!r} has no header row.")

    columns = match_by_name(headers)
    detected_by = "header names"
    notes: dict[str, str] = {role: "matched by header name" for role in columns}

    missing = [role for role in ROLES if role not in columns]
    unresolved_required = [role for role in REQUIRED_ROLES if role not in columns]

    if missing and not args.no_model:
        # Only pay for what names could not settle.
        answer, used = ask_model(headers, rows, missing, args.model)
        detected_by = f"header names + {used}"
        for role in missing:
            entry = answer.get(role) or {}
            index = entry.get("index")
            if isinstance(index, int) and 0 <= index < len(headers) and index not in columns.values():
                columns[role] = index
                notes[role] = f"model ({entry.get('confidence', '?')}): {entry.get('why', '')}"

    unresolved_required = [role for role in REQUIRED_ROLES if role not in columns]

    print(f"sheet: {sheet}   columns: {len(headers)}   sampled rows: {len(rows)}\n")
    print(f"{'role':<14}{'col':>4}  {'header':<30}how")
    for role in ROLES:
        index = columns.get(role)
        header = headers[index] if index is not None else "-"
        mark = "" if index is not None else ("  << REQUIRED, UNRESOLVED" if role in REQUIRED_ROLES else "")
        print(f"{role:<14}{index if index is not None else '-':>4}  {header[:29]:<30}{notes.get(role, '-')}{mark}")

    unmapped = [h for i, h in enumerate(headers) if i not in columns.values()]
    if unmapped:
        print(f"\ncarried through untouched: {', '.join(unmapped)}")

    if unresolved_required:
        raise SystemExit(
            f"\nCannot audit this workbook: required role(s) {unresolved_required} not found.\n"
            "Map them by hand in the schema file, or point --input at the right sheet."
        )

    schema = {
        "source": args.input.name,
        "sheet": sheet,
        "headers": headers,
        "columns": columns,
        "detected_by": detected_by,
        "notes": notes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nschema -> {args.output}")
    missing_optional = [r for r in OPTIONAL_ROLES if r not in columns]
    if missing_optional:
        print(f"absent optional roles: {', '.join(missing_optional)} (pipeline degrades gracefully)")


if __name__ == "__main__":
    main()
