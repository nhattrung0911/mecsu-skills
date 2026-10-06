import json
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest

from pl_read import read_items

HDR = ["Mã Hãng", "Tên Bảng Giá", "Order ID", "Varin Price", "d\nmm", "D\nmm", "B\nmm", "Nắp chắn"]


@pytest.fixture
def mini_data(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(HDR)
    ws.append(["625-2RS ", "Vòng Bi A ", 927517, 5200, 5, 16, 5, "2 Phớt "])
    ws.append(["626-2RS", "Vòng Bi A", "0927518", 5500, 6, 19, 6, "2 Phớt"])
    ws.append(["607-2RS", "Vòng Bi A", "927513", None, 20, 9, 16, "2 Phớt"])
    ws.append(["X1", "Vòng Bi B", "927599", "checking", 1, 2, 3, None])
    ws.append([None, None, None, None, None, None, None, None])
    ws2 = wb.create_sheet("Sheet2")
    ws2.append(HDR)
    ws2.append(["Y1", "Vòng Bi C", "927600.0", 100, 1, 2, 3, "x"])
    p = tmp_path / "mini.xlsx"
    wb.save(p)
    return str(p)


def test_strips_and_groups(mini_data):
    items = read_items(mini_data)
    gs = items["groups"]
    assert [(g["sheet"], g["name"]) for g in gs] == [("Sheet1", "Vòng Bi A"), ("Sheet1", "Vòng Bi B"), ("Sheet2", "Vòng Bi C")]
    assert gs[0]["rows"][0]["code"] == "625-2RS"
    assert gs[0]["rows"][0]["specs"]["Nắp_chắn"] == "2 Phớt"
    assert gs[0]["spec_columns"][0] == {"key": "d_mm", "label": "d\nmm"}
    assert [c["key"] for c in gs[0]["spec_columns"]] == ["d_mm", "D_mm", "B_mm", "Nắp_chắn"]


def test_order_code_padded(mini_data):
    items = read_items(mini_data)
    codes = [r["order_code"] for g in items["groups"] for r in g["rows"]]
    assert "0927517" in codes and "0927600" in codes and all(len(c) == 7 for c in codes)


def test_warns_d_ge_D(mini_data):
    w = read_items(mini_data)["warnings"]
    assert any("607-2RS" in x and "d" in x for x in w)


def test_warns_missing_price(mini_data):
    items = read_items(mini_data)
    w = items["warnings"]
    assert any("607-2RS" in x and "price" in x.lower() for x in w)
    assert items["groups"][0]["rows"][2]["price"] is None
    assert items["groups"][1]["rows"][0]["price"] == "checking"
    assert any("X1" in x and "price" in x.lower() for x in w)


def test_cli_writes_json(mini_data, tmp_path):
    out = tmp_path / "items.json"
    script = Path(__file__).resolve().parent.parent / "scripts" / "pl_read.py"
    r = subprocess.run([sys.executable, str(script), mini_data, "-o", str(out)], capture_output=True)
    assert r.returncode == 0
    assert len(json.loads(out.read_text(encoding="utf-8"))["groups"]) == 3


def test_warns_duplicate_order_and_B_ge_D(tmp_path):
    import openpyxl
    p = tmp_path / "dup.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR)
    ws.append(["607-2RS", "A", "0927513", 1, 7, 9, 16, "x"])
    ws2 = wb.create_sheet("Sheet2")
    ws2.append(HDR)
    ws2.append(["607-2RS", "A", "0927513", 1, 7, 19, 6, "x"])
    wb.save(p)
    items = read_items(str(p))
    w = " | ".join(items["warnings"])
    assert "duplicate order id 0927513" in w and "B (16) >= D (9)" in w
    assert [r["dup"] for g in items["groups"] for r in g["rows"]] == [False, True]


def test_optional_columns(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Mã Hãng", "Tên Bảng Giá", "Order ID", "Varin Price", "d\nmm",
               "mô tả 1 ", "Dòng Mô Tả 2", "Mo Ta 3", "Chú Giải", "Ghi Chú", "Ảnh", "Bản Vẽ"])
    ws.append(["A", "N", "1000001", 1, 5, "L1", "L2", "L1", "C1", None, None, "d.png"])
    ws.append(["B", "N", "1000002", 1, 6, None, "L2x", None, None, "note", "http://x/y.jpg", None])
    p = tmp_path / "o.xlsx"
    wb.save(p)
    g = read_items(str(p))["groups"][0]
    assert [c["key"] for c in g["spec_columns"]] == ["d_mm"]
    assert g["lines"] == ["L1", "L2", "L2x"]
    assert g["legend"] == ["C1"] and g["note"] == "note"
    assert g["image"] == "http://x/y.jpg" and g["drawing"] == "d.png"
    assert g["rows"][1]["image"] == "http://x/y.jpg" and g["rows"][0]["image"] is None


def test_optional_defaults(mini_data):
    g = read_items(mini_data)["groups"][0]
    assert g["lines"] == [] and g["legend"] == [] and g["note"] is None and g["image"] is None and g["drawing"] is None


def _book(tmp_path, name, header, rows, title="Sheet1"):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title
    ws.append(header)
    for r in rows:
        ws.append(r)
    p = tmp_path / name
    wb.save(p)
    return str(p)


H2 = ["mã hãng", "part_description", "cate", "order_id", "varin_price", "Brand", "Trọng lượng", "Tổng Chiều Dài", "Trống"]


def test_aliases_group_fallbacks_and_multifile(tmp_path):
    a = _book(tmp_path, "a.xlsx", H2, [["B1", "Búa 2LB Bosi B1", "Búa", 1000001, 91999.9999973, "Bosi", "2 lbs", None, None]])
    b = _book(tmp_path, "b.xlsx", ["Code", "Order ID", "Price"], [["Z1", "1000002", 5]], title="Kìm")
    items = read_items([a, b])
    g1, g2 = items["groups"]
    assert g1["name"] == "Búa" and g1["category"] == "Búa" and g1["brand"] == "Bosi" and g1["file"] == "a.xlsx"
    assert g2["name"] == "Kìm" and g2["brand"] is None
    assert items["brands"] == {"Bosi": 1}
    r = g1["rows"][0]
    assert r["price"] == 92000 and r["brand"] == "Bosi" and r["desc"] == "Búa 2LB Bosi B1"
    assert r["desc_clean"] == "Búa"
    assert not any("price" in w for w in items["warnings"])


def test_unit_lifting_and_empty_columns(tmp_path):
    p = _book(tmp_path, "u.xlsx", H2, [
        ["A1", "x", "C", 1000001, 1, "Bosi", "2 lbs", None, None],
        ["A2", "x", "C", 1000002, 1, "Bosi", "3 LB", "1/2 inch", None]])
    g = read_items(p)["groups"][0]
    assert [c["label"] for c in g["spec_columns"]] == ["Trọng Lượng\n(lbs)", "Tổng Chiều Dài\n(inch)"]
    assert g["rows"][0]["specs"] == {"Trọng_lượng": 2, "Tổng_Chiều_Dài": None}
    assert g["rows"][1]["specs"]["Tổng_Chiều_Dài"] == "1/2" and g["rows"][1]["specs"]["Trọng_lượng"] == 3
    assert "Trống" not in g["rows"][0]["specs"]


def test_mixed_units_not_lifted(tmp_path):
    p = _book(tmp_path, "m.xlsx", ["mã hãng", "order id", "varin price", "S"], [
        ["A1", 1000001, 1, "2 mm"], ["A2", 1000002, 1, "3 kg"]])
    g = read_items(p)["groups"][0]
    assert g["spec_columns"][0]["label"] == "S" and g["rows"][0]["specs"]["S"] == "2 mm"


def test_desc_clean_variants(tmp_path):
    p = _book(tmp_path, "d.xlsx", ["mã hãng", "mô tả sản phẩm", "order id", "varin price", "brand", "Dài", "Kính", "Cỡ"], [
        ["BS1", "Dũa Ø3x140 mm Bosi BS1", 1000001, 1, "Bosi", "140 mm", "3 mm", None],
        ["BS2", "Búa 10LB Dài 877 mm bosi BS2", 1000002, 1, "Bosi", "877 mm", None, "10 lbs"],
        ["BS3", "Tuýp 10 Inch Hai Màu", 1000003, 1, None, None, None, "10 inch"]])
    rows = read_items(p)["groups"][0]["rows"]
    assert [r["desc_clean"] for r in rows] == ["Dũa", "Búa", "Tuýp Hai Màu"]


def test_quality_warnings(tmp_path):
    rows = [["A1", "Búa 20LB Bosi A1", "C", 1000001, 1, "Bosi", "2 lbs", None, None],
            ["A2", "Búa 20LB Bosi A2", "C", 1000002, 1, "Bosi", None, "900 mm", None],
            ["A3", "Dũa Bosi A3", "C", 1000003, 1, "Bosi", "5 lbs", None, None],
            ["A4", "Dũa Bosi A4", "C", 1000004, 1, "Bosi", "5 lbs", None, None]]
    w = read_items(_book(tmp_path, "q.xlsx", H2, rows))["warnings"]
    assert any("A2" in x and "spec missing but description says 20 lbs" in x for x in w)
    assert not any("A1" in x and "spec missing" in x for x in w)  # 20LB vs 2 lbs: column filled, still flagged? see below
    assert any("A3" in x and "A4" in x and "identical" in x for x in w)


def test_desc_clean_keeps_text_spec_strips_measurements(tmp_path):
    p = _book(tmp_path, "t.xlsx", ["mã hãng", "mô tả sản phẩm", "order id", "varin price", "brand", "Phân Loại", "Trọng lượng"], [
        ["BS9", "Búa Tạ Cán 20LB Dài 920 mm 1/2 inch 3\" Bosi BS9", 1000001, 1, "Bosi", "Búa Tạ", None]])
    assert read_items(p)["groups"][0]["rows"][0]["desc_clean"] == "Búa Tạ Cán"
