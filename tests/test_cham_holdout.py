# -*- coding: utf-8 -*-
"""Cham diem hold-out phai do bang SCRIPT, khong phai bang loi ke cua agent.

Agent tu cham roi tu bao "khop 80%" la con so khong ai kiem lai duoc - dung loai
so bi cam o CLAUDE.md muc 6. Script nay bien no thanh so sinh lai duoc tu artifact.
"""
import json
import subprocess
import sys
from pathlib import Path

import openpyxl

GOC = Path(__file__).resolve().parents[1]
CONG_CU = GOC / "tools" / "cham_holdout.py"


def _file_ket_qua(thu_muc: Path, dien: dict) -> Path:
    """Gia lap file apply_fills.py dung ra: cot goc + cot 'Filter bo sung'."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["part_id", "part_number", "part_description", "Filter bo sung (key: value)"])
    for i, (ma, chuoi) in enumerate(dien.items()):
        ws.append([i, ma, "San pham %s" % ma, chuoi])
    duong_dan = thu_muc / "ket_qua.xlsx"
    wb.save(duong_dan)
    return duong_dan


def _file_dap_an(thu_muc: Path, that: dict) -> Path:
    duong_dan = thu_muc / "dap_an.json"
    duong_dan.write_text(json.dumps(
        {"khoa_la_cot": "part_number", "da_xoa": that}, ensure_ascii=False), encoding="utf-8")
    return duong_dan


def _cham(ket_qua: Path, dap_an: Path):
    return subprocess.run(
        [sys.executable, str(CONG_CU), "--ket-qua", str(ket_qua), "--dap-an", str(dap_an)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def test_khop_y_nguyen(tmp_path):
    that = {"MA1": "Chiều dài: 10 mm | Vật liệu: Thép"}
    ra = _cham(_file_ket_qua(tmp_path, {"MA1": "Chiều dài: 10 mm | Vật liệu: Thép"}),
               _file_dap_an(tmp_path, that))
    assert ra.returncode == 0, ra.stdout + ra.stderr
    assert "y_nguyen        2" in ra.stdout


def test_cung_so_do_khac_cach_viet_khong_bi_tinh_la_sai(tmp_path):
    """'10mm' va '10 mm' la loi DINH DANG, khong phai tra sai so - phai tach ra."""
    that = {"MA1": "Chiều dài: 10 mm"}
    ra = _cham(_file_ket_qua(tmp_path, {"MA1": "Chiều dài: 10mm"}),
               _file_dap_an(tmp_path, that))
    assert ra.returncode == 0, ra.stdout + ra.stderr
    assert "cung_so_do      1" in ra.stdout
    assert "khac            0" in ra.stdout


def test_so_khac_thi_tinh_la_khac(tmp_path):
    that = {"MA1": "Chiều dài: 10 mm"}
    ra = _cham(_file_ket_qua(tmp_path, {"MA1": "Chiều dài: 25 mm"}),
               _file_dap_an(tmp_path, that))
    assert "khac            1" in ra.stdout


def test_khong_dien_thi_tinh_la_de_trong(tmp_path):
    that = {"MA1": "Chiều dài: 10 mm | Vật liệu: Thép"}
    ra = _cham(_file_ket_qua(tmp_path, {"MA1": "Chiều dài: 10 mm"}),
               _file_dap_an(tmp_path, that))
    assert "de_trong        1" in ra.stdout


def test_ma_thieu_han_trong_file_ket_qua_duoc_bao_ra(tmp_path):
    """Thieu ma ma im lang la cham diem tren tap nho hon thuc te -> so bi dep len."""
    that = {"MA1": "Chiều dài: 10 mm", "MA_BIEN_MAT": "Chiều dài: 12 mm"}
    ra = _cham(_file_ket_qua(tmp_path, {"MA1": "Chiều dài: 10 mm"}),
               _file_dap_an(tmp_path, that))
    assert "MA KHONG THAY" in ra.stdout
    assert "MA_BIEN_MAT" in ra.stdout


def test_file_ket_qua_thieu_cot_dien_thi_thoat_khac_0(tmp_path):
    """Doc nham cot roi bao 0% la ket luan sai ve skill - phai chet cho on."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["part_id", "part_number"])
    ws.append([1, "MA1"])
    kq = tmp_path / "thieu_cot.xlsx"
    wb.save(kq)
    ra = _cham(kq, _file_dap_an(tmp_path, {"MA1": "Chiều dài: 10 mm"}))
    assert ra.returncode != 0
    assert "khong co cot nao" in (ra.stdout + ra.stderr)


def test_na_khong_bi_dem_la_mot_cap(tmp_path):
    that = {"MA1": "N/A: N/A | Chiều dài: 10 mm"}
    ra = _cham(_file_ket_qua(tmp_path, {"MA1": "Chiều dài: 10 mm"}),
               _file_dap_an(tmp_path, that))
    assert "tong so CAP key:value phai dien: 1" in ra.stdout
