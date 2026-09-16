# -*- coding: utf-8 -*-
"""Doc .env goc plugin va goi model. Dung chung cho moi script trong skill nay.

Khong script nao tu giu key. Thu tu uu tien: bien moi truong cua may > .env goc.

HAI DIEU DA DO, DUNG BO:

1. Endpoint LUON tra `text/event-stream`, ke ca khi khong xin stream.
   `json.load(urlopen(...))` chet ngay voi JSONDecodeError. Phai parse SSE.

2. Overhead co dinh moi lan goi rat lon: prompt 5 chu do duoc `prompt_tokens=2429`.
   Router tu nhet system prompt. Vi vay GOP BATCH la bat buoc, khong phai toi uu them.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

MAC_DINH = {
    'MECSU_BASE_URL': '',
    'MECSU_API_KEY': '',
    'MECSU_MODELS': '',
    'MECSU_BATCH_SIZE': '25',
    'MECSU_CONCURRENCY': '4',
    'MECSU_TEMPERATURE': '0',
    'MECSU_CHE_DO': '',                      # 'agent' = ep agent tu tra loi, bo qua endpoint
}


def goc_plugin() -> Path:
    """Thu muc goc plugin, di len tu vi tri script - chay tu cwd nao cung trung."""
    o_day = Path(__file__).resolve()
    for cha in o_day.parents:
        if (cha / '.env').exists() or (cha / '.env.example').exists():
            return cha
    return o_day.parents[3]


def doc_env() -> dict:
    cau_hinh = dict(MAC_DINH)
    duong_dan = goc_plugin() / '.env'
    if duong_dan.exists():
        for dong in duong_dan.read_text(encoding='utf-8').splitlines():
            dong = dong.strip()
            if not dong or dong.startswith('#') or '=' not in dong:
                continue
            khoa, _, gia_tri = dong.partition('=')
            cau_hinh[khoa.strip()] = gia_tri.strip()
    for khoa in MAC_DINH:                    # bien moi truong cua may thang .env
        if os.environ.get(khoa):
            cau_hinh[khoa] = os.environ[khoa]
    return cau_hinh


def thieu_khoa(cau_hinh: dict) -> list:
    return [k for k in ('MECSU_BASE_URL', 'MECSU_API_KEY', 'MECSU_MODELS') if not cau_hinh.get(k)]


def co_llm(cau_hinh: dict) -> bool:
    """.env la TUY CHON. Co du ba khoa thi goi model re; khong co thi agent tu tra loi.

    MECSU_CHE_DO=agent ep dung che do agent du .env day du - nguoi dung chon, khong phai
    cu co key la bi bat xai key.
    """
    if str(cau_hinh.get('MECSU_CHE_DO', '')).strip().lower() == 'agent':
        return False
    return not thieu_khoa(cau_hinh)


def phai_co_key(cau_hinh: dict) -> None:
    """Chi dung cho script BAT BUOC phai co endpoint (vi du do model). Duong chinh dung chuan_bi()."""
    if thieu_khoa(cau_hinh):
        raise SystemExit(
            'Thieu %s trong %s\nCopy .env.example thanh .env roi dien.'
            % (', '.join(thieu_khoa(cau_hinh)), goc_plugin() / '.env'))


# ── Che do agent: script khong goi duoc nguoc vao agent, nen ban giao qua file ──
#
# hoi() tra loi da co san thi tra ve ngay. Chua co thi ghi vao danh sach cho va nem
# ThieuTraLoi - call site bo qua lo do roi chay tiep, cuoi buoc chot_hoi_dap() ghi file
# cau hoi va thoat 4. Agent dien xong, chay lai DUNG lenh cu, di tiep qua cung duong
# doi chieu nguoc nhu khi dung LLM.

# 3 da duoc run.py dung cho 'dung cho NGUOI soat'. Dung trung thi agent se di
# tra loi nhung cau hoi khong ton tai. 4 = 'dang cho AGENT tra loi'.
THOAT_CAN_AGENT = 4


class ThieuTraLoi(Exception):
    """Cau hoi nay chua co cau tra loi cua agent."""


class _Phien:
    def __init__(self) -> None:
        self.thu_muc: Path | None = None
        self.da_co: dict = {}
        self.dang_cho: dict = {}


_PHIEN = _Phien()


def khoa_noi_dung(he_thong: str, prompt: str) -> str:
    """Khoa theo NOI DUNG, khong theo so thu tu - doi thu tu input khong gan nham cau tra loi."""
    import hashlib
    return hashlib.sha256(('%s\n\n%s' % (he_thong, prompt)).encode('utf-8')).hexdigest()[:16]


def chuan_bi(cau_hinh: dict, canh_file: Path) -> str:
    """Chon che do va nap cau tra loi agent da dien. Tra ve 'llm' hoac 'agent'."""
    if co_llm(cau_hinh):
        return 'llm'
    _PHIEN.thu_muc = Path(canh_file).resolve().parent / 'hoi_agent'
    _PHIEN.dang_cho = {}
    tra_loi = _PHIEN.thu_muc / 'tra_loi.json'
    if tra_loi.exists():
        _PHIEN.da_co = json.loads(tra_loi.read_text(encoding='utf-8'))
    print('che do agent: .env chua co endpoint, agent tu tra loi (%d cau da dien)'
          % len(_PHIEN.da_co))
    return 'agent'


def chot_hoi_dap(buoc: str) -> None:
    """Con cau chua tra loi thi ghi file va THOAT 4 - khong di tiep voi du lieu thieu."""
    if not _PHIEN.dang_cho:
        return
    _PHIEN.thu_muc.mkdir(parents=True, exist_ok=True)
    cau_hoi = _PHIEN.thu_muc / 'cau_hoi.json'
    cau_hoi.write_text(json.dumps(
        {'buoc': buoc, 'cau_hoi': _PHIEN.dang_cho}, ensure_ascii=False, indent=2), encoding='utf-8')
    # SystemExit(4, 'loi') KHONG thoat 4: Python coi ca tuple la thong diep va thoat 1.
    # Phai in roi thoat bang so tran. Da do: run.py bao "thoat 1 - dung ca day".
    print('\nCAN AGENT TRA LOI %d cau (buoc %s).\n'
          '  1. Doc   %s\n'
          '  2. Ghi   %s  dang {"<khoa>": "<cau tra loi>"}\n'
          '  3. Chay lai DUNG lenh vua roi.'
          % (len(_PHIEN.dang_cho), buoc, cau_hoi, _PHIEN.thu_muc / 'tra_loi.json'))
    raise SystemExit(THOAT_CAN_AGENT)


def doc_sse(than) -> str:
    """Gom noi dung tu luong SSE. Luong dut giua chung la LOI, khong im lang bo qua."""
    manh, thay_done = [], False
    for dong_byte in than:
        dong = dong_byte.decode('utf-8', 'replace').strip()
        if not dong or not dong.startswith('data:'):
            continue
        du_lieu = dong[5:].strip()
        if du_lieu == '[DONE]':
            thay_done = True
            break
        try:
            goi = json.loads(du_lieu)
        except json.JSONDecodeError:
            continue
        for lua_chon in goi.get('choices', []):
            phan = lua_chon.get('delta', {}).get('content') or lua_chon.get('message', {}).get('content')
            if phan:
                manh.append(phan)
    noi_dung = ''.join(manh)
    if not thay_done and not noi_dung:
        raise RuntimeError('luong SSE dut truoc khi co noi dung nao')
    return noi_dung


def hoi(cau_hinh: dict, prompt: str, he_thong: str = '', timeout: int = 180) -> str:
    """Goi model, tra ve text. Loi thi nem ngoai le - khong tra chuoi rong im lang.

    Che do agent: tra ve cau tra loi agent da dien, chua co thi nem ThieuTraLoi.
    """
    if not co_llm(cau_hinh):
        khoa = khoa_noi_dung(he_thong, prompt)
        if khoa in _PHIEN.da_co:
            return _PHIEN.da_co[khoa]
        _PHIEN.dang_cho[khoa] = {'he_thong': he_thong, 'prompt': prompt}
        raise ThieuTraLoi(khoa)
    tin_nhan = ([{'role': 'system', 'content': he_thong}] if he_thong else [])
    tin_nhan.append({'role': 'user', 'content': prompt})

    than_gui = json.dumps({
        'model': cau_hinh['MECSU_MODELS'].split(',')[0].strip(),
        'messages': tin_nhan,
        'temperature': float(cau_hinh.get('MECSU_TEMPERATURE', 0) or 0),
        'stream': True,
    }).encode('utf-8')

    yeu_cau = urllib.request.Request(
        cau_hinh['MECSU_BASE_URL'].rstrip('/') + '/chat/completions',
        data=than_gui, method='POST',
        headers={'Content-Type': 'application/json',
                 'Authorization': 'Bearer ' + cau_hinh['MECSU_API_KEY']})
    try:
        with urllib.request.urlopen(yeu_cau, timeout=timeout) as tra_loi:
            return doc_sse(tra_loi)
    except urllib.error.HTTPError as loi:
        chi_tiet = loi.read().decode('utf-8', 'replace')[:400]
        raise RuntimeError('HTTP %s tu endpoint: %s' % (loi.code, chi_tiet)) from loi


if __name__ == '__main__':
    cau_hinh = doc_env()
    phai_co_key(cau_hinh)
    print('goc plugin : %s' % goc_plugin())
    print('endpoint   : %s' % cau_hinh['MECSU_BASE_URL'])
    print('model      : %s' % cau_hinh['MECSU_MODELS'])
    print('key        : co, do dai %d' % len(cau_hinh['MECSU_API_KEY']))
