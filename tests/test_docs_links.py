# -*- coding: utf-8 -*-
"""Link trong tai lieu goc phai tro toi file co that.

Loi that: README tro toi CLAUDE.md nhieu ngay sau khi file do khong con nam trong
repo nua. `lint_skills.py` khong bat vi no chi soi thu muc skills/, con README va
AGENTS.md la thu nguoi la nhin thay DAU TIEN khi mo GitHub.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TAI_LIEU = ("README.md", "AGENTS.md", "docs/huong-dan-su-dung.md")

# [chu](duong-dan) - bo qua link ngoai va link chi co neo trong cung trang.
LINK = re.compile(r"\[[^\]]*\]\((?!https?://|mailto:|#)([^)\s]+)\)")


@pytest.mark.parametrize("ten", TAI_LIEU)
def test_link_tuong_doi_khong_chet(ten):
    nguon = ROOT / ten
    assert nguon.exists(), f"thieu {ten}"

    hong = []
    for duong_dan in LINK.findall(nguon.read_text(encoding="utf-8")):
        dich = (nguon.parent / duong_dan.split("#", 1)[0]).resolve()
        if not dich.exists():
            hong.append(duong_dan)

    assert not hong, f"{ten} tro toi file khong ton tai: {', '.join(hong)}"
