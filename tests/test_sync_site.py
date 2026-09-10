# -*- coding: utf-8 -*-
"""Them skill moi -> website tu co mat skill do, khong ai phai sua HTML bang tay.

Truoc day site va thu muc skills/ khong co gi rang buoc nhau nen site quang cao
`category-auto` sau khi skill do bien mat.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

SKILL_MOI = """---
name: mecsu-anh
description: Cat logo va xoa nen hang loat cho anh san pham. Use when product photos need
  background removal before going on the web.
---

# mecsu-anh
"""

WEBSITE_JSON = {
    "title": "Xu ly anh san pham",
    "purpose": "Cat logo, xoa nen hang loat truoc khi dua anh len web.",
    "prompt": "Dung skill mecsu-anh de xoa nen cho thu muc anh cua toi.",
}


def _repo(tmp_path: Path) -> Path:
    """Ban sao toi thieu cua repo de khong dung vao cay lam viec that."""
    repo = tmp_path / "repo"
    (repo / "skills").mkdir(parents=True)
    shutil.copytree(ROOT / "site", repo / "site")
    shutil.copy(ROOT / "tools" / "sync_site.py", repo / "sync_site.py")
    for name in ("mecsu-category", "mecsu-filter"):
        target = repo / "skills" / name
        target.mkdir()
        shutil.copy(ROOT / "skills" / name / "SKILL.md", target / "SKILL.md")
        source = ROOT / "skills" / name / "website.json"
        if source.exists():
            shutil.copy(source, target / "website.json")
    return repo


def _sync(repo: Path, *arguments):
    return subprocess.run(
        [sys.executable, str(repo / "sync_site.py"), "--root", str(repo), *arguments],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def test_skill_moi_tu_len_website(tmp_path):
    repo = _repo(tmp_path)
    skill = repo / "skills" / "mecsu-anh"
    skill.mkdir()
    (skill / "SKILL.md").write_text(SKILL_MOI, encoding="utf-8")
    (skill / "website.json").write_text(json.dumps(WEBSITE_JSON, ensure_ascii=False), encoding="utf-8")

    result = _sync(repo)
    assert result.returncode == 0, result.stdout + result.stderr

    catalog = json.loads((repo / "site" / "public-skill-catalog.json").read_text(encoding="utf-8"))
    assert {item["skill_id"] for item in catalog["skills"]} == {
        "mecsu-category", "mecsu-filter", "mecsu-anh"}

    html = (repo / "site" / "index.html").read_text(encoding="utf-8")
    assert 'id="mecsu-anh"' in html
    assert 'id="prompt-mecsu-anh"' in html
    assert WEBSITE_JSON["prompt"] in html


def test_check_bao_loi_khi_site_lech(tmp_path):
    """--check dung cho lint/CI: site lech thi thoat khac 0, khong tu sua."""
    repo = _repo(tmp_path)
    (repo / "skills" / "mecsu-moi").mkdir()
    (repo / "skills" / "mecsu-moi" / "SKILL.md").write_text(SKILL_MOI, encoding="utf-8")

    result = _sync(repo, "--check")
    assert result.returncode != 0, "site thieu skill ma --check van pass"


def test_site_that_dang_dong_bo():
    """Chay --check tren chinh repo nay: site da commit phai khop skills/."""
    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "sync_site.py"), "--check"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
