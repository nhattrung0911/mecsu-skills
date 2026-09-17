# -*- coding: utf-8 -*-
"""Cat mau N dong de chay thu, LAP LAI DUOC.

Khong co cong cu nay thi moi lan chay thu lai mot tap dong khac -> so do giua hai
lan khong so duoc voi nhau, va "hoi quy" tro thanh doan mo.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest

GOC = Path(__file__).resolve().parents[1]
CONG_CU = GOC / "tools" / "lay_mau.py"


def _file_nguon(thu_muc: Path, so_dong: int = 50) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["part_id", "part_number", "part_description"])
    for i in range(so_dong):
        ws.append([i, "MA%03d" % i, "San pham %d" % i])
    duong_dan = thu_muc / "nguon.xlsx"
    wb.save(duong_dan)
    return duong_dan


def _chay(nguon: Path, ra: Path, rows: int, seed: int = 0):
    return subprocess.run(
        [sys.executable, str(CONG_CU), "--input", str(nguon), "--rows", str(rows),
         "--seed", str(seed), "--out", str(ra)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def _van_tay(duong_dan: Path) -> str:
    """Hash noi dung cac dong - de so hai lan chay co ra dung cung tap dong khong."""
    ws = openpyxl.load_workbook(duong_dan, read_only=True).worksheets[0]
    text = "\n".join("|".join(str(v) for v in hang) for hang in ws.iter_rows(values_only=True))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_dung_so_dong_va_giu_nguyen_header(tmp_path):
    nguon = _file_nguon(tmp_path)
    ra = tmp_path / "mau.xlsx"
    assert _chay(nguon, ra, 10).returncode == 0
    hang = list(openpyxl.load_workbook(ra, read_only=True).worksheets[0]
                .iter_rows(values_only=True))
    assert hang[0] == ("part_id", "part_number", "part_description")
    assert len(hang) == 11                      # 1 header + 10 dong du lieu


def test_cung_seed_ra_cung_tap_dong(tmp_path):
    """Cot loi: khong lap lai duoc thi khong so duoc so do giua hai lan chay."""
    nguon = _file_nguon(tmp_path)
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    _chay(nguon, a, 10, seed=7)
    _chay(nguon, b, 10, seed=7)
    assert _van_tay(a) == _van_tay(b)


def test_seed_khac_ra_tap_khac(tmp_path):
    nguon = _file_nguon(tmp_path)
    a, b = tmp_path / "a.xlsx", tmp_path / "b.xlsx"
    _chay(nguon, a, 10, seed=0)
    _chay(nguon, b, 10, seed=1)
    assert _van_tay(a) != _van_tay(b)


def test_xin_nhieu_hon_so_dong_co_that_thi_lay_het_khong_chet(tmp_path):
    nguon = _file_nguon(tmp_path, so_dong=5)
    ra = tmp_path / "mau.xlsx"
    ket_qua = _chay(nguon, ra, 100)
    assert ket_qua.returncode == 0
    hang = list(openpyxl.load_workbook(ra, read_only=True).worksheets[0]
                .iter_rows(values_only=True))
    assert len(hang) == 6


def test_khong_thay_file_thi_thoat_khac_0(tmp_path):
    ket_qua = _chay(tmp_path / "khong-co.xlsx", tmp_path / "ra.xlsx", 10)
    assert ket_qua.returncode != 0


def test_giu_nguyen_thu_tu_goc(tmp_path):
    """Dao thu tu dong lam kho doi chieu bang mat voi file goc."""
    nguon = _file_nguon(tmp_path)
    ra = tmp_path / "mau.xlsx"
    _chay(nguon, ra, 10)
    ids = [h[0] for h in openpyxl.load_workbook(ra, read_only=True).worksheets[0]
           .iter_rows(min_row=2, values_only=True)]
    assert ids == sorted(ids)
