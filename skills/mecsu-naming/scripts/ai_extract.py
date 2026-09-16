# -*- coding: utf-8 -*-
"""B5: tu TEXT DA LAY VE, nho model dat ten tieng Viet va chuan hoa thong so.

    python ai_extract.py --facts facts.json --out ai.json --batch 25

Model KHONG duoc hoi "ma nay la san pham gi". No chi duoc doc doan text da tai ve
tu trang hang va viet lai cho gon. Do 2026-08-31: hoi ma tran sau lan ra sau san
pham khac nhau, kem URL bia va `confidence: 1.0`.

Cache khoa bang HASH NOI DUNG cua tung muc, khong phai so thu tu. Doi thu tu hang
doi thi verdict cu van dinh dung ma - da hong hai lan trong repo nay.

Gop batch la bat buoc: overhead do duoc ~2.4k prompt token moi lan goi, nen hoi
tung dong la tra tien cho overhead nhieu hon cho noi dung.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_env                                              # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Doi bat cu thu gi trong HE_THONG / MAU_PROMPT thi PHAI tang so nay, khong thi
# cache cu van duoc dung va ban sua prompt khong co tac dung nao.
PHIEN_BAN_PROMPT = 2

# Prompt viet CO DAU tieng Viet. Truoc day viet khong dau, va model bat chuoc y
# het: tra ve "Dau Tuyp 6 Canh" trong khi du lieu cua cong ty la "Đầu Tuýp 6 Cạnh".
HE_THONG = (
    'Bạn chuẩn hoá dữ liệu sản phẩm công nghiệp cho một nhà phân phối Việt Nam. '
    'Bạn CHỈ được dùng thông tin có trong đoạn text được cung cấp. '
    'Không suy đoán, không bổ sung kiến thức bên ngoài. '
    'Không chắc thì để trống — ô trống tốt hơn một giá trị sai. '
    'Viết tiếng Việt CÓ DẤU đầy đủ, viết hoa chữ đầu mỗi từ trong tên sản phẩm.'
)

MAU_PROMPT = '''Mỗi mục dưới đây là text lấy từ trang chính hãng của sản phẩm đó.

Với mỗi mục, trả về:
  "ten_viet": tên sản phẩm bằng tiếng Việt CÓ DẤU, theo dạng
              "{{Loại}} {{Kích thước}} {{Hãng}} {{Mã}}" — ví dụ
              "Đầu Tuýp 6 Cạnh 3/8 inch - 11 mm SATA 12306"
  "thong_so": các cặp khoá/giá trị đã chuẩn hoá (đơn vị rõ ràng), LẤY TỪ TEXT
  "bo_trong": danh sách trường bạn không tìm thấy trong text

Chỉ trả về JSON, không giải thích. Dạng:
{{"ket_qua": [{{"id": "...", "ten_viet": "...", "thong_so": {{}}, "bo_trong": []}}]}}

CÁC MỤC:
{muc}'''


def khoa_noi_dung(muc: dict) -> str:
    """Hash cua chinh noi dung nguon. Doi thu tu khong lam doi khoa."""
    loi = json.dumps({'v': PHIEN_BAN_PROMPT, 'ten': muc.get('ten_nguon', ''),
                      'ts': muc.get('thong_so', {})},
                     ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(loi.encode('utf-8')).hexdigest()[:16]


def mo_ta(muc: dict, so: int) -> str:
    thong_so = ' | '.join('%s: %s' % (k, v) for k, v in list(muc.get('thong_so', {}).items())[:14])
    return '[%d] id=%s\n  hang: %s\n  ma: %s\n  ten tren trang: %s\n  thong so tren trang: %s' % (
        so, khoa_noi_dung(muc), muc.get('hang', ''), muc.get('ma_hang', ''),
        muc.get('ten_nguon', ''), thong_so or '(trang khong liet ke)')


def doc_json(text: str) -> dict:
    """Model hay boc JSON trong ```json ... ``` - go ra truoc khi parse."""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1]
        text = text.rsplit('```', 1)[0]
    dau, cuoi = text.find('{'), text.rfind('}')
    if dau < 0 or cuoi < dau:
        raise ValueError('khong tim thay JSON trong tra loi')
    return json.loads(text[dau:cuoi + 1])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--facts', type=Path, required=True, help='facts.json do parse_vendor sinh.')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--cache', type=Path, help='File cache. Mac dinh <out>.cache.json')
    parser.add_argument('--batch', type=int, help='So muc moi lan goi. Mac dinh lay MECSU_BATCH_SIZE.')
    parser.add_argument('--limit', type=int, default=0, help='Chi xu ly N muc dau. 0 = tat ca.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Chi in so lan goi du kien, KHONG goi model.')
    args = parser.parse_args()

    if not args.facts.exists():
        raise SystemExit('khong thay %s' % args.facts)
    danh_sach = json.loads(args.facts.read_text(encoding='utf-8'))
    if not danh_sach:
        raise SystemExit('%s rong' % args.facts)
    if args.limit:
        danh_sach = danh_sach[:args.limit]

    cau_hinh = skill_env.doc_env()
    kich_thuoc = args.batch or int(cau_hinh.get('MECSU_BATCH_SIZE', 25) or 25)

    duong_cache = args.cache or args.out.with_suffix('.cache.json')
    cache = json.loads(duong_cache.read_text(encoding='utf-8')) if duong_cache.exists() else {}

    con_lai = [m for m in danh_sach if khoa_noi_dung(m) not in cache]
    so_lo = (len(con_lai) + kich_thuoc - 1) // kich_thuoc

    print('muc can xu ly   %5d' % len(danh_sach))
    print('  da co cache   %5d' % (len(danh_sach) - len(con_lai)))
    print('  phai goi model%5d  -> %d lan goi (batch %d)' % (len(con_lai), so_lo, kich_thuoc))

    if args.dry_run:
        print('\n--dry-run: khong goi model.')
        return

    if con_lai:
        skill_env.chuan_bi(cau_hinh, args.out)
    for i in range(0, len(con_lai), kich_thuoc):
        lo = con_lai[i:i + kich_thuoc]
        print('  lo %d/%d (%d muc)...' % (i // kich_thuoc + 1, so_lo, len(lo)), flush=True)
        prompt = MAU_PROMPT.format(muc='\n\n'.join(mo_ta(m, n) for n, m in enumerate(lo, 1)))
        try:
            tra_loi = skill_env.hoi(cau_hinh, prompt, HE_THONG)
        except skill_env.ThieuTraLoi:
            continue
        goi = doc_json(tra_loi)
        theo_id = {str(r.get('id')): r for r in goi.get('ket_qua', [])}
        for muc in lo:
            khoa = khoa_noi_dung(muc)
            if khoa in theo_id:
                cache[khoa] = theo_id[khoa]
        duong_cache.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
    skill_env.chot_hoi_dap('nhanh-trang-hang-trich-xuat')

    ket_qua, thieu = [], 0
    for muc in danh_sach:
        khoa = khoa_noi_dung(muc)
        tra = cache.get(khoa)
        if not tra:
            thieu += 1
            continue
        ket_qua.append({**muc, 'ten_viet': tra.get('ten_viet', ''),
                        'thong_so_ai': tra.get('thong_so', {}),
                        'bo_trong': tra.get('bo_trong', []), 'key_hash': khoa})

    print('\nco ket qua      %5d' % len(ket_qua))
    print('model bo sot    %5d' % thieu)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding='utf-8')
    print('da ghi %s' % args.out)

    if danh_sach and not ket_qua:
        raise SystemExit('goi model xong nhung khong muc nao co ket qua - dung lai.')


if __name__ == '__main__':
    main()
