# -*- coding: utf-8 -*-
"""Cat N dong tu mot file Excel de chay thu - LAP LAI DUOC theo seed.

    python tools/lay_mau.py --input samples/Handtools-check-cate-filter.xlsx \\
        --rows 100 --seed 0 --out jobs/mau-100.xlsx

Cung seed thi ra dung cung tap dong. Khong the thi hai lan chay thu lay hai tap
khac nhau, va moi so do so sanh giua chung deu vo nghia.

Giu nguyen HEADER va giu nguyen THU TU goc cua cac dong duoc chon: file mau phai
doi chieu duoc bang mat voi file goc.
"""
from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import openpyxl

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--rows', type=int, default=100)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--sheet', default='', help='Ten sheet. Mac dinh sheet dau tien.')
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit('khong thay file: %s' % args.input)
    if args.rows < 1:
        raise SystemExit('--rows phai >= 1')

    nguon = openpyxl.load_workbook(args.input, read_only=True, data_only=True)
    ws = nguon[args.sheet] if args.sheet else nguon.worksheets[0]

    hang = list(ws.iter_rows(values_only=True))
    if not hang:
        raise SystemExit('%s khong co dong nao' % args.input)
    header, du_lieu = hang[0], hang[1:]
    if not du_lieu:
        raise SystemExit('%s chi co header, khong co dong du lieu' % args.input)

    if args.rows >= len(du_lieu):
        chon = list(range(len(du_lieu)))            # xin nhieu hon co that -> lay het
    else:
        chon = sorted(random.Random(args.seed).sample(range(len(du_lieu)), args.rows))

    ra = openpyxl.Workbook()
    dich = ra.active
    dich.title = ws.title[:31]
    dich.append(list(header))
    for i in chon:
        dich.append(list(du_lieu[i]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ra.save(args.out)

    print('nguon      %s  (%d dong du lieu)' % (args.input, len(du_lieu)))
    print('seed       %d' % args.seed)
    print('da ghi     %s  (%d dong)' % (args.out, len(chon)))
    print('dong dau   %s' % (du_lieu[chon[0]][:3],))
    print('dong cuoi  %s' % (du_lieu[chon[-1]][:3],))


if __name__ == '__main__':
    main()
