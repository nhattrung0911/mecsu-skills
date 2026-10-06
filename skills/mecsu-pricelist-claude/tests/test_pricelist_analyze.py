import pytest

from pl_analyze import (analyze, bearing_series, load_families, match_family, num_key, plan_md, resolve_sort,
                        sort_rows, split_rows)

SERIES = [
    ("6204-2RS", "DÒNG 6200"), ("16005", "DÒNG 16000"), ("62304-2RS", "DÒNG 62300"),
    ("60/28", "DÒNG 6000"), ("62/28", "DÒNG 6200"), ("608-2RS", "LOẠI MINI"), ("629-ZZ", "LOẠI MINI"),
    ("6803-2RS", "DÒNG 6800"), ("NU205", "DÒNG NU200"), ("SKF 6305", "DÒNG 6300"), ("junk", None),
]


@pytest.mark.parametrize("code,label", SERIES)
def test_bearing_series(code, label):
    r = bearing_series(code)
    assert (r[1] if r else None) == label


def test_sort_parsing():
    vals = ['1/2"', "3/8", "6x7", "6x5", "0.25-6", "10", "abc", "", None, "1 1/2", 7]
    out = sorted(vals, key=num_key)
    keys = [num_key(v)[:3] for v in ["3/8", '1/2"', "0.25-6", "6x7", "1 1/2"]]
    assert keys == [(0, 0.375, 0.0), (0, 0.5, 0.0), (0, 0.25, 6.0), (0, 6.0, 7.0), (0, 1.5, 0.0)]
    assert [str(v) for v in out] == ["0.25-6", "3/8", '1/2"', "1 1/2", "6x5", "6x7", "7", "10", "abc", "", "None"]


def _rows(codes, d=None):
    return [{"code": c, "order_code": f"{i:07d}", "price": 1.0, "specs": {"d_mm": (d or {}).get(c, i)}}
            for i, c in enumerate(codes)]


def test_split_bearing_order():
    sub = split_rows({"type": "bearing_series"}, _rows(["6304", "xx", "6204", "608", "16005", "6004", "6203"]), [])
    assert [(s["key"], [r["code"] for r in s["rows"]]) for s in sub] == [
        ("mini", ["608"]), ("60", ["6004"]), ("62", ["6204", "6203"]), ("63", ["6304"]), ("160", ["16005"]),
        ("other", ["xx"])]


def test_split_column_and_regex():
    cols = [{"key": "dr", "label": "Đầu Vuông"}]
    rows = [{"code": "a", "specs": {"dr": 0.5}}, {"code": "b", "specs": {"dr": '1/4"'}},
            {"code": "c", "specs": {"dr": 0.5}}]
    sub = split_rows({"type": "column", "column_any": ["đầu vuông"], "label": "ĐẦU {value}"}, rows, cols)
    assert [(s["label"], len(s["rows"])) for s in sub] == [("ĐẦU 0.5", 2), ('ĐẦU 1/4"', 1)]
    sub = split_rows({"type": "regex", "pattern": r"^(\w\w)"}, [{"code": "AB12", "specs": {}}], [])
    assert sub[0]["label"] == "DÒNG AB"


def test_sort_rows_multi_key():
    cols = [{"key": "d_mm", "label": "d\nmm"}, {"key": "D_mm", "label": "D\nmm"}]
    rows = [{"code": "6204", "specs": {"d_mm": 20, "D_mm": 47}}, {"code": "6003", "specs": {"d_mm": 17, "D_mm": 35}},
            {"code": "6203", "specs": {"d_mm": 17, "D_mm": 40}}, {"code": "6200", "specs": {"d_mm": 10, "D_mm": 30}}]
    labels, miss = resolve_sort([r"^d\b", r"^D\b", r"^B\b"], cols)
    assert labels == ["d\nmm", "D\nmm"] and miss == [r"^B\b"]
    assert [r["code"] for r in sort_rows(rows, labels, cols)] == ["6200", "6003", "6203", "6204"]


def test_families_match():
    fams = load_families()
    assert match_family("Vòng Bi Cầu Rãnh Sâu", fams)[0]["name"] == "bearing"
    assert match_family("Kìm Điện", fams)[0]["name"] == "kim"
    assert match_family("Đầu Tuýp 1/2", fams)[0]["name"] == "dau-tuyp"
    assert match_family("Thước Cuộn", fams) == (fams[-1], False)


def _items():
    cols = [{"key": "d_mm", "label": "d\nmm"}, {"key": "D_mm", "label": "D\nmm"}, {"key": "B_mm", "label": "B\nmm"}]
    codes = ["6305", "608-2RS", "6204-2RS", "6004", "6203"]
    rows = _rows(codes)
    for r, d in zip(rows, [25, 8, 20, 20, 17]):
        r["specs"] = {"d_mm": d, "D_mm": d * 2, "B_mm": 9}
    thuoc = [{"key": "size", "label": "Size (mm)"}]
    return {"groups": [
        {"sheet": "S1", "name": "Vòng Bi", "spec_columns": cols, "rows": rows},
        {"sheet": "S2", "name": "Thước", "spec_columns": thuoc,
         "rows": [{"code": f"T{i}", "order_code": f"9{i:06d}", "price": 1.0, "specs": {"size": 10 - i}}
                  for i in range(45)]},
    ], "warnings": []}


def test_analyze_fixture():
    plan = analyze(_items())
    b, t = plan["groups"]
    assert b["family"] == "bearing" and b["sort"] == ["d\nmm", "D\nmm", "B\nmm"] and b["flags"] == []
    assert [s["label"] for s in b["subgroups"]] == ["LOẠI MINI", "DÒNG 6000", "DÒNG 6200", "DÒNG 6300"]
    assert b["subgroups"][2]["codes_preview"] == ["6204-2RS", "6203"]
    assert t["family"] == "default" and t["split"] is None and t["sort"] == ["Size (mm)"]
    assert any("no family rule" in f for f in t["flags"]) and any("large group" in f for f in t["flags"])
    assert "DÒNG 6200" in plan_md(plan)


def _dua_items(brands=("Bosi", "Bosi", "Bosi", "Bosi")):
    cols = [{"key": "len", "label": "Chiều Dài Lưỡi"}, {"key": "tong", "label": "Tổng Chiều Dài"}]
    data = [("D1", "Dũa Mài Mặt Phẳng Răng Thô", "10 inch"), ("D2", "Dũa Mài Mặt Phẳng Răng Mịn", "10 inch"),
            ("D3", "Dũa Mài Mặt Phẳng Răng Trung Bình", "8 inch"), ("D4", "Dũa Mài Tam Giác", "6 inch")]
    rows = [{"code": c, "order_code": f"{i:07d}", "price": 1.0, "brand": b, "desc_clean": d,
             "specs": {"len": ln, "tong": None}} for i, ((c, d, ln), b) in enumerate(zip(data, brands))]
    return {"groups": [{"sheet": "S", "name": "Dũa", "category": "Dũa", "spec_columns": cols, "rows": rows}],
            "warnings": []}


def test_description_split_and_variant_column():
    plan = analyze(_dua_items())
    g = plan["groups"][0]
    assert g["family"] == "dua" and g["split"]["type"] == "description"
    assert [(s["title"], s["count"]) for s in g["subgroups"]] == [("DŨA MÀI MẶT PHẲNG", 3), ("DŨA MÀI TAM GIÁC", 1)]
    assert g["sort"] == ["Chiều Dài Lưỡi", "Tổng Chiều Dài", "Răng"] or g["sort"][0] == "Chiều Dài Lưỡi"
    assert "DŨA MÀI MẶT PHẲNG" in plan_md(plan)


def test_family_matches_category():
    fams = load_families()
    assert match_family("Hàng X", fams, "Búa Tạ")[0]["name"] == "bua"
    assert match_family("Hàng X", fams, None)[1] is False


def test_brands_flag():
    plan = analyze(_dua_items(("Bosi", "Bosi", "Stanley", None)))
    assert plan["brands"] == ["Bosi", "Stanley"] and "multiple brands" in plan["flags"][0]
    assert "multiple brands" in plan_md(plan)
    assert analyze(_dua_items())["flags"] == []


def test_sort_value_order():
    cols = [{"key": "r", "label": "Răng"}]
    rows = [{"code": c, "specs": {"r": v}} for c, v in (("a", "Thô"), ("b", "Mịn"), ("c", "Trung Bình"))]
    out = sort_rows(rows, ["Răng"], cols, {"Răng": ["Mịn", "Trung Bình", "Thô"]})
    assert [r["code"] for r in out] == ["b", "c", "a"]
