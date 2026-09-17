# -*- coding: utf-8 -*-
"""Nap cau hinh LLM cho skill nay.

Doc theo thu tu uu tien: bien moi truong cua may > .env canh script > .env o goc
plugin. Nho vay nguoi dung dien key MOT lan o goc, moi skill dung chung, nhung
skill van chay doc lap khi bi copy ra ngoai plugin.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent


def _plugin_root(start: Path) -> Path | None:
    """Thu muc chua .claude-plugin/, di len tu thu muc script."""
    for parent in start.parents:
        if (parent / ".claude-plugin").is_dir():
            return parent
    return None


def load_llm_config(legacy_prefix: str | None = None, bat_buoc: bool = True) -> dict:
    """Tra ve dict cau hinh. legacy_prefix giu .env cu (NF_/ONCHECK_) van chay."""
    load_dotenv(HERE / ".env")                    # dien rieng cho skill thi thang
    root = _plugin_root(HERE)
    if root:
        load_dotenv(root / ".env")                # khong ghi de gia tri da co

    def get(name: str, default: str = "") -> str:
        value = os.getenv("MECSU_" + name)
        if not value and legacy_prefix:
            value = os.getenv(legacy_prefix + "_" + name)
        return value if value else default

    base_url = get("BASE_URL").rstrip("/")
    models = [m.strip() for m in get("MODELS").split(",") if m.strip()]
    ep_agent = get("CHE_DO").strip().lower() == "agent"
    if not base_url or not models or ep_agent:
        # .env la TUY CHON: thieu endpoint thi agent dang chay lam thay, khong chet.
        # bat_buoc=True danh cho script PHAI co endpoint that (vi du do model).
        if bat_buoc:
            raise SystemExit(
                "MECSU_BASE_URL / MECSU_MODELS chua co. Copy %s thanh .env roi dien key."
                % ((root / ".env.example") if root else (HERE / ".env.example"))
            )
        return {
            "che_do": "agent", "base_url": base_url, "api_key": get("API_KEY", "local"),
            "models": models or ["agent"], "batch_size": int(get("BATCH_SIZE", "25")),
            "concurrency": int(get("CONCURRENCY", "4")),
            "temperature": float(get("TEMPERATURE", "0")),
        }
    return {
        "che_do": "llm",
        "base_url": base_url,
        "api_key": get("API_KEY", "local"),
        "models": models,
        "batch_size": int(get("BATCH_SIZE", "25")),
        "concurrency": int(get("CONCURRENCY", "4")),
        "temperature": float(get("TEMPERATURE", "0")),
    }


# ── Che do agent: .env la TUY CHON ──────────────────────────────────────────────
#
# Endpoint trong .env mua them mot model re, khong phai dieu kien de chay skill.
# Khong co no thi CHINH AGENT dang chay lam phan viec do. Script khong goi nguoc
# duoc vao agent, nen ban giao qua dia: hoi_agent() tra ve cau tra loi agent da
# dien; chua co thi xep vao hang cho va nem ThieuTraLoi; cuoi buoc chot_hoi_dap()
# ghi cau hoi ra file va thoat 4.
#
# Mau goc + ly do day du: skills/mecsu-naming/references/che_do_agent.md

import hashlib
import json
import threading
import sys

if hasattr(sys.stdout, 'reconfigure'):      # console Windows mac dinh la cp1252
    sys.stdout.reconfigure(encoding='utf-8')

THOAT_CAN_AGENT = 4          # 3 da danh cho "dung cho NGUOI soat" - dung trung la agent
                             # se di tra loi nhung cau hoi khong ton tai.


class ThieuTraLoi(Exception):
    """Cau hoi nay chua co cau tra loi cua agent."""


class _Phien:
    def __init__(self):
        self.thu_muc = None
        self.da_co = {}
        self.dang_cho = {}
        self.khoa = threading.Lock()      # call_model chay trong ThreadPoolExecutor


_PHIEN = _Phien()


def co_llm(config: dict) -> bool:
    return config.get('che_do') != 'agent'


def khoa_noi_dung(he_thong: str, prompt: str) -> str:
    """Khoa theo NOI DUNG. So thu tu bi danh lai khi input doi -> gan nham san pham."""
    return hashlib.sha256(('%s\n\n%s' % (he_thong, prompt)).encode('utf-8')).hexdigest()[:16]


def chuan_bi(config: dict, canh_file) -> str:
    """Chon che do va nap cau tra loi agent da dien. Tra ve 'llm' hoac 'agent'."""
    if co_llm(config):
        return 'llm'
    _PHIEN.thu_muc = Path(canh_file).resolve().parent / 'hoi_agent'
    _PHIEN.dang_cho = {}
    tra_loi = _PHIEN.thu_muc / 'tra_loi.json'
    if tra_loi.exists():
        _PHIEN.da_co = json.loads(tra_loi.read_text(encoding='utf-8'))
    print('che do agent: .env chua co endpoint, agent tu tra loi (%d cau da dien)'
          % len(_PHIEN.da_co))
    return 'agent'


def hoi_agent(he_thong: str, prompt: str) -> str:
    """Tra ve cau tra loi agent da dien, chua co thi xep hang cho va nem ThieuTraLoi."""
    khoa = khoa_noi_dung(he_thong, prompt)
    with _PHIEN.khoa:
        if khoa in _PHIEN.da_co:
            return _PHIEN.da_co[khoa]
        _PHIEN.dang_cho[khoa] = {'he_thong': he_thong, 'prompt': prompt}
    raise ThieuTraLoi(khoa)


def chot_hoi_dap(buoc: str) -> None:
    """Con cau chua tra loi thi ghi file va THOAT 4 - khong di tiep voi du lieu thieu."""
    if not _PHIEN.dang_cho:
        return
    _PHIEN.thu_muc.mkdir(parents=True, exist_ok=True)
    cau_hoi = _PHIEN.thu_muc / 'cau_hoi.json'
    cau_hoi.write_text(json.dumps(
        {'buoc': buoc, 'cau_hoi': _PHIEN.dang_cho}, ensure_ascii=False, indent=2), encoding='utf-8')
    # SystemExit(4, 'loi') KHONG thoat 4: Python coi ca tuple la thong diep va thoat 1.
    print('\nCAN AGENT TRA LOI %d cau (buoc %s).\n'
          '  1. Doc   %s\n'
          '  2. Ghi   %s  dang {"<khoa>": "<cau tra loi>"}\n'
          '  3. Chay lai DUNG lenh vua roi.'
          % (len(_PHIEN.dang_cho), buoc, cau_hoi, _PHIEN.thu_muc / 'tra_loi.json'))
    raise SystemExit(THOAT_CAN_AGENT)
