# -*- coding: utf-8 -*-
"""Nang `--den-vong` KHONG duoc chay lai buoc da xong.

Ba lo do lan chay P1/P2 tren 100 ma that (2026-09-17):

1. Vong 1 bi tra tien lai moi lan nang `--den-vong`: log vong 3 lap lai
   "100 -> 5 lan goi (batch 20)". Di 1 -> 2 -> 3 la tra tien vong 1 BA lan.
2. Chay them vong lam MAT ket qua: sau vong 2 co 21 OK, sau vong 3 con 19 OK.
   Vong 3 tai va rut lai tu dau, lan nay ra it hon. Chay them de tot hon lai te hon.
3. Buoc tim kiem chay lai vo dieu kien: 33 phut moi lan, va o che do agent moi
   lan ban giao la mot lan chay lai ca vong -> file lon gan nhu khong dung duoc.

Hop dong: bo qua buoc nao ma DAU VAO khong doi va dau ra con dung. Khoa theo NOI
DUNG dau vao, khong theo su ton tai cua file - input doi thi phai chay lai.
"""
import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _nap():
    spec = importlib.util.spec_from_file_location("naming_run", SCRIPTS / "run.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["naming_run"] = module
    spec.loader.exec_module(module)
    return module


def _ra(thu_muc: Path, noi_dung="[1]") -> Path:
    p = thu_muc / "ra.json"
    p.write_text(noi_dung, encoding="utf-8")
    return p


def test_dau_vao_khong_doi_thi_bo_qua(tmp_path):
    run = _nap()
    vao = tmp_path / "vao.json"
    vao.write_text('{"a": 1}', encoding="utf-8")
    ra = _ra(tmp_path)
    run.ghi_dau_nguon(ra, [vao])
    assert run.can_chay_lai(ra, [vao]) is False


def test_dau_vao_DOI_thi_phai_chay_lai(tmp_path):
    """Khoa theo noi dung: input doi ma dung ket qua cu la gan nham du lieu."""
    run = _nap()
    vao = tmp_path / "vao.json"
    vao.write_text('{"a": 1}', encoding="utf-8")
    ra = _ra(tmp_path)
    run.ghi_dau_nguon(ra, [vao])
    vao.write_text('{"a": 2}', encoding="utf-8")
    assert run.can_chay_lai(ra, [vao]) is True


def test_chua_co_dau_nguon_thi_phai_chay(tmp_path):
    run = _nap()
    vao = tmp_path / "vao.json"
    vao.write_text("x", encoding="utf-8")
    assert run.can_chay_lai(_ra(tmp_path), [vao]) is True


def test_dau_ra_bien_mat_thi_phai_chay_lai(tmp_path):
    run = _nap()
    vao = tmp_path / "vao.json"
    vao.write_text("x", encoding="utf-8")
    ra = _ra(tmp_path)
    run.ghi_dau_nguon(ra, [vao])
    ra.unlink()
    assert run.can_chay_lai(ra, [vao]) is True


def test_dau_ra_RONG_thi_phai_chay_lai(tmp_path):
    """File rong cung la that bai - dung tin mot ket qua rong da cache."""
    run = _nap()
    vao = tmp_path / "vao.json"
    vao.write_text("x", encoding="utf-8")
    ra = _ra(tmp_path, noi_dung="[]")
    run.ghi_dau_nguon(ra, [vao])
    assert run.can_chay_lai(ra, [vao]) is True


def test_thu_muc_lam_dau_ra_van_tinh_duoc(tmp_path):
    """Vong 2c ghi ra mot THU MUC (web/), khong phai file."""
    run = _nap()
    vao = tmp_path / "vao.json"
    vao.write_text("x", encoding="utf-8")
    web = tmp_path / "web"
    web.mkdir()
    (web / "mot_trang.txt").write_text("noi dung", encoding="utf-8")
    run.ghi_dau_nguon(web, [vao])
    assert run.can_chay_lai(web, [vao]) is False


def test_thu_muc_dau_ra_rong_thi_phai_chay_lai(tmp_path):
    run = _nap()
    vao = tmp_path / "vao.json"
    vao.write_text("x", encoding="utf-8")
    web = tmp_path / "web"
    web.mkdir()
    run.ghi_dau_nguon(web, [vao])
    assert run.can_chay_lai(web, [vao]) is True


def test_ep_lam_lai_thi_bo_qua_moi_dau_nguon(tmp_path):
    run = _nap()
    vao = tmp_path / "vao.json"
    vao.write_text("x", encoding="utf-8")
    ra = _ra(tmp_path)
    run.ghi_dau_nguon(ra, [vao])
    assert run.can_chay_lai(ra, [vao], lam_lai=True) is True


def test_dau_nguon_khong_lan_vao_thu_muc_job(tmp_path):
    """Dau nguon phai la file an, khong duoc lam ban thu muc ket qua cua nguoi dung."""
    run = _nap()
    vao = tmp_path / "vao.json"
    vao.write_text("x", encoding="utf-8")
    ra = _ra(tmp_path)
    run.ghi_dau_nguon(ra, [vao])
    sinh_ra = {p.name for p in tmp_path.iterdir()} - {"vao.json", "ra.json"}
    assert all(n.startswith(".") for n in sinh_ra), sinh_ra


def test_co_lam_lai_ton_tai_trong_argparse():
    """Khong co duong ep chay lai thi nguoi dung bi ket voi ket qua cu."""
    text = (SCRIPTS / "run.py").read_text(encoding="utf-8")
    assert "--lam-lai" in text
