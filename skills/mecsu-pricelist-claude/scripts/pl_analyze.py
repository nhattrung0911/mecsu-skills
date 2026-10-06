"""Analysis step: items.json (pl_read) -> plan.json (family, split, sort per group).

Deterministic, offline. Rules live in config/families.json; Claude may edit plan.json
(family / split / sort / title_suffix) before pl_draft --plan applies it.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

FAMILIES_PATH = Path(__file__).resolve().parent.parent / "config" / "families.json"
LARGE_GROUP = 40
BRANDS = {"SKF", "NSK", "FAG", "NTN", "KOYO", "TIMKEN", "INA", "NACHI", "FBJ", "ZWZ", "HRB", "LYC",
          "SNR", "NKE", "IKO", "THK", "ASAHI", "UBC", "NMB", "KBC", "FKL"}


def _strip_marks(s: str, keep_case: bool) -> str:
    s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s if keep_case else s.lower()


def fold(s: str) -> str:
    """lowercase, no diacritics, single spaces."""
    return re.sub(r"\s+", " ", _strip_marks(str(s), False)).strip()


def load_families(path=None) -> list[dict]:
    with open(path or FAMILIES_PATH, encoding="utf-8") as f:
        return json.load(f)["families"]


def match_family(name: str, families: list[dict], category: str | None = None) -> tuple[dict, bool]:
    """-> (family, matched_by_rule). Matches the group name and its category. The last family is the default."""
    f = fold(name) + " | " + fold(category or "")
    for fam in families[:-1]:
        for t in (fam.get("match") or {}).get("name_any") or []:
            if re.search(r"(?<!\w)" + re.escape(fold(t)) + r"(?!\w)", f):
                return fam, True
    return families[-1], False


# ---------------------------------------------------------------- splits
def bearing_series(code: str, brands=BRANDS):
    """-> (key, label) or None when unparseable."""
    toks = str(code).split()
    while len(toks) > 1 and toks[0].upper() in brands:
        toks.pop(0)
    m = re.match(r"([A-Z]*)(\d+)(/)?", "".join(toks).upper())
    if not m:
        return None
    prefix, digits, slash = m.group(1), m.group(2), m.group(3)
    n = len(digits)
    if slash:
        series = digits
    elif prefix:
        if n < 3:
            return None
        series = digits[:-2] if n <= 4 else digits[:3]
    elif n == 3:
        return "mini", "LOẠI MINI"
    elif n == 4:
        series = digits[:2]
    elif n >= 5:
        series = digits[:3]
    else:
        return None
    return prefix + series, f"DÒNG {prefix}{series}00"


def _bearing_order(key: str):
    if key == "mini":
        return (0, "", 0)
    m = re.match(r"([A-Z]*)(\d+)$", key)
    if key == "other" or not m:
        return (3, "", 0)
    return (2 if m.group(1) else 1, m.group(1), int(m.group(2)))


def _find_column(split: dict, spec_columns: list[dict]):
    if split.get("column"):
        want = fold(split["column"])
        for c in spec_columns:
            if fold(c["label"]) == want:
                return c
        for c in spec_columns:
            if want in fold(c["label"]):
                return c
        return None
    for term in split.get("column_any") or []:
        t = fold(term)
        for c in spec_columns:
            if t in fold(c["label"]):
                return c
    return None


def variant_column(split: dict | None) -> dict | None:
    v = (split or {}).get("variant") if (split or {}).get("type") == "description" else None
    if not v or not v.get("pattern"):
        return None
    label = v.get("label", "Biến thể")
    return {"key": re.sub(r"\W+", "_", fold(label)).strip("_") or "variant", "label": label}


def ext_columns(split: dict | None, spec_columns: list[dict]) -> list[dict]:
    vc = variant_column(split)
    return list(spec_columns) + ([vc] if vc and all(c["label"] != vc["label"] for c in spec_columns) else [])


def value_order(split: dict | None) -> dict:
    vc = variant_column(split)
    return {vc["label"]: split["variant"]["order"]} if vc and split["variant"].get("order") else {}


def _split_description(split: dict, rows: list[dict]) -> list[dict]:
    """One subgroup per base description (desc_clean minus the variant phrase); the variant becomes a spec column."""
    vc = variant_column(split)
    rx = re.compile(split["variant"]["pattern"], re.I) if vc else None
    out: dict[str, dict] = {}
    for r in rows:
        text = (r.get("desc_clean") or "").strip()
        if not text:
            sg = out.setdefault("", {"key": "", "label": None, "rows": []})
            sg["rows"].append(r)
            continue
        val = None
        if rx:
            m = rx.search(text)
            if m:
                val = m.group(1) if m.re.groups else m.group(0)
                text = text[:m.start()] + " " + text[m.end():]
        base = re.sub(r"\s+", " ", text).strip(" -,")
        sg = out.setdefault(base, {"key": base, "label": None, "title": base.upper() or None, "rows": []})
        if vc:
            r = {**r, "specs": {**r["specs"], vc["key"]: val}}
            sg["extra_columns"] = [vc]
        sg["rows"].append(r)
    return list(out.values())


def split_rows(split: dict | None, rows: list[dict], spec_columns: list[dict]) -> list[dict]:
    """Partition rows -> ordered [{key, label|None, rows}]. No split -> one subgroup without label."""
    whole = [{"key": "", "label": None, "rows": list(rows)}]
    if not split:
        return whole
    typ = split.get("type")
    if typ == "description":
        return _split_description(split, rows)
    tpl = split.get("label")
    out: dict[str, dict] = {}

    def add(key, label, row):
        out.setdefault(key, {"key": key, "label": label, "rows": []})["rows"].append(row)

    if typ == "bearing_series":
        brands = {b.upper() for b in split.get("brands", BRANDS)}
        for r in rows:
            add(*(bearing_series(r["code"], brands) or ("other", None)), r)
        return sorted(out.values(), key=lambda sg: _bearing_order(sg["key"]))  # stable
    if typ == "column":
        col = _find_column(split, spec_columns)
        if col is None:
            return whole
        for r in rows:
            v = r["specs"].get(col["key"])
            v = "" if v is None else (f"{v:g}" if isinstance(v, float) else str(v)).strip()
            if v:
                add(v, (tpl or "{value}").replace("{value}", v).replace("{key}", v), r)
            else:
                add("other", None, r)
        return list(out.values())
    if typ == "regex":
        rx = re.compile(split["pattern"])
        for r in rows:
            m = rx.search(str(r["code"]))
            k = m.group(split.get("group", 1)) if m else None
            if k:
                add(k, (tpl or "DÒNG {key}").replace("{key}", k).replace("{value}", k), r)
            else:
                add("other", None, r)
        return list(out.values())
    return whole


# ---------------------------------------------------------------- sort
_NUM = re.compile(r"(\d+)\s+(\d+)/(\d+)|(\d+)/(\d+)|(\d+(?:[.,]\d+)?)")


def _val(m) -> float:
    if m.group(1):
        return int(m.group(1)) + int(m.group(2)) / max(int(m.group(3)), 1)
    if m.group(4):
        return int(m.group(4)) / max(int(m.group(5)), 1)
    return float(m.group(6).replace(",", "."))


def num_key(v):
    """Sortable key: numbers (first, then second as tie-break) < text (alphabetical) < empty."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return (2, 0.0, 0.0, "")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (0, float(v), 0.0, "")
    s = str(v).strip()
    ms = list(_NUM.finditer(s))
    if not ms:
        return (1, 0.0, 0.0, fold(s))
    return (0, _val(ms[0]), _val(ms[1]) if len(ms) > 1 else 0.0, "")


def natural_key(s) -> list:
    return [(0, int(p), "") if p.isdigit() else (1, 0, p.lower()) for p in re.split(r"(\d+)", str(s)) if p]


def resolve_sort(patterns: list[str], spec_columns: list[dict]):
    """regex list -> (column labels in order, patterns without a match). An exact column label also works."""
    labels, missing = [], []
    for p in patterns:
        hit = next((c["label"] for c in spec_columns if c["label"] == p and c["label"] not in labels), None)
        if hit is None:
            try:
                rx = re.compile(p)
            except re.error:
                rx = re.compile(re.escape(p))
            for c in spec_columns:
                if c["label"] not in labels and (rx.search(c["label"]) or rx.search(_strip_marks(c["label"], True))):
                    hit = c["label"]
                    break
        (labels if hit else missing).append(hit or p)
    return labels, missing


def sort_rows(rows: list[dict], labels: list[str], spec_columns: list[dict], orders: dict | None = None) -> list[dict]:
    """orders: {column label: [values in wanted order]} for categorical columns (e.g. Mịn < Trung Bình < Thô)."""
    by_label = {c["label"]: c["key"] for c in spec_columns}
    cols = [(by_label[lb], (orders or {}).get(lb)) for lb in labels if lb in by_label]

    def one(v, order):
        if order and v in order:
            return (0, float(order.index(v)), 0.0, "")
        return num_key(v)

    return sorted(rows, key=lambda r: tuple(one(r["specs"].get(k), o) for k, o in cols) + (natural_key(r["code"]),))


def _first_numeric_col(rows, spec_columns):
    for c in spec_columns:
        if any(num_key(r["specs"].get(c["key"]))[0] == 0 for r in rows):
            return c["label"]
    return None


# ---------------------------------------------------------------- analyze
def live_rows(g: dict) -> list[dict]:
    return [r for r in g["rows"] if not r.get("dup") and r.get("order_code") is not None]


def _card_title(g: dict, sg: dict, fam: dict) -> str:
    if sg.get("title"):
        return sg["title"]
    base = (g["name"] or g["sheet"]).upper()
    tpl = fam.get("title_suffix", "")
    return base + (tpl.replace("{label}", sg["label"]) if sg["label"] and tpl else "")


def analyze(items: dict, families: list[dict] | None = None) -> dict:
    from pl_draft import _merge_groups  # lazy: pl_draft imports this module
    families = families or load_families()
    out = []
    for g in _merge_groups(items["groups"]):
        rows = live_rows(g)
        if not rows:
            continue
        fam, matched = match_family(g["name"], families, g.get("category"))
        cols = g["spec_columns"]
        flags = [] if matched else ["no family rule matched (default)"]
        split = fam.get("split")
        if split and split.get("type") == "column":
            col = _find_column(split, cols)
            split = {"type": "column", "column": col["label"], "label": split.get("label", "{value}")} if col else None
        elif split:
            split = dict(split)
        cols = ext_columns(split, g["spec_columns"])
        labels, missing = resolve_sort(fam.get("sort") or [], cols)
        if not labels and fam.get("sort_fallback") == "first_numeric":
            lb = _first_numeric_col(rows, cols)
            labels, missing = ([lb], []) if lb else ([], missing)
        if (missing and not matched and not labels) or (missing and matched):
            flags.append("sort column not found: " + ", ".join(missing))
        subs = split_rows(split, rows, g["spec_columns"])
        if split and split.get("type") != "column":
            bad = [r["code"] for sg in subs if sg["key"] == "other" for r in sg["rows"]]
            if bad:
                flags.append("unparseable codes: " + ", ".join(bad[:8]) + (" ..." if len(bad) > 8 else ""))
        if not split and len(rows) > LARGE_GROUP:
            flags.append("large group (>40 rows) with no split — consider a split rule")
        out.append({
            "sheet": g["sheet"], "name": g["name"], "family": fam["name"], "split": split,
            "title_suffix": fam.get("title_suffix", "") if split else "",
            "legend_defaults": fam.get("legend_defaults", {}),
            "sort": labels,
            "subgroups": [{"key": sg["key"], "label": sg["label"],
                           "title": _card_title(g, sg, fam if split else {}), "count": len(sg["rows"]),
                           "codes_preview": [r["code"] for r in sg["rows"][:5]]} for sg in subs],
            "flags": flags,
        })
    brands = sorted({r["brand"] for g in items["groups"] for r in g["rows"] if r.get("brand")}, key=str.lower)
    plan = {"groups": out, "brands": brands, "flags": []}
    if len(brands) > 1:
        plan["flags"].append("multiple brands — run one price list per brand")
    return plan


def plan_md(plan: dict) -> str:
    L = ["# Plan phân tích", ""]
    if plan.get("brands"):
        L += [f"- Thương hiệu: {', '.join(plan['brands'])}", ""]
    L += [f"- CẢNH BÁO: {f}" for f in plan.get("flags", [])]
    for g in plan["groups"]:
        sp = g["split"]["type"] if g["split"] else "không"
        srt = ", ".join(x.replace("\n", " ") for x in g["sort"]) or "(không)"
        L.append(f"## {g['name'] or g['sheet']}  (sheet {g['sheet']})")
        L.append(f"- Họ: **{g['family']}** | Tách: {sp} | Sắp xếp: {srt}")
        L += ["", "| Tiêu đề card | Số dòng | Mã đầu |", "|---|---|---|"]
        for s in g["subgroups"]:
            L.append(f"| {s.get('title') or g['name']} | {s['count']} | {', '.join(s['codes_preview'])} |")
        L += [f"- CẢNH BÁO: {f}" for f in g["flags"]]
        L.append("")
    return "\n".join(L)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("items")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--md")
    ap.add_argument("--families")
    a = ap.parse_args()
    with open(a.items, encoding="utf-8") as f:
        items = json.load(f)
    plan = analyze(items, load_families(a.families) if a.families else None)
    Path(a.out).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.md:
        Path(a.md).write_text(plan_md(plan), encoding="utf-8")
    print(json.dumps({"groups": len(plan["groups"]), "flags": sum(len(g["flags"]) for g in plan["groups"])}))
    for g in plan["groups"]:
        for fl in g["flags"]:
            print(f"FLAG {g['name']}: {fl}")
    for fl in plan["flags"]:
        print(f"FLAG: {fl}")


if __name__ == "__main__":
    main()
