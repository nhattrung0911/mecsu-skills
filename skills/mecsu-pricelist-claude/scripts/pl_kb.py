"""Per-brand product knowledge base: decide card content once per manufacturer code, reuse forever.

KB file: <SKILL>/kb/<BRAND>.json = {"brand": ..., "entries": {code: entry}}; images in kb/img/<BRAND>/.
Commands: apply | learn | list | approve | diff   (see SKILL.md)
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys

import pathlib as _pathlib, sys as _sys  # noqa: E401
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
from pathlib import Path

from pl_common import SKILL_DIR, column_role, user_home


def default_kb() -> Path:
    return user_home() / "kb"



def _code_key(card: dict) -> str | None:
    for c in card["columns"]:
        if column_role(c) == "code":
            return c["key"]
    return None


def _norm(code) -> str:
    return str(code).strip()


def _card_codes(card: dict) -> list[str]:
    k = _code_key(card)
    return [_norm(r.get(k, "")) for r in card["rows"]] if k else []


def _safe(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", code)


def _kb_path(kb_dir, brand: str) -> Path:
    return Path(kb_dir) / f"{brand}.json"


def load_kb(kb_dir, brand: str) -> dict:
    kb_dir = kb_dir or default_kb()
    p = _kb_path(kb_dir, brand)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))["entries"]


def _save_kb(kb_dir, brand: str, entries: dict) -> None:
    Path(kb_dir).mkdir(parents=True, exist_ok=True)
    data = {"brand": brand, "entries": dict(sorted(entries.items()))}
    _kb_path(kb_dir, brand).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _rel_img(kb_dir, brand: str, name: str) -> str:
    return f"{Path(kb_dir).name}/img/{brand}/{name}"


def _img_ref(kb_dir, rel: str | None, status: str):
    if not rel:
        return None
    path = str(Path(kb_dir).parent / rel)
    return {"path": path, "status": "ok" if status == "ok" else "review"}


# ---------------------------------------------------------------- learn
def _same(e: dict, c: dict) -> bool:
    return e["title"] == c["title"] and e["lines"] == c["lines"] and e["legend"] == c["legend"]


def learn(doc_path, brand: str, status: str, kb_dir=None, sources=None, force=False) -> dict:
    kb_dir = kb_dir or default_kb()
    doc_path = Path(doc_path)
    base = doc_path.parent
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    entries = load_kb(kb_dir, brand)
    today = datetime.date.today().isoformat()
    conflicts, stored = [], 0

    def srcs(code):
        if isinstance(sources, dict):
            return list(sources.get(code, sources.get("*", [])))
        return list(sources or [])

    def copy_img(ref, code, suffix):
        if not ref or not ref.get("path"):
            return None
        src = Path(ref["path"])
        if not src.is_absolute():
            src = base / src if (base / src).exists() else SKILL_DIR / src
        if not src.exists():
            return None
        name = _safe(code) + suffix + (src.suffix or ".png")
        dst = Path(kb_dir) / "img" / brand / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        return _rel_img(kb_dir, brand, name)

    for card in doc["cards"]:
        if "#" in card["id"]:
            continue  # continuation card from pl_layout
        for code in _card_codes(card):
            if not code:
                continue
            new = {"title": card["title"], "lines": card.get("lines") or [], "legend": card.get("legend") or []}
            old = entries.get(code)
            if old and not _same(old, new):
                conflicts.append({"code": code, "kb": old["title"], "new": new["title"]})
                if old["status"] == "ok" and not force:
                    continue
            entries[code] = {
                "code": code, **new,
                "image": copy_img(card.get("image"), code, ""),
                "drawing": copy_img(card.get("drawing"), code, "_drawing"),
                "sources": srcs(code), "status": status, "updated": today,
                "note": (old or {}).get("note", ""),
            }
            stored += 1
    _save_kb(kb_dir, brand, entries)
    return {"stored": stored, "conflicts": conflicts}


# ---------------------------------------------------------------- apply
def _fill(card: dict, e: dict, kb_dir, override: bool) -> None:
    if card.get("title_source") != "data":  # user's data names are authoritative (user decision 2026-10-06)
        card["title"] = e["title"]
    if override or not card.get("lines"):
        card["lines"] = list(e["lines"])
    if override or not card.get("legend"):
        card["legend"] = list(e["legend"])
    for key in ("image", "drawing"):
        if override or not (card.get(key) or {}).get("path"):
            ref = _img_ref(kb_dir, e.get(key), e["status"])
            if ref:
                card[key] = ref
            elif override:
                card[key] = None


def _rowset(cards):
    k = []
    for c in cards:
        ck = _code_key(c)
        k += [(r.get(ck), r.get("order")) for r in c["rows"]]
    return sorted(map(str, k))


def apply(doc_path, brand: str, kb_dir=None, out_path=None) -> dict:
    kb_dir = kb_dir or default_kb()
    doc_path = Path(doc_path)
    out_path = Path(out_path) if out_path else doc_path
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    kb = load_kb(kb_dir, brand)
    before = _rowset(doc["cards"])
    new_cards, unknown, split, seen = [], [], 0, {}
    for card in doc["cards"]:
        ck = _code_key(card)
        if not ck:
            new_cards.append(card)
            continue
        codes = _card_codes(card)
        for code in codes:
            seen[code] = kb.get(code)
            if code not in kb:
                unknown.append({"code": code, "card": card["id"]})
        if card.get("title_source") == "data":
            known = [c for c in codes if c in kb]
            if known:  # keep the user's title and grouping; KB only fills empty lines/legend/image/drawing
                _fill(card, kb[known[0]], kb_dir, override=False)
            new_cards.append(card)
            continue
        titles = []
        for code in codes:
            t = kb[code]["title"] if code in kb else None
            if t is not None and t not in titles:
                titles.append(t)
        if len(titles) >= 2:
            split += 1
            groups = {t: [] for t in titles}
            rest = []
            for r, code in zip(card["rows"], codes):
                (groups[kb[code]["title"]] if code in kb else rest).append(r)
            n = 0
            for t in titles:
                n += 1
                c = json.loads(json.dumps(card))
                c["id"], c["rows"] = f"{card['id']}-{n}", groups[t]
                _fill(c, kb[_norm(groups[t][0][ck])], kb_dir, override=True)
                new_cards.append(c)
            if rest:
                c = json.loads(json.dumps(card))
                c["id"], c["rows"] = f"{card['id']}-{n + 1}", rest
                new_cards.append(c)
        else:
            if titles and all(c in kb for c in codes):
                _fill(card, kb[codes[0]], kb_dir, override=False)
            new_cards.append(card)
    doc["cards"] = new_cards
    assert _rowset(new_cards) == before, "rows changed by apply"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    (doc_path.parent / "kb_unknown.json").write_text(json.dumps(unknown, ensure_ascii=False, indent=1), encoding="utf-8")
    known = [c for c, e in seen.items() if e]
    return {"known": len(known), "unknown": len({u["code"] for u in unknown}),
            "review": sum(1 for c in known if seen[c]["status"] == "review"), "split_cards": split}


# ---------------------------------------------------------------- list / approve / diff
def list_entries(brand, kb_dir=None, status=None) -> list[dict]:
    kb_dir = kb_dir or default_kb()
    return [e for e in load_kb(kb_dir, brand).values() if not status or e["status"] == status]


def approve(brand, kb_dir=None, codes=None, all_review=False) -> int:
    kb_dir = kb_dir or default_kb()
    entries = load_kb(kb_dir, brand)
    n = 0
    for code, e in entries.items():
        if e["status"] != "ok" and (all_review or code in (codes or [])):
            e["status"] = "ok"
            n += 1
    _save_kb(kb_dir, brand, entries)
    return n


def _titles(path) -> dict[str, str]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if "cards" in d:
        out = {}
        for c in d["cards"]:
            for code in _card_codes(c):
                out.setdefault(code, c["title"])
        return out
    return {c: e["title"] for c, e in d["entries"].items()}


def diff(a, b) -> list[tuple[str, str, str]]:
    ta, tb = _titles(a), _titles(b)
    return [(c, ta[c], tb[c]) for c in ta if c in tb and ta[c] != tb[c]]


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kb-dir", default=None, help="default: <MECSU_PRICELIST_HOME or ~/.mecsu-pricelist>/kb")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("apply")
    p.add_argument("doc"); p.add_argument("--brand", required=True); p.add_argument("-o")
    p = sub.add_parser("learn")
    p.add_argument("doc"); p.add_argument("--brand", required=True)
    p.add_argument("--status", required=True, choices=["ok", "review"])
    p.add_argument("--sources"); p.add_argument("--force", action="store_true")
    p = sub.add_parser("list")
    p.add_argument("--brand", required=True); p.add_argument("--status")
    p = sub.add_parser("approve")
    p.add_argument("--brand", required=True); p.add_argument("--codes"); p.add_argument("--all-review", action="store_true")
    p = sub.add_parser("diff")
    p.add_argument("a"); p.add_argument("b")
    a = ap.parse_args(argv)
    kb = Path(a.kb_dir) if a.kb_dir else default_kb()
    if a.cmd == "apply":
        print(json.dumps(apply(a.doc, a.brand, kb, a.o), ensure_ascii=False))
    elif a.cmd == "learn":
        src = json.loads(Path(a.sources).read_text(encoding="utf-8")) if a.sources else None
        r = learn(a.doc, a.brand, a.status, kb, src, a.force)
        print(f"stored {r['stored']}, conflicts {len(r['conflicts'])}")
        for c in r["conflicts"]:
            print(f"CONFLICT {c['code']}: KB '{c['kb']}' vs new '{c['new']}'")
    elif a.cmd == "list":
        for e in list_entries(a.brand, kb, a.status):
            print(f"{e['code']}\t{e['status']}\t{e['title']}")
    elif a.cmd == "approve":
        print(approve(a.brand, kb, [c.strip() for c in (a.codes or "").split(",") if c.strip()], a.all_review))
    elif a.cmd == "diff":
        rows = diff(a.a, a.b)
        print("code | A | B")
        for c, x, y in rows:
            print(f"{c} | {x} | {y}")
        print(f"{len(rows)} differ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
