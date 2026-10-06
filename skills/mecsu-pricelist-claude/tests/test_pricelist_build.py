import copy
import pytest
from openpyxl import load_workbook
from PIL import Image as PILImage
from pl_common import load_theme
from pl_build import build


def geo(page, col, row, width, spans, desc_rows, nrows, image=None, cont=False, extra=0):
    return {"page": page, "col": col, "row": row, "width": width, "height": 2 + desc_rows + 1 + 2 + nrows + extra,
            "spans": spans, "desc_rows": desc_rows, "image": image, "cont": cont}


COLS = [{"key": "code", "label": "Mã Hãng"}, {"key": "len", "label": "Chiều Dài\n(mm)"},
        {"key": "order", "role": "order_code"}, {"key": "price", "role": "price"}]


def make_doc(tmp_path, img_path):
    img = {"col": 12, "row": 5, "col_off_emu": 0, "row_off_emu": 0, "cx_emu": 800000, "cy_emu": 500000}
    c1 = {"id": "a", "title": "KÌM ĐIỆN", "lines": ["Vật Liệu: Thép", "Tay Cầm Bọc Nhựa"], "legend": [],
          "note": None, "image": {"path": str(img_path)}, "columns": COLS,
          "rows": [{"code": "84-623", "len": 164.6, "order": 927517}, {"code": "84-035", "len": 193, "order": "0059504"}],
          "_geo": geo(0, 3, 5, 17, [4, 3, 5, 5], 3, 2, image=img)}
    c2 = {"id": "b", "title": "KÌM CẮT", "lines": ["Vật Liệu: Thép"], "legend": ["d: đường kính"], "note": "Ghi chú quan trọng",
          "image": None, "columns": COLS,
          "rows": [{"code": "84-124", "len": 4, "order": "0059516"}],
          "_geo": geo(0, 21, 5, 26, [6, 5, 8, 7], 3, 1, extra=2)}
    c3 = copy.deepcopy(c1)
    c3.update({"id": "a#2", "image": None, "rows": [{"code": "84-029", "len": 219.9, "order": "0059500"}]})
    c3["_geo"] = geo(1, 3, 5, 17, [4, 3, 5, 5], 3, 1, cont=True)
    return {"meta": {"brand": "STANLEY", "page_code": "STA", "title": "BẢNG GIÁ STANLEY",
                     "brand_logo": "assets/logos/stanley.png", "page_count": 2},
            "prices": [{"order_code": "0927517", "price": 145300}, {"order_code": "0059504", "price": "checking"},
                       {"order_code": "0059516", "price": 102600}, {"order_code": "0059500", "price": 167000}],
            "cards": [c1, c2, c3]}


@pytest.fixture
def img_path(tmp_path):
    p = tmp_path / "x.png"
    PILImage.new("RGBA", (80, 50), (200, 0, 0, 255)).save(p)
    return p


@pytest.fixture
def built(tmp_path, img_path):
    theme = load_theme()
    doc = make_doc(tmp_path, img_path)
    out = tmp_path / "o.xlsx"
    stats = build(doc, str(out), theme)
    return load_workbook(out), stats, theme


def test_frame_cells(built):
    wb, stats, theme = built
    ws = wb.worksheets[0]
    assert ws.title == theme["sheet1_name"]
    assert ws["S1"].value == "BẢNG GIÁ STANLEY"
    assert ws["AA77"].value == "STA - 01" and ws["AA154"].value == "STA - 02"
    assert ws["A75"].fill.fgColor.rgb == "FFFF0000"
    assert ws.column_dimensions["A"].width == pytest.approx(1.77734375)
    assert ws.row_dimensions[10].height == pytest.approx(10.35)
    assert "S1:AL3" in [str(r) for r in ws.merged_cells.ranges]
    assert stats["pages"] == 2 and stats["cards"] == 3


def test_page_breaks(built):
    ws = built[0].worksheets[0]
    assert [b.id for b in ws.row_breaks.brk] == [77]
    assert ws.page_setup.paperSize == 9 and ws.sheet_view.view == "pageLayout"


def find(ws, text):
    for row in ws.iter_rows():
        for c in row:
            if c.value == text:
                return c


def test_price_formula(built):
    ws = built[0].worksheets[0]
    o = find(ws, "0927517")
    p = ws.cell(o.row, o.column + 4 + 0)  # order span 5 -> price starts 5 cols later
    p = ws.cell(o.row, o.column + 5)
    assert p.value == f"=VLOOKUP({o.coordinate},Sheet2!$A:$B,2,0)"
    assert p.font.i and p.font.color.rgb == "FFFF0000" and p.number_format == "#,##0"


def test_order_code_text(built):
    ws = built[0].worksheets[0]
    o = find(ws, "0927517")
    assert o.number_format == "@" and o.font.b and o.data_type == "s"


def test_sheet2(built):
    wb = built[0]
    ws = wb["Sheet2"]
    assert [c.value for c in ws[1]][:2] == ["Mã Đặt Hàng", "varin_price"]
    rows = {r[0].value: r[1].value for r in ws.iter_rows(min_row=2)}
    assert rows["0927517"] == 145300 and rows["0059504"] == "checking" and len(rows) == 4


def test_logos_and_card_images(built):
    ws = built[0].worksheets[0]
    assert len(ws._images) >= 2 * 2 + 1


def test_card_structure(built):
    ws = built[0].worksheets[0]
    assert ws["C5"].value == "KÌM ĐIỆN" and ws["C5"].font.b and ws["C5"].font.sz == 9
    assert ws["D7"].value == "Vật Liệu: Thép"
    assert ws["C11"].value == "Mã Hãng" and ws["C11"].border.left.style == "thin"
    # legend after lines, note after data
    assert ws["V8"].value == "d: đường kính"
    n = find(ws, "Ghi chú quan trọng")
    assert n.font.i and n.font.b and n.border.bottom.style == "thin"


def test_missing_image_does_not_crash(tmp_path):
    theme = load_theme()
    doc = make_doc(tmp_path, tmp_path / "nope.png")
    doc["meta"]["brand_logo"] = "assets/logos/nope.png"
    (tmp_path / "bad.png").write_bytes(b"garbage")
    doc["cards"][1]["image"] = {"path": str(tmp_path / "bad.png")}
    doc["cards"][1]["_geo"]["image"] = dict(doc["cards"][0]["_geo"]["image"])
    stats = build(doc, str(tmp_path / "o.xlsx"), theme)
    assert len(stats["warnings"]) >= 2 and (tmp_path / "o.xlsx").exists()


def test_free_items(tmp_path, img_path):
    doc = make_doc(tmp_path, img_path)
    doc["free"] = [{"type": "text", "page": 1, "range": "AD11:AL13", "text": "hello", "style": {"bold": True}},
                   {"type": "shape", "page": 0, "range": "A1:B2"}]
    stats = build(doc, str(tmp_path / "o.xlsx"), load_theme())
    ws = load_workbook(tmp_path / "o.xlsx").worksheets[0]
    assert ws["AD88"].value == "hello"
    assert any("shape" in w for w in stats["warnings"])


def test_drawing_drawn_and_missing_warns(tmp_path, img_path):
    doc = make_doc(tmp_path, img_path)
    c = doc["cards"][0]
    c["drawing"] = {"path": str(img_path)}
    c["_geo"]["drawing"] = {"col": 14, "row": 8, "col_off_emu": 0, "row_off_emu": 0, "cx_emu": 500000, "cy_emu": 400000}
    st = build(doc, str(tmp_path / "o.xlsx"), load_theme())
    assert st["drawings"] == 1 and st["images"] == 1 and not st["warnings"]
    c["drawing"] = {"path": str(tmp_path / "nope.png")}
    st = build(doc, str(tmp_path / "o2.xlsx"), load_theme())
    assert st["drawings"] == 0 and any("drawing" in w for w in st["warnings"])


def test_wrapped_row_spans_two_sheet_rows(tmp_path, img_path):
    doc = make_doc(tmp_path, img_path)
    g = doc["cards"][0]["_geo"]
    g["row_heights"] = [2, 1]
    g["height"] += 1
    out = tmp_path / "w.xlsx"
    build(doc, str(out), load_theme())
    ws = load_workbook(out).worksheets[0]
    merged = {str(m) for m in ws.merged_cells.ranges}
    assert "C13:F13" not in merged and any(m.startswith("C13:") and m.endswith("14") for m in merged)
    assert ws["C13"].value == "84-623" and ws["C13"].alignment.wrap_text
    assert ws["C15"].value == "84-035" and not ws["C15"].alignment.wrap_text
    # borders on every cell of the wrapped row
    for r in (13, 14):
        assert ws.cell(r, 3).border.left.style == "thin"
