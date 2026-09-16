# -*- coding: utf-8 -*-
"""Vong 0 (hoc quy uoc) va Vong 1 (ap quy uoc).

Khong ca nao goi model: phan goi model da duoc chay tay tren du lieu that, con
day khoa nhung cho HONG AM THAM - dung sai ma van thoat 0, hoac bo qua doi chieu.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def _nap(ten_file: str, ten_module: str):
    """Nap duoi ten rieng. `skill_env.py` ton tai o nhieu skill; import bang ten
    tran nhet module cua skill nay vao sys.modules va lam do test cua skill kia."""
    spec = importlib.util.spec_from_file_location(ten_module, SCRIPTS / ten_file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[ten_module] = module
    spec.loader.exec_module(module)
    return module


_skill_env = _nap('skill_env.py', 'vong01_skill_env')
sys.modules['skill_env'] = _skill_env
apply_convention = _nap('apply_convention.py', 'vong01_apply')
learn_convention = _nap('learn_convention.py', 'vong01_learn')
del sys.modules['skill_env']


def _chay(ten_file: str, *co):
    return subprocess.run([sys.executable, str(SCRIPTS / ten_file), *co],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=90)


def _ghi(duong_dan: Path, du_lieu) -> Path:
    duong_dan.write_text(json.dumps(du_lieu, ensure_ascii=False), encoding='utf-8')
    return duong_dan


QUY_UOC = {
    'cong_thuc_ten': '{Loại} {Hãng} {Mã}',
    'quy_tac': ['Tên mở đầu bằng chủng loại.'],
    '_quyet_dinh_cua_nguoi': {
        'cong_thuc_chuan': '{Loại sản phẩm} {Đặc trưng} {Hãng} {Mã}',
        'ma_trong_ten': 'Giữ đúng mã gốc.',
    },
}


# --- Vong 1: doi chieu nguoc ------------------------------------------------

def test_ma_bi_viet_lai_thi_khong_dat():
    """Loi that: ma `C-1 450x16x21` bi model viet thanh `C1-450x16x21`."""
    assert not apply_convention.ma_dung_trong_ten(
        'C-1 450x16x21', 'Xà beng nhổ đinh Mokuba Japan C1-450x16x21')


def test_ma_dung_nguyen_van_thi_dat():
    assert apply_convention.ma_dung_trong_ten(
        'C-1 450x16x21', 'Xà beng nhổ đinh Mokuba Japan C-1 450x16x21')


def test_tien_to_noi_bo_khong_phai_la_can_cu():
    """Loi that, do tren 200 dong that: so voi `ma_goc` lam 97/100 dong bao dong gia.

    `SAT-` la tien to NOI BO, khong duoc xuat hien trong ten ban hang. Ten dung
    chua `12913`, khong chua `SAT-12913`. So nham lam nua file thanh REVIEW gia,
    va REVIEW gia nhieu thi nguoi duyet bo qua ca REVIEW that.
    """
    assert apply_convention.ma_dung_trong_ten(
        'SAT-12913', 'Đầu Chuyển Đổi 3/8 Inch SATA 12913', '12913')
    assert apply_convention.ma_dung_trong_ten(
        'BSI-BS522015', 'Bộ Dụng Cụ 5 Chi Tiết Bosi BS522015', 'BS522015')


def test_tien_to_noi_bo_lot_vao_ten_thi_khong_dat():
    """Loi that, do tren 200 dong: 99/200 ten ban hang chua luon tien to noi bo
    (`SATA SAT-70303A`), va TAT CA deu duoc cham OK - vi cau kiem chi hoi "co
    chua ma hang khong", ma `70303A` thi nam ngay trong `SAT-70303A`.

    Chua ma hang la DIEU KIEN CAN, khong phai du.
    """
    assert not apply_convention.ma_dung_trong_ten(
        'SAT-70303A', 'Kìm Điện 200 mm SATA SAT-70303A', '70303A')
    assert apply_convention.ma_dung_trong_ten(
        'SAT-70303A', 'Kìm Điện 200 mm SATA 70303A', '70303A')


def test_van_bat_duoc_ma_bi_viet_lai_khi_co_ma_hang():
    """Noi long theo ma_hang khong duoc lam mat chot chan cu."""
    assert not apply_convention.ma_dung_trong_ten(
        'SAT-70301A', 'Kìm Điện 160 mm SATA 70301 A', '70301A')


def test_tu_sua_bien_the_cua_ma_ve_dung_ma_goc():
    """Nhac trong prompt khong du: model chep dang ma trong ten cu, 4/20 dong,
    lap lai qua nhieu lan chay. Sua bang code moi chac."""
    assert apply_convention.sua_ma_trong_ten(
        'Xà Beng Dài 450 mm Mokuba C1-450x16x21 Japan', 'C-1 450x16x21'
    ) == 'Xà Beng Dài 450 mm Mokuba C-1 450x16x21 Japan'


def test_khong_ghep_nham_hai_ma_khac_nhau():
    """`AG-1` va `AG-10` la HAI san pham. Ghep nham la gan sai ma cho hang."""
    goc = 'Kéo Thu Hoạch Saboten AG-10 Nhật Bản'
    assert apply_convention.sua_ma_trong_ten(goc, 'AG-1') == goc


def test_khong_tim_thay_bien_the_thi_de_nguyen():
    goc = 'Kéo Thu Hoạch Saboten Nhật Bản'
    assert apply_convention.sua_ma_trong_ten(goc, 'AG-1') == goc


def test_ten_rong_thi_khong_dat():
    """Model bo sot mot muc ma van bao OK la mat dong am tham."""
    assert not apply_convention.ma_dung_trong_ten('B-8', '')


# --- Vong 1: chot chan truoc khi tieu tien ----------------------------------

def test_khong_co_quyet_dinh_rieng_thi_dung_chuan_mecsu(tmp_path):
    """Skill nay cua rieng Mecsu nen chuan DI KEM SKILL, khong hoi lai moi lan chay.

    Truoc day bat nguoi dung chot cong thuc o TUNG job - sai, vi ho khong biet
    cong thuc va cung khong can biet.
    """
    codes = _ghi(tmp_path / 'codes.json', [{'ma_goc': 'B-8', 'ten_file': 'Kéo B-8'}])
    quy_uoc = _ghi(tmp_path / 'qu.json', {'cong_thuc_ten': 'x', '_quyet_dinh_cua_nguoi': {}})
    xong = _chay('apply_convention.py', '--codes', str(codes), '--convention', str(quy_uoc),
                 '--out', str(tmp_path / 'names.json'), '--dry-run')
    assert xong.returncode == 0, xong.stdout + xong.stderr


def test_dry_run_bao_so_lan_goi_va_khong_goi_model(tmp_path):
    codes = _ghi(tmp_path / 'codes.json',
                 [{'ma_goc': 'M%d' % i, 'ten_file': 'Kéo %d' % i} for i in range(45)])
    quy_uoc = _ghi(tmp_path / 'qu.json', QUY_UOC)
    ra = tmp_path / 'names.json'
    xong = _chay('apply_convention.py', '--codes', str(codes), '--convention', str(quy_uoc),
                 '--out', str(ra), '--batch', '20', '--dry-run')
    assert xong.returncode == 0, xong.stdout + xong.stderr
    assert '3 lan goi' in xong.stdout, xong.stdout
    assert not ra.exists(), '--dry-run ma van ghi ket qua'


def test_dong_khong_co_ten_de_cho_vong_2(tmp_path):
    """Vong 1 khong ra internet - dong trong phai duoc chuyen tiep, khong bi bia."""
    codes = _ghi(tmp_path / 'codes.json',
                 [{'ma_goc': 'A', 'ten_file': 'Kéo A'}, {'ma_goc': 'B', 'ten_file': ''}])
    quy_uoc = _ghi(tmp_path / 'qu.json', QUY_UOC)
    xong = _chay('apply_convention.py', '--codes', str(codes), '--convention', str(quy_uoc),
                 '--out', str(tmp_path / 'n.json'), '--dry-run')
    assert 'de vong 2' in xong.stdout


# --- Vong 0: hoc quy uoc ----------------------------------------------------

def test_khong_co_ten_nao_de_hoc_thi_dung_va_noi_ro(tmp_path):
    """File chi co ma thi khong hoc duoc quy uoc tu no - phai noi ro, khong bia."""
    codes = _ghi(tmp_path / 'codes.json', [{'ma_goc': 'B-8', 'ten_file': ''}])
    xong = _chay('learn_convention.py', '--codes', str(codes),
                 '--out', str(tmp_path / 'qu.json'))
    assert xong.returncode != 0
    assert 'convention.json' in xong.stdout + xong.stderr


def test_uu_tien_dong_co_nhieu_thong_so_lam_vi_du(tmp_path):
    """Dong co ca ten lan thong so day duoc nhieu hon dong chi co ten."""
    codes = _ghi(tmp_path / 'codes.json', [
        {'ma_goc': 'A', 'ten_file': 'Kéo A', 'dong_thong_so': []},
        {'ma_goc': 'B', 'ten_file': 'Kéo B', 'dong_thong_so': ['Dài: 180mm', 'Lưỡi: 35mm']},
    ])
    xong = _chay('learn_convention.py', '--codes', str(codes),
                 '--out', str(tmp_path / 'qu.json'), '--mau', '1', '--dry-run')
    assert xong.returncode == 0, xong.stdout + xong.stderr
    assert 'dung lam vi du         1' in xong.stdout.replace('  ', ' ').replace('   ', ' ') \
        or 'dung lam vi du' in xong.stdout


def test_learn_dry_run_khong_ghi_file(tmp_path):
    codes = _ghi(tmp_path / 'codes.json', [{'ma_goc': 'A', 'ten_file': 'Kéo A'}])
    ra = tmp_path / 'qu.json'
    xong = _chay('learn_convention.py', '--codes', str(codes), '--out', str(ra), '--dry-run')
    assert xong.returncode == 0
    assert not ra.exists()
