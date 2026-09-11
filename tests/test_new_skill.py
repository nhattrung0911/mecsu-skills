# -*- coding: utf-8 -*-
"""Khuon dung skill phai sinh ra thu QUA DUOC LINT NGAY.

Mot khuon sinh ra thu con phai sua tay moi qua cong thi khong tiet kiem duoc gi -
no chi doi cho gO tay tu dau thanh cho SUA tay, va van quen dung nhung thu cu.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KHUON = ROOT / 'tools' / 'new_skill.py'
LINT = ROOT / 'tools' / 'lint_skills.py'


def _chay(*co, cwd=None):
    return subprocess.run([sys.executable, *co], capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=120, cwd=cwd)


def _kho(tmp_path: Path) -> Path:
    """Ban sao toi thieu: chi can hai thu muc de khuon co cho ma dung."""
    (tmp_path / 'lab').mkdir()
    (tmp_path / 'skills').mkdir()
    return tmp_path


def _dung(kho: Path, ten='mecsu-thu', **them):
    co = [str(KHUON), ten, '--purpose', 'Soat thu gi do trong file Excel',
          '--root', str(kho)]
    for khoa, gia_tri in them.items():
        co += ['--%s' % khoa, gia_tri]
    return _chay(*co)


def test_sinh_du_file(tmp_path):
    kho = _kho(tmp_path)
    assert _dung(kho).returncode == 0

    skill = kho / 'lab' / 'mecsu-thu'
    for duong_dan in ('SKILL.md', 'website.json', 'scripts/run.py',
                      'tests/test_mecsu_thu_smoke.py'):
        assert (skill / duong_dan).exists(), 'thieu %s' % duong_dan

    dau = (skill / 'SKILL.md').read_text(encoding='utf-8')
    assert 'name: mecsu-thu' in dau, 'frontmatter name phai khop ten thu muc'
    assert '${CLAUDE_SKILL_DIR}' in dau, 'phai tro script bang bien, khong hardcode duong dan'


def test_thu_sinh_ra_qua_duoc_lint(tmp_path):
    kho = _kho(tmp_path)
    assert _dung(kho).returncode == 0

    ket_qua = _chay(str(LINT), '--root', str(kho), '--dir', 'lab')
    assert ket_qua.returncode == 0, ket_qua.stdout + ket_qua.stderr


def test_test_sinh_ra_chay_duoc(tmp_path):
    kho = _kho(tmp_path)
    assert _dung(kho).returncode == 0

    # --rootdir + cwd: khong khoa lai thi pytest long nhau bo len tan goc o dia C:
    # va chet o mot thu muc Windows khong cho doc.
    skill = kho / 'lab' / 'mecsu-thu'
    ket_qua = _chay('-m', 'pytest', '-q', '--rootdir', str(skill),
                    '-p', 'no:cacheprovider', 'tests', cwd=skill)
    assert ket_qua.returncode == 0, ket_qua.stdout + ket_qua.stderr


def test_cat_phan_mo_dau_thua_cua_when(tmp_path):
    """`--when` bi dan "Use when" o dau.

    Loi that, quan sat 2026-09-11: mot agent truyen ca cau "Chi dung khi can thu
    nghiem..." va description sinh ra la "Use when Chi dung khi can thu nghiem..."
    - thua chu, cau hong, ma khong gi bao loi.
    """
    kho = _kho(tmp_path)
    assert _dung(kho, when='Chi dung khi can thu nghiem flow').returncode == 0

    dau = (kho / 'lab' / 'mecsu-thu' / 'SKILL.md').read_text(encoding='utf-8')
    assert 'Use when can thu nghiem flow' in dau, dau
    assert 'Use when Chi dung khi' not in dau


def test_tu_choi_ten_da_co(tmp_path):
    kho = _kho(tmp_path)
    (kho / 'skills' / 'mecsu-thu').mkdir()
    ket_qua = _dung(kho)
    assert ket_qua.returncode != 0, 'ghi de len skill dang co ma khong bao gi'
    assert 'da co' in ket_qua.stderr + ket_qua.stdout


def test_tu_choi_ten_sai_dinh_dang(tmp_path):
    kho = _kho(tmp_path)
    assert _dung(kho, ten='Mecsu Thu').returncode != 0


def test_tu_choi_khi_trung_ten_file_test(tmp_path):
    """pytest gom test theo TEN FILE: trung ten la mot trong hai file bi nuot."""
    kho = _kho(tmp_path)
    cu = kho / 'skills' / 'skill-cu' / 'tests'
    cu.mkdir(parents=True)
    (cu / 'test_mecsu_thu_smoke.py').write_text('# da ton tai\n', encoding='utf-8')

    ket_qua = _dung(kho)
    assert ket_qua.returncode != 0, 'trung ten file test ma van cho dung'
