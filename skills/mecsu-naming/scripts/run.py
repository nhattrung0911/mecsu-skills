# -*- coding: utf-8 -*-
"""Chay ca day theo VONG, DONG BO. Buoc nao thoat khac 0 thi dung han.

    python run.py --input <file.xlsx> --job jobs/naming-01              # den vong 0
    python run.py --input <file.xlsx> --job jobs/naming-01 --den-vong 1 # ap quy uoc

  vong 0  hoc quy uoc dat ten tu chinh file        -> convention.json
          NGUOI SOAT convention.json, chot cong thuc, roi moi chay tiep
  vong 1  ap quy uoc cho dong DA CO thong tin      -> names.json
  vong 2  dong chi co ma: tra web tim thong so     (chua cai dat)
  vong 3  ma kho: tim catalog, doc ca PDF          -> round3.json

Buoc DO 2026-09-11 (Đ1): mot agent duoc giao 15 ma da tu che thanh ba nhom chay
song song, roi ket thuc luot TRUOC khi thu ket qua, va bao mot bang rong nhu the
da xong. Vi vay day chuyen nay chay tuan tu trong MOT tien trinh, khong giao viec
dieu phoi cho ai, va kiem NOI DUNG file buoc truoc sinh ra chu khong kiem su ton tai.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

O_DAY = Path(__file__).resolve().parent


def buoc(ten: str, *co) -> None:
    print('\n=== %s ===' % ten, flush=True)
    xong = subprocess.run([sys.executable, *co])
    # Thoat 4 = che do agent dang cho cau tra loi. Van dung ca day (di tiep voi du lieu
    # thieu moi la hong) nhung noi dung khac han. 3 la 'dung cho NGUOI soat'.
    if xong.returncode == 4:
        print('%s dang cho agent tra loi. Dien xong chay lai dung lenh nay.' % ten)
        raise SystemExit(4)
    if xong.returncode != 0:
        raise SystemExit('%s thoat %d - dung ca day.' % (ten, xong.returncode))


def phai_co_noi_dung(duong_dan: Path, ten: str):
    """Kiem NOI DUNG, khong kiem su ton tai: file rong cung la that bai."""
    if not duong_dan.exists():
        raise SystemExit('%s khong sinh ra %s' % (ten, duong_dan))
    try:
        noi_dung = json.loads(duong_dan.read_text(encoding='utf-8'))
    except json.JSONDecodeError as loi:
        raise SystemExit('%s sinh ra %s khong doc duoc: %s' % (ten, duong_dan, loi))
    if not noi_dung:
        raise SystemExit('%s sinh ra %s nhung rong' % (ten, duong_dan))
    return noi_dung


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, required=True, help='File Excel hoac CSV can xu ly.')
    parser.add_argument('--job', type=Path, required=True, help='Thu muc chua ket qua lan chay nay.')
    parser.add_argument('--den-vong', type=int, default=0, choices=[0, 1, 2, 3],
                        help='Chay den vong nao. Mac dinh 0: chi hoc quy uoc roi dung.')
    parser.add_argument('--domain-cua-minh', action='append', default=[],
                        help='Domain cua chinh cong ty. Nguon tu day khong phai bang chung '
                             'doc lap. Lap lai cho nhieu domain.')
    parser.add_argument('--fetch-limit', type=int, default=0,
                        help='Toi da bao nhieu trang tai moi lan chay o vong 2. 0 = tat ca.')
    parser.add_argument('--out', type=Path,
                        help='File Excel de giao. Mac dinh <job>/ket_qua.xlsx')
    parser.add_argument('--code-col', type=int, help='Chi so cot ma, dem tu 0, neu do khong ra.')
    parser.add_argument('--hoc-lai', action='store_true',
                        help='Hoc lai quy uoc du convention.json da co.')
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit('khong thay file: %s' % args.input)
    args.job.mkdir(parents=True, exist_ok=True)
    codes = args.job / 'codes.json'
    quy_uoc = args.job / 'convention.json'
    names = args.job / 'names.json'

    co_b1 = [str(O_DAY / 'extract_codes.py'), '--input', str(args.input), '--out', str(codes)]
    if args.code_col is not None:
        co_b1 += ['--code-col', str(args.code_col)]
    buoc('doc file va do cot ma', *co_b1)
    danh_sach = phai_co_noi_dung(codes, 'doc file')

    co_ten = sum(1 for m in danh_sach if str(m.get('ten_file', '')).strip())
    co_thong_so = sum(1 for m in danh_sach if m.get('dong_thong_so'))
    print('\n%d san pham | %d co ten | %d co dong thong so'
          % (len(danh_sach), co_ten, co_thong_so))

    if quy_uoc.exists() and not args.hoc_lai:
        print('\n=== vong 0 bo qua: da co %s ===' % quy_uoc)
        print('Muon hoc lai thi them --hoc-lai.')
    else:
        buoc('vong 0: hoc quy uoc dat ten tu chinh file',
             str(O_DAY / 'learn_convention.py'), '--codes', str(codes), '--out', str(quy_uoc))

    da_hoc = phai_co_noi_dung(quy_uoc, 'vong 0')
    chot = da_hoc.get('_quyet_dinh_cua_nguoi', {}).get('cong_thuc_chuan', '')

    if args.den_vong < 1:
        print('\n=== dung sau vong 0 ===')
        print('SOAT %s truoc khi ap cho ca file:' % quy_uoc)
        print('  - cong thuc rut ra co dung y ban khong')
        print('  - muc "diem_khong_nhat_quan": %d cho file dang tu mau thuan'
              % len(da_hoc.get('diem_khong_nhat_quan', [])))
        print('  - dien "_quyet_dinh_cua_nguoi.cong_thuc_chuan" %s'
              % ('(da co)' if chot else '(CHUA CO - bat buoc)'))
        print('\nXong thi chay lai kem --den-vong 1.')
        raise SystemExit(3)

    if not chot:
        print('\nKhong co quyet dinh rieng cho job nay -> dung chuan Mecsu co san trong skill.')

    buoc('vong 1: ap quy uoc cho dong da co thong tin',
         str(O_DAY / 'apply_convention.py'), '--codes', str(codes),
         '--convention', str(quy_uoc), '--out', str(names))
    ket_qua = phai_co_noi_dung(names, 'vong 1')

    can_soat = [r for r in ket_qua if r.get('trang_thai') == 'REVIEW']
    thieu_thong_so = [m for m in danh_sach if not m.get('dong_thong_so')]
    print('\n%d ten da chuan hoa, trong do %d dong REVIEW can nguoi soat'
          % (len(ket_qua), len(can_soat)))
    print('%d san pham chua co dong thong so nao -> viec cua vong 2' % len(thieu_thong_so))

    excel = args.out or (args.job / 'ket_qua.xlsx')

    if args.den_vong < 2:
        buoc('dung file Excel de giao', str(O_DAY / 'build_sheet.py'),
             '--input', str(args.input), '--job', str(args.job), '--out', str(excel))
        print('\n=== dung sau vong 1 ===')
        print('%d san pham con thieu thong so. Chay lai kem --den-vong 2 de tra web.'
              % len(thieu_thong_so))
        raise SystemExit(3)

    if not thieu_thong_so:
        print('\nKhong san pham nao thieu thong so - vong 2 khong co viec.')
    else:
        queries = args.job / 'queries.json'
        search = args.job / 'search.json'
        web_dir = args.job / 'web'
        facts = args.job / 'web_facts.json'

        buoc('vong 2a: model nghi truy van tim kiem',
             str(O_DAY / 'build_queries.py'), '--codes', str(codes), '--out', str(queries))
        co_tim = [str(O_DAY / 'search_sources.py'), '--codes', str(codes),
                  '--queries', str(queries), '--out', str(search)]
        for domain in args.domain_cua_minh:
            co_tim += ['--domain-cua-minh', domain]
        buoc('vong 2b: tim nguon tren internet', *co_tim)

        buoc('vong 2c: tai nguon ve dia',
             str(O_DAY / 'fetch_sources.py'), '--sources', str(search),
             '--out-dir', str(web_dir), '--limit', str(args.fetch_limit))
        buoc('vong 2d: rut thong so va doi chieu nguoc',
             str(O_DAY / 'extract_from_web.py'), '--sources-dir', str(web_dir),
             '--search', str(search), '--convention', str(quy_uoc), '--out', str(facts))
        phai_co_noi_dung(facts, 'vong 2d')

    if args.den_vong >= 3:
        # `round3.py` thoat khac 0 khi KHONG co ma nao can vong 3 - do la dung y do,
        # khong phai loi, nen o day khong dung ca day vi chuyen do.
        print('\n=== vong 3: ma kho, tim catalog ===', flush=True)
        xong3 = subprocess.run([sys.executable, str(O_DAY / 'round3.py'),
                                '--job', str(args.job),
                                '--out', str(args.job / 'round3.json')])
        if xong3.returncode not in (0, 1):
            raise SystemExit('vong 3 thoat %d - dung ca day.' % xong3.returncode)

    buoc('dung file Excel de giao', str(O_DAY / 'build_sheet.py'),
         '--input', str(args.input), '--job', str(args.job), '--out', str(excel))

    print('\n=== xong vong %d ===' % args.den_vong)
    print('File giao: %s' % excel)
    print('Dong REVIEW trong file la dong CHUA du bang chung - can nguoi soat, khong phai loi.')
    if args.den_vong < 3:
        raise SystemExit(3)


if __name__ == '__main__':
    main()
