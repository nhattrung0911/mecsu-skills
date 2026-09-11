# -*- coding: utf-8 -*-
"""Lint phai doc dung TEN SCRIPT khi ten co dau gach ngang.

Loi that: regex bat lenh chi nhan chu, so va gach duoi o phan ten file, nen
`chuan-hoa.py` bi cat thanh `hoa.py`. Hai huong hong:

  - bao "script khong ton tai" trong khi no co that -> lint keu oan;
  - te hon: neu tinh co co file ten `hoa.py` thi lint PASS NHAM, va cai sai that
    su di thang qua cong.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINT = ROOT / 'tools' / 'lint_skills.py'

SKILL_MD = '''---
name: {ten}
description: Soat thu gi do. Use when can soat thu do.
---

# {ten}

```bash
python ${{CLAUDE_SKILL_DIR}}/scripts/{script} --input <file.xlsx>
```
'''

SCRIPT = '''# -*- coding: utf-8 -*-
import argparse
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.parse_args()
    print('ok')


if __name__ == '__main__':
    main()
'''


def _dung_skill(goc: Path, ten: str, script: str) -> None:
    skill = goc / 'skills' / ten
    (skill / 'scripts').mkdir(parents=True)
    (skill / 'tests').mkdir()
    (skill / 'SKILL.md').write_text(SKILL_MD.format(ten=ten, script=script), encoding='utf-8')
    (skill / 'scripts' / script).write_text(SCRIPT, encoding='utf-8')
    (skill / 'tests' / ('test_%s_co.py' % ten.replace('-', '_'))).write_text(
        'def test_co():\n    assert True\n', encoding='utf-8')


def _lint(goc: Path):
    return subprocess.run([sys.executable, str(LINT), '--root', str(goc)],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=120)


def test_ten_script_co_gach_ngang_van_tim_ra(tmp_path):
    _dung_skill(tmp_path, 'mecsu-thu', 'chuan-hoa.py')
    ket_qua = _lint(tmp_path)
    assert ket_qua.returncode == 0, ket_qua.stdout + ket_qua.stderr


def test_van_bat_duoc_script_that_su_thieu(tmp_path):
    """Noi long regex khong duoc lam lint hien tinh."""
    _dung_skill(tmp_path, 'mecsu-thu', 'chuan-hoa.py')
    (tmp_path / 'skills' / 'mecsu-thu' / 'scripts' / 'chuan-hoa.py').unlink()
    ket_qua = _lint(tmp_path)
    assert ket_qua.returncode != 0, 'script bien mat ma lint van xanh'
    assert 'khong ton tai' in ket_qua.stdout


def test_soi_ca_file_trong_references(tmp_path):
    """Lint phai doc ca *.md long trong thu muc con, khong chi tang tren cung.

    Loi that, do 2026-09-11: `skill.glob('*.md')` khong de quy, nen mot file
    references/ chua TODO, link chet VA khoi ```powershell van cho ra `0 loi`
    exit 0. mecsu-filter co references/ that chua bao gio duoc soi.
    """
    _dung_skill(tmp_path, 'mecsu-thu', 'chuan-hoa.py')
    tham_chieu = tmp_path / 'skills' / 'mecsu-thu' / 'references'
    tham_chieu.mkdir()
    (tham_chieu / 'tai-lieu.md').write_text(
        '# Tai lieu\n\n- TODO: chua ai viet\n- [link chet](khong-ton-tai.md)\n',
        encoding='utf-8')

    ket_qua = _lint(tmp_path)
    assert ket_qua.returncode != 0, 'loi trong references/ ma lint van xanh'
    assert 'TODO' in ket_qua.stdout
    assert 'link chet' in ket_qua.stdout


def test_website_json_hong_thi_do(tmp_path):
    """website.json quyet dinh skill hien the nao tren web - lint tung khong doc no."""
    _dung_skill(tmp_path, 'mecsu-thu', 'chuan-hoa.py')
    trang = tmp_path / 'skills' / 'mecsu-thu' / 'website.json'

    trang.write_text('{ khong phai json', encoding='utf-8')
    assert _lint(tmp_path).returncode != 0, 'JSON hong ma lint van xanh'

    trang.write_text('{"title": "Thu", "purpose": "", "prompt": "Chay thu"}', encoding='utf-8')
    ket_qua = _lint(tmp_path)
    assert ket_qua.returncode != 0, 'purpose rong ma lint van xanh'
    assert 'purpose' in ket_qua.stdout

    trang.write_text('{"title": "Thu", "purpose": "Soat thu", "prompt": "Chay thu"}',
                     encoding='utf-8')
    assert _lint(tmp_path).returncode == 0, 'website.json day du ma lint van do'


def test_dir_lab_soi_duoc_ban_nhap(tmp_path):
    (tmp_path / 'lab').mkdir()
    ket_qua = subprocess.run(
        [sys.executable, str(LINT), '--root', str(tmp_path), '--dir', 'lab'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120)
    assert ket_qua.returncode == 0, ket_qua.stdout + ket_qua.stderr
