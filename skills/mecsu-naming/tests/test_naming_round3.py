# -*- coding: utf-8 -*-
"""Vong 3 - ma kho, tim catalog.

Trong tam la `dung_duoc`: no da cho qua BA thanh cong gia trong mot lan chay that
2026-09-11. Moi ca duoi day la mot trong ba cai do.
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


_env = _nap('skill_env.py', 'r3_env')
sys.modules['skill_env'] = _env
r3 = _nap('round3.py', 'r3_main')
del sys.modules['skill_env']

TOT = ('Bút đánh dấu sơn PM-10BLU. Chiều dài 143 mm, đường kính 15 mm, '
       'bề rộng nét 2 mm, khối lượng 30 g.')


def test_nhan_trang_that_su_co_thong_so():
    assert r3.dung_duoc('PM-10BLU', 'https://shop.jp/item/pm-10blu', TOT)


def test_loai_trang_cua_san_pham_KHAC():
    """Loi that: S23052 khop trang cua S23055 - trang catalog liet ke nhieu ma
    nen text co chua ca ma minh dang tim."""
    chu = 'Danh sách: S23050, S23051, S23052, S23055. Chiều dài 143 mm, ngang 15 mm.'
    assert not r3.dung_duoc('S23052', 'https://shosekido.co.jp/item/s-23055/', chu)


def test_loai_trang_khong_co_so_do_nao():
    """Loi that: PM-10BLU khop trang ban le ten dung nhung khong mot so do nao."""
    chu = 'Bút đánh dấu sơn màu xanh Craftmaster Japan PM-10BLU. Hàng chính hãng, xuất VAT.'
    assert not r3.dung_duoc('PM-10BLU', 'https://store.vn/but-son-pm-10blu', chu)


def test_loai_so_do_lay_tu_menu_dieu_huong():
    """Loi that: trang PM-10BLU dat nguong nho `12v 18v 20v` trong MENU danh muc
    may pin - cach cho nhac ma rat xa, khong lien quan gi toi cay but."""
    chu = ('Máy khoan 12V Máy bắt vít 18V Máy mài 20V ' + 'x' * 3000
           + ' Bút đánh dấu sơn PM-10BLU hàng chính hãng')
    assert not r3.dung_duoc('PM-10BLU', 'https://store.vn/pm-10blu', chu)


def test_ma_hoa_url_co_dau():
    """Loi that: urllib nem UnicodeEncodeError voi URL co chu co dau - CRASH giua
    chung, mat ca lo dang chay, chu khong phai that bai em."""
    ra = r3.ma_hoa_url('https://vi.example.com/sản-phẩm/bút-sơn?q=xanh')
    ra.encode('ascii')          # khong nem la dat
    assert '%' in ra


def test_ma_hoa_url_thuong_khong_bi_doi():
    goc = 'https://www.shosekido.co.jp/item/s-23055/'
    assert r3.ma_hoa_url(goc) == goc


def test_khong_ma_nao_can_vong_3_thi_thoat_khac_0(tmp_path):
    """Vong 3 khong co viec ma van thoat 0 thi nguoi dung tuong da doc catalog xong."""
    job = tmp_path / 'job'
    (job / 'web').mkdir(parents=True)
    (job / 'web' / 'index.json').write_text(
        json.dumps({'A': {'url': 'u', 'file': 'a.txt.gz'}}), encoding='utf-8')
    (job / 'web_facts.json').write_text(
        json.dumps([{'ma': 'A', 'thong_so': {'Dài': '1 mm'}}], ensure_ascii=False), encoding='utf-8')
    xong = subprocess.run(
        [sys.executable, str(SCRIPTS / 'round3.py'), '--job', str(job),
         '--out', str(tmp_path / 'r.json')],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    assert xong.returncode != 0


def test_gom_dung_ma_can_lam(tmp_path):
    """Hai nguon vao vong 3: tai that bai, va tai duoc nhung khong co thong so."""
    job = tmp_path / 'job'
    (job / 'web').mkdir(parents=True)
    (job / 'web' / 'index.json').write_text(json.dumps({
        'TAI_HONG': {'url': 'u', 'file': None},
        'CO_FILE': {'url': 'u', 'file': 'a.txt.gz'}}), encoding='utf-8')
    (job / 'web_facts.json').write_text(json.dumps([
        {'ma': 'CO_FILE', 'thong_so': {}},
        {'ma': 'DU_ROI', 'thong_so': {'Dài': '1 mm'}}], ensure_ascii=False), encoding='utf-8')
    ma = {m['ma'] for m in r3.can_lam(job)}
    assert ma == {'TAI_HONG', 'CO_FILE'}, ma
