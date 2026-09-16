# -*- coding: utf-8 -*-
"""Vong 2, buoc 0: nho model nghi TRUY VAN cho tung ma. Mot lan goi cho ca lo.

    python build_queries.py --codes codes.json --out queries.json

Vi sao khong tu ghep chuoi: do 2026-09-11, truy van ghep may moc
`PM-10BLA But danh dau son mau den CRAFTMASTER` tra ve 8 ket qua, KHONG ket qua
nao mang ma - toan trang danh muc but son tieng Viet. Ngu canh tieng Viet keo ve
trang ban le Viet, trong khi trang mang ma lai la trang tieng Nhat hoac tieng Anh
cua chinh hang.

Model doc ten san pham roi tu quyet dinh: hang nay goc nuoc nao, nen tim bang
tieng gi, tu khoa nganh nao di kem. Day la viec can hieu biet, khong phai viec
ghep chuoi - nen giao cho model, khong hardcode.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_env                                              # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

HE_THONG = (
    'Bạn giúp tìm trang thông số kỹ thuật của sản phẩm công nghiệp trên internet. '
    'Bạn nghĩ ra truy vấn tìm kiếm, không trả lời thông số. '
    'Không bịa tên hãng hay thông tin sản phẩm.'
)

MAU = '''Với mỗi sản phẩm dưới đây, nghĩ 3 truy vấn tìm kiếm để tìm ra TRANG CÓ THÔNG SỐ
KỸ THUẬT của đúng mã đó.

Lưu ý quan trọng: truy vấn ghép máy móc bằng tiếng Việt thường chỉ ra trang danh mục
của các cửa hàng Việt Nam, không mang mã sản phẩm. Trang mang mã thường là trang của
chính hãng hoặc nhà phân phối ở nước gốc của hãng.

Với mỗi mã, xếp 3 truy vấn theo thứ tự bạn cho là dễ trúng nhất:
  - một truy vấn dùng ngôn ngữ của nước gốc hãng (nếu bạn nhận ra hãng)
  - một truy vấn tiếng Anh
  - một truy vấn còn lại tuỳ bạn

Trả về JSON:
{{"ket_qua": [{{"ma": "...", "hang_doan": "...", "nuoc_doan": "...",
               "truy_van": ["...", "...", "..."]}}]}}

`hang_doan` và `nuoc_doan` là phỏng đoán của bạn để giải thích lựa chọn truy vấn —
không chắc thì để trống, đừng bịa.

Chỉ trả JSON.

SẢN PHẨM:
{du_lieu}'''


def doc_json(text: str) -> dict:
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0]
    dau, cuoi = text.find('{'), text.rfind('}')
    if dau < 0 or cuoi < dau:
        raise ValueError('khong tim thay JSON trong tra loi')
    return json.loads(text[dau:cuoi + 1])


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--codes', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.codes.exists():
        raise SystemExit('khong thay %s' % args.codes)
    danh_sach = json.loads(args.codes.read_text(encoding='utf-8'))
    can_tim = [m for m in danh_sach if not m.get('dong_thong_so')]
    if args.limit:
        can_tim = can_tim[:args.limit]

    print('san pham chua co thong so %5d  -> 1 lan goi model' % len(can_tim))
    if not can_tim:
        raise SystemExit('khong san pham nao thieu thong so.')
    if args.dry_run:
        print('\n--dry-run: khong goi model.')
        return

    cau_hinh = skill_env.doc_env()
    skill_env.chuan_bi(cau_hinh, args.out)
    du_lieu = '\n'.join('- mã: %s | tên trong file: %s'
                        % (m['ma_goc'], m.get('ten_file', '')) for m in can_tim)
    try:
        goi = doc_json(skill_env.hoi(cau_hinh, MAU.format(du_lieu=du_lieu), HE_THONG))
    except skill_env.ThieuTraLoi:
        skill_env.chot_hoi_dap('vong-2-dung-truy-van')

    theo_ma = {str(r.get('ma', '')).strip(): r for r in goi.get('ket_qua', [])}
    ket_qua, thieu = [], 0
    for muc in can_tim:
        r = theo_ma.get(muc['ma_goc'])
        truy_van = [t for t in (r or {}).get('truy_van', []) if str(t).strip()]
        if not truy_van:
            thieu += 1
            continue
        ket_qua.append({'ma_goc': muc['ma_goc'], 'ten_file': muc.get('ten_file', ''),
                        'hang_doan': (r or {}).get('hang_doan', ''),
                        'nuoc_doan': (r or {}).get('nuoc_doan', ''),
                        'truy_van': truy_van})

    print('co truy van  %5d' % len(ket_qua))
    print('model bo sot %5d' % thieu)
    for r in ket_qua[:3]:
        print('  %-12s [%s] %s' % (r['ma_goc'], r['hang_doan'], r['truy_van'][0][:58]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding='utf-8')
    print('da ghi %s' % args.out)

    if can_tim and not ket_qua:
        raise SystemExit('model khong nghi ra truy van nao - dung lai.')


if __name__ == '__main__':
    main()
