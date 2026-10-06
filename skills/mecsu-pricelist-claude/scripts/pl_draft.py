"""items.json (pl_read) -> draft doc.json: one card per group chunk, prices for Sheet2.

Claude (or content agents) then edits titles / lines / images; layout and build stay automatic.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata

import pathlib as _pathlib, sys as _sys  # noqa: E401
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
from pl_common import save_doc
from pl_analyze import ext_columns, fold, live_rows, resolve_sort, sort_rows, split_rows, value_order


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "card"


def _price(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _image(v):
    if not v:
        return None
    if re.match(r"https?://", v, re.I):
        return {"path": None, "status": "missing", "url": v}
    return {"path": v, "status": "ok"}


def _merge_groups(groups):
    """Merge groups with same (name, spec labels) across sheets, first-appearance order."""
    merged = {}
    for g in groups:
        key = (g["name"], tuple(c["label"] for c in g["spec_columns"]))
        m = merged.get(key)
        if m is None:
            m = merged[key] = {"sheet": g["sheet"], "name": g["name"], "category": g.get("category"), "spec_columns": g["spec_columns"],
                               "rows": [], "lines": [], "legend": [], "note": None, "image": None,
                               "drawing": None}
        m["rows"].extend(g["rows"])
        for k in ("lines", "legend"):
            m[k].extend(x for x in g.get(k) or [] if x not in m[k])
        for k in ("note", "image", "drawing"):
            if m[k] is None and g.get(k):
                m[k] = g[k]
    return list(merged.values())


CONSTANT_MIN_ROWS = 3  # a spec identical on every row of a card (>= this many rows) reads better as a line


def _constant_specs_to_lines(card: dict) -> None:
    """Move a spec column whose value is identical on every row into a description line ("Đầu Vuông: 1/2 Inch")."""
    rows = card["rows"]
    if len(rows) < CONSTANT_MIN_ROWS:
        return
    keep = []
    for col in card["columns"]:
        vals = {str(r.get(col["key"], "")).strip() for r in rows} if col.get("role") == "spec" else set()
        label = col.get("label", "")
        head = label.split("\n")[0].strip()
        if len(vals) == 1 and "" not in vals and len(head) > 2 and len(card["lines"]) < 5:  # letter symbols stay
            unit = re.search(r"\(([^)]+)\)", label)
            val = vals.pop()
            line = f"{head}: {val}" + (f" {unit.group(1).title() if unit.group(1) == 'inch' else unit.group(1)}"
                                       if unit else "")
            if len(line) <= 28:
                card["lines"].append(line)
                continue
        keep.append(col)
    card["columns"] = keep


def _default_legend(g: dict, defaults: dict) -> list[str]:
    """Family dictionary legend (e.g. bearings d/D/B) for letter columns, in column order; data legend wins."""
    out = []
    for c in g["spec_columns"]:
        sym = re.split(r"[\s(]", c["label"].strip(), maxsplit=1)[0]
        if sym in defaults and defaults[sym] not in out:
            out.append(defaults[sym])
    return out


def draft(items: dict, brand: str, page_code: str, max_rows: int | None = None, brand_logo: str | None = None,
          plan: dict | None = None, brand_filter: str | None = None, warnings: list | None = None) -> dict:
    cards, prices, seen_ids, seen_codes = [], [], {}, set()
    no_brand = 0
    plan_by = {(p["sheet"], p["name"]): p for p in (plan or {}).get("groups", [])}
    for g in _merge_groups(items["groups"]):
        live = live_rows(g)  # pl_read already warned about the skipped ones
        if brand_filter:
            keep = []
            for r in live:
                if not r.get("brand"):
                    no_brand += 1
                    keep.append(r)
                elif fold(r["brand"]) == fold(brand_filter):
                    keep.append(r)
            live = keep
        pg = plan_by.get((g["sheet"], g["name"]))
        if pg:
            subs = split_rows(pg.get("split"), live, g["spec_columns"])
            labels, _ = resolve_sort(pg.get("sort") or [], ext_columns(pg.get("split"), g["spec_columns"]))
            orders = value_order(pg.get("split"))
            suffix_tpl, fam = pg.get("title_suffix") or "", pg.get("family")
            legend_defaults = pg.get("legend_defaults") or {}
        else:
            subs, labels, suffix_tpl, fam = [{"key": "", "label": None, "rows": live}], [], "", None
            orders = {}
            legend_defaults = {}
        for sg in subs:
            spec_cols = g["spec_columns"] + [c for c in sg.get("extra_columns", [])
                                              if all(c["key"] != x["key"] for x in g["spec_columns"])]
            srows = sort_rows(sg["rows"], labels, spec_cols, orders) if pg else sg["rows"]
            # drop spec columns that are empty for every row of this card
            spec_cols = [c for c in spec_cols if any(r["specs"].get(c["key"]) not in (None, "") for r in srows)]
            cols = [{"key": "code"}]
            cols += [{"key": c["key"], "label": c["label"], "role": "spec"} for c in spec_cols]
            cols += [{"key": "order"}, {"key": "price"}]
            rows = []
            for r in srows:
                rows.append({"code": r["code"], "order": r["order_code"],
                             **{c["key"]: r["specs"].get(c["key"]) for c in spec_cols}})
                if r["order_code"] not in seen_codes:
                    seen_codes.add(r["order_code"])
                    prices.append({"order_code": r["order_code"], "price": _price(r["price"])})
            if not rows:
                continue
            # a split that yields one subgroup adds no information -> no suffix (bearing series stays: "DÒNG 6200")
            informative = len(subs) > 1 or ((pg or {}).get("split") or {}).get("type") == "bearing_series"
            suffix = suffix_tpl.replace("{label}", sg["label"]) if sg["label"] and suffix_tpl and informative else ""
            title = sg.get("title") or (g["name"] or g["sheet"]).upper()
            title += suffix
            base = _slug(title if (suffix or sg.get("title")) else (g["name"] or g["sheet"]))
            n_chunks = max(1, -(-len(rows) // max_rows)) if max_rows else 1
            size = -(-len(rows) // n_chunks)  # balanced chunks
            for i in range(n_chunks):
                seen_ids[base] = seen_ids.get(base, 0) + 1
                card = {
                    "id": f"{base}-{seen_ids[base]}",
                    "group": g["name"],
                    "title": title,
                    "title_source": "data",
                    "lines": list(g["lines"]), "legend": list(g["legend"]) or _default_legend({"spec_columns": spec_cols}, legend_defaults),
                    "note": g["note"],
                    "image": _image(g["image"]),
                    "columns": cols, "rows": rows[i * size:(i + 1) * size],
                    "width": "auto", "split": "allow",
                }
                if suffix:
                    card["title_suffix_source"] = f"family:{fam}"
                if g.get("drawing"):
                    card["drawing"] = _image(g["drawing"])
                _constant_specs_to_lines(card)
                cards.append(card)
    if no_brand and warnings is not None:
        warnings.append(f"brand filter '{brand_filter}': {no_brand} rows have no brand and were kept")
    meta = {"brand": brand, "page_code": page_code}
    if brand_logo:
        meta["brand_logo"] = brand_logo
    return {"meta": meta, "prices": prices, "cards": cards, "free": []}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("items")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--code", required=True, help="3-letter page code, e.g. STA")
    ap.add_argument("--logo")
    ap.add_argument("--max-rows", type=int, default=None, help="pre-split long groups (default: no, layout splits)")
    ap.add_argument("--plan", help="plan.json from pl_analyze: split into cards per product series + sort rows")
    ap.add_argument("--brand-filter", help="keep only rows of this brand (case-insensitive); rows without brand are kept")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    with open(a.items, encoding="utf-8") as f:
        items = json.load(f)
    plan = None
    if a.plan:
        with open(a.plan, encoding="utf-8") as f:
            plan = json.load(f)
    warns: list[str] = []
    doc = draft(items, a.brand, a.code, a.max_rows, a.logo, plan, a.brand_filter, warns)
    save_doc(doc, a.out)
    print(json.dumps({"cards": len(doc["cards"]), "prices": len(doc["prices"]), "warnings": warns}, ensure_ascii=False))


if __name__ == "__main__":
    main()
