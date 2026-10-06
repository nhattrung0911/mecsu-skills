"""Compute geometry (_geo) for every card and pack cards onto pages."""
from __future__ import annotations

import argparse
import copy
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pl_common import (column_label, column_role, load_doc, load_theme, px_to_emu,  # noqa: E402
                       resolve_path, save_doc, validate_doc)


def _fmt(v, price: bool = False) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if price and isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v) >= 1000:
        return f"{v:,}"
    return str(v)


def text_px(s: str, theme: dict, kind: str = "data") -> float:
    """Estimated pixel width of one line of text. kind: data | header | title | line."""
    t, c = theme["table"], theme["card"]
    cls = t["char_classes"]
    px = 0.0
    for ch in s:
        if ch == " ":
            px += cls["space"]
        elif ch in "()":
            px += t.get("char_paren", cls["punct"])
        elif ch in "mwMW":
            px += t.get("char_wide", cls["upper_digit"])
        elif ch.isdigit() or (ch.isalpha() and ch.upper() == ch):
            px += cls["upper_digit"]
        elif ch.isalpha():
            px += cls["lower"]
        else:
            px += cls["punct"]
    bold = t["header_bold_factor"]
    scale = {"data": 1.0, "header": bold, "line": c["line_size"] / t["data_size"],
             "title": c["title_size"] / t["data_size"] * bold}[kind]
    return px * scale


def _wrap_lines(line: str, width_px: float, theme: dict, kind: str) -> int | None:
    """Greedy word wrap; number of lines, or None when a single word is wider than width_px."""
    n, cur = 1, ""
    for word in line.split():
        trial = (cur + " " + word) if cur else word
        if text_px(trial, theme, kind) <= width_px:
            cur = trial
        elif not cur or text_px(word, theme, kind) > width_px:
            if text_px(word, theme, kind) > width_px:
                return None
            cur = word
        else:
            n += 1
            cur = word
    return n


def header_min_cols(label: str, theme: dict) -> int:
    """Smallest span at which the label word-wraps into <= header_rows lines."""
    t, pg = theme["table"], theme["page"]
    for cols in range(1, pg["cols"] + 1):
        w = cols * pg["col_px"] - t["cell_pad_px"]
        total = 0
        for ln in label.split(chr(10)):
            k = _wrap_lines(ln, w, theme, "header") if ln.strip() else 1
            if k is None:
                total = 99
                break
            total += k
        if total <= t["header_rows"]:
            return cols
    return pg["cols"]


def _data_px(card: dict, col: dict, theme: dict) -> float:
    price = column_role(col) == "price"
    px = 0.0
    for r in card["rows"]:
        for line in _fmt(r.get(col["key"]), price).split(chr(10)):
            px = max(px, text_px(line, theme))
    return px


def _content_px(card: dict, col: dict, theme: dict) -> float:
    label = column_label(col, theme)
    px = max((text_px(x, theme, "header") for x in label.split(chr(10))), default=0.0)
    return max(px, _data_px(card, col, theme))


def _header_min_span(card: dict, col: dict, theme: dict) -> int:
    return max(theme["table"]["min_span"][column_role(col)], header_min_cols(column_label(col, theme), theme))


def _data_need(card: dict, col: dict, theme: dict) -> int:
    t, pg = theme["table"], theme["page"]
    px = _data_px(card, col, theme)
    return math.ceil((px + t["cell_pad_px"]) / pg["col_px"]) if px else 0


def _wrap_need(rows: list, col: dict, theme: dict) -> int:
    """Smallest span at which every value of the wrapped rows fits in <= 2 lines."""
    t, pg = theme["table"], theme["page"]
    price = column_role(col) == "price"
    need = 0
    for r in rows:
        for line in _fmt(r.get(col["key"]), price).split(chr(10)):
            for sp in range(1, pg["cols"] + 1):
                k = _wrap_lines(line, sp * pg["col_px"] - t["cell_pad_px"], theme, "data")
                if k is not None and k <= 2:
                    break
            need = max(need, sp)
    return need


def _ideal_and_min(card: dict, theme: dict, wrapped: list | None = None):
    t, pg = theme["table"], theme["page"]
    ideal, mins, fixed = [], [], []
    for col in card["columns"]:
        mn = max(_header_min_span(card, col, theme), _data_need(card, col, theme))
        if wrapped:
            mn = max(mn, _wrap_need(wrapped, col, theme))
        if col.get("span"):
            v = max(col["span"], mn)
            ideal.append(v)
            mins.append(v)
            fixed.append(True)
            continue
        ideal.append(mn)
        mins.append(mn)
        fixed.append(False)
    return ideal, mins, fixed


def column_spans(card: dict, width: int, theme: dict) -> list[int]:
    hs = row_heights(card, width, theme)
    wrapped = [r for r, h in zip(card["rows"], hs) if h > 1]
    if wrapped:  # wrapped rows only need a 2-line fit; they do not set the column width
        card = {**card, "rows": [r for r, h in zip(card["rows"], hs) if h == 1]}
    ideal, mins, fixed = _ideal_and_min(card, theme, wrapped)
    spans = list(ideal)
    n = len(spans)
    chars = [_content_px(card, c, theme) for c in card["columns"]]
    roles = [column_role(c) for c in card["columns"]]
    # surplus -> widest-content columns first
    order = sorted([i for i in range(n) if not fixed[i]] or list(range(n)), key=lambda i: (-chars[i], i))
    k = 0
    while sum(spans) < width:
        spans[order[k % len(order)]] += 1
        k += 1

    def shrink(pred, floor):
        while sum(spans) > width:
            cands = [i for i in range(n) if pred(i) and spans[i] > floor(i)]
            if not cands:
                return
            i = max(cands, key=lambda i: (spans[i] - floor(i), spans[i]))
            spans[i] -= 1

    # spec columns first, then other non-fixed, then anything; below min only as last resort
    shrink(lambda i: roles[i] == "spec" and not fixed[i], lambda i: mins[i])
    shrink(lambda i: not fixed[i], lambda i: mins[i])
    shrink(lambda i: True, lambda i: mins[i])
    shrink(lambda i: True, lambda i: 1)
    return spans


def _title_need(card: dict, theme: dict) -> int:
    px = text_px(card.get("title") or "", theme, "title")
    return math.ceil((px + theme["table"]["cell_pad_px"]) / theme["page"]["col_px"])


def _fits(ideal, mins, cand, tn, theme) -> bool:
    return sum(mins) <= cand and sum(ideal) <= cand * (1 + theme["table"].get("fit_tolerance", 0)) and tn <= cand


def _wrap_set(card: dict, cand: int, tn: int, theme: dict):
    """Rows (indices) to wrap to 2 lines so the card fits width cand; None when impossible (or > wrap_rows_frac)."""
    rows = card["rows"]
    n = len(rows)
    k = int(theme["table"].get("wrap_rows_frac", 0) * n + 1e-9)
    if k < 1 or tn > cand:
        return None
    W: set = set()
    while True:
        keep = [i for i in range(n) if i not in W]
        eff = {**card, "rows": [rows[i] for i in keep]}
        ideal, mins, _ = _ideal_and_min(eff, theme, [rows[i] for i in W])
        if W and _fits(ideal, mins, cand, tn, theme):
            break
        if len(W) >= k or len(keep) <= 1:
            return None
        cols = [c for c in card["columns"] if not c.get("span")]
        col = max(cols or card["columns"], key=lambda c: _data_need(eff, c, theme))
        price = column_role(col) == "price"
        i = max(keep, key=lambda i: max((text_px(x, theme) for x in _fmt(rows[i].get(col["key"]), price).split(chr(10))), default=0.0))
        W.add(i)
    return sorted(W)


def _plan(card: dict, theme: dict) -> tuple[int, list[int]]:
    """-> (width, wrapped row indices)."""
    w = card.get("width", "auto")
    if isinstance(w, int):
        return w, []
    ideal, mins, _ = _ideal_and_min(card, theme)
    tn = _title_need(card, theme)
    snap = theme["lanes"].get("prefer_grid17", False)
    for cand in theme["lanes"]["widths"]:
        if snap and cand == 26:
            continue
        if _fits(ideal, mins, cand, tn, theme):
            return cand, []
        W = _wrap_set(card, cand, tn, theme)
        if W:
            return cand, W
    return theme["lanes"]["widths"][-1], []


def choose_width(card: dict, theme: dict) -> int:
    return _plan(card, theme)[0]


def row_heights(card: dict, width: int | None, theme: dict) -> list[int]:
    """Sheet rows per data row (units of data_row_height): 2 for rows wrapped to keep the card narrow."""
    n = len(card["rows"])
    if not n or not theme["table"].get("wrap_rows_frac"):
        return [1] * n
    w, W = _plan(card, theme)
    if width is not None and width != w:
        return [1] * n
    return [2 if i in set(W) else 1 for i in range(n)]


def _fixed_rows(theme: dict) -> int:
    return theme["card"]["title_rows"] + 1 + theme["table"]["header_rows"]


def _note_rows(card: dict, theme: dict) -> int:
    return theme["card"].get("note_rows", 2) if card.get("note") else 0


def card_height(card: dict, desc_rows: int, theme: dict | None = None, width: int | None = None) -> int:
    theme = theme or load_theme()
    drh = card.get("data_row_height", 1)
    units = sum(row_heights(card, width, theme))
    return _fixed_rows(theme) + desc_rows + units * drh + _note_rows(card, theme)


def _image_plan(card: dict, width: int, theme: dict) -> dict:
    plan = _image_plan0(card, width, theme)
    ov = card.get("desc_rows")
    if isinstance(ov, int) and ov >= 0 and not card.get("_cont"):
        plan["desc_rows"] = ov
    return plan


_BASE: Path | None = None


def _usable(card: dict, key: str) -> bool:
    im = card.get(key)
    if not im or not im.get("path"):
        return False
    path = resolve_path(im["path"], _BASE)
    return bool(path and Path(path).is_file())


def _img_size(card: dict, key: str):
    path = resolve_path((card.get(key) or {}).get("path"), _BASE)
    try:
        from PIL import Image
        with Image.open(path) as f:
            return f.size if f.size[0] > 0 and f.size[1] > 0 else None
    except Exception:
        return None


def _image_plan0(card: dict, width: int, theme: dict) -> dict:
    """-> {mode, box_cols, desc_rows, title_cols, skip, regions}. mode: None | side | side2 | below.
    skip = rows (from card top) before the visual box starts. regions: [(key, col_off, cols, row_off, rows)]."""
    c, ti, pg = theme["card"], theme["image"], theme["page"]
    texts = list(card.get("lines") or []) + list(card.get("legend") or [])
    nlines = len(texts)
    base = 0 if card.get("_cont") else nlines
    tr = c["title_rows"]
    title_cols = math.ceil((text_px(card.get("title") or "", theme, "title") + theme["table"]["cell_pad_px"]) / pg["col_px"])
    keys = [k for k in ("image", "drawing") if _usable(card, k) and not card.get("_cont")]
    if not keys:
        return {"mode": None, "box_cols": 0, "desc_rows": base, "title_cols": width, "need_title": title_cols,
                "skip": 0, "regions": []}
    need_total = max(ti["max_h_rows"], math.ceil((ti.get("min_h_px", 0) + 2 * ti["pad_px"]) / pg["row_px"]))
    both = len(keys) == 2
    if both:  # photo sized exactly as without drawing; drawing takes remaining width (or goes below)
        ps = _image_plan0({**card, "drawing": None}, width, theme)
        maxpx0 = max((text_px(t, theme, "line") for t in texts), default=0.0)
        tc = (c["line_indent_cols"] + math.ceil(maxpx0 / pg["col_px"])) if texts else 0
        avail = {"side": width - max(tc, title_cols), "side2": width - tc}.get(ps["mode"], width)
        want2 = round(width * ti.get("max_w_frac_with_drawing", ti["max_w_frac"]))
        extra = min(want2, avail) - ps["box_cols"]
        img = ps["regions"][0]
        _, _, bc, ro, rr = img
        if extra >= ti["min_cols"]:
            tot = ps["box_cols"] + extra
            out = dict(ps)
            out["box_cols"] = tot
            out["regions"] = [("image", width - tot, bc, ro, rr), ("drawing", width - tot + bc, extra, ro, rr)]
            if ps["mode"] == "side":
                out["title_cols"] = width - tot
            return out
        out = dict(ps)
        out["regions"] = [img, ("drawing", img[1], bc, ro + rr, need_total)]
        out["desc_rows"] = ps["desc_rows"] + need_total
        return out
    maxpx = max((text_px(t, theme, "line") for t in texts), default=0.0)
    text_cols = (c["line_indent_cols"] + math.ceil(maxpx / pg["col_px"])) if texts else 0
    want = round(width * (ti.get("max_w_frac_with_drawing", ti["max_w_frac"]) if both else ti["max_w_frac"]))
    min_box = ti["min_cols"] * (2 if both else 1)
    if both:
        want = max(want, min_box)
    img_rows = need_total - tr
    side_desc = max(nlines, img_rows, c["min_desc_rows"])

    def hsplit(box, row_off, rows):
        if not both:
            return [(keys[0], width - box, box, row_off, rows)]
        left = box // 2
        return [("image", width - box, left, row_off, rows), ("drawing", width - box + left, box - left, row_off, rows)]

    cands = []  # (mode, box, desc_rows, title_cols_out, skip, regions)
    box = min(want, width - max(text_cols, title_cols))
    if box >= min_box:
        cands.append(("side", box, side_desc, width - box, 0, hsplit(box, 0, tr + side_desc)))
    box = min(want, width - text_cols)
    if box >= min_box:
        d = max(side_desc, need_total)
        cands.append(("side2", box, d, width, tr, hsplit(box, tr, d)))
    skip = tr + nlines
    if both:
        box = min(want, width)
        if box < min_box:  # drawing below the photo
            d = nlines + 2 * need_total
            regions = [("image", width - box, box, skip, need_total), ("drawing", width - box, box, skip + need_total, need_total)]
        else:
            d = max(nlines + need_total, c["min_desc_rows"])
            regions = hsplit(box, skip, need_total)
        cands.append(("below", box, d, width, skip, regions))
    else:
        box = min(max(want, round(width * 0.9)), width)
        d = max(nlines + need_total, c["min_desc_rows"])
        cands.append(("below", box, d, width, skip, hsplit(box, skip, need_total)))
    pick = cands[0]
    size = _img_size(card, keys[0]) if not both else None
    if size and len(cands) > 1:
        def fit(cd):
            bc, rr = cd[5][0][2], cd[5][0][4]
            bw, bh = bc * pg["col_px"] - 2 * ti["pad_px"], rr * pg["row_px"] - 2 * ti["pad_px"]
            sc = min(bw / size[0], bh / size[1], max(1.0, ti.get("min_h_px", 0) / size[1]))
            return size[0] * sc, size[1] * sc

        fits = [fit(cd) for cd in cands]
        areas = [w_ * h_ for w_, h_ in fits]
        j = max(range(len(cands)), key=lambda k: areas[k])
        if cands[0][0] != "side":
            pick = cands[j]
        elif ti.get("placement", "rescue") == "max":
            if areas[j] > 1.15 * areas[0]:
                pick = cands[j]
        elif fits[0][1] < min(ti.get("min_h_px", 0), size[1]) - 0.5 and areas[j] > areas[0]:
            pick = cands[j]
    elif cands[0][0] != "side" and len(cands) > 1:
        pick = cands[0]
    mode, box, d, tcols, sk, regions = pick
    return {"mode": mode, "box_cols": box, "desc_rows": d, "title_cols": tcols,
            "need_title": title_cols, "skip": sk, "regions": regions}


def _desc_rows(card: dict, theme: dict, width: int | None = None) -> int:
    return _image_plan(card, width or choose_width(card, theme), theme)["desc_rows"]


def _fit_geo(card, key, region, col, row, theme, base_dir):
    im = card.get(key)
    pg, ti = theme["page"], theme["image"]
    path = resolve_path(im.get("path"), base_dir)
    try:
        from PIL import Image
        if path is None or not Path(path).is_file():
            raise FileNotFoundError(str(im.get("path")))
        with Image.open(path) as f:
            w, h = f.size
        if w <= 0 or h <= 0:
            raise ValueError("empty image")
    except Exception as e:  # missing / unreadable
        card.setdefault("_warnings", []).append(f"{key} unavailable: {im.get('path')} ({type(e).__name__})")
        return None
    _, col_off, box_cols, row_off, box_rows = region
    box_cols, box_rows = max(1, box_cols), max(1, box_rows)
    bw = box_cols * pg["col_px"] - 2 * ti["pad_px"]
    bh = box_rows * pg["row_px"] - 2 * ti["pad_px"]
    if im.get("max_w_px"):
        bw = min(bw, im["max_w_px"])
    if im.get("max_h_px"):
        bh = min(bh, im["max_h_px"])
    s = min(bw / w, bh / h, max(1.0, ti.get("min_h_px", 0) / h))
    iw, ih = w * s, h * s
    x = (box_cols * pg["col_px"] - iw) / 2
    y = (box_rows * pg["row_px"] - ih) / 2 + row_off * pg["row_px"]
    ci, cx = divmod(x, pg["col_px"])
    ri, ry = divmod(y, pg["row_px"])
    return {"col": col + col_off + int(ci), "row": row + int(ri), "col_off_emu": px_to_emu(cx),
            "row_off_emu": px_to_emu(ry), "cx_emu": px_to_emu(iw), "cy_emu": px_to_emu(ih)}


def _image_geo(card, width, col, row, desc_rows, theme, base_dir, key="image"):
    if not card.get(key):
        return None
    if not _usable(card, key):
        if card[key].get("path"):
            card.setdefault("_warnings", []).append(f"{key} unavailable: {card[key]['path']} (FileNotFoundError)")
        return None
    plan = _image_plan(card, width, theme)
    reg = next((r for r in plan["regions"] if r[0] == key), None)
    if reg is None:
        return None
    return _fit_geo(card, key, reg, col, row, theme, base_dir)


def _split(card: dict, theme: dict) -> list[dict]:
    pg = theme["page"]
    body = pg["body_bottom"] - pg["body_top"] + 1
    drh = card.get("data_row_height", 1)
    d1 = _desc_rows(card, theme)
    if card_height(card, d1, theme) <= body:
        return [card]
    d2 = 0
    fixed = _fixed_rows(theme)
    cap1 = body - fixed - d1
    cap2 = body - fixed - d2
    note_u = _note_rows(card, theme)
    minc = max(theme["card"]["min_chunk_rows"], 6)
    rows = card["rows"]
    units = [h * drh for h in row_heights(card, None, theme)]
    chunks, first, i = [], True, 0
    while i < len(rows):
        rem_u = sum(units[i:])
        cap = cap1 if first else cap2
        n, acc = 0, 0
        if rem_u <= cap - note_u:
            n = len(rows) - i
        elif rem_u <= cap:
            while i + n < len(rows) and (n < 1 or acc < rem_u / 2):
                acc += units[i + n]
                n += 1
        else:
            while i + n < len(rows) and acc + units[i + n] <= cap:
                acc += units[i + n]
                n += 1
            n = max(n, 1)
        rem = len(rows) - i
        if 0 < rem - n < minc and rem - minc >= 1:  # orphan control: keep the tail >= minc rows
            n = rem - minc
        chunks.append(rows[i:i + n])
        i += n
        first = False
    out = []
    for k, ch in enumerate(chunks):
        c = copy.deepcopy(card)
        c["rows"] = ch
        if k > 0:
            c["id"] = f"{card['id']}#{k + 1}"
            c["lines"], c["legend"], c["image"], c["place"] = [], [], None, None
            c["drawing"] = None
            c["_cont"] = True
        if k < len(chunks) - 1:
            c["note"] = None
        out.append(c)
    return out


class _Page:
    def __init__(self, theme):
        self.sky = [theme["page"]["body_top"]] * (theme["page"]["cols"] + 2)
        self.rects: list[tuple[int, int, int, int]] = []  # col0, col1, row0, row1


def _collide(p: _Page, c0, c1, r0, r1, gap):
    for a0, a1, b0, b1 in p.rects:
        if c0 <= a1 and a0 <= c1 and r0 - gap <= b1 and b0 <= r1 + gap:
            return b1
    return None


def _try_place(p: _Page, x, w, h, theme):
    gap, pg = theme["card"]["gap_rows"], theme["page"]
    if x + w - 1 > pg["body_right"]:
        return None
    top = max(p.sky[x:x + w])
    while True:
        hit = _collide(p, x, x + w - 1, top, top + h - 1, gap)
        if hit is None:
            break
        top = hit + gap + 1
    if top + h - 1 > pg["body_bottom"]:
        return None
    return top


def _free(p: _Page, x, w, theme):
    """-> (top, free_rows) available at lane x on page p."""
    gap, pg = theme["card"]["gap_rows"], theme["page"]
    if x + w - 1 > pg["body_right"]:
        return 0, 0
    top = max(p.sky[x:x + w])
    while True:
        hit = _collide(p, x, x + w - 1, top, top, gap)
        if hit is None:
            break
        top = hit + gap + 1
    limit = pg["body_bottom"] + 1
    for a0, a1, b0, b1 in p.rects:
        if x <= a1 and a0 <= x + w - 1 and b0 > top:
            limit = min(limit, b0 - gap)
    return top, max(0, limit - top)


def _clip_warnings(card: dict, spans: list[int], theme: dict, heights=None) -> list[str]:
    out = []
    heights = heights or [1] * len(card["rows"])
    for col, span in zip(card["columns"], spans):
        label = column_label(col, theme)
        hn = header_min_cols(label, theme)
        worst, wv = hn, label.replace(chr(10), " ")
        price = column_role(col) == "price"
        t, pg = theme["table"], theme["page"]
        for r, rh in zip(card["rows"], heights):
            for line in _fmt(r.get(col["key"]), price).split(chr(10)):
                if rh > 1:  # wrapped row: may use 2 lines
                    k = _wrap_lines(line, span * pg["col_px"] - t["cell_pad_px"], theme, "data")
                    if k is None or k > 2:
                        out.append(f"clip: wrapped value '{line}' needs more than 2 lines in col '{label.replace(chr(10), ' ')}'")
                    continue
                need = math.ceil((text_px(line, theme) + t["cell_pad_px"]) / pg["col_px"])
                if need > worst:
                    worst, wv = need, line
        if worst > span:
            out.append(f"clip: col '{label.replace(chr(10), ' ')}' value '{wv}' needs {worst} cols, has {span}")
    return out


def _fill_split(c: dict, w: int, d: int, p: _Page, xs, theme):
    """Split c so its first chunk fills the biggest free gap on p. -> (x, top, head, rest) or None."""
    drh = c.get("data_row_height", 1)
    minc = max(theme["card"]["min_chunk_rows"], 6)
    if len(c["rows"]) < theme["card"].get("min_rows_to_split_across_pages", 0):
        return None
    best = None
    for x in xs:
        top, free = _free(p, x, w, theme)
        if best is None or free > best[2]:
            best = (x, top, free)
    x, top, free = best
    avail, n = free - _fixed_rows(theme) - d, 0
    for h in row_heights(c, w, theme):
        if h * drh > avail:
            break
        avail -= h * drh
        n += 1
    n = min(n, len(c["rows"]) - minc)
    if n < minc:
        return None
    head, rest = copy.deepcopy(c), copy.deepcopy(c)
    head["rows"], rest["rows"] = c["rows"][:n], c["rows"][n:]
    head["note"] = None
    rest["lines"], rest["legend"], rest["image"], rest["place"] = [], [], None, None
    rest["_cont"] = True
    rest["drawing"] = None
    return x, top, head, rest


def _commit(p: _Page, x, w, top, h, theme, locked):
    p.rects.append((x, x + w - 1, top, top + h - 1))
    if not locked:
        for i in range(x, x + w):
            p.sky[i] = max(p.sky[i], top + h + theme["card"]["gap_rows"])


def layout(doc: dict, theme: dict | None = None, base_dir=None) -> dict:
    theme = theme or load_theme(doc.get("meta", {}).get("theme_overrides"))
    doc = copy.deepcopy(doc)
    base_dir = Path(base_dir) if base_dir else None
    global _BASE
    _BASE = base_dir
    items = []
    for c in doc["cards"]:
        c.pop("_warnings", None)
        for ch in _split(c, theme):
            ch["_base"] = c["id"]
            items.append(ch)
    for c in items:
        c["_geo"] = {}
    pages: list[_Page] = [_Page(theme)]

    def page(n):
        while len(pages) <= n:
            pages.append(_Page(theme))
        return pages[n]

    span_cache: dict = {}
    if theme["card"].get("harmonize", False):
        groups: dict = {}
        for c in items:
            sig = tuple((column_role(x), column_label(x, theme)) for x in c["columns"])
            w0 = c["width"] if isinstance(c.get("width"), int) else choose_width(c, theme)
            groups.setdefault((sig, w0), []).append(c)
        for (sig, w0), grp in groups.items():
            union = {"columns": grp[0]["columns"],
                     "rows": [r for g in grp for r, h in zip(g["rows"], row_heights(g, w0, theme)) if h == 1],
                     "title": max((g.get("title") or "" for g in grp), key=len)}
            span_cache[(sig, w0)] = column_spans(union, w0, theme)
            for g in grp:
                g["_sig"] = sig

    def prep(c):
        w = choose_width(c, theme)
        d = _desc_rows(c, theme, w)
        return w, d, card_height(c, d, theme, w)

    def finish(c, w, d, h, pn, x, top):
        plan = _image_plan(c, w, theme)
        if plan["need_title"] > w:
            c.setdefault("_warnings", []).append(f"title too long ({plan['need_title']} cols > {w})")
        spans = span_cache.get((c.get("_sig"), w)) or column_spans(c, w, theme)
        c.setdefault("_warnings", []).extend(_clip_warnings(c, spans, theme, row_heights(c, w, theme)))
        nl = len(c.get("lines") or []) + len(c.get("legend") or [])
        if nl > d:
            c["_warnings"].append(f"{nl - d} description line(s) do not fit desc_rows={d}")
        for col in c["columns"]:
            if col.get("span"):
                need = max(_header_min_span(c, col, theme), _data_need(c, col, theme))
                if need > col["span"]:
                    c["_warnings"].append(f"span raised col '{column_label(col, theme).replace(chr(10), ' ')}' {col['span']}->{need}")
        c["_geo"].update({
            "title_cols": plan["title_cols"],
            "page": pn, "col": x, "row": top, "width": w, "height": h,
            "spans": spans, "desc_rows": d, "row_heights": row_heights(c, w, theme),
            "image": _image_geo(c, w, x, top, d, theme, base_dir),
            "drawing": _image_geo(c, w, x, top, d, theme, base_dir, "drawing"),
            "cont": False})

    for c in items:  # locked cards first
        pl = c.get("place")
        if pl and pl.get("locked"):
            w, d, h = prep(c)
            pn, x, top = pl.get("page", 0), pl["col"], pl["row"]
            _commit(page(pn), x, w, top, h, theme, True)
            finish(c, w, d, h, pn, x, top)
    cur = 0
    i = 0
    while i < len(items):
        c = items[i]
        i += 1
        if c["_geo"]:
            continue
        w, d, h = prep(c)
        xs = theme["lanes"]["positions"].get(str(w), [theme["page"]["body_left"]])
        best = None
        fs_used = False
        for attempt in range(2):
            p = page(cur)
            for x in xs:
                top = _try_place(p, x, w, h, theme)
                if top is not None and (best is None or (top, x) < best):
                    best = (top, x)
            if best:
                break
            if attempt == 0 and c.get("split") != "keep_together" and c["rows"]:
                fs = _fill_split(c, w, d, p, xs, theme)
                if fs:
                    x, top, head, rest = fs
                    head["_geo"] = {}
                    c.clear()
                    c.update(head)
                    items.insert(i, rest)
                    rest["_geo"] = {}
                    h = card_height(c, d, theme, w)
                    best = (top, x)
                    fs_used = True
                    break
            cur += 1
        if best is None:
            raise ValueError(f"card {c['id']} cannot be placed (height {h}, width {w})")
        win = theme["card"].get("backfill_window", 0)
        if win and attempt == 0 and not fs_used and not c.get("_bf"):
            gap = theme["card"]["gap_rows"]
            pick = None
            for j in range(i, min(len(items), i + win)):
                d_ = items[j]
                if d_["_geo"] or d_.get("_cont"):  # never pull a continuation chunk ahead of its head
                    continue
                wd, dd, hd = prep(d_)
                for xd in theme["lanes"]["positions"].get(str(wd), [theme["page"]["body_left"]]):
                    td = _try_place(page(cur), xd, wd, hd, theme)
                    if td is not None and td + hd + gap <= best[0] and (pick is None or (td, j) < pick[:2]):
                        pick = (td, j)
            if pick:
                items.insert(i - 1, items.pop(pick[1]))
                items[i - 1]["_bf"] = True
                i -= 1
                continue
        top, x = best
        _commit(page(cur), x, w, top, h, theme, False)
        finish(c, w, d, h, cur, x, top)
    seen: dict[str, int] = {}
    for c in items:  # renumber chunks per base id
        base = c.pop("_base")
        c.pop("_cont", None)
        c.pop("_bf", None)
        c.pop("_hw", None)
        c.pop("_sig", None)
        k = seen.get(base, 0)
        seen[base] = k + 1
        c["id"] = base if k == 0 else f"{base}#{k + 1}"
        c["_geo"]["cont"] = k > 0
    doc["cards"] = items
    doc.setdefault("meta", {})["page_count"] = max([c["_geo"]["page"] for c in items] + [0]) + 1
    validate_doc(doc)
    return doc


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    doc = load_doc(a.doc)
    out = layout(doc, load_theme(doc["meta"].get("theme_overrides")), base_dir=Path(a.doc).resolve().parent)
    save_doc(out, a.out)
    warns = sum(len(c.get("_warnings", [])) for c in out["cards"])
    print(f"cards={len(out['cards'])} pages={out['meta']['page_count']} warnings={warns}")


if __name__ == "__main__":
    main()
