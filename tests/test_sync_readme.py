# -*- coding: utf-8 -*-
"""Them skill moi -> README tu co mat skill do.

Da xay ra that: mecsu-naming len skills/, len site, push xong ma README van
quang cao "Hai skill". Site co `sync_site.py --check` canh, README thi khong.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SKILL_MOI = """---
name: mecsu-anh
description: Cat logo va xoa nen hang loat cho anh san pham. Use when product photos need
  background removal before going on the web.
---

# mecsu-anh
"""

WEBSITE_JSON = """{
  "title": "Xu ly anh san pham",
  "purpose": "Cat logo, xoa nen hang loat truoc khi dua anh len web.",
  "prompt": "Dung skill mecsu-anh de xoa nen cho thu muc anh cua toi."
}
"""


def _repo(tmp_path: Path) -> Path:
    """Ban sao toi thieu cua repo de khong dung vao cay lam viec that."""
    repo = tmp_path / "repo"
    (repo / "skills").mkdir(parents=True)
    (repo / "tools").mkdir()
    shutil.copytree(ROOT / "site", repo / "site")
    shutil.copy(ROOT / "tools" / "sync_site.py", repo / "tools" / "sync_site.py")
    shutil.copy(ROOT / "README.md", repo / "README.md")
    for folder in sorted((ROOT / "skills").iterdir()):
        if not (folder / "SKILL.md").exists():
            continue
        target = repo / "skills" / folder.name
        target.mkdir()
        shutil.copy(folder / "SKILL.md", target / "SKILL.md")
        if (folder / "website.json").exists():
            shutil.copy(folder / "website.json", target / "website.json")
    return repo


def _sync(repo: Path, *flags: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(repo / "tools" / "sync_site.py"), "--root", str(repo), *flags],
        capture_output=True, text=True, encoding="utf-8")


def _them_skill(repo: Path) -> None:
    moi = repo / "skills" / "mecsu-anh"
    moi.mkdir()
    (moi / "SKILL.md").write_text(SKILL_MOI, encoding="utf-8")
    (moi / "website.json").write_text(WEBSITE_JSON, encoding="utf-8")


def test_readme_cua_repo_dang_khop_skills():
    """Cay lam viec that phai khop - day chinh la thu CI se chay."""
    assert _sync(ROOT, "--check").returncode == 0


def test_them_skill_thi_check_bao_readme_lech(tmp_path):
    repo = _repo(tmp_path)
    _them_skill(repo)
    ket_qua = _sync(repo, "--check")
    assert ket_qua.returncode != 0
    assert "README.md" in ket_qua.stdout + ket_qua.stderr


def test_chay_that_thi_readme_co_ten_skill_moi(tmp_path):
    repo = _repo(tmp_path)
    _them_skill(repo)
    assert _sync(repo).returncode == 0
    readme = (repo / "README.md").read_text(encoding="utf-8")
    assert "/mecsu-anh" in readme
    assert "Cat logo, xoa nen hang loat" in readme
    assert _sync(repo, "--check").returncode == 0


def test_chu_ngoai_moc_khong_bi_dong_vao(tmp_path):
    """Phan viet tay cua README - so do, cach cai - script khong duoc cham vao."""
    repo = _repo(tmp_path)
    truoc = (repo / "README.md").read_text(encoding="utf-8")
    _them_skill(repo)
    _sync(repo)
    sau = (repo / "README.md").read_text(encoding="utf-8")
    for doan in ("## Cài", "flowchart LR", "jobs/inbox/"):
        assert doan in truoc and doan in sau
