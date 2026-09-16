# -*- coding: utf-8 -*-
"""B5 - phan logic KHONG can mang: khoa cache, doc JSON, doc SSE.

Khong ca nao goi model that: test goi model la test phu thuoc vao mot dich vu
ben ngoai, va no ton tien moi lan chay.
"""
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def _nap(ten_file: str, ten_module: str):
    """Nap module duoi TEN RIENG, khong dung sys.path.

    `skill_env.py` ton tai o ca mecsu-filter lan mecsu-naming. `sys.path.insert`
    roi `import skill_env` nhet module cua skill nay vao sys.modules, va test cua
    skill kia nhan nham module cua skill nay - 4 test cua mecsu-filter da do vi
    dung ly do do. Cung ho voi luat "ten file test phai duy nhat toan repo".
    """
    duong_dan = SCRIPTS / ten_file
    spec = importlib.util.spec_from_file_location(ten_module, duong_dan)
    module = importlib.util.module_from_spec(spec)
    sys.modules[ten_module] = module          # ai_extract can import duoc skill_env
    spec.loader.exec_module(module)
    return module


skill_env = _nap('skill_env.py', 'naming_skill_env')
sys.modules['skill_env'] = skill_env          # chi de ai_extract nap duoc
ai_extract = _nap('ai_extract.py', 'naming_ai_extract')
del sys.modules['skill_env']                  # tra lai sach cho skill khac


def test_khoa_cache_theo_noi_dung_khong_theo_thu_tu():
    """So thu tu bi danh lai khi input doi -> verdict cu gan nham ma khac.

    Da hong hai lan trong repo nay, nen khoa phai la hash NOI DUNG.
    """
    a = {'ten_nguon': 'Socket 13MM', 'thong_so': {'A': '22.2', 'B': '19'}}
    b = {'ten_nguon': 'Socket 13MM', 'thong_so': {'B': '19', 'A': '22.2'}}
    assert ai_extract.khoa_noi_dung(a) == ai_extract.khoa_noi_dung(b), 'thu tu khoa lam doi hash'

    khac = {'ten_nguon': 'Socket 11MM', 'thong_so': {'A': '22.2', 'B': '19'}}
    assert ai_extract.khoa_noi_dung(a) != ai_extract.khoa_noi_dung(khac)


def test_doi_prompt_thi_cache_cu_khong_con_dung_duoc():
    """Sua prompt ma cache van hit thi ban sua khong co tac dung nao.

    Loi that 2026-09-11: sua prompt cho co dau tieng Viet, chay lai van ra ket
    qua khong dau vi khoa cache khong he tinh den prompt.
    """
    muc = {'ten_nguon': 'Socket 13MM', 'thong_so': {'A': '22.2'}}
    cu = ai_extract.khoa_noi_dung(muc)
    goc = ai_extract.PHIEN_BAN_PROMPT
    try:
        ai_extract.PHIEN_BAN_PROMPT = goc + 1
        assert ai_extract.khoa_noi_dung(muc) != cu, 'doi phien ban prompt ma khoa khong doi'
    finally:
        ai_extract.PHIEN_BAN_PROMPT = goc


def test_prompt_viet_co_dau():
    """Prompt khong dau thi model bat chuoc: tra ve `Dau Tuyp` thay vi `Đầu Tuýp`."""
    assert 'CÓ DẤU' in ai_extract.MAU_PROMPT
    assert 'Đầu Tuýp' in ai_extract.MAU_PROMPT


def test_doc_json_go_duoc_rao_code():
    """Model hay boc JSON trong ```json ... ``` - khong go thi parse chet."""
    assert ai_extract.doc_json('```json\n{"ket_qua": []}\n```') == {'ket_qua': []}
    assert ai_extract.doc_json('  {"ket_qua": [1]} ') == {'ket_qua': [1]}


def test_doc_json_khong_co_json_thi_nem_loi():
    try:
        ai_extract.doc_json('xin loi toi khong the')
    except ValueError:
        return
    raise AssertionError('tra loi khong co JSON ma van cho qua')


def _sse(*goi: str) -> io.BytesIO:
    return io.BytesIO(b''.join(('data: %s\n\n' % g).encode('utf-8') for g in goi))


def test_doc_sse_gom_du_cac_manh():
    """Endpoint LUON stream, ke ca khi khong xin - json.load() chet ngay."""
    than = _sse(json.dumps({'choices': [{'delta': {'content': 'Đầu '}}]}),
                json.dumps({'choices': [{'delta': {'content': 'Tuýp'}}]}),
                '[DONE]')
    assert skill_env.doc_sse(than) == 'Đầu Tuýp'


def test_luong_dut_giua_chung_thi_nem_loi():
    """Dut luong ma tra chuoi rong la mat dong am tham - phai bao loi."""
    try:
        skill_env.doc_sse(io.BytesIO(b': ping\n\n'))
    except RuntimeError:
        return
    raise AssertionError('luong dut ma van bao thanh cong')


def test_dry_run_bao_so_lan_goi_va_khong_goi_model(tmp_path):
    facts = tmp_path / 'facts.json'
    facts.write_text(json.dumps(
        [{'ma_goc': 'X%d' % i, 'ten_nguon': 'Socket %d' % i, 'thong_so': {}} for i in range(30)],
        ensure_ascii=False), encoding='utf-8')
    xong = subprocess.run(
        [sys.executable, str(SCRIPTS / 'ai_extract.py'), '--facts', str(facts),
         '--out', str(tmp_path / 'ai.json'), '--batch', '25', '--dry-run'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    assert xong.returncode == 0, xong.stdout + xong.stderr
    assert '2 lan goi' in xong.stdout, xong.stdout
    assert not (tmp_path / 'ai.json').exists(), '--dry-run ma van ghi ket qua'
