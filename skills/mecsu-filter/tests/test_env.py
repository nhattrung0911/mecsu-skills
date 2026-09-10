# -*- coding: utf-8 -*-
"""Cau hinh nap sai thi moi thu phia sau sai theo, nen kiem tra thu tu uu tien."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

import pytest                       # noqa: E402
import skill_env                    # noqa: E402

BASE = {'MECSU_BASE_URL': 'https://9router.mspro.io.vn/v1',
        'MECSU_MODELS': 'ag/gemini-3.7-flash-medium'}


@pytest.fixture(autouse=True)
def khong_dinh_env_that(monkeypatch):
    """.env that cua may khong duoc lot vao test, neu khong test se do tren may nay
    va xanh tren may khac."""
    monkeypatch.setattr(skill_env, '_plugin_root', lambda _start: None)
    monkeypatch.setattr(skill_env, 'HERE', skill_env.HERE / '__khong_ton_tai__')
    for key in list(__import__('os').environ):
        if key.startswith(('MECSU_', 'NF_')):
            monkeypatch.delenv(key, raising=False)


def test_bien_moi_truong_du_de_chay_khong_can_file(monkeypatch):
    for key, value in BASE.items():
        monkeypatch.setenv(key, value)
    config = skill_env.load_llm_config()
    assert config['base_url'] == BASE['MECSU_BASE_URL']
    assert config['models'] == ['ag/gemini-3.7-flash-medium']
    assert config['api_key'] == 'local'          # khong dien key thi khong duoc chet


def test_env_cu_theo_prefix_rieng_van_chay(monkeypatch):
    monkeypatch.setenv('NF_BASE_URL', 'http://localhost:20128/v1')
    monkeypatch.setenv('NF_MODELS', 'cu')
    assert skill_env.load_llm_config('NF')['models'] == ['cu']


def test_prefix_chung_thang_prefix_cu(monkeypatch):
    monkeypatch.setenv('NF_MODELS', 'cu')
    monkeypatch.setenv('MECSU_MODELS', 'moi')
    monkeypatch.setenv('MECSU_BASE_URL', BASE['MECSU_BASE_URL'])
    assert skill_env.load_llm_config('NF')['models'] == ['moi']


def test_thieu_cau_hinh_thi_chet_kem_duong_dan_file_can_dien():
    with pytest.raises(SystemExit) as error:
        skill_env.load_llm_config('NF')
    assert '.env.example' in str(error.value)
