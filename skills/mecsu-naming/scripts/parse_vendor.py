# -*- coding: utf-8 -*-
"""B4: doc HTML da tai ve, rut ten + thong so tu trang hang. 0 token model.

    python parse_vendor.py --sources-dir jobs/naming-01/sources --out facts.json

Moi gia tri rut ra deu kem `url` cua trang no den tu. Khong suy, khong doan:
cai gi trang khong noi thi khong co trong ket qua.

Hai hang co cau truc khac han nhau, do 2026-09-11:
  SATA  <title>13304-1/2" Dr. 6pt. Socket 13MM-Sata Tools</title> + mot bang
        <table> trong khoi #pills-home: hang dau la nhan, hang sau la gia tri.
  Anex  KHONG co <table> nao. Ten o <title> truoc dau `|`, thong so nam trong
        khoi class="p-item-detail" dang `メーカー品番 ABRS-2110 サイズ... ＋2×110`.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

THE = re.compile(r'<[^>]+>')
HANG_BANG = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S | re.I)
O_BANG = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.S | re.I)

# Nhan tren trang Anex. Xep DAI TRUOC de nhan dai duoc bat truoc nhan ngan
# nam long trong no (`サイズ（刃先×全長）` truoc `サイズ`).
# Phai liet ke ca nhung nhan KHONG can lay: gia tri chay toi nhan KE TIEP, nen
# thieu mot nhan la gia tri truoc no nuot luon ca doan sau.
NHAN_ANEX = sorted(
    ('メーカー品番', 'サイズ（刃先×全長）', 'サイズ', '軸長', '全長', '質量', 'JANコード',
     '入数', '材質', '規格', '取付数（本）', '取付数', '製品特徴', '仕様', '製造国',
     '小箱', '定価（税抜）', '定価', 'パッケージ', '用途'),
    key=len, reverse=True)


def chu(doan: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(THE.sub(' ', doan))).strip()


def tieu_de(trang: str) -> str:
    khop = re.search(r'<title>(.*?)</title>', trang, re.S | re.I)
    return chu(khop.group(1)) if khop else ''


def doc_sata(trang: str, ma: str) -> dict:
    ten = tieu_de(trang)
    # `13304-1/2" Dr. 6pt. Socket 13MM-Sata Tools` -> bo ma o dau va ten hang o cuoi
    ten = re.sub(r'\s*-\s*Sata Tools\s*$', '', ten, flags=re.I)
    ten = re.sub(r'^%s\s*-\s*' % re.escape(ma), '', ten)

    thong_so: dict[str, str] = {}
    dau = trang.find('id="pills-home"')
    if dau >= 0:
        khoi = trang[dau:dau + 20000]
        # Bang DOC: moi <tr> la mot cap (nhan, gia tri). Do 2026-09-11 - luc dau
        # doan nham la bang ngang va ra `Product No = A (mm)`, tuc ghep nhan voi nhan.
        for hang in HANG_BANG.findall(khoi):
            o = [chu(x) for x in O_BANG.findall(hang)]
            if len(o) == 2 and o[0] and o[1]:
                thong_so.setdefault(o[0], o[1])
    return {'ten_nguon': ten.strip(), 'thong_so': thong_so}


def doc_anex(trang: str) -> dict:
    ten = tieu_de(trang).split('|')[0].strip()
    thong_so: dict[str, str] = {}
    khop = re.search(r'class="p-item-detail"(.*?)</section>', trang, re.S | re.I)
    if not khop:
        khop = re.search(r'class="p-item-detail"(.{0,4000})', trang, re.S | re.I)
    if khop:
        doan = chu(khop.group(1))
        # `メーカー品番 ABRS-2110 サイズ（刃先×全長） ＋2×110` - nhan tieng Nhat, gia tri
        # theo sau. Giu nguyen van, khong dich: dich la suy, va suy o tang khac.
        #
        # Tim VI TRI cua moi nhan roi cat text GIUA hai nhan. Truoc day tim tung
        # nhan roi lay token ke tiep, nen `サイズ` khop vao trong `サイズ（刃先×全長）`
        # va tra ve `（刃先×全長）` - tuc lay manh cua chinh cai nhan lam gia tri.
        vi_tri = []
        for nhan in NHAN_ANEX:
            for m in re.finditer(re.escape(nhan), doan):
                vi_tri.append((m.start(), m.end(), nhan))
        # Cung mot vi tri thi nhan DAI phai thang: sap xep theo (dau, -cuoi).
        # Sap xep tang dan ca hai thi `サイズ` chiem cho truoc `サイズ（刃先×全長）`,
        # va gia tri tra ve thanh `（刃先×` - mot manh cua chinh cai nhan.
        vi_tri.sort(key=lambda x: (x[0], -x[1]))
        # Bo nhan nam LONG trong mot nhan khac da bat duoc.
        giu = []
        for dau_n, cuoi_n, nhan in vi_tri:
            if giu and dau_n < giu[-1][1]:
                continue
            giu.append((dau_n, cuoi_n, nhan))
        for i, (_, cuoi_n, nhan) in enumerate(giu):
            het = giu[i + 1][0] if i + 1 < len(giu) else len(doan)
            gia_tri = doan[cuoi_n:het].strip(' :：')
            if gia_tri:
                thong_so.setdefault(nhan, gia_tri)
    return {'ten_nguon': ten, 'thong_so': thong_so}


def doc_cache(duong_dan: Path) -> str:
    """Doc file cache, tu nhan biet co nen gzip hay khong.

    fetch_sources.py luu dang .gz: text nen con ~1% HTML tho, nen job 5.730 san
    pham xuong tu ~2 GB con ~24 MB. Doc thang bang read_text() se ra byte rac.
    """
    if duong_dan.suffix == '.gz':
        return gzip.decompress(duong_dan.read_bytes()).decode('utf-8', 'replace')
    return duong_dan.read_text(encoding='utf-8', errors='replace')


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sources-dir', type=Path, required=True,
                        help='Thu muc fetch_sources.py da ghi, co index.json.')
    parser.add_argument('--codes', type=Path,
                        help='codes.json, de biet hang cua tung ma. Khong co thi doan theo trang.')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()

    chi_muc_file = args.sources_dir / 'index.json'
    if not chi_muc_file.exists():
        raise SystemExit('khong thay %s - chay fetch_sources.py truoc' % chi_muc_file)
    chi_muc = json.loads(chi_muc_file.read_text(encoding='utf-8'))

    hang_theo_ma = {}
    if args.codes and args.codes.exists():
        hang_theo_ma = {m['ma_goc']: m for m in json.loads(args.codes.read_text(encoding='utf-8'))}

    ket_qua, khong_rut_duoc = [], 0
    for ma_goc, muc in chi_muc.items():
        if not muc.get('file'):
            continue
        duong_dan = args.sources_dir / muc['file']
        if not duong_dan.exists():
            continue
        trang = doc_cache(duong_dan)

        thong_tin = hang_theo_ma.get(ma_goc, {})
        hang = thong_tin.get('hang') or ('Anex' if 'anextool' in muc['url'] else 'SATA')
        ma_hang = thong_tin.get('ma_hang', '')
        rut = doc_anex(trang) if hang == 'Anex' else doc_sata(trang, ma_hang)

        if not rut['ten_nguon']:
            khong_rut_duoc += 1
            continue
        ket_qua.append({'ma_goc': ma_goc, 'hang': hang, 'ma_hang': ma_hang,
                        'url': muc['url'], **rut})

    co_thong_so = sum(1 for m in ket_qua if m['thong_so'])
    print('trang da tai   %5d' % sum(1 for m in chi_muc.values() if m.get('file')))
    print('rut duoc ten   %5d' % len(ket_qua))
    print('  kem thong so %5d' % co_thong_so)
    print('khong rut duoc %5d' % khong_rut_duoc)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding='utf-8')
    print('da ghi %s' % args.out)

    if chi_muc and not ket_qua:
        raise SystemExit('co trang tai ve nhung khong rut duoc gi - cau truc trang co the da doi.')


if __name__ == '__main__':
    main()
