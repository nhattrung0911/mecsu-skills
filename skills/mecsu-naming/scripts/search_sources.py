# -*- coding: utf-8 -*-
"""Vong 2, buoc 1: tim URL cho san pham CHUA CO thong so. 0 token model.

    python search_sources.py --codes codes.json --out search.json
    python search_sources.py --codes codes.json --out search.json --limit 3   # thu truoc

Truy van TRAN sinh nhieu: do 2026-09-10, `"SATA 47601 specification"` tra hit dau
la Wikipedia ve chuan o cung SATA - ten hang dung ten chuan may tinh. Vi vay truy
van luon kem NGU CANH NGANH lay tu chinh ten san pham trong file.

Ket qua duoc LOC truoc khi di tiep: trang khong nhac toi ma thi khong phai trang
cua san pham do. Loc o tang 0 token re hon loc o tang model.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


def bo_dau(text: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                   if unicodedata.category(c) != 'Mn')


def don(text: str) -> str:
    """Ve dang so sanh duoc: bo dau, bo ky tu ngan cach, thuong hoa.

    `PM-10BLA` va `PM 10BLA` va `pm10bla` phai coi la mot - trang web viet ma
    moi noi mot kieu.
    """
    return re.sub(r'[^a-z0-9]+', '', bo_dau(text).lower())


def truy_van(muc: dict) -> str:
    """Ma + ngu canh nganh lay tu chinh ten trong file.

    Chi mot minh ma thi cong cu tim kiem tra ve bat cu thu gi trung chuoi do.
    """
    ten = str(muc.get('ten_file', '')).strip()
    ma = muc['ma_goc']
    # Bo phan ma nam trong ten de khong lap, giu phan mo ta loai + hang.
    ngu_canh = re.sub(re.escape(ma), '', ten, flags=re.IGNORECASE).strip()
    ngu_canh = re.sub(r'\s{2,}', ' ', ngu_canh)
    return ('%s %s' % (ma, ngu_canh)).strip() if ngu_canh else ma


def hop_le(ma: str, ket: dict) -> bool:
    """Trang khong nhac toi ma thi khong phai trang cua san pham do."""
    dong = don(str(ket.get('title', '')) + ' ' + str(ket.get('body', '')) + ' '
               + str(ket.get('href', '')))
    return don(ma) in dong


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--codes', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--queries', type=Path,
                        help='queries.json do build_queries.py sinh. Khong co thi ghep chuoi '
                             'may moc - da do 2026-09-11 la keo ve toan trang danh muc.')
    parser.add_argument('--domain-cua-minh', action='append', default=[],
                        help='Domain cua chinh cong ty dang dung skill. Nguon tu day bi danh dau '
                             '`tu_minh` vi no khong phai bang chung doc lap - lay du lieu cua '
                             'minh de xac minh du lieu cua minh la vong tron. Lap lai cho nhieu '
                             'domain.')
    parser.add_argument('--limit', type=int, default=0, help='Chi xu ly N san pham. 0 = tat ca.')
    parser.add_argument('--so-ket-qua', type=int, default=8, help='Lay bao nhieu ket qua moi ma.')
    parser.add_argument('--delay', type=float, default=1.5,
                        help='Nghi giua hai truy van. Ha xuong 0 la de bi chan.')
    parser.add_argument('--dry-run', action='store_true',
                        help='In truy van se dung, KHONG goi tim kiem.')
    args = parser.parse_args()

    if not args.codes.exists():
        raise SystemExit('khong thay %s' % args.codes)
    danh_sach = json.loads(args.codes.read_text(encoding='utf-8'))

    # Chi san pham CHUA CO dong thong so nao - dong da co thi vong 1 lo roi.
    can_tim = [m for m in danh_sach if not m.get('dong_thong_so')]
    if args.limit:
        can_tim = can_tim[:args.limit]

    print('san pham trong file        %5d' % len(danh_sach))
    print('  chua co thong so         %5d  -> can tra web' % len(can_tim))
    if not can_tim:
        raise SystemExit('khong san pham nao thieu thong so - vong 2 khong co viec.')

    if args.dry_run:
        print('\ntruy van se dung:')
        for m in can_tim[:10]:
            print('  %-12s %s' % (m['ma_goc'], truy_van(m)))
        print('\n--dry-run: khong goi tim kiem.')
        return

    try:
        from ddgs import DDGS
    except ImportError:
        raise SystemExit('thieu thu vien ddgs. Chay: pip install -r requirements-dev.txt')

    san_co: dict[str, list] = {}
    if args.queries and args.queries.exists():
        san_co = {r['ma_goc']: r.get('truy_van', [])
                  for r in json.loads(args.queries.read_text(encoding='utf-8'))}

    ket_qua, khong_thay = [], 0
    with DDGS() as ddgs:
        for i, muc in enumerate(can_tim):
            # Thu lan luot cho toi khi co ket qua lien quan. Truy van dau tien
            # khong trung khong co nghia la khong ton tai trang nao.
            danh_sach_cau = san_co.get(muc['ma_goc']) or [truy_van(muc)]
            giu, cau_trung, tong_tho = [], '', 0
            for cau in danh_sach_cau:
                try:
                    tho = list(ddgs.text(cau, max_results=args.so_ket_qua))
                except Exception as loi:                   # mang, chan IP, doi API
                    print('  %-12s LOI TIM KIEM: %s' % (muc['ma_goc'], str(loi)[:60]))
                    tho = []
                tong_tho += len(tho)
                giu = [k for k in tho if hop_le(muc['ma_goc'], k)]
                cau_trung = cau
                if giu:
                    break
                if args.delay:
                    time.sleep(args.delay)

            if not giu:
                khong_thay += 1
            print('  %-12s %d truy van, %d ket qua -> %d lien quan'
                  % (muc['ma_goc'], danh_sach_cau.index(cau_trung) + 1, tong_tho, len(giu)))
            ket_qua.append({
                'ma_goc': muc['ma_goc'], 'ten_file': muc.get('ten_file', ''),
                'truy_van': cau_trung, 'truy_van_da_thu': danh_sach_cau,
                'ung_vien': [{'title': k.get('title', ''), 'url': k.get('href', ''),
                              'trich': str(k.get('body', ''))[:400],
                              'tu_minh': any(d.lower() in str(k.get('href', '')).lower()
                                             for d in args.domain_cua_minh)}
                             for k in giu],
                'so_tho': tong_tho,
            })
            if args.delay and i + 1 < len(can_tim):
                time.sleep(args.delay)

    co_ung_vien = sum(1 for r in ket_qua if r['ung_vien'])
    doc_lap = sum(1 for r in ket_qua if any(not u['tu_minh'] for u in r['ung_vien']))
    print('\nco it nhat 1 nguon lien quan %5d / %d' % (co_ung_vien, len(ket_qua)))
    print('  trong do co nguon DOC LAP  %5d' % doc_lap)
    print('  chi tim thay trang cua minh%5d  -> khong phai bang chung' % (co_ung_vien - doc_lap))
    print('khong tim thay nguon nao     %5d  -> viec cua vong 3' % khong_thay)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding='utf-8')
    print('da ghi %s' % args.out)

    if ket_qua and not co_ung_vien:
        raise SystemExit('khong ma nao tim ra nguon - tim kiem hong hoac bi chan, dung lai.')


if __name__ == '__main__':
    main()
