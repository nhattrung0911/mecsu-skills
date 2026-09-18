# -*- coding: utf-8 -*-
"""Vong 2d phai dung CUNG phep kiem ma nhu vong 1.

Vong 2d cham `ma_dung = m['ma'] in ten` - doi MA THO, ke ca tien to noi bo.
Nhung luat so 3 cua chinh skill CAM tien to noi bo trong ten ban hang, va ghi ro
day la loi da do: "de lot `SATA SAT-70303A` ra ten ban hang (99/200 dong, tat ca
deu dang cham OK)". Vong 1 (`apply_convention.ma_dung_trong_ten`) kiem dung roi.

Do duoc o P2 (2026-09-18), cung mot cache trang web, cung 20 muc:
  che do LLM   : 20/20 ten chua ma tho `BSI-BS236848` -> 19 OK
  che do agent : 18/20 ten dung ma hang `BS236848`    ->  2 OK
Nghia la phep kiem THUONG cho viec pha luat va PHAT viec tuan luat.
"""
import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _nap(ten: str):
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("nm_" + ten, SCRIPTS / (ten + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules["nm_" + ten] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def test_ten_dung_ma_hang_thi_DAT():
    """`Bosi BS236848` la ten DUNG - bo tien to noi bo `BSI-`."""
    ew = _nap("extract_from_web")
    assert ew.ma_dung_trong_ten("BSI-BS236848", "Mỏ Lết Răng 48 Inch Bosi BS236848",
                                "BS236848") is True


def test_ten_de_lot_tien_to_noi_bo_thi_KHONG_DAT():
    """`Bosi BSI-BS236848` la dung loi da do 99/200 dong - khong duoc cham OK."""
    ew = _nap("extract_from_web")
    assert ew.ma_dung_trong_ten("BSI-BS236848", "Mỏ Lết Răng 48 Inch Bosi BSI-BS236848",
                                "BS236848") is False


def test_ten_khong_chua_ma_nao_thi_KHONG_DAT():
    ew = _nap("extract_from_web")
    assert ew.ma_dung_trong_ten("BSI-BS236848", "Mỏ Lết Răng 48 Inch Bosi",
                                "BS236848") is False


def test_khong_tach_duoc_tien_to_thi_can_cu_la_ma_goc():
    """Ma khong co tien to noi bo: `C-1 450x16x21` phai xuat hien nguyen van."""
    ew = _nap("extract_from_web")
    assert ew.ma_dung_trong_ten("C-1 450x16x21", "Xà Beng Mokuba C-1 450x16x21", "") is True
    assert ew.ma_dung_trong_ten("C-1 450x16x21", "Xà Beng Mokuba C1-450x16x21", "") is False


def test_dung_CHUNG_ham_voi_vong_1_khong_viet_lai():
    """Hai vong cham khac nhau la nguon goc cua chinh lo nay."""
    ew, ac = _nap("extract_from_web"), _nap("apply_convention")
    for ma, ten, ma_hang in (
        ("BSI-BS236848", "Mỏ Lết Bosi BS236848", "BS236848"),
        ("BSI-BS236848", "Mỏ Lết Bosi BSI-BS236848", "BS236848"),
        ("SAT-70303A", "Đầu Tuýp SATA 70303A", "70303A"),
        ("SAT-70303A", "Đầu Tuýp SATA SAT-70303A", "70303A"),
    ):
        assert ew.ma_dung_trong_ten(ma, ten, ma_hang) == ac.ma_dung_trong_ten(ma, ten, ma_hang), \
            (ma, ten)


def test_vong_2d_TU_LAY_duoc_ma_hang_tu_ma_tho():
    """Lo trong ban vá dau: `muc_tieu` khong co `ma_hang` nen phep kiem lai roi ve
    ma tho, va vá thanh vo hieu tren du lieu that. Test dau tien khong bat duoc vi
    no truyen ma_hang bang tay."""
    ec = _nap("extract_codes")
    assert ec.tach("BSI-BS236848").get("ma_hang") == "BS236848"
    assert ec.tach("SAT-70303A").get("ma_hang") == "70303A"
    assert ec.tach("10-175").get("ma_hang") == "10-175"       # khong co tien to


def test_vong_2d_co_noi_ma_hang_vao_muc_tieu():
    """Doc thang code: `muc_tieu` phai mang ma_hang, khong thi vá vo hieu."""
    text = (SCRIPTS / "extract_from_web.py").read_text(encoding="utf-8")
    assert "'ma_hang': tach_ma(ma)" in text
