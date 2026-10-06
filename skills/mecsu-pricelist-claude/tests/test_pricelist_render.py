import pytest
from pl_build import build
from pl_common import load_theme
from test_pricelist_build import make_doc, img_path  # noqa: F401


@pytest.mark.excel
def test_render_pages(tmp_path, img_path):
    from pl_render import render
    out = tmp_path / "o.xlsx"
    build(make_doc(tmp_path, img_path), str(out), load_theme())
    files = render(str(out), str(tmp_path / "r"))
    assert [f.split("\\")[-1].split("/")[-1] for f in files] == ["page_01.png", "page_02.png"]
    import os
    assert all(os.path.getsize(f) > 10_000 for f in files)
