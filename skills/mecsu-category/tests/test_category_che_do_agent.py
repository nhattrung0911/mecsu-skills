# -*- coding: utf-8 -*-
""".env la TUY CHON cho ca category/filter, khong chi rieng naming.

Truoc day load_llm_config() thoat ngay khi thieu MECSU_BASE_URL, nen khong co key
la khong dung duoc skill - du agent dang chay du sức lam phan viec do.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parents[3]


def _nap(skill: str):
    """Nap duoi ten rieng: hai skill co skill_env.py trung ten, import thuong se lan nhau."""
    duong_dan = GOC / "skills" / skill / "scripts" / "skill_env.py"
    ten = "env_" + skill.replace("-", "_")
    spec = importlib.util.spec_from_file_location(ten, duong_dan)
    module = importlib.util.module_from_spec(spec)
    sys.modules[ten] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _khong_dinh_env_that(monkeypatch):
    for khoa in ("BASE_URL", "MODELS", "API_KEY", "CHE_DO"):
        monkeypatch.delenv("MECSU_" + khoa, raising=False)
        monkeypatch.delenv("ONCHECK_" + khoa, raising=False)
        monkeypatch.delenv("NF_" + khoa, raising=False)


@pytest.mark.parametrize("skill", ["mecsu-category", "mecsu-filter"])
def test_thieu_endpoint_thi_sang_che_do_agent_chu_khong_chet(skill, monkeypatch, tmp_path):
    env = _nap(skill)
    monkeypatch.setattr(env, "load_dotenv", lambda *a, **k: None)
    config = env.load_llm_config(bat_buoc=False)
    assert config["che_do"] == "agent"
    assert not env.co_llm(config)
    assert env.chuan_bi(config, tmp_path / "out.json") == "agent"


@pytest.mark.parametrize("skill", ["mecsu-category", "mecsu-filter"])
def test_script_bat_buoc_endpoint_thi_van_chet(skill, monkeypatch):
    """eval_models.py do model that: khong co endpoint thi khong do duoc, phai chet."""
    env = _nap(skill)
    monkeypatch.setattr(env, "load_dotenv", lambda *a, **k: None)
    with pytest.raises(SystemExit):
        env.load_llm_config()


@pytest.mark.parametrize("skill", ["mecsu-category", "mecsu-filter"])
def test_ep_che_do_agent_du_co_key(skill, monkeypatch, tmp_path):
    env = _nap(skill)
    monkeypatch.setattr(env, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setenv("MECSU_BASE_URL", "http://x/v1")
    monkeypatch.setenv("MECSU_MODELS", "m")
    monkeypatch.setenv("MECSU_CHE_DO", "agent")
    assert env.load_llm_config(bat_buoc=False)["che_do"] == "agent"


@pytest.mark.parametrize("skill", ["mecsu-category", "mecsu-filter"])
def test_chua_tra_loi_thi_nem_ThieuTraLoi_va_thoat_4(skill, monkeypatch, tmp_path):
    env = _nap(skill)
    monkeypatch.setattr(env, "load_dotenv", lambda *a, **k: None)
    config = env.load_llm_config(bat_buoc=False)
    env.chuan_bi(config, tmp_path / "out.json")
    with pytest.raises(env.ThieuTraLoi):
        env.hoi_agent("he thong", "san pham X thuoc danh muc nao?")
    with pytest.raises(SystemExit) as loi:
        env.chot_hoi_dap("buoc-thu")
    # Phai la SO tran: SystemExit(4, 'msg') lam Python thoat 1 va in nguyen tuple.
    assert loi.value.code == env.THOAT_CAN_AGENT
    ghi = json.loads((tmp_path / "hoi_agent" / "cau_hoi.json").read_text(encoding="utf-8"))
    assert len(ghi["cau_hoi"]) == 1


@pytest.mark.parametrize("skill", ["mecsu-category", "mecsu-filter"])
def test_da_dien_thi_tra_ve_va_khong_thoat(skill, monkeypatch, tmp_path):
    env = _nap(skill)
    monkeypatch.setattr(env, "load_dotenv", lambda *a, **k: None)
    khoa = env.khoa_noi_dung("he thong", "cau hoi")
    (tmp_path / "hoi_agent").mkdir()
    (tmp_path / "hoi_agent" / "tra_loi.json").write_text(
        json.dumps({khoa: '[{"id": 1}]'}), encoding="utf-8")
    config = env.load_llm_config(bat_buoc=False)
    env.chuan_bi(config, tmp_path / "out.json")
    assert env.hoi_agent("he thong", "cau hoi") == '[{"id": 1}]'
    env.chot_hoi_dap("buoc-thu")


@pytest.mark.parametrize("skill", ["mecsu-category", "mecsu-filter"])
def test_khoa_theo_noi_dung_khong_theo_thu_tu(skill):
    env = _nap(skill)
    assert env.khoa_noi_dung("he", "A") != env.khoa_noi_dung("he", "B")
    assert env.khoa_noi_dung("he", "A") == env.khoa_noi_dung("he", "A")


def _nap_script(skill: str, ten_file: str):
    """Nap script co call_model, kem thu muc scripts/ vao sys.path cho import noi bo."""
    thu_muc = GOC / "skills" / skill / "scripts"
    sys.path.insert(0, str(thu_muc))
    try:
        ten = "script_" + skill.replace("-", "_") + "_" + ten_file
        spec = importlib.util.spec_from_file_location(ten, thu_muc / (ten_file + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[ten] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(thu_muc))


LO_FILTER = [{"ask_id": 1, "sample_name": "Bulong DIN 933 M20", "sample_known": {},
              "attr": "Bước Ren"}]
LO_CATEGORY = [{"id": 1, "part_description": "Bulong luc giac M20", "leaf": "Bu lông"}]


def test_call_model_che_do_agent_khong_goi_mang(monkeypatch, tmp_path):
    """call_model phai re sang ban giao file, khong duoc cham toi requests."""
    fill = _nap_script("mecsu-filter", "ai_fill")
    monkeypatch.setattr(fill.requests, "post", lambda *a, **k: pytest.fail("da goi mang"))
    config = {"che_do": "agent", "temperature": 0, "api_key": "x", "base_url": "http://x"}
    fill.skill_env.chuan_bi(config, tmp_path / "out.json")
    with pytest.raises(fill.skill_env.ThieuTraLoi):
        fill.call_model(config, "m", LO_FILTER, "Bu lông", {})


def test_call_model_doc_cau_tra_loi_agent_qua_dung_parse(monkeypatch, tmp_path):
    """Cau tra loi cua agent phai di qua parse_array y nhu cua model."""
    fill = _nap_script("mecsu-filter", "ai_fill")
    monkeypatch.setattr(fill.requests, "post", lambda *a, **k: pytest.fail("da goi mang"))
    config = {"che_do": "agent", "temperature": 0, "api_key": "x", "base_url": "http://x"}
    khoa = fill.skill_env.khoa_noi_dung(
        fill.SYSTEM_PROMPT, fill.build_user_message(LO_FILTER, "Bu lông", {}))
    (tmp_path / "hoi_agent").mkdir()
    (tmp_path / "hoi_agent" / "tra_loi.json").write_text(json.dumps(
        {khoa: '[{"id": 1, "value": "2.5 mm", "confidence": 0.9, "reason": "DIN 933"}]'}),
        encoding="utf-8")
    fill.skill_env.chuan_bi(config, tmp_path / "out.json")
    tra_loi, usage = fill.call_model(config, "m", LO_FILTER, "Bu lông", {})
    assert tra_loi[0]["value"] == "2.5 mm"
    assert usage == {}
