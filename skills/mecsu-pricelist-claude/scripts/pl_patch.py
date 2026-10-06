"""Apply source-backed corrections to items.json (output of pl_read) without touching the user's Excel.

patches.json = [{"op": ..., ..., "source": "why / where verified"}]
  set_spec      {"code", "label", "value"}           set a spec value of one row (label = first line of column label)
  rename_label  {"group", "from", "to"}              rename a spec column in a group (unit suffix kept)
  set_brand     {"group" | "code", "brand"}          fill brand for a group or a row
Every op needs "source". A log is written next to the output (patch_log.md) for the user to review.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import pathlib as _pathlib, sys as _sys  # noqa: E401
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
from pl_read import slug  # noqa: E402


def _head(label: str) -> str:
    return label.split("\n")[0].strip()


_ALIAS = {"lb": "lbs", "lbs": "lbs", "in": "inch", "inch": "inch", '"': "inch", "mm": "mm", "cm": "cm",
          "kg": "kg", "g": "g", "n.m": "N.m", "nm": "N.m", "mm2": "mm²", "mm²": "mm²", "v": "V", "w": "W"}
_VAL = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*([A-Za-z\"².]*)\s*$")


def _canon(u: str) -> str:
    return _ALIAS.get(u.strip().strip(".").lower(), u.strip().lower())


def _unit_value(label: str, value):
    """Column label has a unit '(lbs)': '20 lb' -> 20 ; '20 kg' -> ValueError; otherwise value unchanged."""
    m = re.search(r"\(([^)]+)\)\s*$", label.split("\n", 1)[1]) if "\n" in label else None
    if not m or not isinstance(value, str):
        return value
    col_unit = _canon(m.group(1))
    v = _VAL.match(value)
    if not v:
        return value
    num, unit = v.group(1).replace(",", "."), v.group(2)
    if unit and _canon(unit) != col_unit:
        raise ValueError(f"unit mismatch: column {label.splitlines()[0]!r} is in {m.group(1)!r} but value is "
                         f"{value!r} - convert it yourself from the source or drop the patch")
    f = float(num)
    return int(f) if f.is_integer() else f


def _find_col(group: dict, name: str) -> dict | None:
    return next((c for c in group["spec_columns"] if _head(c["label"]).lower() == name.strip().lower()), None)


def apply_patches(items: dict, patches: list[dict]) -> tuple[dict, list[str]]:
    log = []
    for p in patches:
        if not p.get("source"):
            raise ValueError(f"patch without source: {p}")
        op, done = p["op"], 0
        for g in items["groups"]:
            if op == "rename_label" and g["name"] == p["group"]:
                col = _find_col(g, p["from"])
                if col:
                    rest = col["label"][len(_head(col["label"])):]
                    col["label"] = p["to"] + rest
                    done += 1
            elif op == "set_brand" and (g["name"] == p.get("group") or p.get("code")):
                for r in g["rows"]:
                    if p.get("code") in (None, r["code"]):
                        r["brand"] = p["brand"]
                        done += 1
                if p.get("group") == g["name"]:
                    g["brand"] = p["brand"]
            elif op == "set_spec":
                for r in g["rows"]:
                    if r["code"] == p["code"]:
                        col = _find_col(g, p["label"])
                        if col is None:  # column dropped as empty for the group -> add it back
                            col = {"key": slug(p["label"]), "label": p["label"]}
                            g["spec_columns"].append(col)
                        r["specs"][col["key"]] = _unit_value(col["label"], p["value"])
                        done += 1
        if not done:
            raise ValueError(f"patch matched nothing: {p}")
        log.append(f"- {op} {json.dumps({k: v for k, v in p.items() if k not in ('op', 'source')}, ensure_ascii=False)}"
                   f" — nguồn: {p['source']} ({done} chỗ)")
    return items, log


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("items")
    ap.add_argument("patches")
    ap.add_argument("-o", "--out", help="default: overwrite items")
    a = ap.parse_args()
    items = json.load(open(a.items, encoding="utf-8"))
    try:
        items, log = apply_patches(items, json.load(open(a.patches, encoding="utf-8")))
    except ValueError as e:
        print(f"PATCH REFUSED: {e}")
        sys.exit(2)
    out = a.out or a.items
    json.dump(items, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    _pathlib.Path(out).with_name("patch_log.md").write_text(
        "# Sửa data (không đổi file Excel gốc)\n\n" + "\n".join(log) + "\n", encoding="utf-8")
    print(json.dumps({"applied": len(log)}))


if __name__ == "__main__":
    main()
