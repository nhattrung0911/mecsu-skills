# -*- coding: utf-8 -*-
"""Tang 1 - dung URL trang hang tu ma.

Khong ca nao o day cham mang: `--check` la phep do song, co y de chay tay khi
muon biet mau URL con dung khong, khong phai thu de gai vao bo test.
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'vendor_url.py'


def _chay(tmp_path: Path, danh_sach: list, *co):
    vao = tmp_path / 'codes.json'
    vao.write_text(json.dumps(danh_sach, ensure_ascii=False), encoding='utf-8')
    ra = tmp_path / 'sources.json'
    xong = subprocess.run(
        [sys.executable, str(SCRIPT), '--codes', str(vao), '--out', str(ra), *co],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    return xong, (json.loads(ra.read_text(encoding='utf-8')) if ra.exists() else None)


def _muc(hang: str, ma: str) -> dict:
    return {'ma_goc': '%s-%s' % (hang[:3].upper(), ma), 'hang': hang, 'ma_hang': ma, 'dong': [2]}


def test_sata_dung_dung_mau(tmp_path):
    _, ra = _chay(tmp_path, [_muc('SATA', '34505')])
    assert ra[0]['url_hang'] == 'https://www.satatools.com/en/Product/show/34505.html'
    assert ra[0]['tang'] == 'trang-hang'


def test_anex_giu_gach_ngang(tmp_path):
    """Do 2026-09-11: .../item/ABRS-2110/ tra 200, .../item/ABRS2110/ tra 404.

    Thieu ca nay thi mot lan "don dep" ma bo gach ngang se lam ca nhanh Anex tra
    404 het, va khong gi bao ngoai viec ket qua rong.
    """
    _, ra = _chay(tmp_path, [_muc('Anex', 'ABRS-2110')])
    assert ra[0]['url_hang'] == 'https://www.anextool.co.jp/item/ABRS-2110/'


def test_hau_to_chu_van_vao_url(tmp_path):
    _, ra = _chay(tmp_path, [_muc('SATA', '96552K')])
    assert ra[0]['url_hang'].endswith('/96552K.html')


def test_hang_chua_co_mau_thi_roi_xuong_tim_kiem(tmp_path):
    """Bosi chua co mau tra thang - phai ghi ro la can tim kiem, khong dung URL bua."""
    _, ra = _chay(tmp_path, [_muc('Bosi', 'BS423172'), {'ma_goc': 'X1', 'hang': '', 'ma_hang': 'X1', 'dong': [2]}])
    assert all(m['url_hang'] is None for m in ra)
    assert all(m['tang'] == 'can-tim-kiem' for m in ra)


def test_codes_rong_thi_thoat_khac_0(tmp_path):
    """File rong ma thoat 0 la bao xong trong khi chua lam gi."""
    xong, _ = _chay(tmp_path, [])
    assert xong.returncode != 0


def test_thieu_file_codes_thi_thoat_khac_0(tmp_path):
    xong = subprocess.run(
        [sys.executable, str(SCRIPT), '--codes', str(tmp_path / 'khong-co.json')],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    assert xong.returncode != 0
