# -*- coding: utf-8 -*-
"""Website phai mo ta dung nhung skill DANG CO trong repo.

Loi that: site quang cao skill `category-auto` trong nhieu tuan sau khi skill do khong con
ton tai, vi khong co gi rang buoc site voi thu muc skills/.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SKILLS = ROOT / "skills"

# Thu KHONG duoc lo ra trang public: key, endpoint noi bo, ten file du lieu khach hang.
# Khong chan chung chung ".env" hay ".xlsx" - trang phai duoc phep huong dan nguoi dung
# ve file .env va ve file .xlsx cua chinh ho.
FORBIDDEN = (
    "MECSU_API_KEY",
    "MECSU_BASE_URL",
    "9router",
    "mspro.io.vn",
    "Handtools-check",
    "Cate_mine",
)


def skill_ids() -> set:
    return {p.name for p in SKILLS.iterdir() if (p / "SKILL.md").exists()}


def catalog() -> list:
    return json.loads((SITE / "public-skill-catalog.json").read_text(encoding="utf-8"))["skills"]


def test_du_file_de_deploy():
    for name in ("index.html", "app.js", "styles.css", "favicon.svg", "_headers"):
        assert (SITE / name).exists(), f"thieu site/{name}"


def test_catalog_khop_thu_muc_skills():
    assert {item["skill_id"] for item in catalog()} == skill_ids()


def test_moi_skill_co_mot_muc_tren_trang():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    for item in catalog():
        assert f'id="{item["website_section"]}"' in html, f"trang thieu muc {item['skill_id']}"
        assert f'id="prompt-{item["skill_id"]}"' in html, f"thieu prompt mau cho {item['skill_id']}"


def test_khong_lo_duong_dan_noi_bo():
    for name in ("index.html", "app.js", "public-skill-catalog.json"):
        text = (SITE / name).read_text(encoding="utf-8")
        for needle in FORBIDDEN:
            assert needle not in text, f"site/{name} lo '{needle}' ra trang public"
