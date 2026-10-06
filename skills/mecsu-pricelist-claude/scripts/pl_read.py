"""Read a data.xlsx input into grouped items (items.json)."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pl_common import norm_order_code  # noqa: E402

COLUMNS = json.loads((Path(__file__).resolve().parent.parent / "config" / "columns.json").read_text(encoding="utf-8"))
REQUIRED = ("code", "order", "price")
UNIT_RE = re.compile(r"^(\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?)\s*(inch|lbs?|kg|mm²|mm2|mm|cm|n\.?m|g|v|w)$", re.I)
UNIT_NORM = {"lb": "lbs", "lbs": "lbs", "inch": "inch", "nm": "N.m", "n.m": "N.m", "v": "V", "w": "W", "mm2": "mm²"}
UNIT_SYN = {"inch": r'inch|in(?!\w)|"|”', "lbs": r"lbs?", "N.m": r"n\.?m", "mm²": r"mm²|mm2"}


def _fold(h: str) -> str:
    h = unicodedata.normalize("NFD", h.replace("đ", "d").replace("Đ", "D"))
    h = "".join(c for c in h if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s_-]+", " ", h).strip().lower()


def _opt_kind(h: str):
    """Optional column header -> (group, order) or None."""
    f = _fold(h)
    m = re.fullmatch(r"(?:dong )?mo ta(?: ([1-5]))?", f)
    if m:
        return "lines", int(m.group(1) or 0)
    m = re.fullmatch(r"chu giai(?: ([1-5]))?", f)
    if m:
        return "legend", int(m.group(1) or 0)
    if f == "ghi chu":
        return "note", 0
    if f in ("anh", "hinh anh", "image"):
        return "image", 0
    if f in ("ban ve", "drawing"):
        return "drawing", 0
    return None


def _s(v):
    return v.strip() if isinstance(v, str) else v


def slug(label: str) -> str:
    return re.sub(r"[^\w]+", "_", label.strip()).strip("_")


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _role_index(header):
    """role -> first matching column index (header aliases from config/columns.json)."""
    folded = [_fold(h) for h in header]
    idx = {}
    for role, aliases in COLUMNS.items():
        for a in aliases:
            if a in folded:
                idx[role] = folded.index(a)
                break
    return idx


def _is_empty(v):
    return v is None or v == ""


def _title(label: str) -> str:
    if "\n" in label:
        return label
    return " ".join(w[0].upper() + w[1:] if len(w) > 1 and w[0].isalpha() else w for w in label.split(" "))


def _unit_of(label: str):
    return label.split("\n")[-1].strip("() ") if "\n" in label else None


def _norm_unit(u: str) -> str:
    return UNIT_NORM.get(u.lower(), u.lower())


def _unit_re(u: str) -> str:
    return UNIT_SYN.get(u, re.escape(u)).replace("|in|", r"|in(?![a-z])|")


def _lift_units(g):
    """Per spec column: '<n> <unit>' everywhere with one unit -> label '<L>\\n(<unit>)', numeric values."""
    g["col_units"] = {}
    for c in g["spec_columns"]:
        vals = [r["specs"].get(c["key"]) for r in g["rows"]]
        vals = [v for v in vals if not _is_empty(v)]
        ms = [UNIT_RE.match(v.strip()) if isinstance(v, str) else None for v in vals]
        if vals and all(ms) and len({_norm_unit(m.group(2)) for m in ms}) == 1 and "\n" not in c["label"]:
            unit = _norm_unit(ms[0].group(2))
            for r in g["rows"]:
                v = r["specs"].get(c["key"])
                if isinstance(v, str) and v.strip():
                    n = UNIT_RE.match(v.strip()).group(1)
                    if re.fullmatch(r"\d+(?:[.,]\d+)?", n):
                        f = float(n.replace(",", "."))
                        r["specs"][c["key"]] = int(f) if f.is_integer() else f
                    else:
                        r["specs"][c["key"]] = n
            c["label"] = f"{_title(c['label'])}\n({unit})"
            g["col_units"][c["key"]] = unit
        else:
            c["label"] = _title(c["label"])
            u = _unit_of(c["label"])
            if u:
                g["col_units"][c["key"]] = _norm_unit(u)


def _clean_desc(desc, code, brand, raw):
    """desc minus code, brand, and this row's spec values (with unit/format variants)."""
    if not desc:
        return None
    t = desc
    pats = [re.escape(code)]
    if brand:
        pats += [r"(?<!\w)" + re.escape(w) + r"(?!\w)" for w in brand.split()]
    nums = []
    for label, v in raw:
        if _is_empty(v):
            continue
        if isinstance(v, str):
            m = UNIT_RE.match(v.strip())
            if m:
                n = m.group(1).replace(",", ".")
                nums.append((n, _norm_unit(m.group(2))))
            # pure-text values are never stripped from the description
        else:
            u = _unit_of(label)
            if u:
                nums.append((f"{v:g}", _norm_unit(u)))
    for n, u in nums:
        num = re.escape(n).replace(r"\ ", r"\s+")
        pats.append(r"(?:(?:d[aà]i|dai)\s+)?Ø?(?<![\w.])" + num + r"\s*(?:" + _unit_re(u) + r")(?![a-z\d])")
    for (n1, u1), (n2, u2) in ((a, b) for a in nums for b in nums if a is not b):
        pats.append(r"Ø?\s*" + re.escape(n1) + r"\s*[x×*]\s*" + re.escape(n2) + r"(?:\s*(?:" + _unit_re(u2) + r"))?")
    pats += [r"Ø?(?<![\w.])\d+(?:[.,]\d+)?\s*[x×*]\s*\d+(?:[.,]\d+)?\s*mm(?!\w)",
             r"(?:(?:d[aà]i|dai)\s*)?Ø?(?<![\w.])\d+(?:[.,/]\d+)?\s*(?:lbs?|inch|in|mm|cm|kg|g)(?!\w)",
             r"(?<![\w.])\d+(?:[.,/]\d+)?\s*[\"”]"]
    for p in pats:
        t = re.sub(p, " ", t, flags=re.I)
    t = re.sub(r"\s+", " ", t).strip(" ,;-")
    return t or None


_DESC_TOKEN = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(inch|lbs?|kg|mm|cm|g)(?![\w])", re.I)


def _quality(g, where, warnings):
    units = g["col_units"]
    for r in g["rows"]:
        desc = r.get("desc")
        if not desc:
            continue
        covered = set()
        for k, v in r["specs"].items():
            if k in units and isinstance(v, (int, float)):
                covered.add((float(v), units[k]))
        for m in _DESC_TOKEN.finditer(desc):
            n, u = float(m.group(1)), _norm_unit(m.group(2))
            if (n, u) in covered:
                continue
            empty = [c["label"].split("\n")[0] for c in g["spec_columns"]
                     if units.get(c["key"]) == u and _is_empty(r["specs"].get(c["key"]))]
            if empty:
                warnings.append(f"{where} {r['code']}: spec missing but description says {m.group(1)} {u} "
                                f"({', '.join(empty)} empty)")
    same = {}
    for r in g["rows"]:
        if r.get("desc_clean"):
            same.setdefault((r["desc_clean"], json.dumps(r["specs"], sort_keys=True, ensure_ascii=False)), []).append(r["code"])
    for (d, _), codes in same.items():
        if len(codes) > 1:
            warnings.append(f"{where}: identical description and specs, cannot tell apart: {', '.join(codes)} ({d})")


def read_items(paths) -> dict:
    if isinstance(paths, (str, Path)):
        paths = [paths]
    groups, warnings, seen = [], [], {}
    for path in paths:
        fname = Path(path).name
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        for ws in wb.worksheets:
            if _fold(ws.title) in ("huong dan", "readme", "guide"):  # instruction sheet of the template
                continue
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            header = [h if isinstance(h, str) else ("" if h is None else str(h)) for h in rows[0]]
            idx = _role_index(header)
            missing = [k for k in REQUIRED if k not in idx]
            if missing:
                warnings.append(f"{ws.title}: missing column '{COLUMNS[missing[0]][0]}', sheet skipped")
                continue
            fixed_idx = set(idx.values())
            opt = {}  # col index -> (group, order)
            for i, h in enumerate(header):
                k = _opt_kind(h) if i not in fixed_idx and h.strip() else None
                if k:
                    opt[i] = k
            fixed_idx |= set(opt)
            opt_order = sorted(opt, key=lambda i: (opt[i][1], i))
            spec_idx = [i for i, h in enumerate(header) if i not in fixed_idx and h.strip()]
            spec_cols = [{"key": slug(header[i]), "label": header[i].strip() if "\n" not in header[i] else header[i]}
                         for i in spec_idx]

            def cell(row, role):
                return _s(row[idx[role]]) if role in idx else None

            cur = None
            for n, row in enumerate(rows[1:], start=2):
                row = list(row) + [None] * (len(header) - len(row))
                code = _s(row[idx["code"]])
                if code in (None, ""):
                    continue
                code = str(code)
                cat = cell(row, "category")
                cat = None if _is_empty(cat) else str(cat)
                name = cell(row, "name")
                name = str(name) if not _is_empty(name) else (cat or ("" if "name" in idx else ws.title))
                if cur is None or cur["name"] != name or cur["sheet"] != ws.title or cur["file"] != fname:
                    cur = {"file": fname, "sheet": ws.title, "name": name, "category": cat,
                           "spec_columns": [dict(c) for c in spec_cols], "rows": [],
                           "lines": [], "legend": [], "note": None, "image": None, "drawing": None}
                    groups.append(cur)
                oc = norm_order_code(_s(row[idx["order"]]))
                where = f"{ws.title}!{n}" if len(paths) == 1 else f"{fname}:{ws.title}!{n}"
                if oc is None:
                    warnings.append(f"{where} {code}: invalid order id {row[idx['order']]!r}")
                dup = oc is not None and oc in seen
                if dup:
                    warnings.append(f"{where} {code}: duplicate order id {oc} (first at {seen[oc]})")
                elif oc is not None:
                    seen[oc] = where
                price = _s(row[idx["price"]])
                if price in (None, ""):
                    price = None
                    warnings.append(f"{where} {code}: missing price")
                elif _num(price) is None:
                    warnings.append(f"{where} {code}: non-numeric price {price!r}")
                else:
                    price = int(round(float(price)))
                specs = {spec_cols[j]["key"]: (None if _is_empty(_s(row[i])) else _s(row[i])) for j, i in enumerate(spec_idx)}
                d, D, B = (_num(specs.get(k)) for k in ("d_mm", "D_mm", "B_mm"))
                if d is not None and D is not None and d >= D:
                    warnings.append(f"{where} {code}: d ({d:g}) >= D ({D:g})")
                if B is not None and D is not None and B >= D:
                    warnings.append(f"{where} {code}: B ({B:g}) >= D ({D:g})")
                image = None
                for i in opt_order:
                    v = _s(row[i])
                    if v in (None, ""):
                        continue
                    v = str(v)
                    grp = opt[i][0]
                    if grp in ("lines", "legend"):
                        if v not in cur[grp]:
                            cur[grp].append(v)
                    elif cur[grp] is None:
                        cur[grp] = v
                    if grp == "image" and image is None:
                        image = v
                brand = cell(row, "brand")
                desc = cell(row, "description")
                cur["rows"].append({
                    "code": code, "order_code": oc, "price": price, "specs": specs, "dup": dup, "image": image,
                    "brand": None if _is_empty(brand) else str(brand),
                    "desc": None if _is_empty(desc) else str(desc),
                    "_raw": [(c["label"], specs[c["key"]]) for c in spec_cols],
                })
    brands = {}
    for g in groups:
        for r in g["rows"]:
            r["desc_clean"] = _clean_desc(r["desc"], r["code"], r["brand"], r.pop("_raw"))
            if r["brand"]:
                brands[r["brand"]] = brands.get(r["brand"], 0) + 1
        g["spec_columns"] = [c for c in g["spec_columns"]
                             if any(not _is_empty(r["specs"].get(c["key"])) for r in g["rows"])]
        keep = {c["key"] for c in g["spec_columns"]}
        for r in g["rows"]:
            r["specs"] = {k: v for k, v in r["specs"].items() if k in keep}
        _lift_units(g)
        bs = {r["brand"] for r in g["rows"] if r["brand"]}
        g["brand"] = bs.pop() if len(bs) == 1 and all(r["brand"] for r in g["rows"]) else None
        _quality(g, f"{g['file']}:{g['sheet']} [{g['name']}]", warnings)
        del g["col_units"]
    return {"groups": groups, "warnings": warnings, "brands": brands}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx", nargs="+")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    items = read_items(a.xlsx)
    Path(a.out).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"brands={items['brands']} groups={len(items['groups'])} rows={sum(len(g['rows']) for g in items['groups'])} warnings={len(items['warnings'])}")


if __name__ == "__main__":
    main()
