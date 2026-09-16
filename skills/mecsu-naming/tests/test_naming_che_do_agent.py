# -*- coding: utf-8 -*-
""".env la TUY CHON: co endpoint thi goi model re, khong co thi agent tu tra loi.

Truoc day thieu .env la SystemExit ngay - nghia la khong co key thi khong dung duoc
skill, du agent dang chay hoan toan du sức lam phan viec do.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _nap():
    """Nap bang importlib duoi ten rieng - nhieu skill co skill_env.py trung ten."""
    spec = importlib.util.spec_from_file_location("naming_skill_env", SCRIPTS / "skill_env.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["naming_skill_env"] = module
    spec.loader.exec_module(module)
    return module


CO_KEY = {"MECSU_BASE_URL": "http://x/v1", "MECSU_API_KEY": "k", "MECSU_MODELS": "m"}
KHONG_KEY = {"MECSU_BASE_URL": "", "MECSU_API_KEY": "", "MECSU_MODELS": ""}


def test_du_ba_khoa_thi_la_che_do_llm(tmp_path):
    env = _nap()
    assert env.co_llm(CO_KEY)
    assert env.chuan_bi(CO_KEY, tmp_path / "out.json") == "llm"


def test_thieu_khoa_thi_khong_chet_ma_sang_che_do_agent(tmp_path):
    env = _nap()
    assert not env.co_llm(KHONG_KEY)
    assert env.chuan_bi(KHONG_KEY, tmp_path / "out.json") == "agent"


def test_chua_co_cau_tra_loi_thi_nem_ThieuTraLoi_va_thoat_3(tmp_path):
    env = _nap()
    env.chuan_bi(KHONG_KEY, tmp_path / "out.json")
    with pytest.raises(env.ThieuTraLoi):
        env.hoi(KHONG_KEY, "san pham X la gi?", "tra ve JSON")

    with pytest.raises(SystemExit) as loi:
        env.chot_hoi_dap("vong-2")
    # Phai la SO tran. SystemExit(3, 'loi') lam Python thoat 1 va in nguyen tuple -
    # run.py se bao "hong" thay vi "dang cho agent". Da xay ra that.
    assert loi.value.code == env.THOAT_CAN_AGENT

    cau_hoi = json.loads((tmp_path / "hoi_agent" / "cau_hoi.json").read_text(encoding="utf-8"))
    assert cau_hoi["buoc"] == "vong-2"
    assert len(cau_hoi["cau_hoi"]) == 1


def test_da_dien_tra_loi_thi_hoi_tra_ve_va_khong_thoat(tmp_path):
    env = _nap()
    khoa = env.khoa_noi_dung("tra ve JSON", "san pham X la gi?")
    thu_muc = tmp_path / "hoi_agent"
    thu_muc.mkdir()
    (thu_muc / "tra_loi.json").write_text(
        json.dumps({khoa: '{"ten": "co le"}'}, ensure_ascii=False), encoding="utf-8")

    env.chuan_bi(KHONG_KEY, tmp_path / "out.json")
    assert env.hoi(KHONG_KEY, "san pham X la gi?", "tra ve JSON") == '{"ten": "co le"}'
    env.chot_hoi_dap("vong-2")          # khong con cau cho -> khong thoat


def test_khoa_theo_noi_dung_khong_theo_thu_tu(tmp_path):
    """Luat repo: doi thu tu input khong duoc gan cau tra loi cu sang san pham khac."""
    env = _nap()
    a = env.khoa_noi_dung("he", "san pham A")
    b = env.khoa_noi_dung("he", "san pham B")
    assert a != b
    assert a == env.khoa_noi_dung("he", "san pham A")


def test_co_key_nhung_ep_che_do_agent_thi_van_la_agent(tmp_path):
    """Co .env khong co nghia la bi bat xai .env - nguoi dung chon."""
    env = _nap()
    ep = dict(CO_KEY, MECSU_CHE_DO='agent')
    assert not env.co_llm(ep)
    assert env.chuan_bi(ep, tmp_path / "out.json") == "agent"


def test_phai_co_key_van_chet_cho_script_bat_buoc_endpoint():
    """eval_models.py do model that - khong co endpoint thi khong do duoc, phai chet."""
    env = _nap()
    with pytest.raises(SystemExit):
        env.phai_co_key(KHONG_KEY)
