# -*- coding: utf-8 -*-
"""B1 - do cot ma va tach tien to noi bo.

Moi ca duoi day tra loi duoc cau "loi that nao lot neu thieu ca nay".
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'extract_codes.py'


def _chay(*co):
    return subprocess.run([sys.executable, str(SCRIPT), *co], capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=120)


def _csv(tmp_path: Path, noi_dung: str) -> Path:
    duong_dan = tmp_path / 'vao.csv'
    duong_dan.write_text(noi_dung, encoding='utf-8')
    return duong_dan


def _ket_qua(tmp_path: Path, noi_dung: str, *co):
    vao = _csv(tmp_path, noi_dung)
    ra = tmp_path / 'ra.json'
    xong = _chay('--input', str(vao), '--out', str(ra), *co)
    assert xong.returncode == 0, xong.stdout + xong.stderr
    return json.loads(ra.read_text(encoding='utf-8'))


def test_khong_nhan_nham_cot_chi_vi_chua_chuoi_con(tmp_path):
    """Loi that: `"ma" in "gamma"` -> cot `gamma` bi nhan la cot ma va script chay tiep.

    Thieu ca nay thi script doan bua mot cot bat ky roi tra ve rac, thay vi dung lai.
    """
    xong = _chay('--input', str(_csv(tmp_path, 'alpha,beta,gamma\nx,y,z\n')))
    assert xong.returncode != 0, 'header khong co cot ma ma script van chay tiep'


def test_dung_thi_in_header_that_va_ten_co(tmp_path):
    """Dung lai ma khong noi ro phai lam gi thi nguoi dung tac o do."""
    xong = _chay('--input', str(_csv(tmp_path, 'alpha,beta\nx,y\n')))
    loi = xong.stdout + xong.stderr
    assert '--code-col' in loi, 'khong chi ra ten co de sua'
    assert 'alpha' in loi and 'beta' in loi, 'khong in header that cua file'


def test_do_ra_cot_part_number(tmp_path):
    muc = _ket_qua(tmp_path, 'part_id,part_number,mo_ta\n1,SAT-34505,x\n')
    assert muc[0]['ma_hang'] == '34505'


def test_code_col_ep_tay_duoc(tmp_path):
    muc = _ket_qua(tmp_path, 'alpha,beta\nq,SAT-34505\n', '--code-col', '1')
    assert muc[0]['hang'] == 'SATA'


def test_tach_tien_to_giu_nguyen_phan_con_lai(tmp_path):
    """Hau to chu va gach ngang la MOT PHAN cua ma hang, bo di la tra sai trang.

    Do 2026-09-11: anextool.co.jp/item/ABRS-2110/ tra 200, con ABRS2110 tra 404.
    """
    muc = {m['ma_goc']: m for m in _ket_qua(
        tmp_path,
        'part_number\nSAT-96552K\nANE-ABRS-2110\nANE-No.3510\nBSI-BS423172\n')}

    assert muc['SAT-96552K']['hang'] == 'SATA'
    assert muc['SAT-96552K']['ma_hang'] == '96552K', 'hau to K bi bo'
    assert muc['ANE-ABRS-2110']['ma_hang'] == 'ABRS-2110', 'gach ngang bi bo'
    assert muc['ANE-No.3510']['ma_hang'] == '3510', 'tien to No. cua catalogue chua duoc bo'
    assert muc['BSI-BS423172']['hang'] == 'Bosi'


def test_tien_to_chua_xac_minh_thi_KHONG_duoc_cat(tmp_path):
    """Loi that: `PM-10BLA` bi cat thanh `10BLA` va ma sai di thang vao file giao.

    `PM` la mot phan cua ma hang (Paint Marker), khong phai tien to noi bo. Cat
    moi cum 2-4 chu cai truoc gach ngang la lam hong ma cua khach. Kiem "ten co
    chua ma hang khong" cung khong bat duoc, vi luc do no so voi `10BLA` - chinh
    la ket qua da hong.
    """
    muc = {m['ma_goc']: m for m in _ket_qua(
        tmp_path, 'part_number\nPM-10BLA\nBOS-12345\nSAT-96552K\n')}

    assert muc['PM-10BLA']['ma_hang'] == 'PM-10BLA', 'ma hang bi cat mat'
    assert muc['PM-10BLA']['tien_to'] == ''
    assert muc['BOS-12345']['ma_hang'] == 'BOS-12345', '`BOS` chua xac minh - khong duoc cat'
    # Tien to DA xac minh thi van cat binh thuong.
    assert muc['SAT-96552K']['ma_hang'] == '96552K'
    assert muc['SAT-96552K']['hang'] == 'SATA'


def test_gop_ma_trung_va_giu_so_dong(tmp_path):
    """Tra mot lan cho ma trung, nhung phai biet duong ma ghi ket qua ve du dong."""
    muc = _ket_qua(tmp_path, 'part_number\nSAT-34505\nSAT-99999\nSAT-34505\n')
    theo_ma = {m['ma_goc']: m for m in muc}
    assert len(muc) == 2, 'ma trung chua duoc gop'
    assert theo_ma['SAT-34505']['dong'] == [2, 4]


def test_nhan_ra_header_tieng_viet_co_dau(tmp_path):
    """Cot `Mã` phai duoc nhan ra.

    Loi that: ham cat tu cat theo [^a-z0-9], nen `Mã` thanh ['m'] - ky tu `ã` bi
    vut - va cot ma cua moi file tieng Viet deu khong bao gio duoc nhan ra.
    """
    muc = _ket_qua(tmp_path, 'Description,Mã,Type\nXa beng,C-1 450x16x21,RFQ\n')
    assert muc[0]['ma_goc'] == 'C-1 450x16x21'


def test_header_khong_o_dong_dau(tmp_path):
    """File that `Tao ma Hatok.xlsx` co dong 0 rong, header o dong 1.

    Cho rang header luon o dong 0 thi doc ra mot bang toan rong.
    """
    muc = _ket_qua(tmp_path, '\nDescription,Mã\nXa beng,C-1\n')
    assert len(muc) == 1 and muc[0]['ma_goc'] == 'C-1'


def test_bo_cuc_kieu_khoi_gom_dung_dong_thong_so(tmp_path):
    """Mot san pham = mot dong co ma + N dong chi co cot mo ta.

    Gan nham dong thong so sang san pham khac la gan sai kich thuoc cho hang.
    """
    muc = {m['ma_goc']: m for m in _ket_qua(
        tmp_path,
        'Description,Mã\n'
        'Xa beng C-1,C-1\n'
        'Chieu dai: 450mm,\n'
        'Duong kinh: 16mm,\n'
        'But son PM-10,PM-10BLA\n')}

    assert len(muc) == 2
    assert muc['C-1']['dong_thong_so'] == ['Chieu dai: 450mm', 'Duong kinh: 16mm']
    assert muc['PM-10BLA']['dong_thong_so'] == [], 'dong thong so bi gan lan sang san pham sau'
    assert muc['PM-10BLA']['ten_file'] == 'But son PM-10'


def test_chuan_hoa_dau_nhan_unicode(tmp_path):
    """`×` (U+00D7) va `x` phai ve cung mot ma, khong thi thanh hai ma khac nhau."""
    muc = _ket_qua(tmp_path, 'part_number\nSAT-10×20\n')
    assert muc[0]['ma_hang'] == '10x20'
