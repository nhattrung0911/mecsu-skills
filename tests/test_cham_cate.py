# -*- coding: utf-8 -*-
"""Cham soat danh muc phai do HAI mat, va phai la script.

Chi do "bat duoc bao nhieu" thi mot skill bao sai CA FILE cung dat 100%. Con so
len tai lieu phai sinh lai duoc tu artifact (CLAUDE.md muc 6), nen phep cham nay
la lenh chay duoc, khong phai loi ke cua agent.
"""
import json
import subprocess
import sys
from pathlib import Path

import openpyxl

GOC = Path(__file__).resolve().parents[1]
CONG_CU = GOC / "tools" / "cham_cate.py"


def _changelog(thu_muc: Path, bao: dict) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["part_id", "part_number", "old_leaf_name", "new_leaf_name"])
    for i, (ma, moi) in enumerate(bao.items()):
        ws.append([i, ma, "cu", moi])
    p = thu_muc / "changelog.xlsx"
    wb.save(p)
    return p


def _dap_an(thu_muc: Path, da_doi: dict) -> Path:
    p = thu_muc / "dap_an.json"
    p.write_text(json.dumps({"khoa_la_cot": "part_number", "da_doi": da_doi},
                            ensure_ascii=False), encoding="utf-8")
    return p


def _cham(changelog: Path, dap_an: Path, tong: int):
    return subprocess.run(
        [sys.executable, str(CONG_CU), "--changelog", str(changelog),
         "--dap-an", str(dap_an), "--tong-dong", str(tong)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def test_bat_dung_het_va_khong_bao_gia(tmp_path):
    da_doi = {"A": {"goc": "Cưa Tay", "gan_sai": "Cờ Lê"},
              "B": {"goc": "Cưa Tay", "gan_sai": "Cờ Lê"}}
    ra = _cham(_changelog(tmp_path, {"A": "Cưa Tay", "B": "Cưa Tay"}),
               _dap_an(tmp_path, da_doi), 10)
    assert ra.returncode == 0, ra.stdout + ra.stderr
    assert "bat dung          2/2" in ra.stdout
    assert "bao dong gia      0/8" in ra.stdout
    assert "de xuat dung goc   2/2" in ra.stdout


def test_bao_ca_file_thi_bao_dong_gia_phai_lo_ra(tmp_path):
    """Skill bao sai moi dong: bat dung 100% nhung bao dong gia 100% - phai thay ca hai."""
    da_doi = {"A": {"goc": "Cưa Tay", "gan_sai": "Cờ Lê"}}
    bao = {"A": "Cưa Tay", "B": "x", "C": "x", "D": "x"}
    ra = _cham(_changelog(tmp_path, bao), _dap_an(tmp_path, da_doi), 4)
    assert "bat dung          1/1" in ra.stdout
    assert "bao dong gia      3/3" in ra.stdout


def test_bo_sot_duoc_bao_ra(tmp_path):
    da_doi = {"A": {"goc": "Cưa Tay", "gan_sai": "Cờ Lê"},
              "B": {"goc": "Cưa Tay", "gan_sai": "Cờ Lê"}}
    ra = _cham(_changelog(tmp_path, {"A": "Cưa Tay"}), _dap_an(tmp_path, da_doi), 10)
    assert "BO SOT (1)" in ra.stdout and "'B'" in ra.stdout


def test_bat_dung_nhung_de_xuat_sai_thi_lo_ra(tmp_path):
    """Bat dung dong sai ma de xuat mot danh muc khac cung la sai - khong duoc tinh la dat."""
    da_doi = {"A": {"goc": "Cưa Tay", "gan_sai": "Cờ Lê"}}
    ra = _cham(_changelog(tmp_path, {"A": "Kìm Điện"}), _dap_an(tmp_path, da_doi), 10)
    assert "de xuat dung goc   0/1" in ra.stdout
    assert "BAT DUNG NHUNG DE XUAT SAI" in ra.stdout


def test_dap_an_kieu_xoa_o_thi_thoat_khac_0(tmp_path):
    """Dua dap an cua mecsu-filter vao day la dung sai cong cu - phai chet cho on."""
    p = tmp_path / "dap_an.json"
    p.write_text(json.dumps({"da_xoa": {"A": "x"}}), encoding="utf-8")
    ra = _cham(_changelog(tmp_path, {"A": "y"}), p, 10)
    assert ra.returncode != 0
    assert "khong phai kieu gan sai" in (ra.stdout + ra.stderr)


def test_changelog_thieu_cot_thi_thoat_khac_0(tmp_path):
    wb = openpyxl.Workbook()
    wb.active.append(["part_id", "part_number"])
    p = tmp_path / "thieu.xlsx"
    wb.save(p)
    ra = _cham(p, _dap_an(tmp_path, {"A": {"goc": "x", "gan_sai": "y"}}), 10)
    assert ra.returncode != 0
