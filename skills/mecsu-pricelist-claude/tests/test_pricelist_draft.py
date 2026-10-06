from pl_common import validate_doc
from pl_draft import draft


def _items(n_rows=45, price=1000.0):
    return {"groups": [{
        "sheet": "S1", "name": "Vòng Bi Cầu Rãnh Sâu",
        "spec_columns": [{"key": "d_mm", "label": "d\nmm"}],
        "rows": [{"code": f"60{i:02d}", "order_code": f"{i:07d}", "price": price, "specs": {"d_mm": i}}
                 for i in range(n_rows)],
    }], "warnings": []}


def test_chunks_balanced_and_rows_kept():
    doc = draft(_items(45), "FBJ", "FBJ", max_rows=20)
    sizes = [len(c["rows"]) for c in doc["cards"]]
    assert sizes == [15, 15, 15] and sum(sizes) == 45
    assert len({c["id"] for c in doc["cards"]}) == 3
    assert doc["cards"][0]["title"] == "VÒNG BI CẦU RÃNH SÂU"
    validate_doc(doc)


def test_columns_order_and_prices():
    doc = draft(_items(3, 41300.0), "FBJ", "FBJ")
    keys = [c["key"] for c in doc["cards"][0]["columns"]]
    assert keys == ["code", "d_mm", "order", "price"]
    assert doc["prices"][0] == {"order_code": "0000000", "price": 41300}
    assert doc["cards"][0]["rows"][0]["order"] == "0000000"


def test_non_numeric_price_kept():
    doc = draft(_items(1, "checking"), "X", "XXX")
    assert doc["prices"][0]["price"] == "checking"


def test_skips_duplicates_and_empty_groups():
    items = _items(2)
    items["groups"].append({**items["groups"][0], "sheet": "S2",
                            "rows": [dict(r, dup=True) for r in items["groups"][0]["rows"]]})
    doc = draft(items, "FBJ", "FBJ")
    assert len(doc["cards"]) == 1 and len(doc["prices"]) == 2


def test_merge_across_sheets_and_content():
    a = _items(2)["groups"][0]
    a.update(lines=["L1"], legend=[], note=None, image="img/a.png", drawing=None)
    b = dict(a, sheet="S2", lines=["L1", "L2"], image=None,
             rows=[dict(r, order_code=f"9{i:06d}") for i, r in enumerate(a["rows"])])
    other = dict(a, sheet="S2", name="Khác", image="https://h/x.jpg",
                 rows=[dict(r, order_code=f"8{i:06d}") for i, r in enumerate(a["rows"])])
    doc = draft({"groups": [a, other, b], "warnings": []}, "X", "XXX")
    assert [c["title"] for c in doc["cards"]] == ["VÒNG BI CẦU RÃNH SÂU", "KHÁC"]
    c = doc["cards"][0]
    assert len(c["rows"]) == 4 and c["lines"] == ["L1", "L2"] and c["title_source"] == "data"
    assert c["image"] == {"path": "img/a.png", "status": "ok"}
    assert doc["cards"][1]["image"] == {"path": None, "status": "missing", "url": "https://h/x.jpg"}
    validate_doc(doc)


def test_draft_with_plan_end_to_end():
    from pl_analyze import analyze
    cols = [{"key": "d_mm", "label": "d\nmm"}, {"key": "D_mm", "label": "D\nmm"}]
    spec = {"6305": (25, 62), "608-2RS": (8, 22), "6204-2RS": (20, 47), "6004": (20, 42), "6203": (17, 40),
            "6003": (17, 35)}
    rows = [{"code": c, "order_code": f"{i:07d}", "price": 5.0, "specs": {"d_mm": d, "D_mm": D}}
            for i, (c, (d, D)) in enumerate(spec.items())]
    items = {"groups": [{"sheet": "S1", "name": "Vòng Bi Cầu", "spec_columns": cols, "rows": rows,
                         "lines": ["L1"], "legend": ["d: trong"], "note": "N", "image": "img/a.png"}],
             "warnings": []}
    doc = draft(items, "FBJ", "FBJ", plan=analyze(items))
    titles = [c["title"] for c in doc["cards"]]
    assert titles == ["VÒNG BI CẦU - LOẠI MINI", "VÒNG BI CẦU - DÒNG 6000", "VÒNG BI CẦU - DÒNG 6200",
                      "VÒNG BI CẦU - DÒNG 6300"]
    by = {c["title"]: [r["code"] for r in c["rows"]] for c in doc["cards"]}
    assert by["VÒNG BI CẦU - DÒNG 6000"] == ["6003", "6004"]  # d 17 before d 20
    assert by["VÒNG BI CẦU - DÒNG 6200"] == ["6203", "6204-2RS"]
    assert sorted(sum(by.values(), [])) == sorted(spec)  # row set unchanged
    c = doc["cards"][0]
    assert c["title_source"] == "data" and c["title_suffix_source"] == "family:bearing"
    assert c["lines"] == ["L1"] and c["legend"] == ["d: trong"] and c["note"] == "N" and c["image"]["path"] == "img/a.png"
    assert len({c["id"] for c in doc["cards"]}) == 4
    validate_doc(doc)


def test_family_default_legend_when_data_has_none():
    from pl_draft import _default_legend
    g = {"spec_columns": [{"key": "d_mm", "label": "d\nmm"}, {"key": "D_mm", "label": "D\nmm"},
                          {"key": "n", "label": "Nắp chắn"}]}
    defaults = {"d": "d: Đường Kính Trong", "D": "D: Đường Kính Ngoài", "B": "B: Độ Dày Vòng Bi"}
    assert _default_legend(g, defaults) == ["d: Đường Kính Trong", "D: Đường Kính Ngoài"]


def test_draft_description_split_sort_and_empty_columns():
    from test_pricelist_analyze import _dua_items
    from pl_analyze import analyze
    items = _dua_items()
    doc = draft(items, "BOSI", "BOS", plan=analyze(items))
    c0, c1 = doc["cards"]
    assert c0["title"] == "DŨA MÀI MẶT PHẲNG" and c0["title_source"] == "data"
    assert [r["code"] for r in c0["rows"]] == ["D3", "D2", "D1"] or [r["code"] for r in c0["rows"]][0] == "D3"
    assert [r["Rang"] if "Rang" in r else r["rang"] for r in c0["rows"]] == ["Trung Bình", "Mịn", "Thô"]
    keys0 = [c["key"] for c in c0["columns"]]
    assert keys0 == ["code", "len", "rang", "order", "price"]  # Tổng Chiều Dài empty -> dropped
    assert [c["key"] for c in c1["columns"]] == ["code", "len", "order", "price"]  # no variant here
    validate_doc(doc)


def test_brand_filter_and_warning():
    from test_pricelist_analyze import _dua_items
    items = _dua_items(("Bosi", "bosi", "Stanley", None))
    warns = []
    doc = draft(items, "BOSI", "BOS", brand_filter="BOSI", warnings=warns)
    codes = sorted(r["code"] for c in doc["cards"] for r in c["rows"])
    assert codes == ["D1", "D2", "D4"] and len(warns) == 1 and "1 rows" in warns[0]


def test_constant_spec_becomes_line_and_letters_stay():
    from pl_draft import _constant_specs_to_lines
    card = {"lines": [], "rows": [{"code": f"A{i}", "dv": "1/2", "s": i, "d": 5} for i in range(4)],
            "columns": [{"key": "code"}, {"key": "dv", "label": "Đầu Vuông\n(inch)", "role": "spec"},
                        {"key": "s", "label": "Size\n(mm)", "role": "spec"},
                        {"key": "d", "label": "d\nmm", "role": "spec"}, {"key": "order"}, {"key": "price"}]}
    _constant_specs_to_lines(card)
    assert card["lines"] == ["Đầu Vuông: 1/2 Inch"]
    assert [c["key"] for c in card["columns"]] == ["code", "s", "d", "order", "price"]
