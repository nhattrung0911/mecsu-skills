# -*- coding: utf-8 -*-
"""Cham diem hold-out: so gia tri skill dien vao voi DAP AN THAT da bi xoa.

    python tools/cham_holdout.py --ket-qua <file_chuanhoa.xlsx> \\
        --dap-an jobs/mau-100-holdout.dap_an.json

Vi sao la script chu khong phai nguoi/agent doc bang mat: con so do chinh xac phai
SINH LAI DUOC tu artifact tren dia. Agent tu cham roi tu bao "khop 80%" la con so
khong ai kiem duoc - dung loai so bi cam trong CLAUDE.md muc 6.

Bon muc, khong gop thanh mot ty le duy nhat:
  y_nguyen   chuoi giong het sau khi chuan hoa khoang trang
  cung_so_do measure() ra cung (so, don vi) nhung cach viet khac  -> van dung
  khac       cung khoa nhung gia tri khac han                    -> SAI
  de_trong   khoa co trong dap an nhung skill khong dien

Gop 4 muc thanh 1 se che mat chuyen skill viet "2.5mm" thay vi "2.5 mm" - do la
loi dinh dang, khac han loi tra sai so.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import openpyxl

if hasattr(sys.stdout, 'reconfigure'):      # console Windows mac dinh la cp1252
    sys.stdout.reconfigure(encoding='utf-8')

SEP = re.compile(r'\s*\|\s*')
COT_DIEN = ('Filter bo sung (key: value)', 'E chuan hoa (day du)')


def nap_measure():
    """Dung chinh measure() cua skill - khong tu viet lai phep so don vi."""
    import importlib.util
    duong_dan = (Path(__file__).resolve().parents[1]
                 / 'skills' / 'mecsu-filter' / 'scripts' / 'verify_values.py')
    spec = importlib.util.spec_from_file_location('vv_cham', duong_dan)
    module = importlib.util.module_from_spec(spec)
    sys.modules['vv_cham'] = module
    spec.loader.exec_module(module)
    return module.measure


def tach_cap(text) -> dict:
    """'A: 1 mm | B: Thep' -> {'A': '1 mm', 'B': 'Thep'}. Khoa trung: giu cai dau."""
    ra = {}
    if text is None:
        return ra
    for phan in SEP.split(str(text)):
        phan = phan.strip()
        if not phan or ':' not in phan:
            continue
        k, _, v = phan.partition(':')
        k, v = k.strip(), v.strip()
        if k and k.upper() != 'N/A':
            ra.setdefault(k, v)
    return ra


def gon(s: str) -> str:
    return ' '.join(str(s).split()).strip().lower()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--ket-qua', type=Path, required=True, help='File xlsx skill dung ra.')
    parser.add_argument('--dap-an', type=Path, required=True)
    parser.add_argument('--vi-du', type=int, default=3, help='In bao nhieu vi du moi muc.')
    args = parser.parse_args()

    for p in (args.ket_qua, args.dap_an):
        if not p.exists():
            raise SystemExit('khong thay %s' % p)

    measure = nap_measure()
    dap_an = json.loads(args.dap_an.read_text(encoding='utf-8'))
    that = dap_an['da_xoa']
    cot_khoa = dap_an.get('khoa_la_cot', 'part_number')

    ws = openpyxl.load_workbook(args.ket_qua, read_only=True, data_only=True).worksheets[0]
    hang = list(ws.iter_rows(values_only=True))
    if not hang:
        raise SystemExit('%s rong' % args.ket_qua)
    hdr = [str(v) if v is not None else '' for v in hang[0]]
    if cot_khoa not in hdr:
        raise SystemExit('%s khong co cot khoa %r. Cot that: %s' % (args.ket_qua, cot_khoa, hdr))
    i_khoa = hdr.index(cot_khoa)
    i_dien = [hdr.index(c) for c in COT_DIEN if c in hdr]
    if not i_dien:
        raise SystemExit('%s khong co cot nao trong %s - khong biet skill dien vao dau'
                         % (args.ket_qua, list(COT_DIEN)))

    theo_ma = {}
    for r in hang[1:]:
        if not any(v is not None for v in r):
            continue
        cap = {}
        for i in i_dien:
            cap.update(tach_cap(r[i]))
        theo_ma[str(r[i_khoa])] = cap

    dem = {'y_nguyen': 0, 'cung_so_do': 0, 'khac': 0, 'de_trong': 0}
    vi_du = {k: [] for k in dem}
    thieu_ma = []

    for ma, chuoi_that in that.items():
        if ma not in theo_ma:
            thieu_ma.append(ma)
            continue
        goc, dien = tach_cap(chuoi_that), theo_ma[ma]
        for khoa, v_that in goc.items():
            v_dien = dien.get(khoa)
            if v_dien is None or not str(v_dien).strip():
                muc = 'de_trong'
            elif gon(v_dien) == gon(v_that):
                muc = 'y_nguyen'
            else:
                a, b = measure(str(v_dien)), measure(str(v_that))
                muc = 'cung_so_do' if (a is not None and a == b) else 'khac'
            dem[muc] += 1
            if len(vi_du[muc]) < args.vi_du:
                vi_du[muc].append((ma, khoa, v_dien, v_that))

    tong = sum(dem.values())
    print('file ket qua : %s' % args.ket_qua)
    print('dap an       : %s  (%d ma bi xoa)' % (args.dap_an, len(that)))
    if thieu_ma:
        print('MA KHONG THAY trong file ket qua: %d  %s' % (len(thieu_ma), thieu_ma[:5]))
    print('tong so CAP key:value phai dien: %d\n' % tong)
    if not tong:
        raise SystemExit('khong cap nao de cham - kiem lai file ket qua co dung cot khong.')
    for muc in ('y_nguyen', 'cung_so_do', 'khac', 'de_trong'):
        print('%-11s %5d  %5.1f%%' % (muc, dem[muc], 100.0 * dem[muc] / tong))
    print('\ndung (y_nguyen + cung_so_do): %d/%d = %.1f%%'
          % (dem['y_nguyen'] + dem['cung_so_do'], tong,
             100.0 * (dem['y_nguyen'] + dem['cung_so_do']) / tong))
    for muc in ('khac', 'de_trong', 'cung_so_do'):
        if vi_du[muc]:
            print('\n-- vi du %s --' % muc)
            for ma, khoa, v_dien, v_that in vi_du[muc]:
                print('  %s | %s\n      skill: %r\n      goc  : %r' % (ma, khoa, v_dien, v_that))


if __name__ == '__main__':
    main()
