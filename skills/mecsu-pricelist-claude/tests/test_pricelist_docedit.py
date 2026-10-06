import json

import pytest

import pl_docedit
from pl_common import load_doc, save_doc
from test_pricelist_build import make_doc  # noqa: F401
from test_pricelist_build import img_path  # noqa: F401


@pytest.fixture
def docfile(tmp_path, img_path):
    doc = make_doc(tmp_path, img_path)
    doc["cards"][0]["title_source"] = "data"
    p = tmp_path / "doc.json"
    save_doc(doc, p)
    return p, doc["cards"][0]["id"], doc["cards"][1]["id"]


def w(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def test_applies_and_logs(tmp_path, docfile):
    p, c0, c1 = docfile
    e = w(tmp_path, "e1.json", [{"card": c0, "set": {"lines": ["Thép"], "note": "n"}, "source": "catalog"}])
    assert pl_docedit.main([str(p), e]) == 0
    c = {c["id"]: c for c in load_doc(p)["cards"]}[c0]
    assert c["lines"] == ["Thép"] and c["note"] == "n"
    assert "catalog" in (tmp_path / "edit_log.md").read_text(encoding="utf-8")


def test_refuses_data_title_unknown_card_and_bad_field(tmp_path, docfile, capsys):
    p, c0, c1 = docfile
    before = p.read_text(encoding="utf-8")
    for edits in ([{"card": c0, "set": {"title": "X"}}], [{"card": "nope", "set": {"note": "x"}}],
                  [{"card": c1, "set": {"rows": []}}]):
        assert pl_docedit.main([str(p), w(tmp_path, "e.json", edits)]) == 2
    assert p.read_text(encoding="utf-8") == before


def test_title_allowed_when_not_from_data(tmp_path, docfile):
    p, c0, c1 = docfile
    assert pl_docedit.main([str(p), w(tmp_path, "e.json", [{"card": c1, "set": {"title": "MỚI"}}])]) == 0


def test_conflict_between_files_exit_2(tmp_path, docfile, capsys):
    p, c0, c1 = docfile
    a = w(tmp_path, "a.json", [{"card": c1, "set": {"note": "A"}}])
    b = w(tmp_path, "b.json", [{"card": c1, "set": {"note": "B"}, "source": "s"}])
    before = p.read_text(encoding="utf-8")
    assert pl_docedit.main([str(p), a, b]) == 2
    assert "CONFLICT" in capsys.readouterr().out and p.read_text(encoding="utf-8") == before
