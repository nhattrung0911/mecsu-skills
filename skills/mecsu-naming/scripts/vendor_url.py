# -*- coding: utf-8 -*-
"""Tang 1: dung URL trang hang tu ma. 0 token, khong search.

    python vendor_url.py --codes codes.json --out sources.json
    python vendor_url.py --codes codes.json --check 10      # do that bang HTTP

Buoc DO 2026-09-11 do duoc: 94,2% file thuoc ba hang, va hai trong so do co URL
suy thang tu ma. Search chi con danh cho phan duoi.

Mau URL la GIA DINH VE MOT TRANG WEB BEN NGOAI - no gay bat cu luc nao ma khong
ai bao. `--check` ton tai de phat hien dieu do som, bang HTTP that, 0 token.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Chi ghi vao day mau da KIEM BANG HTTP THAT, kem ngay do.
MAU = {
    # 5/5 ma thu tra 200, trang server-render, so do nam trong HTML tho. Do 2026-09-11.
    'SATA': 'https://www.satatools.com/en/Product/show/{ma}.html',
    # 4/4 ma thu tra 200. Gach ngang BAT BUOC giu: ABRS-2110 -> 200, ABRS2110 -> 404.
    'Anex': 'https://www.anextool.co.jp/item/{ma}/',
    # Bosi KHONG co mau tra thang: bosi.cn gom theo NHOM san pham, mot nhom hang
    # chuc ma. Phai crawl catalogue mot lan dung chi muc - viec cua me sau.
}

UA = 'Mozilla/5.0 (compatible; mecsu-naming/1.0)'

# Duoi nguong nay thi coi nhu mau URL da gay, khong phai vai ma le khong co trang.
NGUONG_GAY = .5


def dung_url(muc: dict) -> str | None:
    mau = MAU.get(muc.get('hang', ''))
    return mau.format(ma=muc['ma_hang']) if mau else None


def thu(url: str, timeout: int = 25) -> int:
    yeu_cau = urllib.request.Request(url, headers={'User-Agent': UA}, method='HEAD')
    try:
        with urllib.request.urlopen(yeu_cau, timeout=timeout) as tra_loi:
            return tra_loi.status
    except urllib.error.HTTPError as loi:
        return loi.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--codes', type=Path, required=True, help='codes.json do extract_codes sinh.')
    parser.add_argument('--out', type=Path, help='Ghi ket qua ra day.')
    parser.add_argument('--check', type=int, default=0,
                        help='Do that N ma bang HTTP de xem mau URL con dung khong.')
    parser.add_argument('--seed', type=int, default=0, help='Seed cho --check, de lap lai duoc.')
    args = parser.parse_args()

    if not args.codes.exists():
        raise SystemExit('khong thay %s' % args.codes)
    danh_sach = json.loads(args.codes.read_text(encoding='utf-8'))
    if not danh_sach:
        raise SystemExit('%s rong - khong co ma nao de xu ly' % args.codes)

    for muc in danh_sach:
        url = dung_url(muc)
        muc['url_hang'] = url
        muc['tang'] = 'trang-hang' if url else 'can-tim-kiem'

    dem = Counter(m['tang'] for m in danh_sach)
    tong = len(danh_sach)
    print('tong ma: %d' % tong)
    for tang, n in dem.most_common():
        print('  %-14s %5d  %5.1f%%' % (tang, n, n / tong * 100))

    if args.check:
        co_url = [m for m in danh_sach if m['url_hang']]
        if not co_url:
            raise SystemExit('khong ma nao dung duoc URL - mau URL hoac du lieu hang co van de')
        random.seed(args.seed)
        mau_thu = random.sample(co_url, min(args.check, len(co_url)))
        print('\ndo that %d ma bang HTTP:' % len(mau_thu))
        truot = []
        for muc in mau_thu:
            ma_http = thu(muc['url_hang'])
            print('  %-14s %-12s HTTP %s' % (muc['hang'], muc['ma_hang'], ma_http or 'khong noi duoc'))
            if ma_http != 200:
                truot.append(muc['ma_hang'])

        ty_le = (len(mau_thu) - len(truot)) / len(mau_thu)
        print('\n%d/%d tra 200 (%.0f%%).' % (len(mau_thu) - len(truot), len(mau_thu), ty_le * 100))

        # Mot ma 404 KHONG phai mau URL gay - no la ma khong co trang rieng, va
        # phai roi xuong tang tim kiem. Do 2026-09-11: SAT-08007ASJ tra 404 trong
        # khi 11 ma con lai tra 200. Chi khi ty le tut han moi la mau da gay.
        if truot:
            print('Khong co trang rieng, se roi xuong tang tim kiem: %s' % ', '.join(truot))
        if ty_le < NGUONG_GAY:
            print('\nTy le duoi %.0f%% - mau URL cua trang hang co the da doi. Kiem tay truoc khi chay tiep.'
                  % (NGUONG_GAY * 100))
            raise SystemExit(1)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(danh_sach, ensure_ascii=False, indent=2), encoding='utf-8')
        print('da ghi %s' % args.out)


if __name__ == '__main__':
    main()
