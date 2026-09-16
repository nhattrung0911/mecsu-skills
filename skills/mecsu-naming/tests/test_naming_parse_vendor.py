# -*- coding: utf-8 -*-
"""B4 - rut ten va thong so tu HTML da tai ve.

Khong ca nao cham mang: HTML dung o day la ban rut gon cua trang that, giu dung
cau truc da gay loi. Cham mang thi test phu thuoc vao mot website ben ngoai.
"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'parse_vendor.py'

# Bang DOC: moi <tr> la mot cap (nhan, gia tri). Luc dau doan nham la bang ngang
# va ket qua ra `Product No = A (mm)` - ghep nhan voi nhan.
SATA = '''<html><head><title>13304-1/2" Dr. 6pt. Socket 13MM-Sata Tools</title></head>
<body><div id="pills-home"><table><tbody>
<tr><td>Product No</td><td>13304</td></tr>
<tr><td>A (mm)</td><td>22.2</td></tr>
<tr><td>Net Weight (kg)</td><td>0.09</td></tr>
</tbody></table></div></body></html>'''

# Nhan ngan nam LONG trong nhan dai. Sap xep sai thi `サイズ` chiem cho truoc
# `サイズ（刃先×全長）` va gia tri thanh `（刃先×` - mot manh cua chinh cai nhan.
ANEX = '''<html><head><title>黒龍靭ビット スリムタイプ 2本組 ＋2×110 | ANEXブランド</title></head>
<body><section class="p-item-detail">
メーカー品番 ABRS-2110 サイズ（刃先×全長） ＋2×110 取付数（本） 2
材質 クロム・モリブデン・バナジウム鋼 製造国 日本 JANコード 4962485399832
</section></body></html>'''


def _chay(tmp_path: Path, trang: dict, codes: list | None = None):
    nguon = tmp_path / 'sources'
    nguon.mkdir()
    chi_muc = {}
    for ma, (ten_file, url, noi_dung) in trang.items():
        (nguon / ten_file).write_text(noi_dung, encoding='utf-8')
        chi_muc[ma] = {'url': url, 'file': ten_file, 'byte': len(noi_dung), 'http': 200}
    (nguon / 'index.json').write_text(json.dumps(chi_muc, ensure_ascii=False), encoding='utf-8')

    co = [sys.executable, str(SCRIPT), '--sources-dir', str(nguon),
          '--out', str(tmp_path / 'facts.json')]
    if codes is not None:
        duong_dan = tmp_path / 'codes.json'
        duong_dan.write_text(json.dumps(codes, ensure_ascii=False), encoding='utf-8')
        co += ['--codes', str(duong_dan)]

    xong = subprocess.run(co, capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=120)
    ra = tmp_path / 'facts.json'
    return xong, (json.loads(ra.read_text(encoding='utf-8')) if ra.exists() else None)


def test_sata_bang_doc_ghep_dung_cap(tmp_path):
    xong, ra = _chay(
        tmp_path,
        {'SAT-13304': ('a.html', 'https://www.satatools.com/en/Product/show/13304.html', SATA)},
        codes=[{'ma_goc': 'SAT-13304', 'hang': 'SATA', 'ma_hang': '13304'}])
    assert xong.returncode == 0, xong.stdout + xong.stderr
    ts = ra[0]['thong_so']
    assert ts['Product No'] == '13304'
    assert ts['A (mm)'] == '22.2', 'ghep nham nhan voi nhan'
    assert ts['Net Weight (kg)'] == '0.09'


def test_sata_ten_bo_ma_va_ten_hang(tmp_path):
    _, ra = _chay(
        tmp_path,
        {'SAT-13304': ('a.html', 'https://www.satatools.com/en/Product/show/13304.html', SATA)},
        codes=[{'ma_goc': 'SAT-13304', 'hang': 'SATA', 'ma_hang': '13304'}])
    assert ra[0]['ten_nguon'] == '1/2" Dr. 6pt. Socket 13MM'


def test_anex_nhan_dai_thang_nhan_ngan(tmp_path):
    _, ra = _chay(
        tmp_path,
        {'ANE-ABRS-2110': ('b.html', 'https://www.anextool.co.jp/item/ABRS-2110/', ANEX)},
        codes=[{'ma_goc': 'ANE-ABRS-2110', 'hang': 'Anex', 'ma_hang': 'ABRS-2110'}])
    ts = ra[0]['thong_so']
    assert ts['メーカー品番'] == 'ABRS-2110'
    assert ts['サイズ（刃先×全長）'] == '＋2×110', 'nhan ngan chiem cho nhan dai'
    assert 'サイズ' not in ts or ts.get('サイズ') != '（刃先×'
    assert ts['JANコード'] == '4962485399832'


def test_anex_gia_tri_khong_tran_sang_muc_sau(tmp_path):
    """Gia tri chay toi nhan KE TIEP - thieu mot nhan la nuot ca doan sau."""
    _, ra = _chay(
        tmp_path,
        {'ANE-ABRS-2110': ('b.html', 'https://www.anextool.co.jp/item/ABRS-2110/', ANEX)},
        codes=[{'ma_goc': 'ANE-ABRS-2110', 'hang': 'Anex', 'ma_hang': 'ABRS-2110'}])
    assert ra[0]['thong_so']['製造国'] == '日本'


def test_moi_dong_deu_kem_url_nguon(tmp_path):
    """Khong co URL thi khong ai kiem lai duoc gia tri - luat cot loi cua skill nay."""
    _, ra = _chay(
        tmp_path,
        {'SAT-13304': ('a.html', 'https://www.satatools.com/en/Product/show/13304.html', SATA)},
        codes=[{'ma_goc': 'SAT-13304', 'hang': 'SATA', 'ma_hang': '13304'}])
    assert ra[0]['url'].endswith('/13304.html')


def test_co_trang_nhung_khong_rut_duoc_thi_thoat_khac_0(tmp_path):
    """Cau truc trang doi ma van bao xong la che do hong te nhat."""
    xong, _ = _chay(
        tmp_path,
        {'SAT-1': ('a.html', 'https://www.satatools.com/en/Product/show/1.html',
                   '<html><body>khong co title</body></html>')},
        codes=[{'ma_goc': 'SAT-1', 'hang': 'SATA', 'ma_hang': '1'}])
    assert xong.returncode != 0


def test_thieu_index_thi_thoat_khac_0(tmp_path):
    (tmp_path / 'sources').mkdir()
    xong = subprocess.run(
        [sys.executable, str(SCRIPT), '--sources-dir', str(tmp_path / 'sources'),
         '--out', str(tmp_path / 'facts.json')],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    assert xong.returncode != 0
