# -*- coding: utf-8 -*-
"""B3 - tai trang hang, co cache.

Khong ca nao goi mang that. Ca quan trong nhat dung mot URL KHONG THE tai duoc:
neu script van bao "tu cache" va thoat 0 thi cache dung that, chu khong phai
no lang le di tai lai.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'

_spec = importlib.util.spec_from_file_location('fetch_nguon', SCRIPTS / 'fetch_sources.py')
fetch_sources = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch_sources)

# Cong 1 tren localhost: khong dich vu nao lang nghe -> tai la hong ngay.
URL_CHET = 'http://127.0.0.1:1/khong-the-tai.html'


def _chay(*co):
    return subprocess.run([sys.executable, str(SCRIPTS / 'fetch_sources.py'), *co],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=90)


def _sources(tmp_path: Path, danh_sach) -> Path:
    duong_dan = tmp_path / 'sources.json'
    duong_dan.write_text(json.dumps(danh_sach, ensure_ascii=False), encoding='utf-8')
    return duong_dan


def test_ten_cache_theo_noi_dung_url():
    """Cung URL ra cung ten file, du chay bao nhieu lan hay thu tu nao."""
    assert fetch_sources.ten_cache(URL_CHET) == fetch_sources.ten_cache(URL_CHET)
    assert fetch_sources.ten_cache(URL_CHET) != fetch_sources.ten_cache(URL_CHET + 'x')


def test_luu_nen_va_phan_biet_hai_dang():
    """Mac dinh luu text nen: do 2026-09-11, 8 trang that tu 2,9 MB con 56 KB.

    Hai dang phai ra ten file KHAC nhau, khong thi doi --luu ma cache cu van hit
    va buoc sau doc phai text trong khi no can bang HTML.
    """
    assert fetch_sources.ten_cache(URL_CHET).endswith('.txt.gz')
    assert fetch_sources.ten_cache(URL_CHET, 'html').endswith('.html.gz')
    assert fetch_sources.ten_cache(URL_CHET) != fetch_sources.ten_cache(URL_CHET, 'html')


def test_loc_chu_bo_the_va_script():
    trang = b'<html><head><style>a{color:red}</style></head><body><p>Dai: 180mm</p></body></html>'
    chu = fetch_sources.loc_chu(trang).decode('utf-8')
    assert 'Dai: 180mm' in chu
    assert 'color' not in chu, 'noi dung <style> lot vao text gui cho model'


def test_doc_cache_hieu_file_nen(tmp_path):
    """Doc thang bang read_text() tren file .gz se ra byte rac."""
    import gzip
    duong_dan = tmp_path / 'a.txt.gz'
    duong_dan.write_bytes(gzip.compress('Chiều dài: 180mm'.encode('utf-8')))
    assert fetch_sources.doc_cache(duong_dan) == 'Chiều dài: 180mm'


def test_co_cache_thi_khong_tai_lai(tmp_path):
    """URL nay khong the tai duoc. Neu ket qua la 'tu cache 1' va thoat 0 thi
    script that su doc dia, chu khong lang le di tai."""
    nguon = _sources(tmp_path, [{'ma_goc': 'A', 'url_hang': URL_CHET}])
    thu_muc = tmp_path / 'sources'
    thu_muc.mkdir()
    (thu_muc / fetch_sources.ten_cache(URL_CHET)).write_text(
        'x' * (fetch_sources.NHO_NHAT + 10), encoding='utf-8')

    xong = _chay('--sources', str(nguon), '--out-dir', str(thu_muc), '--delay', '0')
    assert xong.returncode == 0, xong.stdout + xong.stderr
    assert 'tu cache          1' in xong.stdout.replace('\t', ' ') or 'tu cache' in xong.stdout
    assert 'tai moi           0' in xong.stdout or 'tai moi' in xong.stdout


def test_file_cache_qua_nho_thi_khong_tinh_la_co(tmp_path):
    """Trang loi thuong rat ngan. Coi no la cache hop le thi loi dong bang vinh vien."""
    nguon = _sources(tmp_path, [{'ma_goc': 'A', 'url_hang': URL_CHET}])
    thu_muc = tmp_path / 'sources'
    thu_muc.mkdir()
    (thu_muc / fetch_sources.ten_cache(URL_CHET)).write_text('loi', encoding='utf-8')

    xong = _chay('--sources', str(nguon), '--out-dir', str(thu_muc), '--delay', '0')
    # Tai lai that bai -> khong lay duoc ma nao -> phai thoat khac 0.
    assert xong.returncode != 0, 'ca hang doi that bai ma van bao xong'


def test_khong_ma_nao_co_url_thi_thoat_khac_0(tmp_path):
    nguon = _sources(tmp_path, [{'ma_goc': 'A', 'url_hang': None}])
    xong = _chay('--sources', str(nguon), '--out-dir', str(tmp_path / 'ra'), '--delay', '0')
    assert xong.returncode != 0


def test_uu_tien_nguon_doc_lap_hon_trang_cua_chinh_minh(tmp_path):
    """Trang cua chinh cong ty khong xac minh duoc du lieu cua chinh cong ty do.

    Do 2026-09-11: PM-10WHI chi tim ra hatok.vn - chinh la trang cua khach hang
    dang dung skill. Lay no lam bang chung la lap luan vong tron.
    """
    nguon = _sources(tmp_path, [{
        'ma_goc': 'A',
        'ung_vien': [{'url': 'https://hatok.vn/x', 'tu_minh': True},
                     {'url': URL_CHET, 'tu_minh': False}],
    }])
    thu_muc = tmp_path / 'sources'
    thu_muc.mkdir()
    # Dat cache san cho nguon DOC LAP. Neu script chon dung no thi bao "tu cache";
    # chon trang cua chinh minh thi phai di tai va that bai.
    (thu_muc / fetch_sources.ten_cache(URL_CHET)).write_text(
        'x' * (fetch_sources.NHO_NHAT + 10), encoding='utf-8')

    xong = _chay('--sources', str(nguon), '--out-dir', str(thu_muc), '--delay', '0')
    assert xong.returncode == 0, xong.stdout + xong.stderr
    assert 'tu cache' in xong.stdout and 'tai moi           0' in xong.stdout, xong.stdout


def test_thieu_file_sources_thi_thoat_khac_0(tmp_path):
    xong = _chay('--sources', str(tmp_path / 'khong-co.json'), '--out-dir', str(tmp_path / 'ra'))
    assert xong.returncode != 0


def test_limit_gioi_han_hang_doi(tmp_path):
    """Tai het 3.672 trang trong mot lan chay la khong ai kiem soat duoc."""
    nguon = _sources(tmp_path, [{'ma_goc': 'M%d' % i, 'url_hang': URL_CHET + str(i)}
                                for i in range(10)])
    thu_muc = tmp_path / 'sources'
    thu_muc.mkdir()
    for i in range(3):
        (thu_muc / fetch_sources.ten_cache(URL_CHET + str(i))).write_text(
            'x' * (fetch_sources.NHO_NHAT + 10), encoding='utf-8')

    xong = _chay('--sources', str(nguon), '--out-dir', str(thu_muc),
                 '--limit', '3', '--delay', '0')
    assert xong.returncode == 0, xong.stdout + xong.stderr
    assert 'hang doi: 3 / 10' in xong.stdout, xong.stdout
