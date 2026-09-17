# -*- coding: utf-8 -*-
"""Script nao in chu tieng Viet thi phai ep stdout sang UTF-8.

Console Windows mac dinh la cp1252. `print('ô filter còn thiếu')` nem
UnicodeEncodeError va CHET, keo ca day chuyen chet theo.

Da xay ra that (P3 lan 3, 2026-09-17): `build_ai_queue.py` chet o dong in bang
thong ke, exit 1, `run.py` dung ca day. Lo suot nhieu phien vi moi lan chay tay
deu co san PYTHONIOENCODING=utf-8 trong moi truong - bien do CHE mat loi.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

GOC = Path(__file__).resolve().parents[1]
SCRIPTS = sorted(GOC.glob('skills/*/scripts/*.py'))
KHONG_ASCII = re.compile(r'[^\x00-\x7F]')


def _co_ep_utf8(text: str) -> bool:
    return 'reconfigure' in text and 'utf-8' in text


@pytest.mark.parametrize('duong_dan', SCRIPTS, ids=lambda p: '%s/%s' % (p.parts[-3], p.name))
def test_script_in_chu_co_dau_thi_phai_ep_stdout_utf8(duong_dan):
    text = duong_dan.read_text(encoding='utf-8')
    if not KHONG_ASCII.search(text):
        pytest.skip('script khong co ky tu ngoai ASCII')
    assert _co_ep_utf8(text), (
        '%s co chu ngoai ASCII nhung khong ep stdout UTF-8. Them:\n'
        "    if hasattr(sys.stdout, 'reconfigure'):\n"
        "        sys.stdout.reconfigure(encoding='utf-8')" % duong_dan.name)


def test_build_ai_queue_chay_duoc_voi_console_cp1252(tmp_path):
    """Chay THAT voi stdout cp1252 - thu duy nhat chung minh duoc la da vá."""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(['part_id', 'part_number', 'part_description',
               'leaf_category_name', 'category_lv1', 'active_filter_count', 'mapped_filters'])
    for i in range(12):
        day_du = 'Chiều dài: %d mm | Vật liệu: Thép' % (10 + i)
        ws.append([i, 'MA%03d' % i, 'Cờ Lê Vòng Miệng %d mm Test' % (10 + i),
                   'Cờ Lê Vòng Miệng', 'Dụng cụ cầm tay', 2, None if i < 3 else day_du])
    nguon = tmp_path / 'nguon.xlsx'
    wb.save(nguon)

    moi_truong = dict(os.environ, PYTHONIOENCODING='cp1252')
    scripts = GOC / 'skills' / 'mecsu-filter' / 'scripts'

    def chay(*co):
        return subprocess.run([sys.executable, *co], capture_output=True, text=True,
                              encoding='utf-8', errors='replace', env=moi_truong, timeout=180)

    b1 = chay(str(scripts / 'filter_audit.py'), str(nguon),
              '--out', str(tmp_path / 'audit'), '--xlsx-out', str(tmp_path / 'audit.xlsx'))
    assert b1.returncode == 0, b1.stdout + b1.stderr

    b2 = chay(str(scripts / 'learn_deps.py'), '--audit', str(tmp_path / 'audit.pkl'),
              '--out', str(tmp_path / 'deps.json'))
    assert b2.returncode == 0, b2.stdout + b2.stderr

    b3 = chay(str(scripts / 'build_ai_queue.py'), '--audit', str(tmp_path / 'audit.pkl'),
              '--deps', str(tmp_path / 'deps.json'), '--out', str(tmp_path / 'queue.json'),
              '--filled-out', str(tmp_path / 'corpus.json'))
    assert 'UnicodeEncodeError' not in (b3.stdout + b3.stderr)
    assert b3.returncode == 0, b3.stdout + b3.stderr
