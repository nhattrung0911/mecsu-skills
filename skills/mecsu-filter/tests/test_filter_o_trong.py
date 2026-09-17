# -*- coding: utf-8 -*-
"""O filter DE TRONG THAT trong Excel phai duoc coi la RONG.

openpyxl tra ve None cho o trong, khong phai chuoi rong. `parse_filters(None)` chay
`str(None)` -> chuoi "None" -> sinh ra mot cap filter gia ('None', ''), nen o trong
bi coi la CO filter.

Hau qua da do tren 100 dong that (P3, 2026-09-17): 30 o bi xoa trang khong dong nao
duoc gan co rong, audit bao "0 o filter con thieu", hang doi rong, ca day chuyen chet.
Nang hon: nhung dong trong do LOT vao tap "peer hop le" cua `learn_cluster`, lam
phinh mau so, keo ty le ho tro xuong duoi nguong, nen ca cum 16 dong khong hoc duoc
thuoc tinh nao - 11 dong con nguyen filter cung bi va lay.

Nghia la: file co o trong -> skill bao "khong thieu gi". Sai am tham.
"""
import importlib.util
import pickle
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _nap():
    spec = importlib.util.spec_from_file_location("filter_audit_test", SCRIPTS / "filter_audit.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["filter_audit_test"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("o_trong", [None, "", "   ", "\n"])
def test_moi_kieu_o_trong_deu_ra_khong_co_cap_filter(o_trong):
    fa = _nap()
    assert fa.parse_filters(o_trong) == [], repr(o_trong)


@pytest.mark.parametrize("o_trong", [None, "", "   "])
def test_moi_kieu_o_trong_deu_bi_coi_la_rong(o_trong):
    fa = _nap()
    assert fa.is_empty_filter(fa.parse_filters(o_trong)) is True, repr(o_trong)


def test_khong_sinh_ra_khoa_rac_ten_None():
    """'None' tung bi dung lam TEN thuoc tinh, roi di vao von tu va vao prompt."""
    fa = _nap()
    assert not any(k.strip().lower() == "none" for k, _ in fa.parse_filters(None))


def test_gia_tri_that_van_parse_binh_thuong():
    fa = _nap()
    cap = fa.parse_filters("Chiều dài: 10 mm | Vật liệu: Thép")
    assert ("Chiều dài", "10 mm") in cap
    assert fa.is_empty_filter(cap) is False


def test_na_van_duoc_coi_la_rong():
    """Du lieu that dung 'N/A: N/A' cho o chua co gi - dung lam hong duong nay."""
    fa = _nap()
    assert fa.is_empty_filter(fa.parse_filters("N/A: N/A")) is True


def test_audit_that_gan_co_rong_cho_o_de_trong(tmp_path):
    """Chay filter_audit.py that: dong co o trong phai bi dem la thieu filter."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["part_id", "part_number", "part_description",
               "leaf_category_name", "category_lv1", "active_filter_count", "mapped_filters"])
    for i in range(12):
        # Ba dong dau de TRONG THAT (None), chin dong sau co filter day du.
        day_du = "Chiều dài: %d mm | Vật liệu: Thép" % (10 + i)
        ws.append([i, "MA%03d" % i, "Cờ Lê Vòng Miệng %d mm Test" % (10 + i),
                   "Cờ Lê Vòng Miệng", "Dụng cụ cầm tay", 2, None if i < 3 else day_du])
    nguon = tmp_path / "co_o_trong.xlsx"
    wb.save(nguon)

    ket_qua = subprocess.run(
        [sys.executable, str(SCRIPTS / "filter_audit.py"), str(nguon),
         "--out", str(tmp_path / "audit"), "--xlsx-out", str(tmp_path / "audit.xlsx")],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    assert ket_qua.returncode == 0, ket_qua.stdout + ket_qua.stderr

    rows, _ = pickle.load(open(tmp_path / "audit.pkl", "rb"))
    theo_ma = {str(r["ma"]): r for r in rows}          # audit dat ten khoa la 'ma'
    for i in range(3):
        # 'e_rong' la 'X' hoac '' - khong phai bool.
        assert theo_ma["MA%03d" % i]["e_rong"] == "X",             "MA%03d de trong that nhung audit khong coi la rong" % i
    for i in range(3, 12):
        assert theo_ma["MA%03d" % i]["e_rong"] == "", "MA%03d co filter day du" % i
