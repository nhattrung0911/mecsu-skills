import pytest

from pl_patch import apply_patches


def _items():
    return {"groups": [{"name": "Tuýp", "brand": None, "spec_columns": [
        {"key": "Size", "label": "Size\n(inch)"}, {"key": "Chiều_Dài", "label": "Chiều Dài\n(mm)"}],
        "rows": [{"code": "BS1", "brand": None, "specs": {"Size": "1/2", "Chiều_Dài": 10}}]},
        {"name": "Búa", "brand": "Bosi", "spec_columns": [{"key": "W", "label": "Trọng Lượng\n(lbs)"}],
         "rows": [{"code": "BS2", "brand": "Bosi", "specs": {"W": None}}]}]}


def test_rename_keeps_unit_and_set_spec_and_brand():
    items, log = apply_patches(_items(), [
        {"op": "rename_label", "group": "Tuýp", "from": "Size", "to": "Đầu Vuông", "source": "catalog"},
        {"op": "rename_label", "group": "Tuýp", "from": "Chiều Dài", "to": "Size", "source": "catalog"},
        {"op": "set_brand", "group": "Tuýp", "brand": "Bosi", "source": "catalog"},
        {"op": "set_spec", "code": "BS2", "label": "Trọng Lượng", "value": 20, "source": "title 20LB"}])
    g0, g1 = items["groups"]
    assert [c["label"] for c in g0["spec_columns"]] == ["Đầu Vuông\n(inch)", "Size\n(mm)"]
    assert g0["brand"] == "Bosi" and g0["rows"][0]["brand"] == "Bosi"
    assert g1["rows"][0]["specs"]["W"] == 20 and len(log) == 4


def test_patch_needs_source_and_must_match():
    with pytest.raises(ValueError):
        apply_patches(_items(), [{"op": "set_spec", "code": "BS2", "label": "Trọng Lượng", "value": 1}])
    with pytest.raises(ValueError):
        apply_patches(_items(), [{"op": "set_spec", "code": "NOPE", "label": "X", "value": 1, "source": "s"}])


def test_set_spec_strips_same_unit_and_refuses_other(tmp_path):
    items, _ = apply_patches(_items(), [{"op": "set_spec", "code": "BS2", "label": "Trọng Lượng",
                                         "value": "20 lb", "source": "s"}])
    assert items["groups"][1]["rows"][0]["specs"]["W"] == 20 and isinstance(items["groups"][1]["rows"][0]["specs"]["W"], int)
    items, _ = apply_patches(_items(), [{"op": "set_spec", "code": "BS1", "label": "Chiều Dài",
                                         "value": "12.5mm", "source": "s"}])
    assert items["groups"][0]["rows"][0]["specs"]["Chiều_Dài"] == 12.5
    items, _ = apply_patches(_items(), [{"op": "set_spec", "code": "BS1", "label": "Size", "value": "1/2", "source": "s"}])
    assert items["groups"][0]["rows"][0]["specs"]["Size"] == "1/2"  # not numeric: untouched
    with pytest.raises(ValueError, match="unit mismatch"):
        apply_patches(_items(), [{"op": "set_spec", "code": "BS2", "label": "Trọng Lượng", "value": "9 kg",
                                  "source": "s"}])


def test_cli_exit_2_on_unit_mismatch(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    (tmp_path / "i.json").write_text(json.dumps(_items()), encoding="utf-8")
    (tmp_path / "p.json").write_text(json.dumps([{"op": "set_spec", "code": "BS2", "label": "Trọng Lượng",
                                                  "value": "9 kg", "source": "s"}]), encoding="utf-8")
    script = Path(__file__).resolve().parent.parent / "scripts" / "pl_patch.py"
    r = subprocess.run([sys.executable, str(script), str(tmp_path / "i.json"), str(tmp_path / "p.json")],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 2 and "unit mismatch" in r.stdout
