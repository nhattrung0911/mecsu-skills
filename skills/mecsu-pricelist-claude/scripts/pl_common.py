"""Shared helpers for the pricelist skill: theme loading, grid coordinates, doc I/O."""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

import jsonschema

SKILL_DIR = Path(__file__).resolve().parent.parent
THEME_PATH = SKILL_DIR / "config" / "theme.json"
SCHEMA_PATH = SKILL_DIR / "config" / "doc.schema.json"
EMU_PER_PX = 9525


def _deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_theme(overrides: dict | None = None) -> dict:
    with open(THEME_PATH, encoding="utf-8") as f:
        theme = json.load(f)
    return _deep_merge(theme, overrides or {})


def col_letter(idx: int) -> str:
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def col_index(letter: str) -> int:
    n = 0
    for ch in letter.upper():
        n = n * 26 + ord(ch) - 64
    return n


def abs_row(theme: dict, page: int, row: int) -> int:
    return page * theme["page"]["rows"] + row


def norm_order_code(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, float):
        if not v.is_integer():
            return None
        v = int(v)
    s = str(v).strip()
    s = re.sub(r"\.0+$", "", s)
    if not s.isdigit() or len(s) > 7:
        return None
    return s.zfill(7)


_ROLE_BY_KEY = {"code": "code", "order": "order_code", "order_code": "order_code", "price": "price"}


def column_role(col: dict) -> str:
    """Explicit role, else inferred from key; everything else is a spec column."""
    return col.get("role") or _ROLE_BY_KEY.get(col["key"], "spec")


def column_label(col: dict, theme: dict) -> str:
    return col.get("label") or theme["table"]["labels"].get(column_role(col), col["key"])


def px_to_emu(px: float) -> int:
    return int(round(px * EMU_PER_PX))


def user_home() -> Path:
    """User data dir (KB, learned logos). Lives OUTSIDE the plugin: plugin dirs are replaced on update."""
    env = os.environ.get("MECSU_PRICELIST_HOME")
    return Path(env).expanduser() if env else Path.home() / ".mecsu-pricelist"


def resolve_path(p: str | None, base: Path | None = None) -> Path | None:
    """Resolve a doc/theme path: absolute as-is, else doc dir (base) -> user_home() -> SKILL_DIR."""
    if not p:
        return None
    path = Path(p)
    if path.is_absolute():
        return path
    if base is not None and (base / path).exists():
        return base / path
    home = user_home() / path
    if home.exists():
        return home
    return SKILL_DIR / path


def validate_doc(doc: dict) -> None:
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    jsonschema.validate(doc, schema)


def load_doc(path) -> dict:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    validate_doc(doc)
    return doc


def save_doc(doc: dict, path) -> None:
    validate_doc(doc)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
