# -*- coding: utf-8 -*-
"""Buoc cuoi: gom moi thu ve MOT file Excel de giao. 0 token model.

    python build_sheet.py --input <file goc.xlsx> --job jobs/naming-01 --out ket_qua.xlsx

Day la thanh pham. Cac file JSON trong thu muc job la BUOC TRUNG GIAN va cache -
nguoi dung chi can file nay.

Khong ghi de file goc. Cot moi duoc THEM vao ben canh cot cu, de nguoi duyet nhin
thay ca hai ma so.

Dong nao khong du bang chung thi ghi ro TRANG THAI va GHI CHU - trung thuc, de
nguoi tu sua, chu khong de trong cam lang cung khong bia cho day o.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

COT_MOI = ['Tên chuẩn hoá', 'Thông số', 'Nguồn', 'Trạng thái', 'Ghi chú']


def doc(duong_dan: Path):
    return json.loads(duong_dan.read_text(encoding='utf-8')) if duong_dan.exists() else []


def gom(job: Path) -> dict:
    """Gop ket qua cua moi vong lai theo ma. Vong sau bo sung cho vong truoc."""
    theo_ma: dict[str, dict] = {}

    # Thong so SAN CO trong file goc. Bo qua no thi 11/20 san pham cua file that
    # hien "chua tim duoc thong so" trong khi thong so nam ngay trong file.
    thong_so_goc = {m['ma_goc']: m.get('dong_thong_so', [])
                    for m in doc(job / 'codes.json')}

    for r in doc(job / 'names.json'):                       # vong 1
        dong = thong_so_goc.get(r['ma'], [])
        theo_ma[r['ma']] = {
            'ten': r.get('ten_moi', ''),
            'thong_so': {'(từ file gốc)': ' | '.join(dong)} if dong else {},
            'nguon': 'dữ liệu sẵn trong file' if dong else '',
            'trang_thai': r.get('trang_thai', 'OK'), 'ghi_chu': r.get('ghi_chu', ''),
        }

    for r in doc(job / 'web_facts.json'):                   # vong 2
        cu = theo_ma.get(r['ma'], {})
        # Ten cua vong 1 uu tien: no dua tren du lieu khach da co.
        giu_ten_vong_1 = bool(cu.get('ten'))
        ghi_chu_vong_2 = r.get('ghi_chu', '')

        # Vong 2 co the phan nan ve TEN NO DE XUAT. Neu ten do khong duoc dung
        # thi loi phan nan ay noi ve mot thu khong co trong file giao - gay nhieu.
        # Do 2026-09-11: PM-10YEL bi ghi "ten khong chua dung ma goc" trong khi
        # ten thuc su giao ra co chua dung ma.
        if giu_ten_vong_1:
            ghi_chu_vong_2 = ' '.join(
                c for c in ghi_chu_vong_2.split('. ') if 'Tên đề xuất' not in c).strip()

        theo_ma[r['ma']] = {
            'ten': cu.get('ten') or r.get('ten_de_xuat', ''),
            'thong_so': r.get('thong_so', {}),
            'nguon': r.get('url', ''),
            'trang_thai': cu.get('trang_thai') if giu_ten_vong_1 and cu.get('trang_thai') == 'REVIEW'
                          else r.get('trang_thai', 'OK'),
            'ghi_chu': ' '.join(x for x in (cu.get('ghi_chu', ''), ghi_chu_vong_2) if x),
        }

    for r in doc(job / 'round3.json'):                      # vong 3
        cu = theo_ma.get(r['ma'], {'ten': '', 'thong_so': {}, 'nguon': '', 'ghi_chu': ''})
        if r.get('trang_thai') == 'CO_NGUON' and r.get('url'):
            cu['nguon'] = r['url']
            cu['ghi_chu'] = (cu['ghi_chu'] + ' Vòng 3 tìm được nguồn, thông số chưa rút.').strip()
        else:
            # Ghi chu trung thuc cua vong 3 la KET QUA, khong phai loi. No noi ro
            # da tim o dau, thieu gi, nguoi can lam gi.
            cu['ghi_chu'] = (cu['ghi_chu'] + ' ' + r.get('ghi_chu', '')).strip()
        cu['trang_thai'] = 'REVIEW'
        theo_ma[r['ma']] = cu
    return theo_ma


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, required=True, help='File goc, KHONG bi ghi de.')
    parser.add_argument('--job', type=Path, required=True, help='Thu muc job chua ket qua cac vong.')
    parser.add_argument('--out', type=Path, required=True, help='File Excel de giao.')
    parser.add_argument('--sheet', help='Ten sheet trong file goc. Mac dinh sheet dau.')
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit('khong thay %s' % args.input)
    codes = args.job / 'codes.json'
    if not codes.exists():
        raise SystemExit('khong thay %s - chay run.py truoc' % codes)

    import openpyxl
    theo_ma = gom(args.job)
    if not theo_ma:
        raise SystemExit('khong vong nao co ket qua trong %s - dung lai thay vi giao file rong.'
                         % args.job)

    # Dong nao trong file goc ung voi ma nao: lay tu codes.json, khong do lai.
    dong_cua_ma: dict[int, str] = {}
    for muc in json.loads(codes.read_text(encoding='utf-8')):
        for so_dong in muc.get('dong', []):
            dong_cua_ma[so_dong] = muc['ma_goc']

    wb = openpyxl.load_workbook(args.input)
    ws = wb[args.sheet] if args.sheet else wb[wb.sheetnames[0]]

    # Them cot moi vao ben phai cot cuoi cung dang co.
    cot_dau = ws.max_column + 2
    dong_header = min(dong_cua_ma) - 1 if dong_cua_ma else 1
    for i, ten_cot in enumerate(COT_MOI):
        ws.cell(row=dong_header, column=cot_dau + i, value=ten_cot)

    da_ghi = theo_trang_thai = {'OK': 0, 'REVIEW': 0, 'THIEU': 0}
    for so_dong, ma in sorted(dong_cua_ma.items()):
        ket = theo_ma.get(ma)
        if not ket:
            trang_thai, ghi_chu = 'THIEU', 'Chưa vòng nào xử lý mã này.'
            ten = thong_so = nguon = ''
        else:
            ten = ket['ten']
            thong_so = ' | '.join('%s: %s' % (k, v) for k, v in ket['thong_so'].items())
            nguon, trang_thai = ket['nguon'], ket['trang_thai']
            ghi_chu = ket['ghi_chu']
            # Khong co thong so ma van danh OK la noi qua: OK phai nghia la du
            # ban giao. Thieu thong so thi la REVIEW, kem ly do.
            if not thong_so:
                trang_thai = 'REVIEW'
                ghi_chu = (ghi_chu + ' Chưa tìm được thông số — cần người tự điền.').strip()
        for i, gia_tri in enumerate((ten, thong_so, nguon, trang_thai, ghi_chu)):
            ws.cell(row=so_dong, column=cot_dau + i, value=gia_tri)
        theo_trang_thai[trang_thai] = theo_trang_thai.get(trang_thai, 0) + 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)

    tong = sum(theo_trang_thai.values())
    print('dong da ghi      %5d' % tong)
    for trang_thai, n in sorted(theo_trang_thai.items()):
        print('  %-8s       %5d' % (trang_thai, n))
    print('file goc KHONG bi ghi de: %s' % args.input)
    print('da ghi %s' % args.out)

    if not tong:
        raise SystemExit('khong ghi duoc dong nao - dung lai thay vi giao file rong.')


if __name__ == '__main__':
    main()
