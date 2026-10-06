import copy

import pytest

from pl_lint import fix_label, lint


def _card(**kw):
    c = {"id": "c1", "title": "KÌM ĐIỆN", "lines": ["Vật Liệu: Thép"], "legend": [],
         "image": {"path": "img/x.png", "status": "ok"},
         "columns": [{"key": "code"}, {"key": "len", "label": "Chiều Dài\n(mm)"}, {"key": "order"}, {"key": "price"}],
         "rows": [{"code": "84-623", "len": 164.6, "order": "0120316"}]}
    c.update(kw)
    return c


def _doc(*cards):
    return {"meta": {"brand": "X", "page_code": "XX"}, "cards": list(cards)}


def test_clean_doc_passes():
    assert lint(_doc(_card())) == {"errors": [], "warnings": []}


@pytest.mark.parametrize("raw,want", [
    ("Chiều Dài mm", "Chiều Dài\n(mm)"),
    ("Chiều Dài (Inch)", "Chiều Dài\n(inch)"),
    ("Chiều Dài\nmm", "Chiều Dài\n(mm)"),
    ("Lực Siết (Nm)", "Lực Siết\n(N.m)"),
    ("d mm", "d\nmm"),
    ("d\nmm", "d\nmm"),
    ("L (mm)", "L\n(mm)"),
    ("Số Chi Tiết", "Số Chi Tiết"),
    ("Bấm Cos", "Bấm Cos"),
])
def test_fix_label(raw, want):
    assert fix_label(raw) == want


def test_errors_detected():
    bad = _card(title="Kìm điện " + "x" * 40, lines=["a" * 30] * 6,
                columns=[{"key": "len", "label": "Chiều Dài mm"}, {"key": "code"}, {"key": "order"}, {"key": "price"}],
                rows=[{"code": "", "len": 1, "order": "123"}])
    errs = " | ".join(lint(_doc(bad))["errors"])
    for frag in ("not UPPERCASE", "chars > 40", "lines > 5", "line > 28", "columns must be",
                 "label unit style", "not 7 digits", "empty Mã Hãng"):
        assert frag in errs


def test_letter_label_needs_legend():
    c = _card(columns=[{"key": "code"}, {"key": "L", "label": "L\n(mm)"}, {"key": "order"}, {"key": "price"}],
              rows=[{"code": "a", "L": 1, "order": "0000001"}])
    assert any("no legend" in e for e in lint(_doc(c))["errors"])
    c["legend"] = ["L: Chiều Dài Kìm"]
    assert lint(_doc(c))["errors"] == []


def test_fix_makes_doc_clean():
    c = _card(title=" kìm điện. ", lines=["Vật Liệu: Thép. "],
              columns=[{"key": "code"}, {"key": "len", "label": "Chiều Dài mm"}, {"key": "order"}, {"key": "price"}])
    doc = _doc(c)
    lint(doc, fix=True)
    assert doc["cards"][0]["title"] == "KÌM ĐIỆN"
    assert doc["cards"][0]["lines"] == ["Vật Liệu: Thép"]
    assert lint(doc)["errors"] == []


def test_duplicate_order_across_cards_and_synonyms():
    a = _card()
    b = copy.deepcopy(_card(id="c2", title="KÌM CẮT",
                            columns=[{"key": "code"}, {"key": "L", "label": "L\n(mm)"}, {"key": "order"}, {"key": "price"}],
                            legend=["L: Chiều Dài"]))
    b["rows"] = [{"code": "x", "L": 1, "order": "0120316"}]
    res = lint(_doc(a, b))
    assert any("also in c1" in e for e in res["errors"])
    assert any("synonyms" in w for w in res["warnings"])
    b["title"] = "KÌM ĐIỆN"
    assert any("duplicate title" in e for e in lint(_doc(a, b))["errors"])


def test_continuation_chunk_exempt_from_image_and_legend():
    c = _card(id="c1#2", image=None,
              columns=[{"key": "code"}, {"key": "L", "label": "L\n(mm)"}, {"key": "order"}, {"key": "price"}],
              rows=[{"code": "a", "L": 1, "order": "0000002"}])
    assert lint(_doc(c)) == {"errors": [], "warnings": []}


def test_stress_rules():
    c = _card(title="KHÔNG TIÊU ĐỀ", lines=["S: Kích Thước", "6"],
              columns=[{"key": "code"}, {"key": "S", "label": "S\n(mm)"}, {"key": "order"}, {"key": "price"}],
              legend=["S: Kích Thước (in)"], rows=[{"code": "a", "S": 1, "order": "0000003"}])
    res = lint(_doc(c))
    errs, warns = " | ".join(res["errors"]), " | ".join(res["warnings"])
    assert "placeholder" in errs and "legend-like" in errs and "junk" in errs
    assert "legend unit (in) != column unit (mm)" in warns
    c2 = _card(id="c9", title="VẬT LIỆU: NHÔM", lines=[])
    res2 = lint(_doc(c2))
    assert any("':'" in e for e in res2["errors"]) and any("no description lines" in w for w in res2["warnings"])


def test_fix_strips_bullets():
    c = _card(lines=["*Màn Hình LCD"])
    doc = _doc(c)
    lint(doc, fix=True)
    assert doc["cards"][0]["lines"] == ["Màn Hình LCD"]


def test_symbols_drawing_and_case():
    cols = [{"key": "code"}, {"key": "a", "label": "AVM"}, {"key": "p", "label": "Φ\n(mm)"},
            {"key": "order"}, {"key": "price"}]
    c = _card(columns=cols, legend=["AVM: Dòng Điện Xoay Chiều", "Φ: Đường Kính"],
              rows=[{"code": "x", "a": 1, "p": 2, "order": "0000004"}])
    assert lint(_doc(c))["errors"] == []
    c["legend"] = ["Avm: Dòng Điện", "Φ: Đường Kính"]
    assert any("case differs" in e for e in lint(_doc(c))["errors"])
    c["legend"] = []
    assert any("no legend" in e for e in lint(_doc(c))["errors"])
    c["drawing"] = {"path": "img/d.png", "status": "ok"}
    assert lint(_doc(c))["errors"] == []


def test_short_words_are_not_symbols():
    from pl_lint import _is_symbol
    assert all(_is_symbol(t) for t in ["d", "D", "C₀", "AVM", "ØQ", "Φ", "SW", "AVm"])
    assert not any(_is_symbol(t) for t in ["Phe", "Cao", "Size", "Cán", "Avm"])
    cols = [{"key": "code"}, {"key": "p", "label": "Phe"}, {"key": "order"}, {"key": "price"}]
    c = _card(columns=cols, rows=[{"code": "x", "p": "Trong", "order": "0000005"}])
    assert lint(_doc(c))["errors"] == []


def test_data_titles_duplicate_with_other_columns_is_warning():
    a = _card(title_source="data")
    b = _card(id="c2", title_source="data",
              columns=[{"key": "code"}, {"key": "w", "label": "Nặng\n(kg)"}, {"key": "order"}, {"key": "price"}],
              rows=[{"code": "x", "w": 1, "order": "0000009"}])
    res = lint(_doc(a, b))
    assert res["errors"] == [] and any("from data" in w for w in res["warnings"])
    b2 = _card(id="c3", title_source="data", rows=[{"code": "y", "len": 1, "order": "0000010"}])
    assert any("duplicate title" in e for e in lint(_doc(a, b2))["errors"])


def test_size_description_line_is_not_legend_like():
    ok = lint(_doc(_card(lines=["Size: 1/2 Inch"])))
    assert not any("legend-like" in e for e in ok["errors"])
    bad = lint(_doc(_card(lines=["d: Đường Kính Trong"])))  # real dimension symbol -> still flagged
    assert any("legend-like" in e for e in bad["errors"])
