# -*- coding: utf-8 -*-
"""make_sample.py phai DO cot tu header, khong duoc dem cot cung.

Loi that: script hardcode `r[2]` la ten va `r[4]` la filter trong khi moi script khac
deu dò header. Tren layout Handtools, `r[4]` la `category_lv1` -> group_of() tra
'(khong ro)' cho MOI dong, phan tang bo mau hong am tham. workflow.md §0 bao chay
script nay dau tien.
"""
import subprocess
import sys
from pathlib import Path

import openpyxl

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))

FILTER_CELL = 'Size Ren Of Bulong: M14 | Buoc Ren Of Bulong: 2 mm'


def _workbook(path: Path, header, rows):
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    wb.save(path)
    return path


def _run(*arguments):
    return subprocess.run([sys.executable, str(SCRIPTS / 'make_sample.py'), *arguments],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=120)


def test_doc_cot_tu_header_du_thu_tu_cot_khac(tmp_path):
    """Filter o cot 0, ten o cot 1 - thu tu nao cung phai ra dung nhom."""
    src = _workbook(
        tmp_path / 'in.xlsx',
        ['mapped_filters', 'part_description', 'part_id'],
        [[FILTER_CELL, 'Bulong M%dx35' % size, size] for size in range(8, 20)],
    )
    proc = _run('--input', str(src), '--output', str(tmp_path / 'out.xlsx'), '--rows', '5')
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '(khong ro)' not in proc.stdout, proc.stdout
    assert 'Bulong' in proc.stdout, proc.stdout


def test_dung_lai_va_hoi_khi_khong_nhan_ra_cot(tmp_path):
    """Header khong doan duoc -> dung lai, noi ro phai chi cot nao; khong duoc doan bua."""
    src = _workbook(
        tmp_path / 'in.xlsx',
        ['cot a', 'cot b', 'cot c'],
        [['x', 'y', 'z']],
    )
    proc = _run('--input', str(src), '--output', str(tmp_path / 'out.xlsx'))
    assert proc.returncode != 0, proc.stdout
    message = proc.stdout + proc.stderr
    assert '--name-col' in message and '--filter-col' in message, message


def test_ep_cot_bang_tham_so_khi_header_vo_nghia(tmp_path):
    """Nguoi dung chi ro cot thi chay tiep - 0-based, cung quy uoc voi filter_audit.py."""
    src = _workbook(
        tmp_path / 'in.xlsx',
        ['cot a', 'cot b', 'cot c'],
        [['Bulong M%dx35' % size, FILTER_CELL, size] for size in range(8, 20)],
    )
    proc = _run('--input', str(src), '--output', str(tmp_path / 'out.xlsx'),
                '--name-col', '0', '--filter-col', '1', '--rows', '5')
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert '(khong ro)' not in proc.stdout, proc.stdout
