"""Apply worker edit files to doc.json (merge step of team work).

    python pl_docedit.py doc.json edits1.json [edits2.json ...] [--log edit_log.md]

edit file = [{"card": id, "set": {"lines": [...], "legend": [...], "note": "...", "width": 26,
              "data_row_height": 1, "desc_rows": 3}, "source": "why / where"}]
Refused (exit 2, nothing written): unknown card, field outside the allow-list, title change when
title_source == "data", two edits touching the same card+field.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pl_common import load_doc, save_doc  # noqa: E402

ALLOWED = {"lines", "legend", "note", "width", "data_row_height", "desc_rows", "title"}


def plan_edits(doc: dict, files: list[str]):
    """Return ([(file, card, field, value, source)], errors)."""
    cards = {c["id"]: c for c in doc["cards"]}
    errors, ops, seen = [], [], {}
    for f in files:
        try:
            edits = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{f}: unreadable ({e})")
            continue
        for e in edits:
            cid = e.get("card")
            if cid not in cards:
                errors.append(f"{f}: unknown card {cid!r}")
                continue
            for field, val in (e.get("set") or {}).items():
                if field not in ALLOWED:
                    errors.append(f"{f}: {cid}.{field} not allowed (allowed: {', '.join(sorted(ALLOWED))})")
                    continue
                if field == "title" and cards[cid].get("title_source") == "data":
                    errors.append(f"{f}: {cid}.title comes from user data and must not change")
                    continue
                key = (cid, field)
                if key in seen:
                    errors.append(f"CONFLICT {cid}.{field}: {seen[key]} vs {Path(f).name}")
                    continue
                seen[key] = Path(f).name
                ops.append((Path(f).name, cid, field, val, e.get("source", "")))
    return ops, errors


def apply_edits(doc_path, files: list[str], log_path=None) -> tuple[int, list[str]]:
    doc = load_doc(doc_path)
    ops, errors = plan_edits(doc, files)
    if errors:
        return 0, errors
    cards = {c["id"]: c for c in doc["cards"]}
    for _, cid, field, val, _ in ops:
        cards[cid][field] = val
    try:
        save_doc(doc, doc_path)  # schema-validates before writing
    except Exception as e:
        return 0, [f"schema: {str(e).splitlines()[0]}"]
    log = Path(log_path) if log_path else Path(doc_path).with_name("edit_log.md")
    fresh = not log.exists()
    with log.open("a", encoding="utf-8") as fh:
        if fresh:
            fh.write("# edit log\n")
        for fn, cid, field, val, src in ops:
            fh.write(f"- {fn}: {cid}.{field} = {json.dumps(val, ensure_ascii=False)} (source: {src or 'none'})\n")
    return len(ops), []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("doc")
    ap.add_argument("edits", nargs="+")
    ap.add_argument("--log")
    a = ap.parse_args(argv)
    n, errors = apply_edits(a.doc, a.edits, a.log)
    if errors:
        print("REFUSED (doc unchanged):")
        for e in errors:
            print("  - " + e)
        return 2
    print(f"applied {n} edit(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
