"""Image tooling for pricelist: local lookup, web candidate search, contact sheets, prep (bg removal + trim).

CLI:
  pl_images.py resolve doc.json --folder DIR --work DIR   fill card.image.path from local files; writes missing.json
  pl_images.py search missing.json --work DIR [-n 4]      web candidates + contact sheets (sheet_N.png)
  pl_images.py pick picks.json --work DIR --doc doc.json  picks = {"card_id": 1-based index | file path}
"""
import argparse
import io
import json
import re
import sys
import unicodedata
from pathlib import Path

import math
import time

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))

EXTS = (".png", ".jpg", ".jpeg", ".webp")
MAX_BYTES = 5 * 1024 * 1024
THUMB = 160
SHEET_MAX_GROUPS = 20


def _norm_code(code: str) -> str:
    return str(code).strip().replace("/", "-").lower()


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).replace("đ", "d").replace("Đ", "D"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def find_local(code: str, group: str, folder: str | None) -> str | None:
    """<folder>/<code>.(png|jpg|jpeg|webp) case-insensitive, then <group-slug>.*"""
    if not folder or not Path(folder).is_dir():
        return None
    files = {}
    for p in sorted(Path(folder).iterdir()):
        if p.is_file() and p.suffix.lower() in EXTS:
            files.setdefault(p.stem.lower(), str(p))
    for key in (_norm_code(code) if str(code).strip() else "", _slug(group) if group else ""):
        if key and key in files:
            return files[key]
    return None


def _ext_for(fmt: str) -> str | None:
    return {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}.get(fmt)


def _image_urls(query: str, n: int) -> list[str]:
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            raise RuntimeError("web search unavailable: pip install ddgs") from None
    res = DDGS().images(query, max_results=n * 4)
    return [r.get("image") for r in res if r.get("image")]


def search_candidates(query: str, n: int = 4, out_dir: str = ".") -> list[str]:
    """ddgs image search; download up to n valid images (untrusted: opened only with Pillow, never executed)."""
    import requests
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    try:
        urls = _image_urls(query, n)
    except Exception as e:  # network / rate limit
        print(f"search failed: {e}", file=sys.stderr)  # includes 'web search unavailable: pip install ddgs'
        return saved
    for url in urls:
        if len(saved) >= n:
            break
        try:
            r = requests.get(url, timeout=10, stream=True, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200 or "image" not in r.headers.get("content-type", "").lower():
                continue
            data = b""
            for chunk in r.iter_content(65536):
                data += chunk
                if len(data) > MAX_BYTES:
                    data = b""
                    break
            if not data:
                continue
            im = Image.open(io.BytesIO(data))
            ext = _ext_for(im.format or "")
            if not ext:
                continue
            im.verify()
            p = out / f"cand_{len(saved) + 1}{ext}"
            p.write_bytes(data)
            saved.append(str(p))
        except Exception:
            continue
    return saved


def _font(size=13):
    for f in ("arial.ttf", "calibri.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            pass
    return ImageFont.load_default()


def contact_sheet(groups: dict[str, list[str]], out_png: str) -> str:
    """One row per group: label + numbered 160px thumbnails. Max 20 groups per sheet."""
    items = list(groups.items())[:SHEET_MAX_GROUPS]
    cols = max([len(v) for _, v in items] + [1])
    label_h, pad = 22, 6
    cell_w, cell_h = THUMB + pad, THUMB + label_h + pad
    sheet = Image.new("RGB", (cols * cell_w + pad, max(len(items), 1) * cell_h + pad), "white")
    d = ImageDraw.Draw(sheet)
    f = _font()
    for r, (label, paths) in enumerate(items):
        y = pad + r * cell_h
        d.text((pad, y), str(label)[:60], fill="black", font=f)
        for c, p in enumerate(paths):
            x = pad + c * cell_w
            try:
                im = Image.open(p).convert("RGBA")
                im.thumbnail((THUMB, THUMB))
                bg = Image.new("RGBA", im.size, "white")
                bg.alpha_composite(im)
                sheet.paste(bg.convert("RGB"), (x, y + label_h))
            except Exception:
                d.rectangle([x, y + label_h, x + THUMB, y + label_h + THUMB], outline="red")
            d.rectangle([x, y + label_h, x + 22, y + label_h + 18], fill="red")
            d.text((x + 6, y + label_h + 2), str(c + 1), fill="white", font=f)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)
    return out_png


def chosen_sheet(items: list[tuple[str, str]], out_png: str, cols: int = 5, per_sheet: int = 30) -> list[str]:
    """Grid contact sheet of the images chosen for each card: [(label, path)] -> chosen_sheet.png (+ _2, _3...)."""
    f = _font()
    cell_w, cell_h, pad, lab = THUMB + 8, THUMB + 46, 6, 40
    paths = []
    for n, i in enumerate(range(0, max(len(items), 1), per_sheet), 1):
        chunk = items[i:i + per_sheet]
        rows = max(1, -(-len(chunk) // cols))
        sheet = Image.new("RGB", (cols * cell_w + pad, rows * cell_h + pad), "white")
        d = ImageDraw.Draw(sheet)
        for k, (label, p) in enumerate(chunk):
            x, y = pad + (k % cols) * cell_w, pad + (k // cols) * cell_h
            d.text((x, y), str(label)[:30], fill="black", font=f)
            d.text((x, y + 15), str(label)[30:60], fill="gray", font=f)
            try:
                im = Image.open(p).convert("RGBA")
                im.thumbnail((THUMB, THUMB))
                bg = Image.new("RGBA", im.size, "white")
                bg.alpha_composite(im)
                sheet.paste(bg.convert("RGB"), (x, y + lab))
            except Exception:
                d.rectangle([x, y + lab, x + THUMB, y + lab + THUMB], outline="red")
        out = out_png if n == 1 else str(Path(out_png).with_name(f"{Path(out_png).stem}_{n}{Path(out_png).suffix}"))
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        sheet.save(out)
        paths.append(out)
    return paths


def _floodfill_white(im: Image.Image, tol: int = 235) -> Image.Image:
    """Fallback bg removal: near-white pixels connected to the border become transparent."""
    rgb = im.convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    seen = bytearray(w * h)
    stack = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    while stack:
        x, y = stack.pop()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        if min(px[x, y]) < tol:
            continue
        mp[x, y] = 255
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and not seen[ny * w + nx]:
                stack.append((nx, ny))
    out = im.convert("RGBA")
    out.putalpha(ImageChops.multiply(out.getchannel("A"), ImageChops.invert(mask)))
    return out


def _remove_bg(im: Image.Image) -> Image.Image:
    try:
        from rembg import remove
        return remove(im).convert("RGBA")
    except Exception as e:
        print(f"rembg unavailable ({type(e).__name__}: {e}); using flood-fill fallback", file=sys.stderr)
        return _floodfill_white(im)


def _trim_cap(im: Image.Image) -> Image.Image:
    box = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if box:
        im = im.crop(box)
    s = 600 / max(im.size)
    if s < 1:
        im = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    return im


def _pca(im: Image.Image):
    """(angle_deg in math coords [0,180), elongation) of the alpha mask."""
    ys, xs = np.nonzero(np.asarray(im.getchannel("A")) > 8)
    if len(xs) < 3:
        return 0.0, 1.0
    x = xs.astype(float)
    y = -ys.astype(float)
    cov = np.cov(np.vstack([x - x.mean(), y - y.mean()]))
    vals, vecs = np.linalg.eigh(cov)
    l2, l1 = max(vals[0], 1e-9), max(vals[1], 1e-9)
    v = vecs[:, 1]
    return math.degrees(math.atan2(v[1], v[0])) % 180, math.sqrt(l1 / l2)


def _low_is_heavier(im: Image.Image, t_deg: float) -> bool:
    """True if the half at the low end (smaller projection on the axis at t_deg) has more thickness-weighted mass."""
    ys, xs = np.nonzero(np.asarray(im.getchannel("A")) > 8)
    proj = xs * math.cos(math.radians(t_deg)) + (-ys) * math.sin(math.radians(t_deg))
    bins = np.floor(proj - proj.min()).astype(int)
    n = np.bincount(bins).astype(float)  # pixels per perpendicular slice = local thickness
    mid = len(n) / 2
    mass = n * n
    idx = np.arange(len(n)) + 0.5
    return mass[idx < mid].sum() >= mass[idx >= mid].sum()


def _orient_image(im: Image.Image, mode="diagonal", angle=30, heavy_end="low", min_elongation=1.8):
    info = {"elongation": 1.0, "rotated_deg": 0.0, "flipped": False, "compact": True}
    if mode == "keep":
        return _trim_cap(im), info
    theta, elong = _pca(im)
    info["elongation"] = round(float(elong), 3)
    if elong < min_elongation:
        return _trim_cap(im), info
    info["compact"] = False
    target = {"horizontal": 0.0, "vertical": 90.0}.get(mode, float(angle))
    delta = (target - theta + 90) % 180 - 90  # shortest rotation, in [-90, 90)
    im = im.rotate(delta, resample=Image.BICUBIC, expand=True, fillcolor=(0, 0, 0, 0))
    im = _trim_cap(im)
    flipped = False
    if _low_is_heavier(im, target) != (heavy_end != "high"):
        im = im.rotate(180, expand=True)
        flipped = True
    info.update(rotated_deg=round(delta + (180 if flipped else 0), 2), flipped=flipped)
    return im, info


def normalize_orientation(src_png, dst_png, mode="diagonal", angle=30, heavy_end="auto", min_elongation=1.8) -> dict:
    """Rotate product so its principal axis is horizontal / vertical / diagonal(+angle, rising right);
    heavier half (handle) at the low end (heavy_end low/auto) or high end. Compact objects only trimmed."""
    im = Image.open(src_png)
    im.load()
    im = im.convert("RGBA")
    if im.getchannel("A").getextrema()[0] == 255:  # no transparency -> need a mask
        im = _remove_bg(im)
    im, info = _orient_image(im, mode, angle, heavy_end, min_elongation)
    Path(dst_png).parent.mkdir(parents=True, exist_ok=True)
    im.save(dst_png, "PNG")
    return info


def prep_image(src: str, dst_png: str, remove_bg: bool = True, orient: dict | None = None) -> dict:
    """Open with Pillow, remove bg if no alpha, trim transparent/white border, max side 600, save PNG RGBA."""
    try:
        im = Image.open(src)
        im.load()
    except Exception as e:
        raise ValueError(f"not a valid image: {src}: {e}")
    has_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
    im = im.convert("RGBA")
    if remove_bg and not has_alpha:
        im = _remove_bg(im)
    alpha = im.getchannel("A").point(lambda v: 255 if v > 8 else 0)
    diff = ImageChops.difference(im.convert("RGB"), Image.new("RGB", im.size, "white")).convert("L")
    nonwhite = diff.point(lambda v: 255 if v > 12 else 0)
    box = ImageChops.multiply(alpha, nonwhite).getbbox()
    if box:
        im = im.crop(box)
    if orient and orient.get("mode", "keep") != "keep" and (has_alpha or remove_bg):
        im, _ = _orient_image(im, orient.get("mode", "diagonal"), orient.get("angle", 30),
                              orient.get("heavy_end", "low"), orient.get("min_elongation", 1.8))
    im = _trim_cap(im)
    Path(dst_png).parent.mkdir(parents=True, exist_ok=True)
    im.save(dst_png, "PNG")
    return {"w": im.width, "h": im.height}


# ---------------- CLI ----------------
def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _dump(obj, p):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _first_code(card) -> str:
    for r in card.get("rows", []):
        if r.get("code"):
            return str(r["code"]).strip()
    return ""


_UA = {"User-Agent": "Mozilla/5.0 (pricelist-skill)"}
_last_req = [0.0]
CATALOG_DELAY = 0.5


def _get(url: str):
    import requests
    wait = CATALOG_DELAY - (time.time() - _last_req[0])
    if wait > 0:
        time.sleep(wait)
    _last_req[0] = time.time()
    return requests.get(url, headers=_UA, timeout=20)


def fetch_catalog(order_code: str, out_png: str, sources: list[dict]) -> str | None:
    """Official catalog photo by order id: page -> og:image -> PNG. None if not found/invalid."""
    code = str(order_code).strip()
    if not code:
        return None
    for src in sources or []:
        try:
            r = _get(src["page"].format(order=code))
            if r.status_code != 200:
                continue
            m = (re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', r.text, re.I)
                 or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', r.text, re.I))
            if not m:
                continue
            url = m.group(1)
            skip = src.get("skip_if_contains")
            if skip and skip.lower() in url.lower():
                continue
            ir = _get(url)
            if ir.status_code != 200 or len(ir.content) > 5_000_000:
                continue
            im = Image.open(io.BytesIO(ir.content))
            im.verify()
            im = Image.open(io.BytesIO(ir.content)).convert("RGBA")
            Path(out_png).parent.mkdir(parents=True, exist_ok=True)
            im.save(out_png, "PNG")
            return str(out_png)
        except Exception:
            continue
    return None


def pick_representative(paths: list[str]) -> str:
    """Of several photos of one card, the one whose elongation is closest to the median (ties: larger mask)."""
    if len(paths) == 1:
        return paths[0]
    import tempfile
    stats = []
    for p in paths:
        with tempfile.TemporaryDirectory() as td:
            t = Path(td) / "t.png"
            prep_image(p, str(t), remove_bg=True)
            im = Image.open(t).convert("RGBA")
        area = int((np.asarray(im.getchannel("A")) > 8).sum())
        stats.append((_pca(im)[1], area, p))
    med = float(np.median([e for e, _, _ in stats]))
    return min(stats, key=lambda x: (abs(x[0] - med), -x[1]))[2]


def cmd_resolve(a):
    doc = _load(a.doc)
    brand = doc.get("meta", {}).get("brand", "")
    from pl_common import load_theme
    sources = [] if a.no_catalog else load_theme().get("image", {}).get("catalog_sources", [])
    orient = load_theme().get("image", {}).get("orientation")
    ncand = load_theme().get("image", {}).get("catalog_candidates", 3)
    no_cat = set(_load(a.no_catalog_cards)) if getattr(a, "no_catalog_cards", None) else set()
    missing = []
    for c in doc["cards"]:
        img = c.get("image") or {}
        ip = img.get("path")
        if ip and not a.refresh and (Path(ip).exists() or (Path(a.doc).resolve().parent / ip).exists()):
            continue  # only-missing (default): keep existing images
        found = None
        for r in c.get("rows", []):
            if r.get("code"):
                found = find_local(str(r["code"]), "", a.folder)
                if found:
                    break
        found = found or find_local("", c.get("group") or "", a.folder)
        if found:
            c["image"] = {**img, "path": found, "status": "ok"}
            continue
        raws, seen_o = [], set()
        for r in c.get("rows", []):
            o = str(r.get("order") or "").strip()
            if not (sources and o) or c["id"] in no_cat or o in seen_o or len(seen_o) >= ncand:
                continue
            seen_o.add(o)
            raw = Path(a.work) / "catalog" / f"{_slug(c['id'])}_{o}.png"
            if fetch_catalog(o, str(raw), sources):
                raws.append(str(raw))
        if raws:
            best = pick_representative(raws)
            dst = Path(a.work) / "img" / f"{_slug(c['id'])}.png"
            prep_image(best, str(dst), remove_bg=True, orient=orient)
            c["image"] = {**img, "path": str(dst), "status": "ok", "source": f"catalog:{sources[0]['name']}"}
        if not (c.get("image") or {}).get("path"):
            missing.append({"card_id": c["id"], "group": c.get("group", ""), "title": c["title"],
                            # short queries work best; the alt adds the product type (first 3 title words)
                            "query": f"{brand} {_first_code(c)}".strip(),
                            "query_alt": f"{brand} {_first_code(c)} {' '.join(c['title'].split()[:3])}".strip()})
    _dump(doc, a.doc)
    _dump(missing, Path(a.work) / "missing.json")
    print(f"resolved; missing={len(missing)}")


def cmd_search(a):
    missing = _load(a.missing)
    work = Path(a.work)
    cands = {}
    for m in missing:  # missing.json may be hand-edited (query / query_alt) before re-running search
        out = str(work / "cand" / m["card_id"])
        cands[m["card_id"]] = search_candidates(m["query"], a.n, out)
        if len(cands[m["card_id"]]) < 2 and m.get("query_alt"):
            cands[m["card_id"]] += search_candidates(m["query_alt"], a.n, out + "_alt")
    _dump(cands, work / "candidates.json")
    ids = list(cands)
    for i in range(0, len(ids), SHEET_MAX_GROUPS):
        chunk = {cid: cands[cid] for cid in ids[i:i + SHEET_MAX_GROUPS]}
        print("sheet:", contact_sheet(chunk, str(work / f"sheet_{i // SHEET_MAX_GROUPS + 1}.png")))
    print("candidates:", {k: len(v) for k, v in cands.items()})


def cmd_pick(a):
    picks = _load(a.picks)
    work = Path(a.work)
    cands = _load(work / "candidates.json") if (work / "candidates.json").exists() else {}
    doc = _load(a.doc)
    from pl_common import load_theme
    orient = load_theme().get("image", {}).get("orientation")
    byid = {c["id"]: c for c in doc["cards"]}
    for cid, sel in picks.items():
        if cid not in byid:
            print(f"skip unknown card {cid}", file=sys.stderr)
            continue
        if isinstance(sel, int):
            lst = cands.get(cid, [])
            if not 1 <= sel <= len(lst):
                print(f"skip {cid}: bad index {sel}", file=sys.stderr)
                continue
            src = lst[sel - 1]
        else:
            src = str(sel)
        dst = work / "img" / f"{_slug(cid) or 'card'}.png"
        try:
            prep_image(src, str(dst), remove_bg=not a.no_rembg, orient=orient)
        except ValueError as e:
            print(f"skip {cid}: {e}", file=sys.stderr)
            continue
        byid[cid]["image"] = {**(byid[cid].get("image") or {}), "path": str(dst), "status": "review"}
    _dump(doc, a.doc)
    print("picked", len(picks))


def cmd_orient(a):
    from pl_common import load_theme
    cfg = dict(load_theme().get("image", {}).get("orientation") or {})
    for k, v in (("mode", a.mode), ("angle", a.angle), ("heavy_end", a.heavy_end)):
        if v is not None:
            cfg[k] = v
    doc = _load(a.doc)
    for c in doc["cards"]:
        img = c.get("image") or {}
        src = img.get("path")
        if not src or not Path(src).exists():
            continue
        dst = Path(src).with_name(Path(src).stem.removesuffix("_o") + "_o.png")
        info = normalize_orientation(src, str(dst), cfg.get("mode", "diagonal"), cfg.get("angle", 30),
                                     cfg.get("heavy_end", "low"), cfg.get("min_elongation", 1.8))
        c["image"] = {**img, "path": str(dst)}
        print(c["id"], info)
    _dump(doc, a.doc)


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("resolve")
    p.add_argument("doc"); p.add_argument("--folder"); p.add_argument("--work", required=True)
    p.add_argument("--no-catalog", action="store_true")
    p.add_argument("--no-catalog-cards", help="JSON list of card ids that must skip the catalog (rejected images)")
    p.add_argument("--refresh", action="store_true", help="re-resolve cards that already have an image")
    p.set_defaults(f=cmd_resolve)
    p = sp.add_parser("search")
    p.add_argument("missing"); p.add_argument("--work", required=True); p.add_argument("-n", type=int, default=4)
    p.set_defaults(f=cmd_search)
    p = sp.add_parser("pick")
    p.add_argument("picks"); p.add_argument("--work", required=True); p.add_argument("--doc", required=True)
    p.add_argument("--no-rembg", action="store_true")
    p.set_defaults(f=cmd_pick)
    p = sp.add_parser("orient")
    p.add_argument("doc"); p.add_argument("--mode"); p.add_argument("--angle", type=float)
    p.add_argument("--heavy-end", dest="heavy_end")
    p.set_defaults(f=cmd_orient)
    a = ap.parse_args(argv)
    a.f(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
