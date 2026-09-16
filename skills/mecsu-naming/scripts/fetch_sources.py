# -*- coding: utf-8 -*-
"""B3: tai trang hang ve dia, co cache. 0 token model.

    python fetch_sources.py --sources sources.json --out-dir jobs/naming-01/sources --limit 20
    python fetch_sources.py --sources sources.json --out-dir ... --limit 0     # tai het

Cache khoa bang HASH CUA URL, khong phai so thu tu: input doi thi so thu tu bi
danh lai va ket qua cu gan nham sang ma khac - da hong hai lan trong repo nay.

Cache nam trong thu muc job tren dia, KHONG duoc de duoi tmp_path cua pytest:
pytest.ini chot --basetemp=.pytest_tmp va pytest xoa sach thu muc do moi lan chay,
nen ty le cache-hit se luon do ra 0 va trong nhu cache hong.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

UA = 'Mozilla/5.0 (compatible; mecsu-naming/1.0)'
NHO_NHAT = 500          # byte; trang that deu lon hon nhieu, nho hon la trang loi


BO_THE = re.compile(r'<(script|style)[^>]*>.*?</\1>', re.S | re.I)
THE = re.compile(r'<[^>]+>')


def ten_cache(url: str, dang: str = 'text') -> str:
    """Ten file theo hash noi dung URL - on dinh qua moi lan chay, moi thu tu."""
    duoi = '.txt.gz' if dang == 'text' else '.html.gz'
    return hashlib.sha256(url.encode('utf-8')).hexdigest()[:16] + duoi


def loc_chu(than: bytes) -> bytes:
    """Bo the, giu chu. Do tren 8 trang that 2026-09-11: text con 4,1% HTML tho."""
    trang = than.decode('utf-8', 'replace')
    trang = BO_THE.sub(' ', trang)
    return re.sub(r'\s+', ' ', html.unescape(THE.sub(' ', trang))).strip().encode('utf-8')


def doc_cache(duong_dan: Path) -> str:
    """Doc file cache, tu nhan biet co nen hay khong."""
    if duong_dan.suffix == '.gz':
        return gzip.decompress(duong_dan.read_bytes()).decode('utf-8', 'replace')
    return duong_dan.read_text(encoding='utf-8', errors='replace')


def ma_hoa_url(url: str) -> str:
    """Ma hoa phan khong-ASCII cua URL.

    Do 2026-09-11: `urllib` nem UnicodeEncodeError khi URL co chu co dau - no
    encode request bang ascii. Day la CRASH giua chung, khong phai that bai em,
    nen ca lo dang chay bi mat.
    """
    tach = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((
        tach.scheme, tach.netloc.encode('idna').decode('ascii') if tach.netloc else '',
        urllib.parse.quote(tach.path, safe="/%:@&=+$,~"),
        urllib.parse.quote(tach.query, safe="/%:@&=+$,~?"), ''))


def tai(url: str, timeout: int) -> tuple[int, bytes]:
    yeu_cau = urllib.request.Request(ma_hoa_url(url), headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(yeu_cau, timeout=timeout) as tra_loi:
            return tra_loi.status, tra_loi.read()
    except urllib.error.HTTPError as loi:
        return loi.code, b''
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeError):
        return 0, b''


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--sources', type=Path, required=True, help='sources.json do vendor_url sinh.')
    parser.add_argument('--out-dir', type=Path, required=True, help='Thu muc chua HTML tai ve.')
    parser.add_argument('--limit', type=int, default=20,
                        help='Toi da bao nhieu ma moi lan chay. 0 = tai het.')
    parser.add_argument('--delay', type=float, default=1.0,
                        help='Nghi bao nhieu giay giua hai lan tai. Dung ha xuong 0 khi tai nhieu.')
    parser.add_argument('--timeout', type=int, default=30)
    parser.add_argument('--refetch', action='store_true', help='Tai lai ca nhung ma da co cache.')
    parser.add_argument('--luu', choices=['text', 'html'], default='text',
                        help='text = chi giu chu, nen gzip (mac dinh, ~1%% HTML tho). '
                             'html = giu ca the, nen gzip - can khi buoc sau doc BANG trong trang.')
    args = parser.parse_args()

    if not args.sources.exists():
        raise SystemExit('khong thay %s' % args.sources)
    danh_sach = json.loads(args.sources.read_text(encoding='utf-8'))

    # Nhan ca hai dang: sources.json (vendor_url.py, co `url_hang`) va search.json
    # (search_sources.py, co danh sach `ung_vien`). Uu tien nguon DOC LAP: trang
    # cua chinh cong ty khong xac minh duoc du lieu cua chinh cong ty do.
    for muc in danh_sach:
        if muc.get('url_hang') or not muc.get('ung_vien'):
            continue
        doc_lap = [u for u in muc['ung_vien'] if not u.get('tu_minh')]
        chon = (doc_lap or muc['ung_vien'])[0]
        muc['url_hang'] = chon.get('url')
        muc['nguon_tu_minh'] = not doc_lap

    can_tai = [m for m in danh_sach if m.get('url_hang')]
    if not can_tai:
        raise SystemExit('khong ma nao co url_hang - chay vendor_url.py truoc')

    args.out_dir.mkdir(parents=True, exist_ok=True)
    chi_muc_file = args.out_dir / 'index.json'
    chi_muc = json.loads(chi_muc_file.read_text(encoding='utf-8')) if chi_muc_file.exists() else {}

    hang_doi = can_tai if args.limit == 0 else can_tai[:args.limit]
    tu_cache = tai_moi = that_bai = 0
    lan_dau = True

    for muc in hang_doi:
        url = muc['url_hang']
        duong_dan = args.out_dir / ten_cache(url, args.luu)

        if duong_dan.exists() and duong_dan.stat().st_size >= NHO_NHAT and not args.refetch:
            tu_cache += 1
            continue

        if not lan_dau and args.delay:
            time.sleep(args.delay)
        lan_dau = False

        ma_http, than = tai(url, args.timeout)
        if ma_http == 200 and len(than) >= NHO_NHAT:
            noi_dung = loc_chu(than) if args.luu == 'text' else than
            duong_dan.write_bytes(gzip.compress(noi_dung, 6))
            chi_muc[muc['ma_goc']] = {'url': url, 'file': duong_dan.name, 'dang': args.luu,
                                      'byte': len(than), 'byte_luu': duong_dan.stat().st_size,
                                      'http': ma_http}
            tai_moi += 1
        else:
            chi_muc[muc['ma_goc']] = {'url': url, 'file': None, 'byte': len(than), 'http': ma_http}
            that_bai += 1

    chi_muc_file.write_text(json.dumps(chi_muc, ensure_ascii=False, indent=2), encoding='utf-8')

    print('hang doi: %d / %d ma co url' % (len(hang_doi), len(can_tai)))
    print('  tu cache      %5d' % tu_cache)
    print('  tai moi       %5d' % tai_moi)
    print('  khong lay duoc%5d' % that_bai)
    print('da ghi %s' % chi_muc_file)

    # Ca hang doi that bai la hong that: mang, chan IP, hoac mau URL da doi.
    if hang_doi and tu_cache + tai_moi == 0:
        raise SystemExit('khong tai duoc ma nao - dung lai thay vi bao xong.')


if __name__ == '__main__':
    main()
