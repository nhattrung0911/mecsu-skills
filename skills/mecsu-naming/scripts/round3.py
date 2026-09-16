# -*- coding: utf-8 -*-
"""Vong 3: ma kho - tim catalog doc ky hon. Van khong ra thi GHI NOTE trung thuc.

    python round3.py --job jobs/naming-01 --out round3.json

Vao day la nhung ma vong 2 khong xong: tai that bai, hoac tai duoc nhung trang
khong co thong so nao dung duoc.

Khac vong 2 o hai cho:
  - truy van huong vao CATALOG / bang gia / datasheet PDF, khong phai trang ban le
  - doc duoc ca PDF, khong chi HTML

Khong ra thi KHONG bia va cung khong de trong cam lang: model viet mot ghi chu
noi ro da tim o dau, thieu gi, nguoi can lam gi. Do la ket qua trung thuc.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_env                                              # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

UA = 'Mozilla/5.0 (compatible; mecsu-naming/1.0)'
THE = re.compile(r'<[^>]+>')
BO_THE = re.compile(r'<(script|style)[^>]*>.*?</\1>', re.S | re.I)

HE_THONG_HOI = (
    'Bạn tìm tài liệu kỹ thuật của sản phẩm công nghiệp. '
    'Bạn nghĩ truy vấn tìm kiếm, không trả lời thông số. Không bịa.'
)

MAU_HOI = '''Các mã dưới đây KHÔNG tìm được thông số ở vòng tìm kiếm thông thường —
kết quả chỉ ra trang bán lẻ không có số liệu.

Hãy nghĩ 3 truy vấn nhắm vào TÀI LIỆU KỸ THUẬT: catalog tổng hợp của hãng,
bảng giá, datasheet, tờ thông số. Ưu tiên PDF và trang của chính hãng ở nước gốc.

Trả JSON: {{"ket_qua":[{{"ma":"...","truy_van":["...","...","..."]}}]}}
Chỉ trả JSON.

MÃ:
{du_lieu}'''

HE_THONG_GHI = (
    'Bạn viết ghi chú bàn giao cho người phụ trách dữ liệu sản phẩm. '
    'Viết ngắn, cụ thể, tiếng Việt có dấu. Không bịa thông số.'
)

MAU_GHI = '''Các mã dưới đây đã tìm qua nhiều vòng mà vẫn không đủ thông số.

Với mỗi mã, viết một ghi chú cho người phụ trách: đã tìm ở đâu, tìm được gì,
còn thiếu gì, và họ nên làm gì tiếp (hỏi nhà cung cấp, tra catalog giấy, v.v.).

Trả JSON: {{"ket_qua":[{{"ma":"...","ghi_chu":"..."}}]}}
Chỉ trả JSON. Tuyệt đối không đoán thông số.

MÃ:
{du_lieu}'''


def doc_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0]
    dau, cuoi = text.find('{'), text.rfind('}')
    if dau < 0 or cuoi < dau:
        raise ValueError('khong tim thay JSON trong tra loi')
    return json.loads(text[dau:cuoi + 1])


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


def tai(url: str, timeout: int = 40) -> tuple[int, bytes, str]:
    yeu_cau = urllib.request.Request(ma_hoa_url(url), headers={'User-Agent': UA})
    try:
        with urllib.request.urlopen(yeu_cau, timeout=timeout) as tra_loi:
            return tra_loi.status, tra_loi.read(), tra_loi.headers.get('Content-Type', '')
    except urllib.error.HTTPError as loi:
        return loi.code, b'', ''
    except (urllib.error.URLError, TimeoutError, OSError, UnicodeError):
        return 0, b'', ''


def ra_chu(than: bytes, kieu: str, url: str) -> str:
    """PDF thi doc bang pypdf, con lai coi la HTML."""
    if 'pdf' in kieu.lower() or url.lower().endswith('.pdf'):
        try:
            from pypdf import PdfReader
        except ImportError:
            return ''
        try:
            doc = PdfReader(io.BytesIO(than))
            return ' '.join((t.extract_text() or '') for t in doc.pages[:12])
        except Exception:
            return ''
    trang = BO_THE.sub(' ', than.decode('utf-8', 'replace'))
    return re.sub(r'\s+', ' ', THE.sub(' ', trang)).strip()


SO_DO = re.compile(r'\d+(?:[.,]\d+)?\s*(?:mm|cm|kg|g|ml|Nm|W|V|A|inch|"|本)\b', re.I)


def don(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', text.lower())


def dung_duoc(ma: str, url: str, chu: str, toi_thieu: int = 2) -> bool:
    """Trang chi NHAC TOI ma thi chua du - phai la trang CUA no va co so do.

    Do 2026-09-11, hai thanh cong gia:
      - S23052 khop mot trang cua san pham S23055, vi trang catalog liet ke nhieu
        ma nen text co chua ca ma minh tim;
      - PM-10BLU khop mot trang ban le co ten dung nhung KHONG mot so do nao.
    """
    if don(ma) not in don(chu):
        return False
    # Trang cua chinh san pham thuong mang ma trong URL. Khong bat buoc, nhung
    # neu URL mang mot ma KHAC thi gan nhu chac chan la trang cua san pham khac.
    if don(ma) not in don(url):
        return False

    # So do phai nam GAN cho nhac ma. Do 2026-09-11: trang PM-10BLU dat nguong
    # so do chi nho `12v 18v 20v` trong MENU DIEU HUONG cua website (danh muc may
    # pin) - khong lien quan gi toi cay but. So do o dau do tren trang khong phai
    # so do cua san pham nay.
    i = chu.lower().find(ma.lower())
    if i < 0:
        i = don(chu).find(don(ma))
        if i < 0:
            return False
    quanh = chu[max(0, i - 800):i + 1500]
    return len(SO_DO.findall(quanh)) >= toi_thieu


def can_lam(job: Path) -> list[dict]:
    """Ma nao vong 2 chua xong: tai that bai, hoac tai duoc ma khong co thong so."""
    tim = {r['ma_goc']: r for r in json.loads((job / 'search.json').read_text(encoding='utf-8'))} \
        if (job / 'search.json').exists() else {}
    chua = {}
    idx_file = job / 'web' / 'index.json'
    if idx_file.exists():
        for ma, muc in json.loads(idx_file.read_text(encoding='utf-8')).items():
            if not muc.get('file'):
                chua[ma] = 'tải trang không thành công'
    wf = job / 'web_facts.json'
    if wf.exists():
        for r in json.loads(wf.read_text(encoding='utf-8')):
            if not r.get('thong_so'):
                chua[r['ma']] = 'trang tải được nhưng không có thông số nào dùng được'
    return [{'ma': ma, 'ly_do': ly_do, 'ten_file': tim.get(ma, {}).get('ten_file', '')}
            for ma, ly_do in chua.items()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--so-ket-qua', type=int, default=6)
    parser.add_argument('--delay', type=float, default=2.0)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.job.exists():
        raise SystemExit('khong thay %s' % args.job)
    danh_sach = can_lam(args.job)
    print('ma vong 2 chua xong  %5d' % len(danh_sach))
    for m in danh_sach:
        print('   %-14s %s' % (m['ma'], m['ly_do']))
    if not danh_sach:
        raise SystemExit('khong ma nao can vong 3 - vong 2 da xong het.')
    if args.dry_run:
        print('\n--dry-run: khong goi model, khong tim kiem.')
        return

    cau_hinh = skill_env.doc_env()
    skill_env.phai_co_key(cau_hinh)

    du_lieu = '\n'.join('- %s (%s) — tên trong file: %s' % (m['ma'], m['ly_do'], m['ten_file'])
                        for m in danh_sach)
    goi = doc_json(skill_env.hoi(cau_hinh, MAU_HOI.format(du_lieu=du_lieu), HE_THONG_HOI))
    truy_van = {str(r.get('ma', '')).strip(): r.get('truy_van', [])
                for r in goi.get('ket_qua', [])}

    try:
        from ddgs import DDGS
    except ImportError:
        raise SystemExit('thieu thu vien ddgs. Chay: pip install -r requirements-dev.txt')

    thu_muc = args.job / 'catalog'
    thu_muc.mkdir(parents=True, exist_ok=True)
    lay_duoc: dict[str, dict] = {}

    with DDGS() as ddgs:
        for muc in danh_sach:
            for cau in truy_van.get(muc['ma'], [])[:3]:
                try:
                    ket = list(ddgs.text(cau, max_results=args.so_ket_qua))
                except Exception as loi:
                    print('  %-14s LOI TIM: %s' % (muc['ma'], str(loi)[:50]))
                    ket = []
                for k in ket:
                    url = k.get('href', '')
                    ma_http, than, kieu = tai(url)
                    if ma_http != 200 or len(than) < 500:
                        continue
                    chu = ra_chu(than, kieu, url)
                    if not dung_duoc(muc['ma'], url, chu):
                        continue
                    lay_duoc[muc['ma']] = {'url': url, 'text': chu[:4000],
                                           'la_pdf': 'pdf' in kieu.lower()}
                    break
                if muc['ma'] in lay_duoc:
                    break
                if args.delay:
                    time.sleep(args.delay)
            print('  %-14s %s' % (muc['ma'],
                                  'tìm được nguồn' if muc['ma'] in lay_duoc else 'vẫn không ra'))

    con_thieu = [m for m in danh_sach if m['ma'] not in lay_duoc]
    ghi_chu: dict[str, str] = {}
    if con_thieu:
        du = '\n'.join('- %s (%s) — %s' % (m['ma'], m['ly_do'], m['ten_file']) for m in con_thieu)
        g = doc_json(skill_env.hoi(cau_hinh, MAU_GHI.format(du_lieu=du), HE_THONG_GHI))
        ghi_chu = {str(r.get('ma', '')).strip(): r.get('ghi_chu', '')
                   for r in g.get('ket_qua', [])}

    ket_qua = []
    for m in danh_sach:
        nguon = lay_duoc.get(m['ma'])
        ket_qua.append({
            'ma': m['ma'], 'ly_do_vao_vong_3': m['ly_do'],
            'url': (nguon or {}).get('url', ''), 'la_pdf': (nguon or {}).get('la_pdf', False),
            'text': (nguon or {}).get('text', ''),
            'trang_thai': 'CO_NGUON' if nguon else 'KHONG_RA',
            'ghi_chu': ghi_chu.get(m['ma'], ''),
        })

    co = sum(1 for r in ket_qua if r['trang_thai'] == 'CO_NGUON')
    print('\ntìm được nguồn  %5d' % co)
    print('vẫn không ra    %5d  -> đã ghi chú cho người tự xử' % (len(ket_qua) - co))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding='utf-8')
    print('da ghi %s' % args.out)


if __name__ == '__main__':
    main()
