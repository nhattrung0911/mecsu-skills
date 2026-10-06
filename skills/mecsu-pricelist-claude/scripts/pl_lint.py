"""Content lint for doc.json: enforces references/content_rules.md so every price list reads the same.

Errors block the build (exit 1). Warnings go to the report. `--fix` applies only safe, meaning-preserving
fixes (case, units, spacing, trailing dots) and rewrites the doc.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import pathlib as _pathlib, sys as _sys  # noqa: E401
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
from pl_common import column_label, column_role, load_doc, save_doc  # noqa: E402

TITLE_MAX = 40
LINE_MAX = 28
LINES_MAX = 5
NOTE_MAX = 110
UNITS = ["mm²", "mm", "inch", "kN", "rpm", "N.m", "Nm", "kg", "g", "cm", "V", "W"]
UNIT_FIX = {"in": "inch", "Inch": "inch", "INCH": "inch", "Nm": "N.m", "MM": "mm"}
SYM = r"[A-Za-zΦφØøΔδ]{1,4}[₀0-9]?"
LETTER_LABEL = re.compile(r"^(" + SYM + r")(\n(\(.+\)|mm))?$")
LEGEND = re.compile(r"^(" + SYM + r")\s*:\s*\S.*$")
EMPTY_MARKERS = {"N/A", "n/a", "-", "--", "NA"}
SYNONYMS = [("Chiều Dài", "L"), ("Size", "S")]
PLACEHOLDER_TITLE = re.compile(r"^(KHÔNG TIÊU ĐỀ|UNTITLED|NO TITLE|TIÊU ĐỀ)?$")
UNIT_IN_TEXT = re.compile(r"\((mm|inch|in|cm)\)")


def _is_symbol(tok: str) -> bool:
    """d, D, C₀, AVM, ØQ, Φ are symbols; Phe, Cao, Size are words."""
    letters = [ch for ch in tok if ch.isalpha()]
    if len(letters) <= 1 or any(ch in "ΦφØøΔδ₀0123456789" for ch in tok):
        return True
    return sum(ch.isupper() for ch in letters) >= len(letters) - 1


def _clean(s: str) -> str:
    s = re.sub(r"[ \t]+", " ", s.strip().lstrip("*•").strip())
    return re.sub(r"\s*\.$", "", s)


def _title_case_ok(line: str) -> bool:
    for w in re.split(r"[\s:/]+", line):
        if w and w[0].isalpha() and w[0].islower() and len(w) > 1 and not re.match(r"^(mm|inch|kg|g|cm|x)\b", w):
            return False
    return True


def fix_label(label: str) -> str:
    """'Chiều Dài mm' / 'Chiều Dài (Inch)' / 'Chiều Dài\\nmm' -> 'Chiều Dài\\n(mm)'; letter labels 'd mm' -> 'd\\nmm'."""
    s = re.sub(r"[ \t]+", " ", label.strip())
    flat = s.replace("\n", " ")
    m = re.match(r"^(.*?)[ ]*\(?\b(" + "|".join(map(re.escape, list(UNIT_FIX) + UNITS)) + r")\)?$", flat)
    if not m or not m.group(1).strip():
        return s
    name, unit = m.group(1).strip(), UNIT_FIX.get(m.group(2), m.group(2))
    if LETTER_LABEL.match(name) and len(name) <= 3 and unit == "mm" and "(" not in flat:
        return f"{name}\nmm"  # narrow bearing exception (content_rules §4)
    return f"{name}\n({unit})"


def lint(doc: dict, fix: bool = False) -> dict:
    errors, warnings = [], []
    order_seen: dict[str, str] = {}
    label_texts = set()
    titles = {}
    for c in doc["cards"]:
        cid = c["id"]
        cont = "#" in cid
        if fix:
            c["title"] = _clean(c["title"]).upper()
            c["lines"] = [_clean(x) for x in c.get("lines", [])]
            c["legend"] = [_clean(x) for x in c.get("legend", [])]
            if c.get("note"):
                c["note"] = _clean(c["note"])
            for col in c["columns"]:
                if col.get("label"):
                    col["label"] = fix_label(col["label"])
            for r in c["rows"]:
                for k, v in list(r.items()):
                    if isinstance(v, str):
                        r[k] = v.strip()
        t = c["title"]
        if t != t.upper():
            errors.append(f"{cid}: title not UPPERCASE: {t!r}")
        if PLACEHOLDER_TITLE.match(t.strip()):
            errors.append(f"{cid}: placeholder/empty title {t!r} — write the product type")
        if ":" in t:
            errors.append(f"{cid}: title must not contain ':' (attribute belongs in lines): {t!r}")
        if len(t) > TITLE_MAX:
            errors.append(f"{cid}: title {len(t)} chars > {TITLE_MAX}")
        lines = c.get("lines", [])
        if len(lines) > LINES_MAX:
            errors.append(f"{cid}: {len(lines)} lines > {LINES_MAX}")
        for ln in lines:
            if len(ln) > LINE_MAX:
                errors.append(f"{cid}: line > {LINE_MAX} chars: {ln!r}")
            lm = LEGEND.match(ln)
            if lm and _is_symbol(lm.group(1)):  # 'Size: 1/2 Inch' is a description, not a legend
                errors.append(f"{cid}: legend-like line in lines (move to legend): {ln!r}")
            if len(ln) < 3 or not re.search(r"[^\W\d_]{2}", ln):
                errors.append(f"{cid}: junk description line {ln!r}")
            if not _title_case_ok(ln):
                warnings.append(f"{cid}: line not Title Case: {ln!r}")
        for lg in c.get("legend", []):
            if not LEGEND.match(lg):
                errors.append(f"{cid}: legend must be 'X: Tên': {lg!r}")
        if not cont and not lines and not c.get("legend") and len(c["rows"]) >= 1:
            warnings.append(f"{cid}: no description lines (standard card has 1-5)")
        note = c.get("note")
        if note and len(note) > NOTE_MAX:
            warnings.append(f"{cid}: note {len(note)} chars > {NOTE_MAX}")
        roles = [column_role(col) for col in c["columns"]]
        if roles[:1] != ["code"] or roles[-2:] != ["order_code", "price"] or roles.count("price") != 1:
            errors.append(f"{cid}: columns must be code, specs..., order_code, price (got {roles})")
        legend_letters = {LEGEND.match(x).group(1).replace("₀", "0") for x in c.get("legend", []) if LEGEND.match(x)}
        for col in c["columns"]:
            if column_role(col) != "spec":
                continue
            lab = column_label(col, {"table": {"labels": {}}}) if col.get("label") else col["key"]
            label_texts.add(lab.split("\n")[0])
            if fix_label(lab) != lab:
                errors.append(f"{cid}: label unit style {lab!r} -> {fix_label(lab)!r} (run --fix)")
            m = LETTER_LABEL.match(lab)
            if m and not _is_symbol(m.group(1)):
                m = None  # ordinary short word (Phe, Cao, Size), not a dimension symbol
            has_drawing = bool((c.get("drawing") or {}).get("path"))
            if m and m.group(1).replace("₀", "0") not in legend_letters and not cont:
                letter = m.group(1).replace("₀", "0")
                if letter.lower() in {x.lower() for x in legend_letters}:
                    errors.append(f"{cid}: letter label {letter!r} case differs from legend")
                elif not has_drawing:
                    errors.append(f"{cid}: letter label {letter!r} has no legend line (or add a drawing)")
            if m:
                col_unit = UNIT_IN_TEXT.search(lab)
                for lg in c.get("legend", []):
                    lm, lu = LEGEND.match(lg), UNIT_IN_TEXT.search(lg)
                    if lm and lm.group(1) == m.group(1) and lu and col_unit and                             lu.group(1).replace("in", "inch").replace("inchch", "inch") != col_unit.group(1):
                        warnings.append(f"{cid}: legend unit {lu.group(0)} != column unit {col_unit.group(0)} for {m.group(1)!r}")
        okey = next((col["key"] for col in c["columns"] if column_role(col) == "order_code"), None)
        ckey = next((col["key"] for col in c["columns"] if column_role(col) == "code"), None)
        for i, r in enumerate(c["rows"]):
            oc = str(r.get(okey, ""))
            if not re.fullmatch(r"\d{7}", oc):
                errors.append(f"{cid} row {i + 1}: order code {oc!r} not 7 digits")
            elif oc in order_seen and order_seen[oc] != cid.split("#")[0]:
                errors.append(f"{cid} row {i + 1}: order code {oc} also in {order_seen[oc]}")
            else:
                order_seen[oc] = cid.split("#")[0]
            if not str(r.get(ckey, "")).strip():
                errors.append(f"{cid} row {i + 1}: empty Mã Hãng")
            for k, v in r.items():
                if isinstance(v, str) and v.strip() in EMPTY_MARKERS:
                    warnings.append(f"{cid} row {i + 1}: use '' instead of {v!r} in {k}")
        img = c.get("image") or {}
        if not cont and not img.get("path"):
            warnings.append(f"{cid}: no image")
        elif img.get("status") == "review":
            warnings.append(f"{cid}: image needs review")
        # Rule C (user decision 2026-10-06): one title = one product type. Same type + same image -> one card
        # with several rows; different type -> its own card with the variant in the title.
        # Titles taken from the user's data are authoritative: a duplicate that differs in columns or image is the
        # user's naming of different products -> warning; same title + same columns + same image is a true
        # duplicate that must be merged -> error. Titles Claude wrote: any duplicate is an error (rule C).
        cols_sig = (tuple(column_label(col, {"table": {"labels": {}}}) if col.get("label") else col["key"]
                          for col in c["columns"]), (c.get("image") or {}).get("path"))
        if not cont and t in titles:
            other_id, other_sig = titles[t]
            if c.get("title_source") == "data" and cols_sig != other_sig:
                warnings.append(f"{cid}: same title as {other_id} from data (different columns/image) — ask "
                                f"user whether to give them distinct names")
            else:
                errors.append(f"{cid}: duplicate title {t!r} (also {other_id}) — merge rows if same type and "
                              f"image, else put the variant in the title")
        titles.setdefault(t, (cid, cols_sig))
    for long, short in SYNONYMS:
        if long in label_texts and short in label_texts:
            warnings.append(f"labels mix synonyms {long!r} and {short!r} — pick one per price list")
    return {"errors": errors, "warnings": warnings}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("doc")
    ap.add_argument("--fix", action="store_true", help="apply safe fixes and save the doc")
    ap.add_argument("-o", "--out", help="write report (markdown)")
    a = ap.parse_args()
    doc = load_doc(a.doc)
    res = lint(doc, fix=a.fix)
    if a.fix:
        save_doc(doc, a.doc)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(f"# Lint report\n\n## Errors ({len(res['errors'])})\n")
            f.writelines(f"- {e}\n" for e in res["errors"])
            f.write(f"\n## Warnings ({len(res['warnings'])})\n")
            f.writelines(f"- {w}\n" for w in res["warnings"])
    print(json.dumps({"errors": len(res["errors"]), "warnings": len(res["warnings"]),
                      "first_errors": res["errors"][:10]}, ensure_ascii=False))
    sys.exit(1 if res["errors"] else 0)


if __name__ == "__main__":
    main()
