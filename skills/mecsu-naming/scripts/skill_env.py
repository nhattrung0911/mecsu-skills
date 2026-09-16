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


def phai_co_key(cau_hinh: dict) -> None:
    """Dung som va noi ro phai dien gi o dau, thay vi chet giua chung."""
    thieu = [k for k in ('MECSU_BASE_URL', 'MECSU_API_KEY', 'MECSU_MODELS') if not cau_hinh.get(k)]
    if thieu:
        raise SystemExit(
            'Thieu %s trong %s\nCopy .env.example thanh .env roi dien.'
            % (', '.join(thieu), goc_plugin() / '.env'))


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
    """Goi model, tra ve text. Loi thi nem ngoai le - khong tra chuoi rong im lang."""
    phai_co_key(cau_hinh)
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
