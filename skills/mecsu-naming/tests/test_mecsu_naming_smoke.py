# -*- coding: utf-8 -*-
"""Test khoi dong cho mecsu-naming. Chua kiem logic - chi kiem script con chay duoc.

Hai dieu duoi day van dung sau khi logic duoc viet xong, nen khong phai sua lai.
"""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'run.py'


def _chay(*co):
    return subprocess.run([sys.executable, str(SCRIPT), *co],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=60)


def test_help_chay_duoc():
    ket_qua = _chay('--help')
    assert ket_qua.returncode == 0, ket_qua.stdout + ket_qua.stderr
    assert '--input' in ket_qua.stdout


def test_thieu_input_thi_thoat_khac_0():
    """Thieu tham so bat buoc ma van thoat 0 la che do hong te nhat."""
    assert _chay().returncode != 0
