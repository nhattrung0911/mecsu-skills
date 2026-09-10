# -*- coding: utf-8 -*-
"""Test cho cac chot chan da tung vo trong thuc te.

Moi test o day tuong ung mot loi DA XAY RA khi chay tren du lieu that, khong phai
loi tuong tuong.
"""
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(TOOLS))

import filter_audit as fa          # noqa: E402
import learn_deps as ld            # noqa: E402
import verify_values as vv         # noqa: E402


# --- quy uoc format hoc theo he do, khong theo corpus toan cuc ---

def test_token_unc_bao_hieu_he_inch():
    """He met viet M8x27, he inch viet 3/8-24 x 1. Dau hieu phai hoc tu token."""
    names = ['Bulong Ma Kem M%dx%d' % (i, i * 3) for i in range(4, 44)]
    names += ['Bulong Ma Kem UNC %d/8-24 x %d' % (i % 7 + 1, i) for i in range(1, 44)]
    markers, default = fa.learn_conventions(names)['dim']
    assert fa._predict(markers, default, 'Bulong Ma Kem UNC 3/8-24 x 1') is True
    # Ten he met khong co token quyet dinh -> tra None = "khong chac, dung sua".
    # Chi can no KHONG khang dinh la he inch.
    assert fa._predict(markers, default, 'Bulong Ma Kem M8x24') is not True


def test_token_x_bi_loai_vi_ro_ri_nhan():
    """Token 'x' chi ton tai khi da tach -> du doan hoan hao nhung vo dung."""
    names = ['Bulong M%dx%d' % (i, i * 3) for i in range(4, 44)]
    names += ['Bulong UNC %d/8-24 x %d' % (i % 7 + 1, i) for i in range(1, 44)]
    markers, _default = fa.learn_conventions(names)['dim']
    assert 'x' not in markers


def test_cum_lan_hai_he_thi_khong_sua():
    """Cum tron met lan inch -> khong du bang chung -> khong duoc sua gi."""
    rows = [(1, 'a', 'Bulong M8x20', 1, 'x'), (2, 'b', 'Bulong UNC 3/8-24 x 1', 1, 'x')]
    conv = fa.cluster_conv(rows, [0, 1])
    assert conv['dim_nospace'] is None


def test_khong_sua_khi_khong_co_bang_chung():
    """local rong + marker khong chac -> ten giu nguyen."""
    corpus = fa.learn_conventions(['Bulong M8x20', 'Bulong M10x30'])
    out, fixes = fa.fix_name('Bulong UNC 3/8-24 x 1', corpus, {})
    assert 'bo space quanh x' not in ' '.join(fixes)


def test_gop_space_thua_van_duoc_sua():
    corpus = fa.learn_conventions(['Bulong M8x20'] * 5)
    out, fixes = fa.fix_name('  Bulong  M8x20  ', corpus, {})
    assert out == 'Bulong M8x20'
    assert fixes


# --- tra cuu corpus: mot dong lam chung la khong du ---

def test_lookup_tu_choi_bang_chung_mot_dong():
    """DIN2093 M36 tung bi suy thanh 'M35' tu dung 1 dong."""
    rels = {'Washer': [{
        'target': 'Dung Cho Bulong', 'det': ['Duong Kinh Trong'],
        'table': {'36 mm': 'M35'}, 'keys': {'36 mm': [1, 1]},
        'support': 1, 'consistency': 1.0, 'usable': 1.0,
    }]}
    hit = ld.lookup(rels, 'Washer', {'Duong Kinh Trong': '36 mm'}, 'Dung Cho Bulong')
    assert hit is not None and hit.get('weak') is True


def test_lookup_nhan_khi_du_bang_chung():
    rels = {'Bulong': [{
        'target': 'Size Khoa', 'det': ['Size Ren', 'Tieu Chuan'],
        'table': {'M22\x1fDIN 931': '32 mm'}, 'keys': {'M22\x1fDIN 931': [59, 59]},
        'support': 5660, 'consistency': 0.998, 'usable': 0.41,
    }]}
    hit = ld.lookup(rels, 'Bulong', {'Size Ren': 'M22', 'Tieu Chuan': 'DIN 931'}, 'Size Khoa')
    assert hit['value'] == '32 mm' and not hit.get('weak')


def test_lookup_tu_choi_to_hop_khong_sach():
    """To hop cho ra 2 gia tri khac nhau -> khong duoc tra."""
    rels = {'Bulong': [{
        'target': 'Buoc Ren', 'det': ['Size Ren'],
        'table': {'M20': '2.5 mm'}, 'keys': {'M20': [6, 12]},
        'support': 12, 'consistency': 0.9, 'usable': 1.0,
    }]}
    hit = ld.lookup(rels, 'Bulong', {'Size Ren': 'M20'}, 'Buoc Ren')
    assert hit is None or hit.get('weak')


# --- verify bang duong cong don dieu, TACH THEO LAT CAT ---

def _ring(std, lo, ranh):
    return {'group': 'Ring', 'ten': 'Phe Gai %s D%s' % (std, lo),
            'filter_goc': 'Tieu Chuan: %s | lo: %s mm | ranh: %s mm' % (std, lo, ranh)}


def _index():
    """Hai tieu chuan, hai duong cong khac nhau tren cung mot truc `lo`."""
    rows = [_ring('DIN 472', 44 + 2 * i, 46.5 + 2 * i) for i in range(8)]
    rows += [_ring('DIN 7980', 44 + 2 * i, 60 + 2 * i) for i in range(8)]
    return vv.build_index(rows)


def test_verify_bat_gia_tri_ngoai_khoang_khi_da_tach_lat_cat():
    known = {'lo': '49 mm', 'Tieu Chuan': 'DIN 472'}
    status, detail = vv.verify_one(_index(), 'Ring', 'ranh', known, '20 mm')
    assert status == 'OUT_OF_RANGE'
    assert 'lat cat' in detail


def test_verify_chap_nhan_gia_tri_trong_khoang():
    known = {'lo': '49 mm', 'Tieu Chuan': 'DIN 472'}
    status, _d = vv.verify_one(_index(), 'Ring', 'ranh', known, '51.5 mm')
    assert status == 'PLAUSIBLE'


def test_verify_khong_tach_duoc_thi_khong_bac_bo():
    """Tron ca hai tieu chuan -> chi duoc canh bao, khong duoc tu dong loai.

    Day la loi da xay ra that: corpus tron DIN 127 voi DIN 7980 cho cung
    `Dung Cho Bulong = M14` roi bac bo gia tri DIN 7980 dung la 21.1 mm.
    """
    known = {'lo': '49 mm'}                      # khong biet tieu chuan
    status, _d = vv.verify_one(_index(), 'Ring', 'ranh', known, '20 mm')
    assert status != 'OUT_OF_RANGE'


def test_verify_khong_co_tham_chieu_thi_khong_ket_luan():
    status, _d = vv.verify_one(vv.build_index([]), 'Ring', 'ranh', {'lo': '49 mm'}, '53.5 mm')
    assert status == 'NO_REFERENCE'


# --- chot chan tang 2, them sau khi cham tay bat duoc 5/12 o sai ---

import build_ai_queue as bq          # noqa: E402


def _row(ten, filt=''):
    return {'ten': ten, 'filter_goc': filt, 'group': 'X'}


def test_the_kinh_doanh_khong_duoc_lam_bo_xac_dinh():
    """'Vit Col Inox 316' tung bi dien Vat Lieu = Inox 304 vi suy tu `Nganh Hang`."""
    hit = {'det': ['Ngành Hàng'], 'value': 'Inox 304'}
    assert bq._rejected(hit, bq.NameGuard([]), _row('Vit Col Inox 316'),
                        'Vat Lieu', __import__('collections').Counter()) is True


def test_ten_san_pham_phu_dinh_gia_tri():
    rows = [_row('Bulong Inox 316 M8', 'Vat Lieu: Inox 316'),
            _row('Bulong Inox 304 M8', 'Vat Lieu: Inox 304')] * 6
    guard = bq.NameGuard(rows)
    assert guard.rejects(_row('Bulong Inox 316 M8'), 'Vat Lieu', 'Inox 304') is True
    assert guard.rejects(_row('Bulong Inox 316 M8'), 'Vat Lieu', 'Inox 316') is False


def test_thuoc_tinh_khong_viet_trong_ten_thi_khong_chan_bay():
    """Thuoc tinh chua bao gio xuat hien trong ten -> guard phai im lang."""
    rows = [_row('Bulong M8', 'Buoc Ren: 1.25 mm')] * 12
    guard = bq.NameGuard(rows)
    assert guard.rejects(_row('Bulong M8'), 'Buoc Ren', '1.25 mm') is False


def test_von_tu_khac_nhom_van_chan_duoc():
    """Nhom U-Bolts khong co gia tri "Nhung Nong Kem" nen von tu rieng nhom mu.

    Model bi `allowed_values` ep chon "Ma Kem" cho san pham ten ghi ro nhung nong.
    """
    rows = [_row('Bulong Ma Kem M8', 'Xu Ly Be Mat Of Bulong: Ma Kem'),
            _row('Bulong Nhung Nong Kem M8', 'Xu Ly Be Mat Of Bulong: Nhung Nong Kem')] * 6
    rows += [_row('Cum U Ma Kem DN40', 'Xu Ly Be Mat Of U-Bolts: Ma Kem')] * 12
    guard = bq.NameGuard(rows)
    assert guard.rejects(_row('Cum U Thep SS400 Nhung Nong Kem DN40'),
                         'Xu Ly Be Mat Of U-Bolts', 'Ma Kem') is True


# --- so cac cau tra loi cua model voi nhau ---

def _washer(std, size, od):
    return {'group': 'Washer', 'ten': 'Long Den %s M%s' % (std, size),
            'filter_goc': ('Tieu Chuan Of Washer: %s | Dung Cho Bulong Of Washer: M%s '
                           '| Duong Kinh Ngoai Of Washer: %s mm' % (std, size, od))}


def _washer_index():
    """Hai tieu chuan, hai bang so khac nhau tren cung truc `Dung Cho Bulong`."""
    rows = [_washer('DIN 127', 6 + 2 * i, 11.8 + 3 * i) for i in range(8)]
    rows += [_washer('DIN 7980', 6 + 2 * i, 9.3 + 2.7 * i) for i in range(8)]
    return vv.build_index(rows)


def _answer(size, value, std='DIN 7980'):
    return {'attr': 'Duong Kinh Ngoai Of Washer', 'value': '%s mm' % value,
            'key': '%s-%s-%s' % (std, size, value),
            'known': {'Dung Cho Bulong Of Washer': 'M%s' % size,
                      'Tieu Chuan Of Washer': std}}


def test_cross_check_bat_cung_co_cung_chuan_khac_gia_tri():
    """DIN 7980 M14 duoc tra 24.4 o dong nay va 21.1 o dong khac - it nhat 1 cai sai."""
    flags = vv.cross_check(_washer_index(), [_answer(14, 24.4), _answer(14, 21.1)])
    assert len(flags) == 2


def test_cross_check_khong_bat_khi_tang_dung_chieu():
    """Co khac nhau, gia tri tang theo -> hop le, khong duoc bao dong."""
    flags = vv.cross_check(_washer_index(), [_answer(14, 21.1), _answer(20, 30.1)])
    assert flags == {}


def test_cross_check_khong_bat_khi_khac_tieu_chuan():
    """Cung co nhung khac tieu chuan thi khac bang so - khong phai mau thuan."""
    flags = vv.cross_check(_washer_index(),
                           [_answer(14, 21.1, 'DIN 7980'), _answer(14, 24.1, 'DIN 127')])
    assert flags == {}


# --- nhan dien cot: exact match phai thang substring ---

HANDTOOLS_HEADER = ['part_id', 'part_number', 'part_description', 'leaf_category_name',
                    'category_lv1', 'active_filter_count', 'mapped_filters']


def test_cot_filter_khong_bi_cot_dem_cuop_mat():
    """active_filter_count chua chuoi 'filter' nhung no la cot DEM, khong phai cot filter.

    Da xay ra that tren Handtools-check-cate-filter.xlsx: audit chay xong, exit 0,
    ra file rac vi filt tro vao cot so.
    """
    cols = fa.detect_columns(HANDTOOLS_HEADER)
    assert HANDTOOLS_HEADER[cols['filt']] == 'mapped_filters'
    assert HANDTOOLS_HEADER[cols['name']] == 'part_description'
    assert HANDTOOLS_HEADER[cols['cat']] == 'leaf_category_name'


def test_cot_dem_van_duoc_nhan_dung_vai_count():
    cols = fa.detect_columns(HANDTOOLS_HEADER)
    assert HANDTOOLS_HEADER[cols['count']] == 'active_filter_count'


def test_cot_filter_khong_giong_filter_thi_dung_lai():
    """Doan cot sai thi phai chet o day, khong duoc audit tiep roi ghi file rac."""
    import pytest
    rows = [(str(i), 'X%d' % i, 'San Pham %d' % i, '6', '6') for i in range(20)]
    cols = {'pid': 0, 'code': 1, 'name': 2, 'count': 3, 'filt': 4}
    with pytest.raises(SystemExit):
        fa.check_filter_column(rows, cols, HANDTOOLS_HEADER)
