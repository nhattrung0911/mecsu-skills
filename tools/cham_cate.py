# -*- coding: utf-8 -*-
"""Cham diem soat danh muc: so changelog voi danh sach da GAN SAI co chu dich.

    python tools/cham_cate.py --changelog <..._changelog.xlsx> \\
        --dap-an jobs/mau-cate-100.dap_an.json --tong-dong 102

Do HAI mat, khong mot mat:
  bat_dung     bao nhieu dong gan sai bi bat  (thieu mat nay -> skill bo sot)
  bao_dong_gia bao nhieu dong CON NGUYEN bi bao (thieu mat nay -> skill bao bua)

Chi do mat dau thi mot skill bao sai CA FILE cung dat 100%. Con so tren tai lieu
phai sinh lai duoc tu artifact, nen phep cham phai la script chu khong phai loi ke.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import openpyxl

if hasattr(sys.stdout, 'reconfigure'):      # console Windows mac dinh la cp1252
    sys.stdout.reconfigure(encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--changelog', type=Path, required=True)
    parser.add_argument('--dap-an', type=Path, required=True)
    parser.add_argument('--tong-dong', type=int, required=True,
                        help='Tong so dong du lieu cua file dau vao, de tinh bao dong gia.')
    args = parser.parse_args()

    for p in (args.changelog, args.dap_an):
        if not p.exists():
            raise SystemExit('khong thay %s' % p)

    dap_an = json.loads(args.dap_an.read_text(encoding='utf-8'))
    da_doi = dap_an.get('da_doi')
    if not da_doi:
        raise SystemExit('%s khong co muc "da_doi" - day la dap an cua kieu xoa o, '
                         'khong phai kieu gan sai danh muc' % args.dap_an)
    cot_khoa = dap_an.get('khoa_la_cot', 'part_number')

    ws = openpyxl.load_workbook(args.changelog, read_only=True, data_only=True).worksheets[0]
    hang = list(ws.iter_rows(values_only=True))
    if not hang:
        raise SystemExit('%s rong' % args.changelog)
    hdr = [str(v) if v is not None else '' for v in hang[0]]
    for can in (cot_khoa, 'new_leaf_name'):
        if can not in hdr:
            raise SystemExit('%s thieu cot %r. Cot that: %s' % (args.changelog, can, hdr))
    i_ma, i_moi = hdr.index(cot_khoa), hdr.index('new_leaf_name')

    bao = {}
    for r in hang[1:]:
        if any(v is not None for v in r):
            bao[str(r[i_ma])] = str(r[i_moi] or '').strip()

    gan_sai = set(da_doi)
    bat_dung = gan_sai & set(bao)
    bao_dong_gia = set(bao) - gan_sai
    con_nguyen = args.tong_dong - len(gan_sai)
    tra_dung_goc = sum(1 for ma in bat_dung if bao[ma] == str(da_doi[ma]['goc']).strip())

    print('changelog     : %s  (%d dong)' % (args.changelog, len(bao)))
    print('dap an        : %s  (%d dong gan sai)' % (args.dap_an, len(gan_sai)))
    print('tong dong vao : %d  -> %d dong con nguyen\n' % (args.tong_dong, con_nguyen))
    print('bat dung        %3d/%-3d  %5.1f%%' % (len(bat_dung), len(gan_sai),
                                                 100.0 * len(bat_dung) / len(gan_sai)))
    print('bao dong gia    %3d/%-3d  %5.1f%%' % (len(bao_dong_gia), con_nguyen,
                                                 100.0 * len(bao_dong_gia) / max(con_nguyen, 1)))
    print('de xuat dung goc %3d/%-3d' % (tra_dung_goc, len(bat_dung)))

    bo_sot = sorted(gan_sai - set(bao))
    if bo_sot:
        print('\nBO SOT (%d): %s' % (len(bo_sot), bo_sot[:8]))
    if bao_dong_gia:
        print('\nBAO DONG GIA (%d): %s' % (len(bao_dong_gia), sorted(bao_dong_gia)[:8]))
    sai_goc = [ma for ma in sorted(bat_dung) if bao[ma] != str(da_doi[ma]['goc']).strip()]
    if sai_goc:
        print('\nBAT DUNG NHUNG DE XUAT SAI (%d):' % len(sai_goc))
        for ma in sai_goc[:5]:
            print('  %s: de xuat %r, goc %r' % (ma, bao[ma], da_doi[ma]['goc']))


if __name__ == '__main__':
    main()
