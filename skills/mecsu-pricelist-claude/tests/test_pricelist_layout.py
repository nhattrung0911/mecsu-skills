import random
from pathlib import Path

import pytest
from PIL import Image

from pl_common import load_theme, validate_doc
from pl_layout import card_height, choose_width, column_spans, layout

T = load_theme()


def mk_card(cid, nrows=4, lines=3, cols=None, **kw):
    cols = cols or [{"key": "code", "label": "Mã Hãng"}, {"key": "d", "label": "d\nmm"},
                    {"key": "order", "label": "Mã Đặt Hàng"}, {"key": "price", "label": "Giá/Cái\nChưa VAT"}]
    rows = [{"code": f"C{cid}-{i}", "d": i, "order": f"{1000000 + i}", "price": 5000 + i} for i in range(nrows)]
    c = {"id": cid, "title": f"Card {cid}", "lines": [f"line {i}" for i in range(lines)], "columns": cols, "rows": rows}
    c.update(kw)
    return c


def mk_doc(cards):
    return {"meta": {"brand": "Test", "page_code": "TST"}, "cards": cards}


def rect(c):
    g = c["_geo"]
    return (g["page"], g["col"], g["row"], g["col"] + g["width"] - 1, g["row"] + g["height"] - 1)


def test_no_overlap_and_inside_body():
    rnd = random.Random(1)
    cards = [mk_card(f"k{i}", nrows=rnd.randint(1, 30), lines=rnd.randint(0, 6)) for i in range(40)]
    out = layout(mk_doc(cards), T)
    validate_doc(out)
    rs = [rect(c) for c in out["cards"]]
    for r in rs:
        assert 5 <= r[2] and r[4] <= 74 and 3 <= r[1] and r[3] <= 55
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)):
            a, b = rs[i], rs[j]
            if a[0] != b[0]:
                continue
            assert a[3] < b[1] or b[3] < a[1] or a[4] < b[2] or b[4] < a[2], (a, b)


def test_auto_width_grows():
    cols = [{"key": "code", "label": "Mã Hãng"}] + \
           [{"key": f"s{i}", "label": "Một Nhãn Rất Dài Dòng"} for i in range(4)] + \
           [{"key": "order", "label": "Mã Đặt Hàng"}, {"key": "price", "label": "Giá"}]
    card = mk_card("w", cols=cols, rows=None) if False else mk_card("w", cols=cols)
    for r in card["rows"]:
        for i in range(4):
            r[f"s{i}"] = "giá trị khá dài ở đây"
    w = choose_width(card, T)
    assert w in (26, 35, 53)
    assert sum(column_spans(card, w, T)) == w
    out = layout(mk_doc([card]), T)
    g = out["cards"][0]["_geo"]
    assert sum(g["spans"]) == g["width"] and g["col"] + g["width"] - 1 <= 55


def test_small_card_is_17():
    assert choose_width(mk_card("s"), T) == 17
    assert sum(column_spans(mk_card("s"), 17, T)) == 17


def test_split_long_card():
    out = layout(mk_doc([mk_card("big", nrows=120)]), T)
    cs = out["cards"]
    assert len(cs) >= 2 and [c["id"] for c in cs][:2] == ["big", "big#2"]
    assert sum(len(c["rows"]) for c in cs) == 120
    codes = [r["code"] for c in cs for r in c["rows"]]
    assert len(set(codes)) == 120
    assert all(c["_geo"]["height"] <= 70 and c["title"] == "Card big" for c in cs)
    assert [c["_geo"]["cont"] for c in cs] == [False] + [True] * (len(cs) - 1)


def test_locked_card_kept():
    cards = [mk_card("a"), mk_card("b", place={"page": 0, "col": 21, "row": 5, "locked": True})]
    out = layout(mk_doc(cards), T)
    g = out["cards"][1]["_geo"]
    assert (g["page"], g["col"], g["row"]) == (0, 21, 5)
    ra, rb = rect(out["cards"][0]), rect(out["cards"][1])
    assert ra[3] < rb[1] or rb[3] < ra[1] or ra[4] < rb[2] or rb[4] < ra[2]


def test_height_formula():
    c = mk_card("h", nrows=4, lines=3)
    assert card_height(c, 3) == 2 + 3 + 1 + 2 + 4
    out = layout(mk_doc([c]), T)
    assert out["cards"][0]["_geo"]["height"] == 12 and out["cards"][0]["_geo"]["desc_rows"] == 3
    c3 = mk_card("h3", nrows=4, data_row_height=3)
    assert card_height(c3, 3) == 2 + 3 + 1 + 2 + 12


def test_page_count_set():
    out = layout(mk_doc([mk_card(f"p{i}", nrows=40, width=53, split="keep_together") for i in range(3)]), T)
    assert out["meta"]["page_count"] == 3
    assert [c["_geo"]["page"] for c in out["cards"]] == [0, 1, 2]


def test_input_not_mutated():
    d = mk_doc([mk_card("m")])
    layout(d, T)
    assert "_geo" not in d["cards"][0]


def test_image_fit_and_missing(tmp_path):
    Image.new("RGBA", (400, 100), (255, 0, 0, 255)).save(tmp_path / "wide.png")
    c1 = mk_card("i1", image={"path": "wide.png"})
    c2 = mk_card("i2", image={"path": "nope.png"})
    out = layout(mk_doc([c1, c2]), T, base_dir=tmp_path)
    g1, g2 = out["cards"][0]["_geo"], out["cards"][1]["_geo"]
    assert g1["desc_rows"] >= T["image"]["max_h_rows"] - 2
    im = g1["image"]
    assert im and im["cx_emu"] > 3 * im["cy_emu"] * 0.99
    assert im["col"] >= g1["col"] and im["col"] <= g1["col"] + g1["width"] - 1
    assert im["row"] >= g1["row"] and im["col_off_emu"] >= 0 and im["row_off_emu"] >= 0
    assert g2["image"] is None and out["cards"][1]["_warnings"]


def test_wide_photo_narrow_card_goes_below_and_bigger(tmp_path):
    Image.new("RGBA", (600, 150), (255, 0, 0, 255)).save(tmp_path / "w.png")
    c = mk_card("w", width=17, lines=0, image={"path": "w.png"})
    c["lines"] = ["Đầu Vuông: 1/2 Inch Dài"]
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    assert g["image"]["row"] >= g["row"] + 2 + 1
    assert g["image"]["cx_emu"] > 9525 * 17 * T["page"]["col_px"] * 0.5


def test_rescue_keeps_side_when_photo_big_enough_max_switches(tmp_path):
    Image.new("RGBA", (600, 150), (255, 0, 0, 255)).save(tmp_path / "w.png")
    c = mk_card("w", width=26, lines=0, image={"path": "w.png"})
    c["lines"] = ["a"]
    row = lambda th: layout(mk_doc([dict(c)]), th, base_dir=tmp_path)["cards"][0]["_geo"]
    r = row(load_theme({"image": {"placement": "rescue", "min_h_px": 20}}))
    assert r["image"]["row"] < r["row"] + 2 + 2          # side kept: photo already >= min_h_px
    m = row(load_theme({"image": {"placement": "max", "min_h_px": 20}}))
    assert m["image"]["cx_emu"] >= r["image"]["cx_emu"]


def test_rescue_moves_below_when_side_photo_too_small(tmp_path):
    Image.new("RGBA", (600, 150), (255, 0, 0, 255)).save(tmp_path / "w.png")
    c = mk_card("w", width=17, lines=0, image={"path": "w.png"})
    c["lines"] = ["Đầu Vuông: 1/2 Inch Dài"]
    g = layout(mk_doc([c]), load_theme({"image": {"placement": "rescue"}}), base_dir=tmp_path)["cards"][0]["_geo"]
    assert g["image"]["row"] >= g["row"] + 3


def test_split_chunks_never_orphaned():
    from pl_layout import _split
    for n in range(40, 150):
        ch = _split(mk_card("s", nrows=n, width=17), T)
        assert sum(len(c["rows"]) for c in ch) == n
        assert all(len(c["rows"]) >= 6 for c in ch), (n, [len(c["rows"]) for c in ch])


def test_split_no_orphan_and_head_first(tmp_path):
    Image.new("RGBA", (200, 100), (255, 0, 0, 255)).save(tmp_path / "ph.png")
    filler = [mk_card(f"f{i}", nrows=10, width=17) for i in range(3)]
    for nrows in range(44, 56):
        big = mk_card("big", nrows=nrows, width=17, lines=0, image={"path": "ph.png"})
        out = layout(mk_doc(filler + [big]), T, base_dir=tmp_path)["cards"]
        ch = [c for c in out if c["id"].split("#")[0] == "big"]
        assert sum(len(c["rows"]) for c in ch) == nrows
        assert [c["id"] for c in ch] == ["big"] + [f"big#{k}" for k in range(2, len(ch) + 1)], nrows
        codes = [r["code"] for c in ch for r in c["rows"]]
        assert codes == [r["code"] for r in big["rows"]], nrows           # row order kept
        assert ch[0]["_geo"]["image"] and not any(c["_geo"]["image"] for c in ch[1:])
        assert all(len(c["rows"]) >= 6 for c in ch), (nrows, [len(c["rows"]) for c in ch])
        pages = [c["_geo"]["page"] for c in ch]
        assert pages == sorted(pages)


def test_tall_photo_keeps_side(tmp_path):
    Image.new("RGBA", (100, 400), (255, 0, 0, 255)).save(tmp_path / "t.png")
    c = mk_card("t", width=26, lines=0, image={"path": "t.png"})
    c["lines"] = ["a", "b"]
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    assert g["image"]["col"] >= g["col"] + g["width"] // 3
    assert g["image"]["row"] < g["row"] + 2 + 2


def test_note_height_and_split_note_last_chunk():
    c = mk_card("n", nrows=4, lines=3, note="* ghi chu")
    out = layout(mk_doc([c]), T)
    assert out["cards"][0]["_geo"]["height"] == 12 + T["card"]["note_rows"]
    assert card_height(c, 3, T) == 12 + T["card"]["note_rows"]
    big = layout(mk_doc([mk_card("nb", nrows=120, note="x")]), T)["cards"]
    assert [bool(c["note"]) for c in big] == [False] * (len(big) - 1) + [True]
    assert all(c["_geo"]["height"] <= 70 for c in big) and sum(len(c["rows"]) for c in big) == 120


def _img_card(cid, lines, tmp_path, **kw):
    Image.new("RGBA", (100, 100), (0, 0, 255, 255)).save(tmp_path / "sq.png")
    c = mk_card(cid, lines=0, image={"path": "sq.png"}, **kw)
    c["lines"] = lines
    return c


def test_image_clear_of_long_text(tmp_path):
    c = _img_card("t1", ["x" * 20, "short"], tmp_path)
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    text_end = g["col"] + T["card"]["line_indent_cols"] + -(-20 * T["card"]["line_char_px"] // T["page"]["col_px"])
    assert g["image"] and g["image"]["col"] >= text_end


def test_image_below_when_text_very_long(tmp_path):
    c = _img_card("t2", ["x" * 40, "y" * 38], tmp_path)
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    nl = 2
    assert g["image"] and g["image"]["row"] >= g["row"] + 2 + nl
    need = max(T["image"]["max_h_rows"], -(-(T["image"]["min_h_px"] + 2 * T["image"]["pad_px"]) // T["page"]["row_px"]))
    assert g["desc_rows"] == nl + need
    assert g["height"] == 2 + g["desc_rows"] + 1 + 2 + 4
    assert g["image"]["row"] + 0 <= g["row"] + 2 + g["desc_rows"] - 1


def test_bearing_card_gets_26():
    cols = [{"key": "code", "label": "Mã Hãng"}, {"key": "d", "label": "d\nmm"}, {"key": "D", "label": "D\nmm"},
            {"key": "B", "label": "B\nmm"}, {"key": "cap", "label": "Nắp Chắn"},
            {"key": "order", "label": "Mã Đặt Hàng"}, {"key": "price", "label": "Giá/Cái\nChưa VAT"}]
    card = mk_card("br", nrows=20, cols=cols)
    for r in card["rows"]:
        r.update({"D": 30, "B": 8, "cap": "2 Phớt Cao Su", "code": "6000-2RSZ2V2"})
    assert choose_width(card, T) == 26
    sp = column_spans(card, 26, T)
    assert sum(sp) == 26 and all(s >= 2 for s in sp)


def test_fill_split_uses_page_bottom():
    a = mk_card("A", nrows=40, width=53)
    b = mk_card("B", nrows=40, width=53)
    out = layout(mk_doc([a, b]), T)
    cs = out["cards"]
    assert [c["id"] for c in cs] == ["A", "B", "B#2"]
    assert cs[1]["_geo"]["page"] == 0 and cs[2]["_geo"]["page"] == 1
    assert [c["_geo"]["cont"] for c in cs] == [False, False, True]
    assert sum(len(c["rows"]) for c in cs[1:]) == 40
    assert cs[1]["_geo"]["row"] + cs[1]["_geo"]["height"] - 1 <= 74
    assert out["meta"]["page_count"] == 2
    assert len({r["code"] for c in cs[1:] for r in c["rows"]}) == 40


def test_short_card_not_split_across_pages():
    a = mk_card("A", nrows=40, width=53)
    b = mk_card("B", nrows=15, width=53)
    out = layout(mk_doc([a, b]), T)
    ids = [c["id"] for c in out["cards"]]
    assert ids == ["A", "B"] or ids == ["A", "A#2", "B"] or not any(i.startswith("B#") for i in ids)
    assert not any(i.startswith("B#") for i in ids)


def test_fill_split_respects_min_rows_and_chunk():
    from pl_layout import _fill_split, _Page
    th = load_theme({"card": {"min_rows_to_split_across_pages": 100}})
    c = mk_card("B", nrows=40, width=53)
    assert _fill_split(c, 53, 0, _Page(th), [th["page"]["body_left"]], th) is None


def test_keep_together_not_split_and_note_last():
    a = mk_card("A", nrows=40, width=53)
    b = mk_card("B", nrows=40, width=53, split="keep_together")
    cs = layout(mk_doc([a, b]), T)["cards"]
    assert [c["id"] for c in cs] == ["A", "B"] and cs[1]["_geo"]["page"] == 1
    b2 = mk_card("B", nrows=40, width=53, split="allow", note="n")
    cs = layout(mk_doc([a, b2]), T)["cards"]
    assert [bool(c["note"]) for c in cs[1:]] == [False, True]


def test_text_px_and_code_span_6():
    from pl_layout import text_px
    assert text_px("6000-2RSZ2V2", T) > text_px("6000-2RS", T) > 0
    assert text_px("ab", T, "header") > text_px("ab", T)
    cols = [{"key": "code", "label": "Mã Hãng"}, {"key": "order", "label": "Mã Đặt Hàng"}, {"key": "price", "label": "Giá"}]
    c = mk_card("cs", cols=cols)
    c["rows"][0]["code"] = "6000-2RSZ2V2"
    assert column_spans(c, 17, T)[0] >= 6


def test_header_never_clipped():
    from pl_layout import header_min_cols
    cols = [{"key": "code", "label": "Mã Hãng"}, {"key": "s", "label": "Đường Kính Ngoài"},
            {"key": "order", "label": "Mã Đặt Hàng"}, {"key": "price", "label": "Giá/Cái\nChưa VAT"}]
    c = mk_card("hc", cols=cols)
    for w in (17, 26, 35):
        sp = column_spans(c, w, T)
        assert sp[1] >= header_min_cols("Đường Kính Ngoài", T)
        assert sp[2] >= header_min_cols("Mã Đặt Hàng", T)


def test_title_one_line_and_title_cols(tmp_path):
    long_t = "VÒNG BI CẦU RÃNH SÂU MINI DÒNG 600 - 620"
    c = _img_card("tt", ["Đường Kính Trong d"], tmp_path)
    c["title"] = long_t
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    from pl_layout import text_px
    need = -(-(text_px(long_t, T, "title") + T["table"]["cell_pad_px"]) // T["page"]["col_px"])
    assert g["title_cols"] >= need or g["title_cols"] == g["width"]
    if g["title_cols"] < g["width"]:
        assert g["image"]["col"] >= g["col"] + g["title_cols"]
    c2 = _img_card("t3", ["Đường Kính Trong d"], tmp_path, width=17)
    c2["title"] = long_t
    g2 = layout(mk_doc([c2]), T, base_dir=tmp_path)["cards"][0]
    assert g2["_geo"]["title_cols"] == 17 and g2["_warnings"] and "title too long" in g2["_warnings"][-1]


def test_continuation_has_no_desc_rows():
    cs = layout(mk_doc([mk_card("big", nrows=120)]), T)["cards"]
    assert cs[0]["_geo"]["desc_rows"] >= 3 and all(c["_geo"]["desc_rows"] == 0 for c in cs[1:])
    assert all("title_cols" in c["_geo"] for c in cs)
    assert all(c["_geo"]["height"] <= 70 for c in cs) and sum(len(c["rows"]) for c in cs) == 120


def test_clip_warning_reported():
    cols = [{"key": "code", "label": "Mã Hãng"}, {"key": "order", "label": "Mã Đặt Hàng"}, {"key": "price", "label": "Giá"}]
    c = mk_card("cl", cols=cols, width=17)
    c["rows"][0]["code"] = "VERY-LONG-CODE-VALUE-XXXXXXXXXXXXXXX"
    w = layout(mk_doc([c]), T)["cards"][0].get("_warnings", [])
    assert any(x.startswith("clip: col 'Mã Hãng'") and "VERY-LONG" in x for x in w)
    ok = layout(mk_doc([mk_card("ok")]), T)["cards"][0].get("_warnings", [])
    assert not any(x.startswith("clip") for x in ok)


def test_desc_rows_override(tmp_path):
    c = _img_card("ov", ["a", "b"], tmp_path, desc_rows=6)
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    assert g["desc_rows"] == 6 and g["height"] == 2 + 6 + 1 + 2 + 4
    c2 = mk_card("ov2", lines=5, desc_rows=2)
    o = layout(mk_doc([c2]), T)["cards"][0]
    assert o["_geo"]["desc_rows"] == 2 and any("do not fit" in x for x in o["_warnings"])


def test_header_wraps_to_two_lines():
    from pl_layout import header_min_cols, text_px
    n = header_min_cols("Mã Đặt Hàng", T)
    full = -(-(text_px("Mã Đặt Hàng", T, "header") + T["table"]["cell_pad_px"]) // T["page"]["col_px"])
    assert n <= 4 and n < full
    assert text_px("mm", T) > text_px("ab", T) and header_min_cols("(mm)", T) == 3
    assert header_min_cols("Giá/Cái\nChưa VAT", T) >= header_min_cols("Chưa VAT", T)


def test_numeric_not_comma_formatted():
    from pl_layout import _fmt
    assert _fmt(1000) == "1000" and _fmt(5.0) == "5" and _fmt(1500, price=True) == "1,500"
    cols = [{"key": "code", "label": "Mã Hãng"}, {"key": "L", "label": "L"}, {"key": "order", "label": "Mã Đặt Hàng"},
            {"key": "price", "label": "Giá"}]
    c = mk_card("nf", cols=cols)
    for r in c["rows"]:
        r["L"] = 1000
    out = layout(mk_doc([c]), T)["cards"][0]
    assert not any("'L'" in x for x in out.get("_warnings", []))


def test_data_clip_widens_card():
    cols = [{"key": "code", "label": "Mã Hãng"}, {"key": "s", "label": "S"}, {"key": "order", "label": "Mã Đặt Hàng"},
            {"key": "price", "label": "Giá"}]
    c = mk_card("dc", cols=cols)
    c["rows"][0]["s"] = "5, 6, PH1, PH2, PZ1, PZ2, S1, S2"
    assert choose_width(c, T) >= 26
    g = layout(mk_doc([c]), T)["cards"][0]
    assert not [x for x in g.get("_warnings", []) if x.startswith("clip")]
    c["rows"][0]["s"] = "x" * 200
    g = layout(mk_doc([c]), T)["cards"][0]
    assert g["_geo"]["width"] == 53 and any(x.startswith("clip") for x in g["_warnings"])


def test_title_widens_card():
    c = mk_card("tw")
    c["title"] = "VÒNG BI CẦU RÃNH SÂU DÒNG RẤT DÀI VÀ NHIỀU CHỮ HƠN"
    assert choose_width(c, T) > 17


def test_image_min_height(tmp_path):
    Image.new("RGBA", (20, 20), (0, 255, 0, 255)).save(tmp_path / "tiny.png")
    c = mk_card("im", lines=0, image={"path": "tiny.png"})
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    assert g["image"]["cy_emu"] >= (T["image"]["min_h_px"] - 1) * 9525
    assert g["desc_rows"] >= T["image"]["max_h_rows"] - T["card"]["title_rows"]


def test_span_is_minimum_hint():
    cols = [{"key": "code", "label": "Mã Hãng", "span": 3}, {"key": "s", "label": "S", "span": 2},
            {"key": "order", "label": "Mã Đặt Hàng"}, {"key": "price", "label": "Giá"}]
    c = mk_card("sp", cols=cols)
    c["rows"][0]["s"] = "0.25-6 mm²"
    g = layout(mk_doc([c]), T)["cards"][0]
    assert g["_geo"]["spans"][1] >= 5
    assert any(w.startswith("span raised col 'S' 2->") for w in g["_warnings"])
    assert not any(w.startswith("clip") for w in g["_warnings"])


def test_harmonize_same_columns_same_spans():
    a = mk_card("ha", nrows=3)
    b = mk_card("hb", nrows=3)
    b["rows"][0]["code"] = "6000-2RSZ2V2"
    g = layout(mk_doc([a, b]), T)["cards"]
    assert g[0]["_geo"]["width"] == g[1]["_geo"]["width"]
    assert g[0]["_geo"]["spans"] == g[1]["_geo"]["spans"]
    off = layout(mk_doc([a, b]), load_theme({"card": {"harmonize": False}}))["cards"]
    assert off[0]["_geo"]["spans"] != off[1]["_geo"]["spans"]
    assert "_sig" not in g[0]


def test_harmonize_outlier_becomes_wider_tier():
    cards = [mk_card(f"o{i}", nrows=3) for i in range(3)]
    cards[2]["rows"][0]["code"] = "X" * 40
    g = layout(mk_doc(cards), T)["cards"]
    assert [c["_geo"]["width"] for c in g] == [17, 17, 26 if g[2]["_geo"]["width"] == 26 else g[2]["_geo"]["width"]]
    assert g[2]["_geo"]["width"] > 17
    assert g[0]["_geo"]["spans"] == g[1]["_geo"]["spans"]


def _draw_card(cid, tmp_path, image=True, drawing=True, lines=None, **kw):
    Image.new("RGBA", (200, 100), (255, 0, 0, 255)).save(tmp_path / "ph.png")
    Image.new("RGBA", (100, 100), (0, 0, 255, 255)).save(tmp_path / "dr.png")
    c = mk_card(cid, lines=0, **kw)
    c["lines"] = lines or ["a", "b"]
    if image:
        c["image"] = {"path": "ph.png"}
    if drawing:
        c["drawing"] = {"path": "dr.png"}
    return c


def test_drawing_side_by_side(tmp_path):
    c = _draw_card("d1", tmp_path, width=35)
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    assert g["image"] and g["drawing"]
    assert g["drawing"]["col"] > g["image"]["col"]
    assert g["image"]["col"] + g["image"]["cx_emu"] / 9525 / T["page"]["col_px"] <= g["drawing"]["col"] + 0.5
    assert g["drawing"]["col"] + g["drawing"]["cx_emu"] / 9525 / T["page"]["col_px"] <= g["col"] + g["width"] + 0.01


def test_drawing_only_uses_whole_box_and_none_in_cont(tmp_path):
    c = _draw_card("d2", tmp_path, image=False)
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    assert g["image"] is None and g["drawing"] and g["drawing"]["cx_emu"] > 0
    big = _draw_card("d3", tmp_path)
    big = dict(big, rows=mk_card("x", nrows=120)["rows"])
    out = layout(mk_doc([big]), T, base_dir=tmp_path)["cards"]
    assert len(out) >= 2 and all(c["_geo"]["drawing"] is None for c in out[1:])


def test_drawing_below_when_narrow(tmp_path):
    c = _draw_card("d4", tmp_path, width=17, lines=["x" * 30, "y" * 30])
    g = layout(mk_doc([c]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    assert g["image"] and g["drawing"] and g["image"]["row"] >= g["row"] + 2 and g["drawing"]["row"] > g["image"]["row"]
    assert g["height"] == 2 + g["desc_rows"] + 1 + 2 + 4


def test_backfill_fills_third_lane():
    cols = [{"key": "code", "label": "Mã Hãng"}, {"key": "a", "label": "Một Nhãn Rất Dài Dòng"},
            {"key": "b", "label": "Hai Nhãn Rất Dài Dòng"}, {"key": "order", "label": "Mã Đặt Hàng"},
            {"key": "price", "label": "Giá"}]
    wide = []
    for i in range(3):
        c = mk_card(f"w{i}", nrows=10, cols=cols, width=35)
        for r in c["rows"]:
            r.update({"a": 1, "b": 2})
        wide.append(c)
    small = mk_card("s0", nrows=5, width=17)
    doc = mk_doc(wide + [small])
    off = layout(doc, load_theme({"card": {"backfill_window": 0}}))["cards"]
    on = layout(doc, T)["cards"]
    s_off = next(c for c in off if c["id"] == "s0")["_geo"]
    s_on = next(c for c in on if c["id"] == "s0")["_geo"]
    assert (s_on["page"], s_on["row"]) <= (s_off["page"], s_off["row"])
    assert s_on["col"] == 39 and s_on["row"] == 5
    assert sorted(c["id"] for c in on) == sorted(c["id"] for c in off)


def test_photo_height_same_with_and_without_drawing(tmp_path):
    a = _draw_card("pa", tmp_path, drawing=False, width=26)
    b = _draw_card("pb", tmp_path, width=26)
    ga = layout(mk_doc([a]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    gb = layout(mk_doc([b]), T, base_dir=tmp_path)["cards"][0]["_geo"]
    assert gb["drawing"] and abs(ga["image"]["cy_emu"] - gb["image"]["cy_emu"]) <= 9525


def test_no_image_collapses_desc_rows(tmp_path):
    c1 = mk_card("n1", lines=0, image={"path": None, "status": "missing"})
    c2 = mk_card("n2", lines=0, image=None)
    c3 = mk_card("n3", lines=2, image={"path": "nope.png"})
    out = layout(mk_doc([c1, c2, c3]), T, base_dir=tmp_path)["cards"]
    assert [c["_geo"]["desc_rows"] for c in out] == [0, 0, 2]
    assert out[0]["_geo"]["height"] == 2 + 0 + 1 + 2 + 4
    assert out[2]["_warnings"]


def _wrap_card(txt="Có Phe Chặn Thép", n=20):
    cols = [{"key": "code"}, {"key": "d", "label": "d\nmm"}, {"key": "nap", "label": "Nắp"},
            {"key": "order"}, {"key": "price"}]
    c = mk_card("w", nrows=n, cols=cols)
    for r in c["rows"]:
        r["nap"] = "2RS"
    c["rows"][3]["nap"] = txt
    return c


def test_few_long_rows_wrap_instead_of_widening():
    from pl_layout import row_heights
    c = _wrap_card()
    T0 = load_theme({"table": {"wrap_rows_frac": 0}})
    assert choose_width(c, T0) == 26
    assert choose_width(c, T) == 17
    hs = row_heights(c, 17, T)
    assert hs[3] == 2 and sum(hs) == 21
    assert card_height(c, 3, T, 17) == card_height(c, 3, T0, 17) + 1
    out = layout(mk_doc([c]), T)["cards"][0]["_geo"]
    assert out["width"] == 17 and out["row_heights"] == hs and out["height"] == card_height(c, 3, T, 17)
    assert sum(out["spans"]) == 17


def test_too_many_long_rows_still_widen():
    c = _wrap_card()
    for i in range(0, 8):
        c["rows"][i]["nap"] = "Có Phe Chặn Thép"
    assert choose_width(c, T) == 26
