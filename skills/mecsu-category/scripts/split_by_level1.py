"""Split On_web_category.xlsx into one workbook per level1 category."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from common import HEADERS, SHEET, job_root, read_rows, safe_name, write_rows
import sys

if hasattr(sys.stdout, "reconfigure"):      # product names are Vietnamese; the Windows console is cp1252
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = job_root()
DEFAULT_INPUT = ROOT / "jobs" / "inbox" / "On_web_category.xlsx"
DEFAULT_OUTPUT = ROOT / "jobs" / "oncheck" / "split"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sheet", default=SHEET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = read_rows(args.input, args.sheet)
    groups: dict[str, list] = collections.defaultdict(list)
    for row in rows:
        groups[str(row.level1_name or "(trong)")].append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for level1, members in sorted(groups.items(), key=lambda item: -len(item[1])):
        name = f"{safe_name(level1)}.xlsx"
        write_rows(args.output_dir / name, [m.as_tuple() for m in members], HEADERS, sheet="data")
        index.append({"level1_category_name": level1, "rows": len(members), "file": name})
        print(f"{len(members):>6}  {name}")

    manifest = args.output_dir / "index.json"
    manifest.write_text(
        json.dumps({"source": args.input.name, "total_rows": len(rows), "groups": index}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n{len(rows)} rows -> {len(index)} files in {args.output_dir}")


if __name__ == "__main__":
    main()
