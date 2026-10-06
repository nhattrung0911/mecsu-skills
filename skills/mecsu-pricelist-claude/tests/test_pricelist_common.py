import pytest
from jsonschema import ValidationError

from pl_common import abs_row, col_index, col_letter, load_theme, norm_order_code, validate_doc


def test_col_roundtrip():
    assert col_letter(1) == "A" and col_letter(56) == "BD" and col_index("AY") == 51
    assert all(col_index(col_letter(i)) == i for i in range(1, 200))


def test_abs_row():
    t = load_theme()
    assert abs_row(t, 0, 1) == 1 and abs_row(t, 2, 77) == 231


def test_norm_order_code():
    assert norm_order_code(927517) == "0927517"
    assert norm_order_code(927517.0) == "0927517"
    assert norm_order_code(" 0927517 ") == "0927517"
    assert norm_order_code("927517.0") == "0927517"
    assert norm_order_code("abc") is None and norm_order_code(None) is None
    assert norm_order_code("12345678") is None


def test_theme_has_core_keys():
    t = load_theme()
    for k in ("page", "fonts", "colors", "header", "footer", "lanes", "card", "table", "image"):
        assert k in t


def test_theme_override_deep_merge():
    t = load_theme({"card": {"vat_text": "VAT: 10%"}})
    assert t["card"]["vat_text"] == "VAT: 10%" and t["card"]["gap_rows"] == 1


def test_schema_rejects_bad_order_code():
    doc = {"meta": {"brand": "X", "page_code": "X"}, "cards": [], "prices": [{"order_code": "123"}]}
    with pytest.raises(ValidationError):
        validate_doc(doc)


def test_column_role_and_label():
    from pl_common import column_label, column_role
    t = load_theme()
    assert column_role({"key": "code"}) == "code"
    assert column_role({"key": "order"}) == "order_code"
    assert column_role({"key": "len_mm"}) == "spec"
    assert column_role({"key": "x", "role": "price"}) == "price"
    assert column_label({"key": "price"}, t) == "Giá/Cái\nChưa VAT"
    assert column_label({"key": "len_mm", "label": "L (mm)"}, t) == "L (mm)"


def test_user_home_env_and_default(monkeypatch, tmp_path):
    from pathlib import Path
    from pl_common import user_home
    monkeypatch.setenv("MECSU_PRICELIST_HOME", str(tmp_path))
    assert user_home() == tmp_path
    monkeypatch.delenv("MECSU_PRICELIST_HOME")
    assert user_home() == Path.home() / ".mecsu-pricelist"


def test_resolve_path_order(monkeypatch, tmp_path):
    from pl_common import SKILL_DIR, resolve_path
    home, doc_dir = tmp_path / "home", tmp_path / "doc"
    (home / "logos").mkdir(parents=True)
    doc_dir.mkdir()
    monkeypatch.setenv("MECSU_PRICELIST_HOME", str(home))
    (home / "logos" / "x.png").write_bytes(b"h")
    assert resolve_path("logos/x.png", doc_dir) == home / "logos" / "x.png"  # home before skill
    (doc_dir / "logos").mkdir()
    (doc_dir / "logos" / "x.png").write_bytes(b"d")
    assert resolve_path("logos/x.png", doc_dir) == doc_dir / "logos" / "x.png"  # doc dir wins
    assert resolve_path("assets/logos/bsi.png", doc_dir) == SKILL_DIR / "assets" / "logos" / "bsi.png"
    assert resolve_path(str(tmp_path / "abs.png"), doc_dir) == tmp_path / "abs.png"
