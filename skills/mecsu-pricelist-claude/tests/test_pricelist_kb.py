import json
import subprocess
import sys
from pathlib import Path

import pytest

import pl_kb

SCRIPT = Path(pl_kb.__file__)


def _card(cid, codes, title="T", **kw):
    c = {"id": cid, "title": title,
         "columns": [{"key": "code"}, {"key": "size"}, {"key": "order"}, {"key": "price"}],
         "rows": [{"code": x, "size": i, "order": f"{1000000 + i:07d}"} for i, x in enumerate(codes)]}
    c.update(kw)
    return c


def _write_doc(dirp, cards, name="doc.json"):
    doc = {"meta": {"brand": "BOSI", "page_code": "BSI"}, "prices": [], "cards": cards}
    p = dirp / name
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return p


def _read(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


@pytest.fixture
def kbdir(tmp_path):
    return tmp_path / "kb"


def _learn(kbdir, doc, status="review", **kw):
    return pl_kb.learn(doc, "BSI", status, kbdir, **kw)


def test_learn_then_apply_roundtrip(tmp_path, kbdir):
    (tmp_path / "a.png").write_bytes(b"png")
    d1 = _write_doc(tmp_path, [_card("c1", ["A1", "A2"], title="KÌM BẤM COS", lines=["L1"], legend=["d: x"],
                                     image={"path": "a.png", "status": "ok"})])
    _learn(kbdir, d1, sources=["nk.com"])
    kb = pl_kb.load_kb(kbdir, "BSI")
    assert kb["A1"]["title"] == "KÌM BẤM COS" and kb["A1"]["sources"] == ["nk.com"]
    assert (kbdir / "img" / "BSI" / "A1.png").read_bytes() == b"png"
    sub = tmp_path / "w"
    sub.mkdir()
    d2 = _write_doc(sub, [_card("x", ["A1", "A2", "Z9"], title="OTHER")])
    out = pl_kb.apply(d2, "BSI", kbdir, sub / "out.json")
    assert out["known"] == 2 and out["unknown"] == 1 and out["review"] == 2
    assert len(_read(sub / "out.json")["cards"]) == 1
    assert _read(sub / "kb_unknown.json") == [{"code": "Z9", "card": "x"}]


def test_apply_sets_content_when_all_known(tmp_path, kbdir):
    (tmp_path / "a.png").write_bytes(b"png")
    _learn(kbdir, _write_doc(tmp_path, [_card("c1", ["A1"], title="KÌM", lines=["L"], legend=["g"],
                                              image={"path": "a.png", "status": "ok"})]))
    d2 = _write_doc(tmp_path, [_card("n", ["A1"], title="WRONG")], "d2.json")
    out = pl_kb.apply(d2, "BSI", kbdir, tmp_path / "o.json")
    c = _read(tmp_path / "o.json")["cards"][0]
    assert c["title"] == "KÌM" and c["lines"] == ["L"] and c["legend"] == ["g"]
    assert Path(c["image"]["path"]).read_bytes() == b"png"
    assert out["unknown"] == 0


def test_apply_does_not_override_existing_lines(tmp_path, kbdir):
    _learn(kbdir, _write_doc(tmp_path, [_card("c1", ["A1"], title="KÌM", lines=["KB"])]))
    d2 = _write_doc(tmp_path, [_card("n", ["A1"], lines=["MINE"])], "d2.json")
    pl_kb.apply(d2, "BSI", kbdir, tmp_path / "o.json")
    assert _read(tmp_path / "o.json")["cards"][0]["lines"] == ["MINE"]


def test_apply_splits_mixed_titles_preserving_rows(tmp_path, kbdir):
    _learn(kbdir, _write_doc(tmp_path, [_card("a", ["A1", "A3"], title="TITLE A"),
                                        _card("b", ["A2"], title="TITLE B")]))
    d2 = _write_doc(tmp_path, [_card("m", ["A1", "A2", "A3", "U1"], title="MIX")], "d2.json")
    before = d2.read_text(encoding="utf-8")
    out = pl_kb.apply(d2, "BSI", kbdir, tmp_path / "o.json")
    assert d2.read_text(encoding="utf-8") == before
    cards = _read(tmp_path / "o.json")["cards"]
    assert [c["id"] for c in cards] == ["m-1", "m-2", "m-3"]
    assert [c["title"] for c in cards] == ["TITLE A", "TITLE B", "MIX"]
    assert [[r["code"] for r in c["rows"]] for c in cards] == [["A1", "A3"], ["A2"], ["U1"]]
    assert out["split_cards"] == 1 and out["unknown"] == 1
    assert all(c["columns"] == cards[0]["columns"] for c in cards)


def test_learn_ok_not_overwritten_and_conflict_reported(tmp_path, kbdir):
    _learn(kbdir, _write_doc(tmp_path, [_card("a", ["A1"], title="ONE")]), status="ok")
    res = _learn(kbdir, _write_doc(tmp_path, [_card("a", ["A1"], title="TWO")], "d2.json"))
    assert res["conflicts"] == [{"code": "A1", "kb": "ONE", "new": "TWO"}]
    assert pl_kb.load_kb(kbdir, "BSI")["A1"]["title"] == "ONE"
    _learn(kbdir, tmp_path / "d2.json", force=True)
    assert pl_kb.load_kb(kbdir, "BSI")["A1"]["title"] == "TWO"


def test_learn_skips_continuation_cards(tmp_path, kbdir):
    _learn(kbdir, _write_doc(tmp_path, [_card("a", ["A1"], title="ONE"), _card("a#2", ["A2"], title="ONE")]))
    assert set(pl_kb.load_kb(kbdir, "BSI")) == {"A1"}


def test_approve_and_list(tmp_path, kbdir):
    _learn(kbdir, _write_doc(tmp_path, [_card("a", ["A1", "A2"], title="ONE")]))
    assert pl_kb.approve("BSI", kbdir, codes=["A1"]) == 1
    kb = pl_kb.load_kb(kbdir, "BSI")
    assert kb["A1"]["status"] == "ok" and kb["A2"]["status"] == "review"
    assert pl_kb.approve("BSI", kbdir, all_review=True) == 1
    assert pl_kb.list_entries("BSI", kbdir, status="review") == []


def test_diff_doc_vs_doc_and_kb(tmp_path, kbdir):
    a = _write_doc(tmp_path, [_card("a", ["A1", "A2"], title="ONE")], "a.json")
    b = _write_doc(tmp_path, [_card("b", ["A1"], title="ONE"), _card("c", ["A2"], title="TWO")], "b.json")
    assert pl_kb.diff(a, b) == [("A2", "ONE", "TWO")]
    _learn(kbdir, a)
    assert pl_kb.diff(kbdir / "BSI.json", b) == [("A2", "ONE", "TWO")]


def test_cli_runs_isolated(tmp_path):
    d = _write_doc(tmp_path, [_card("a", ["A1"], title="ONE")])
    base = [sys.executable, "-I", str(SCRIPT), "--kb-dir", str(tmp_path / "kb")]
    r = subprocess.run(base + ["learn", str(d), "--brand", "BSI", "--status", "review"],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    r = subprocess.run(base + ["list", "--brand", "BSI"], capture_output=True, text=True, encoding="utf-8")
    assert "A1" in r.stdout and "ONE" in r.stdout


def test_apply_keeps_data_title_and_grouping(tmp_path):
    import json as _j
    from pl_kb import apply
    kbd = tmp_path / "kb"; kbd.mkdir()
    (kbd / "XX.json").write_text(_j.dumps({"brand": "XX", "entries": {
        "A1": {"code": "A1", "title": "KB TITLE ONE", "lines": ["Vật Liệu: Thép"], "legend": [], "image": None,
               "drawing": None, "sources": [], "status": "ok", "updated": "2026-10-06", "note": ""},
        "A2": {"code": "A2", "title": "KB TITLE TWO", "lines": [], "legend": [], "image": None,
               "drawing": None, "sources": [], "status": "ok", "updated": "2026-10-06", "note": ""}}}), encoding="utf-8")
    doc = {"meta": {"brand": "X", "page_code": "XX"}, "cards": [{
        "id": "c", "title": "TÊN CỦA ANH", "title_source": "data", "lines": [], "legend": [],
        "columns": [{"key": "code"}, {"key": "order"}, {"key": "price"}],
        "rows": [{"code": "A1", "order": "0000001"}, {"code": "A2", "order": "0000002"}]}]}
    p = tmp_path / "doc.json"; p.write_text(_j.dumps(doc, ensure_ascii=False), encoding="utf-8")
    apply(p, "XX", kb_dir=kbd)
    out = _j.loads(p.read_text(encoding="utf-8"))
    assert len(out["cards"]) == 1 and out["cards"][0]["title"] == "TÊN CỦA ANH"
    assert out["cards"][0]["lines"] == ["Vật Liệu: Thép"]


def test_default_kb_is_under_user_home(monkeypatch, tmp_path):
    import pl_kb
    monkeypatch.setenv("MECSU_PRICELIST_HOME", str(tmp_path))
    assert pl_kb.default_kb() == tmp_path / "kb"
    assert pl_kb.load_kb(None, "ZZZ") == {}
