# -*- coding: utf-8 -*-
"""Vong 2 - nghi truy van va tim nguon.

Khong ca nao goi mang hay goi model: ca hai deu la dich vu ben ngoai, va test
phu thuoc vao chung thi do khi ho doi, khong phai khi code sai.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def _nap(ten_file: str, ten_module: str):
    spec = importlib.util.spec_from_file_location(ten_module, SCRIPTS / ten_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[ten_module] = module
    spec.loader.exec_module(module)
    return module


_env = _nap('skill_env.py', 'vong2tim_env')
sys.modules['skill_env'] = _env
tim = _nap('search_sources.py', 'vong2tim_search')
hoi = _nap('build_queries.py', 'vong2tim_queries')
del sys.modules['skill_env']


def _chay(ten_file: str, *co):
    return subprocess.run([sys.executable, str(SCRIPTS / ten_file), *co],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=90)


def _codes(tmp_path: Path, danh_sach) -> Path:
    duong_dan = tmp_path / 'codes.json'
    duong_dan.write_text(json.dumps(danh_sach, ensure_ascii=False), encoding='utf-8')
    return duong_dan


# --- loc ket qua tim kiem ---------------------------------------------------

def test_trang_khong_nhac_toi_ma_thi_bi_loai():
    """Loi that: truy van cho PM-10BLA tra ve 8 trang danh muc but son, khong
    trang nao mang ma. Khong loc thi ca 8 trang rac di thang vao prompt."""
    assert not tim.hop_le('PM-10BLA', {
        'title': 'Bút sơn công nghiệp', 'body': 'Các loại bút sơn', 'href': 'https://x/but-son'})


def test_ma_viet_khac_dau_gach_van_khop():
    """Trang web viet ma moi noi mot kieu: `PM-10BLA`, `PM 10BLA`, `pm10bla`."""
    for cach_viet in ('PM 10BLA', 'pm10bla', 'PM_10-BLA'):
        assert tim.hop_le('PM-10BLA', {'title': 'Bút sơn %s' % cach_viet, 'body': '', 'href': ''}), cach_viet


def test_ma_nam_trong_url_cung_tinh():
    assert tim.hop_le('S23050', {
        'title': 'Bút sơn', 'body': '', 'href': 'https://shop.jp/item/s23050'})


def test_truy_van_du_phong_kem_ngu_canh_khong_chi_co_ma():
    """Ma tran thi cong cu tim kiem tra ve bat cu thu gi trung chuoi do."""
    cau = tim.truy_van({'ma_goc': 'B-8', 'ten_file': 'Kéo thu hoạch nho B-8 Saboten Nhật Bản'})
    assert 'B-8' in cau
    assert 'Saboten' in cau, 'truy van mat ngu canh nganh'


def test_khong_san_pham_nao_thieu_thong_so_thi_thoat_khac_0(tmp_path):
    """Vong 2 khong co viec ma van thoat 0 thi nguoi dung tuong da tra web xong."""
    codes = _codes(tmp_path, [{'ma_goc': 'A', 'ten_file': 'Kéo A', 'dong_thong_so': ['Dài: 1mm']}])
    xong = _chay('search_sources.py', '--codes', str(codes), '--out', str(tmp_path / 'r.json'))
    assert xong.returncode != 0


def test_dry_run_in_truy_van_va_khong_goi_tim_kiem(tmp_path):
    codes = _codes(tmp_path, [{'ma_goc': 'B-8', 'ten_file': 'Kéo nho B-8 Saboten',
                               'dong_thong_so': []}])
    ra = tmp_path / 'r.json'
    xong = _chay('search_sources.py', '--codes', str(codes), '--out', str(ra), '--dry-run')
    assert xong.returncode == 0, xong.stdout + xong.stderr
    assert 'B-8' in xong.stdout
    assert not ra.exists(), '--dry-run ma van ghi ket qua'


# --- nghi truy van bang model ----------------------------------------------

def test_doc_json_go_duoc_rao_code():
    assert hoi.doc_json('```json\n{"ket_qua": []}\n```') == {'ket_qua': []}


def test_doc_json_khong_co_json_thi_nem_loi():
    try:
        hoi.doc_json('xin loi')
    except ValueError:
        return
    raise AssertionError('tra loi khong co JSON ma van cho qua')


def test_build_queries_dry_run_khong_goi_model(tmp_path):
    codes = _codes(tmp_path, [{'ma_goc': 'B-8', 'ten_file': 'Kéo nho B-8', 'dong_thong_so': []}])
    ra = tmp_path / 'q.json'
    xong = _chay('build_queries.py', '--codes', str(codes), '--out', str(ra), '--dry-run')
    assert xong.returncode == 0, xong.stdout + xong.stderr
    assert '1 lan goi model' in xong.stdout
    assert not ra.exists()


def test_build_queries_khong_co_viec_thi_thoat_khac_0(tmp_path):
    codes = _codes(tmp_path, [{'ma_goc': 'A', 'ten_file': 'Kéo A', 'dong_thong_so': ['Dài: 1mm']}])
    xong = _chay('build_queries.py', '--codes', str(codes), '--out', str(tmp_path / 'q.json'))
    assert xong.returncode != 0
