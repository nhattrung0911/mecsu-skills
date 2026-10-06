import json
import pytest
from PIL import Image

import pl_images as pi


def _img(path, size=(40, 30), color=(200, 0, 0)):
    Image.new("RGB", size, color).save(path)


def test_find_local_exact_and_case(tmp_path):
    _img(tmp_path / "84-623.PNG")
    assert pi.find_local(" 84-623 ", "Kìm", str(tmp_path)).endswith("84-623.PNG")
    _img(tmp_path / "FBJ-6204.jpg")
    assert pi.find_local("fbj/6204", "x", str(tmp_path)).endswith("FBJ-6204.jpg")
    assert pi.find_local("nope", "x", str(tmp_path)) is None
    assert pi.find_local("a", "x", None) is None
    assert pi.find_local("a", "x", str(tmp_path / "missing_dir")) is None


def test_find_local_group_fallback(tmp_path):
    _img(tmp_path / "kim-mo-nhon.webp")
    assert pi.find_local("zzz", "Kìm Mỏ Nhọn", str(tmp_path)).endswith("kim-mo-nhon.webp")


def test_prep_trims_white_border(tmp_path):
    im = Image.new("RGB", (200, 200), "white")
    im.paste((10, 10, 200), (80, 90, 120, 110))  # 40x20 blue box
    im.save(tmp_path / "s.png")
    out = tmp_path / "o.png"
    info = pi.prep_image(str(tmp_path / "s.png"), str(out), remove_bg=False)
    assert info == {"w": 40, "h": 20}
    r = Image.open(out)
    assert r.mode == "RGBA" and r.size == (40, 20)


def test_prep_max_side(tmp_path):
    Image.new("RGBA", (1500, 300), (0, 0, 0, 255)).save(tmp_path / "b.png")
    info = pi.prep_image(str(tmp_path / "b.png"), str(tmp_path / "o.png"), remove_bg=False)
    assert max(info["w"], info["h"]) == 600


def test_prep_bad_file_raises(tmp_path):
    (tmp_path / "x.png").write_bytes(b"not an image")
    with pytest.raises(ValueError):
        pi.prep_image(str(tmp_path / "x.png"), str(tmp_path / "o.png"), remove_bg=False)


def test_floodfill_fallback_removes_border_white(tmp_path):
    im = Image.new("RGB", (60, 60), "white")
    im.paste((0, 0, 0), (20, 20, 40, 40))
    out = pi._floodfill_white(im)
    assert out.getpixel((0, 0))[3] == 0 and out.getpixel((30, 30))[3] == 255


def test_contact_sheet_size(tmp_path):
    files = []
    for i in range(3):
        p = tmp_path / f"c{i}.png"
        _img(p, (300, 100))
        files.append(str(p))
    out = pi.contact_sheet({"A": files, "B": files[:2]}, str(tmp_path / "s.png"))
    im = Image.open(out)
    assert im.width >= 160 * 3 and im.height >= 160 * 2


def test_resolve_and_pick_cli(tmp_path):
    doc = {"meta": {"brand": "X", "page_code": "XX"},
           "cards": [{"id": "c1", "group": "G", "title": "T",
                      "columns": [{"key": "code"}, {"key": "order"}],
                      "rows": [{"code": "AB/1"}], "image": None},
                     {"id": "c2", "group": "H", "title": "T2",
                      "columns": [{"key": "code"}, {"key": "order"}],
                      "rows": [{"code": "ZZ"}]}]}
    folder = tmp_path / "imgs"
    folder.mkdir()
    _img(folder / "ab-1.png")
    dp = tmp_path / "doc.json"
    dp.write_text(json.dumps(doc), encoding="utf-8")
    work = tmp_path / "w"
    pi.main(["resolve", str(dp), "--folder", str(folder), "--work", str(work)])
    d = json.loads(dp.read_text(encoding="utf-8"))
    assert d["cards"][0]["image"]["path"].endswith("ab-1.png")
    assert d["cards"][0]["image"]["status"] == "ok"
    miss = json.loads((work / "missing.json").read_text(encoding="utf-8"))
    assert [m["card_id"] for m in miss] == ["c2"]
    cdir = work / "cand" / "c2"
    cdir.mkdir(parents=True)
    _img(cdir / "cand_1.jpg", (100, 80))
    (work / "candidates.json").write_text(json.dumps({"c2": [str(cdir / "cand_1.jpg")]}), encoding="utf-8")
    pk = tmp_path / "picks.json"
    pk.write_text(json.dumps({"c2": 1}), encoding="utf-8")
    pi.main(["pick", str(pk), "--work", str(work), "--doc", str(dp), "--no-rembg"])
    d = json.loads(dp.read_text(encoding="utf-8"))
    assert d["cards"][1]["image"]["status"] == "review"
    assert (work / "img" / "c2.png").exists()


@pytest.mark.net
def test_search_candidates_net(tmp_path):
    out = pi.search_candidates("FBJ 6204 bearing", 2, str(tmp_path))
    assert out and all(p.endswith((".jpg", ".png", ".webp", ".jpeg")) for p in out)


# ---- orientation ----
import math
import numpy as np
from PIL import ImageDraw


def _pca_angle(path):
    im = Image.open(path).convert("RGBA")
    ys, xs = np.nonzero(np.asarray(im.getchannel("A")) > 8)
    x = xs - xs.mean()
    y = -(ys - ys.mean())
    vals, vecs = np.linalg.eigh(np.cov(np.vstack([x, y])))
    v = vecs[:, 1]
    return math.degrees(math.atan2(v[1], v[0])) % 180


def _file_shape(path, tilt=0):
    """Thin blade 300x16 plus thick red handle 100x50 at the LEFT, rotated by tilt."""
    im = Image.new("RGBA", (500, 500), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([100, 242, 400, 258], fill=(80, 80, 80, 255))
    d.rectangle([60, 225, 160, 275], fill=(200, 0, 0, 255))
    im.rotate(tilt, resample=Image.BICUBIC).save(path)


def _handle_pos(path):
    a = np.asarray(Image.open(path).convert("RGBA"))
    red = (a[..., 0] > 150) & (a[..., 1] < 60) & (a[..., 3] > 200)
    ally, allx = np.nonzero(a[..., 3] > 8)
    ry, rx = np.nonzero(red)
    return rx.mean() - allx.mean(), -(ry.mean() - ally.mean())


def test_bar_to_diagonal(tmp_path):
    im = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    ImageDraw.Draw(im).rectangle([50, 190, 350, 210], fill=(0, 0, 0, 255))
    im.rotate(70, resample=Image.BICUBIC).save(tmp_path / "b.png")
    info = pi.normalize_orientation(str(tmp_path / "b.png"), str(tmp_path / "o.png"), "diagonal", 30)
    assert not info["compact"] and info["elongation"] > 5
    assert abs(_pca_angle(tmp_path / "o.png") - 30) < 2


@pytest.mark.parametrize("tilt", [0, 70, 200])
def test_handle_lower_left_diagonal(tmp_path, tilt):
    _file_shape(tmp_path / "f.png", tilt)
    pi.normalize_orientation(str(tmp_path / "f.png"), str(tmp_path / "o.png"), "diagonal", 30, "low")
    assert abs(_pca_angle(tmp_path / "o.png") - 30) < 3
    hx, hy = _handle_pos(tmp_path / "o.png")
    assert hx < 0 and hy < 0


def test_handle_left_horizontal_and_high(tmp_path):
    _file_shape(tmp_path / "f.png", 130)
    pi.normalize_orientation(str(tmp_path / "f.png"), str(tmp_path / "o.png"), "horizontal", heavy_end="low")
    a = _pca_angle(tmp_path / "o.png")
    assert min(a, 180 - a) < 2
    assert _handle_pos(tmp_path / "o.png")[0] < 0
    pi.normalize_orientation(str(tmp_path / "f.png"), str(tmp_path / "o2.png"), "horizontal", heavy_end="high")
    assert _handle_pos(tmp_path / "o2.png")[0] > 0


def test_compact_unchanged(tmp_path):
    im = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    im.paste((0, 0, 200, 255), (20, 20, 80, 80))
    im.save(tmp_path / "s.png")
    info = pi.normalize_orientation(str(tmp_path / "s.png"), str(tmp_path / "o.png"))
    assert info["compact"] and info["rotated_deg"] == 0
    assert Image.open(tmp_path / "o.png").size == (60, 60)


def test_no_alpha_white_bg(tmp_path, monkeypatch):
    monkeypatch.setattr(pi, "_remove_bg", pi._floodfill_white)
    im = Image.new("RGB", (400, 400), "white")
    ImageDraw.Draw(im).rectangle([50, 190, 350, 210], fill=(0, 0, 0))
    im.save(tmp_path / "w.png")
    info = pi.normalize_orientation(str(tmp_path / "w.png"), str(tmp_path / "o.png"), "vertical")
    assert not info["compact"]
    assert abs(_pca_angle(tmp_path / "o.png") - 90) < 2


def test_prep_image_orient_and_keep(tmp_path):
    _file_shape(tmp_path / "f.png", 40)
    cfg = {"mode": "diagonal", "angle": 30, "heavy_end": "low", "min_elongation": 1.8}
    pi.prep_image(str(tmp_path / "f.png"), str(tmp_path / "o.png"), orient=cfg)
    assert abs(_pca_angle(tmp_path / "o.png") - 30) < 3
    pi.prep_image(str(tmp_path / "f.png"), str(tmp_path / "k.png"), orient={"mode": "keep"})
    assert abs(_pca_angle(tmp_path / "k.png") - 40) < 3


# ---- catalog ----
import io as _io

SRC = [{"name": "mecsu", "page": "https://x/i/{order}", "og_image": True, "skip_if_contains": "logo"}]


class _Resp:
    def __init__(self, status=200, text="", content=b""):
        self.status_code, self.text, self.content = status, text, content


def _png_bytes():
    b = _io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(b, "PNG")
    return b.getvalue()


def _fake(monkeypatch, pages):
    monkeypatch.setattr(pi, "_get", lambda url: pages.get(url, _Resp(404)))


def test_catalog_hit(tmp_path, monkeypatch):
    page = '<meta property="og:image" content="https://a/f/1002306.png">'
    _fake(monkeypatch, {"https://x/i/1002306": _Resp(text=page), "https://a/f/1002306.png": _Resp(content=_png_bytes())})
    out = pi.fetch_catalog("1002306", str(tmp_path / "o.png"), SRC)
    assert out and Image.open(out).size == (20, 20)


def test_catalog_404_and_logo(tmp_path, monkeypatch):
    page = '<meta property="og:image" content="https://a/logo.png">'
    _fake(monkeypatch, {"https://x/i/2": _Resp(text=page), "https://a/logo.png": _Resp(content=_png_bytes())})
    assert pi.fetch_catalog("1", str(tmp_path / "o.png"), SRC) is None
    assert pi.fetch_catalog("2", str(tmp_path / "o.png"), SRC) is None


def test_catalog_bad_image(tmp_path, monkeypatch):
    page = '<meta property="og:image" content="https://a/f.png">'
    _fake(monkeypatch, {"https://x/i/3": _Resp(text=page), "https://a/f.png": _Resp(content=b"not an image")})
    assert pi.fetch_catalog("3", str(tmp_path / "o.png"), SRC) is None


def test_pick_representative_prefers_full_shot(tmp_path):
    def bar(name, w, h):
        im = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        im.paste((0, 0, 0, 255), (10, 10, 10 + w, 10 + h))
        im.save(tmp_path / name)
        return str(tmp_path / name)
    full1, close, full2 = bar("a.png", 280, 20), bar("b.png", 90, 60), bar("c.png", 250, 25)
    assert pi.pick_representative([close, full1, full2]) in (full1, full2)
    assert pi.pick_representative([close]) == close


def test_resolve_keeps_existing_image(tmp_path, monkeypatch):
    import argparse
    Image.new("RGB", (10, 10), "red").save(tmp_path / "keep.png")
    Image.new("RGB", (10, 10), "blue").save(tmp_path / "A1.png")
    doc = {"meta": {}, "cards": [
        {"id": "c1", "title": "T", "rows": [{"code": "A1"}], "image": {"path": str(tmp_path / "keep.png")}},
        {"id": "c2", "title": "T", "rows": [{"code": "A1"}], "image": {"path": str(tmp_path / "gone.png")}},
        {"id": "c3", "title": "T", "rows": [{"code": "A1"}], "image": None}]}
    (tmp_path / "doc.json").write_text(json.dumps(doc), encoding="utf-8")
    ns = lambda **k: argparse.Namespace(doc=str(tmp_path / "doc.json"), folder=str(tmp_path), work=str(tmp_path / "w"), no_catalog=True, refresh=False, **k)
    pi.cmd_resolve(ns())
    d = json.loads((tmp_path / "doc.json").read_text(encoding="utf-8"))["cards"]
    assert d[0]["image"]["path"].endswith("keep.png")
    assert d[1]["image"]["path"].endswith("A1.png") and d[2]["image"]["path"].endswith("A1.png")
    a = ns(); a.refresh = True
    pi.cmd_resolve(a)
    assert json.loads((tmp_path / "doc.json").read_text(encoding="utf-8"))["cards"][0]["image"]["path"].endswith("A1.png")
