# -*- coding: utf-8 -*-
"""Vong 2, buoc cuoi: rut thong so tu trang da tai, roi DOI CHIEU NGUOC.

    python extract_from_web.py --sources-dir web --search search.json \\
        --convention convention.json --out web_facts.json

Model doc text da tai ve va de xuat thong so + ten. Sau do SCRIPT kiem lai, 0 token:
moi gia tri phai CO MAT trong chinh text nguon. Khong co mat thi REVIEW, khong ghi
vao ket qua nhu that.

Do 2026-08-31: hoi model ma tran sau lan ra sau san pham khac nhau, kem URL bia va
`confidence: 1.0`. Vi vay do tin cua model khong duoc dung lam can cu - chi text
nguon moi la can cu.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_env                                              # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BO_THE = re.compile(r'<(script|style)[^>]*>.*?</\1>', re.S | re.I)
THE = re.compile(r'<[^>]+>')
SO = re.compile(r'\d[\d.,]*')

HE_THONG = (
    'Bạn rút thông số kỹ thuật của sản phẩm công nghiệp từ một trang web. '
    'Bạn CHỈ được dùng thông tin có trong đoạn text được cung cấp. '
    'Không suy đoán, không bổ sung kiến thức bên ngoài, không bịa số. '
    'Không thấy thì để trống. Viết tiếng Việt có dấu.'
)

MAU = '''Công thức đặt tên của khách hàng (đã chốt):
  {cong_thuc}

Với mỗi sản phẩm dưới đây, đọc đoạn text lấy từ trang web của nó và trả về JSON:

{{"ket_qua": [{{
  "ma": "mã y nguyên như đề bài",
  "ten_de_xuat": "tên theo đúng công thức trên, CHỨA ĐÚNG mã gốc",
  "thong_so": {{"nhãn": "giá trị kèm đơn vị"}},
  "khong_thay": ["thông tin bạn tìm mà text không có"]
}}]}}

Chỉ lấy thông số THỰC SỰ có trong text. Text là trang bán hàng thì thường chỉ có
vài thông số, đó là bình thường — để trống phần còn lại.

BẮT BUỘC: nếu text nguồn viết bằng tiếng nước ngoài và bạn dịch sang tiếng Việt,
hãy kèm NGUYÊN VĂN trong ngoặc đơn. Ví dụ: "Gốc dầu (油性)", "Nhựa (樹脂)".
Có một bước kiểm tra tự động đối chiếu giá trị bạn đưa ra với chính text nguồn;
bản dịch không kèm nguyên văn sẽ không đối chiếu được và bị đánh dấu cần soát tay.

Chỉ trả JSON.

SẢN PHẨM:
{du_lieu}'''


def chu(trang: str) -> str:
    trang = BO_THE.sub(' ', trang)
    return re.sub(r'\s+', ' ', html.unescape(THE.sub(' ', trang))).strip()


def don(text: str) -> str:
    """Bo dau tieng Viet, bo ky tu ngan cach, GIU chu cua moi he chu viet.

    Loc bang [^a-z0-9] se xoa sach chu Nhat/Trung: `油性` thanh chuoi rong, roi
    moi gia tri co chu Nhat deu bi bac oan du no nam ngay trong text nguon.
    Da xay ra 2026-09-11 voi ba ma SHOSEKIDO.
    """
    khong_dau = ''.join(c for c in unicodedata.normalize('NFD', text)
                        if unicodedata.category(c) != 'Mn')
    return ''.join(c for c in khong_dau.lower() if c.isalnum())


NGOAC = re.compile(r'[（(]([^）)]+)[）)]')


def co_trong_nguon(gia_tri: str, nguon_don: str) -> bool:
    """Gia tri phai NEO duoc vao text nguon. Cho phep model dich.

    Hai luat:
      - Co con so thi MOI con so phai co mat. Viet lai don vi (`180mm` -> `180 mm`)
        la chuyen thuong; bia ra con so 180 thi khong.
      - Khong co so thi it nhat MOT manh cua gia tri phai co mat. Model hay dich
        roi kem nguyen van: `Gốc dầu (油性)`. Phan dich khong nam trong trang tieng
        Nhat, nhung `油性` thi co - va do la bang chung that. So ca cum thi bac oan.
    """
    gia_tri = gia_tri or ''
    cac_so = SO.findall(gia_tri)
    if cac_so:
        return all(don(s) in nguon_don for s in cac_so)

    manh = NGOAC.findall(gia_tri) + [NGOAC.sub(' ', gia_tri)]
    manh += re.split(r'[/,;·]', NGOAC.sub(' ', gia_tri))
    for m in manh:
        khoa = don(m)
        if len(khoa) >= 2 and khoa in nguon_don:
            return True
    return False


def doc_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0]
    dau, cuoi = text.find('{'), text.rfind('}')
    if dau < 0 or cuoi < dau:
        raise ValueError('khong tim thay JSON trong tra loi')
    return json.loads(text[dau:cuoi + 1])


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
    parser.add_argument('--sources-dir', type=Path, required=True)
    parser.add_argument('--search', type=Path, required=True)
    parser.add_argument('--convention', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--batch', type=int, default=10)
    parser.add_argument('--dai-text', type=int, default=3000,
                        help='Cat text moi trang con bao nhieu ky tu truoc khi gui model.')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    chi_muc_file = args.sources_dir / 'index.json'
    for duong_dan in (chi_muc_file, args.search, args.convention):
        if not duong_dan.exists():
            raise SystemExit('khong thay %s' % duong_dan)

    chi_muc = json.loads(chi_muc_file.read_text(encoding='utf-8'))
    tim = {r['ma_goc']: r for r in json.loads(args.search.read_text(encoding='utf-8'))}
    quy_uoc = json.loads(args.convention.read_text(encoding='utf-8'))
    # Chuan Mecsu di kem skill - khong bat job nao phai chot lai.
    cong_thuc = (quy_uoc.get('_quyet_dinh_cua_nguoi', {}).get('cong_thuc_chuan')
                 or '{Loại sản phẩm} {Đặc trưng} {Thông số quan trọng để khách lựa chọn} '
                    '{Hãng} {Mã}')

    muc_tieu = []
    for ma, muc in chi_muc.items():
        if not muc.get('file'):
            continue
        duong_dan = args.sources_dir / muc['file']
        if not duong_dan.exists():
            continue
        text = doc_cache(duong_dan)
        muc_tieu.append({'ma': ma, 'url': muc['url'], 'text': text,
                         'ten_file': tim.get(ma, {}).get('ten_file', '')})

    so_lo = (len(muc_tieu) + args.batch - 1) // args.batch
    print('trang da tai      %5d  -> %d lan goi (batch %d)' % (len(muc_tieu), so_lo, args.batch))
    print('khong tai duoc    %5d  -> viec cua vong 3'
          % sum(1 for m in chi_muc.values() if not m.get('file')))
    if args.dry_run:
        print('\n--dry-run: khong goi model.')
        return
    if not muc_tieu:
        raise SystemExit('khong trang nao doc duoc - dung lai.')

    cau_hinh = skill_env.doc_env()
    skill_env.phai_co_key(cau_hinh)

    theo_ma: dict[str, dict] = {}
    for i in range(0, len(muc_tieu), args.batch):
        lo = muc_tieu[i:i + args.batch]
        print('  lo %d/%d...' % (i // args.batch + 1, so_lo), flush=True)
        du_lieu = '\n\n'.join(
            '- mã: %s\n  tên trong file: %s\n  text từ %s:\n  %s'
            % (m['ma'], m['ten_file'], m['url'], m['text'][:args.dai_text]) for m in lo)
        goi = doc_json(skill_env.hoi(cau_hinh, MAU.format(
            cong_thuc=cong_thuc, du_lieu=du_lieu), HE_THONG))
        for r in goi.get('ket_qua', []):
            theo_ma[str(r.get('ma', '')).strip()] = r

    ket_qua = []
    for m in muc_tieu:
        r = theo_ma.get(m['ma'], {})
        # Can cu = text trang web CONG voi chinh du lieu san co trong file cua khach.
        # Chi doi chieu voi trang web thi bac oan: mau `Trang` cua S23050 nam ngay
        # trong ten file (`... mau trang SHOSEKIDO S23050`), con trang web la tieng
        # Nhat nen khong he co chu do.
        nguon_don = don(m['text'] + ' ' + m['ten_file'])
        thong_so, bac_bo = {}, {}
        for nhan, gia_tri in (r.get('thong_so') or {}).items():
            if co_trong_nguon(str(gia_tri), nguon_don):
                thong_so[nhan] = gia_tri
            else:
                bac_bo[nhan] = gia_tri

        ten = r.get('ten_de_xuat', '')
        ma_dung = bool(m['ma']) and m['ma'] in ten
        if bac_bo or not ma_dung or not thong_so:
            trang_thai = 'REVIEW'
        else:
            trang_thai = 'OK'

        ghi_chu = []
        if bac_bo:
            ghi_chu.append('%d giá trị model đưa ra KHÔNG có trong text nguồn: %s'
                           % (len(bac_bo), ', '.join(bac_bo)))
        if not ma_dung:
            ghi_chu.append('Tên đề xuất không chứa đúng mã gốc %r.' % m['ma'])
        if not thong_so:
            ghi_chu.append('Trang không cho thông số nào dùng được — cần vòng 3 hoặc người tự điền.')

        ket_qua.append({'ma': m['ma'], 'url': m['url'], 'ten_de_xuat': ten,
                        'thong_so': thong_so, 'bi_bac_bo': bac_bo,
                        'khong_thay': r.get('khong_thay', []),
                        'trang_thai': trang_thai, 'ghi_chu': ' '.join(ghi_chu)})

    ok = sum(1 for r in ket_qua if r['trang_thai'] == 'OK')
    tong_bac_bo = sum(len(r['bi_bac_bo']) for r in ket_qua)
    print('\nOK            %5d' % ok)
    print('REVIEW        %5d' % (len(ket_qua) - ok))
    print('gia tri bi bac bo %3d  (model dua ra nhung text nguon khong co)' % tong_bac_bo)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding='utf-8')
    print('da ghi %s' % args.out)

    if muc_tieu and not ket_qua:
        raise SystemExit('goi model xong nhung khong muc nao co ket qua - dung lai.')


if __name__ == '__main__':
    main()
