# -*- coding: utf-8 -*-
"""Vong 0: doc chinh file dau vao, RUT RA quy uoc dat ten cua nha. Mot lan.

    python learn_convention.py --codes codes.json --out convention.json

Khong hardcode bang anh xa nao. File cua khach da co san hang tram ten dat dung
kieu cua ho; viec o day la de model doc nhung dong DA CO va tu rut ra cong thuc,
tu vung thong so, cho dat hang va ma. Nho vay `dau tuyp` / `Dau Tuyp` / `socket`
deu ve cung mot khai niem ma khong ai phai liet ke.

Mot lan goi cho ca file. Ket qua la mot file NGUOI SOAT DUOC bang mat truoc khi
no duoc dem ap cho toan bo du lieu.
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
    'Bạn là người biên tập dữ liệu sản phẩm công nghiệp cho một nhà phân phối Việt Nam. '
    'Bạn đọc dữ liệu CÓ SẴN của họ và rút ra quy ước họ đang dùng. '
    'Bạn mô tả quy ước có thật trong dữ liệu, không đề xuất quy ước mới của riêng bạn. '
    'Viết tiếng Việt có dấu.'
)

MAU = '''Dưới đây là các sản phẩm đã được đặt tên sẵn trong file của khách hàng.

Hãy đọc và RÚT RA quy ước đặt tên mà họ đang dùng. Trả về JSON:

{{
  "cong_thuc_ten": "công thức chung, ví dụ \\"{{Loại}} {{Thông số chính}} {{Mã}} {{Hãng}} {{Nước}}\\"",
  "giai_thich": "từng thành phần lấy từ đâu, viết hoa ra sao, đơn vị viết thế nào",
  "nhom_san_pham": [
     {{"ten_nhom": "...", "cong_thuc": "...", "vi_du_trong_file": "..."}}
  ],
  "tu_vung_thong_so": ["các nhãn thông số họ dùng, chép đúng chữ trong file"],
  "quy_tac": ["các quy tắc bạn quan sát được, mỗi quy tắc một dòng"],
  "diem_khong_nhat_quan": ["chỗ trong file tự mâu thuẫn nhau, nếu có"]
}}

Chỉ trả JSON, không giải thích thêm.

DỮ LIỆU:
{du_lieu}'''


def mo_ta(muc: dict) -> str:
    dong = ['- mã: %s' % muc['ma_goc'], '  tên: %s' % muc.get('ten_file', '')]
    for t in muc.get('dong_thong_so', [])[:8]:
        dong.append('  thông số: %s' % t)
    return '\n'.join(dong)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--codes', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mau', type=int, default=60,
                        help='Toi da bao nhieu san pham lam vi du. Nhieu hon khong tot hon.')
    parser.add_argument('--dry-run', action='store_true', help='In so lan goi, khong goi model.')
    args = parser.parse_args()

    if not args.codes.exists():
        raise SystemExit('khong thay %s' % args.codes)
    danh_sach = json.loads(args.codes.read_text(encoding='utf-8'))

    # Chi lay dong DA CO ten lam thay: dong trong khong day duoc gi.
    co_ten = [m for m in danh_sach if str(m.get('ten_file', '')).strip()]
    if not co_ten:
        raise SystemExit(
            'Khong dong nao co san ten de hoc quy uoc.\n'
            'File chi co ma thi phai co mot file khac lam mau, hoac tu viet convention.json.')

    # Uu tien dong co ca ten lan thong so - chung day duoc nhieu hon.
    co_ten.sort(key=lambda m: -len(m.get('dong_thong_so', [])))
    mau = co_ten[:args.mau]

    print('san pham trong file      %5d' % len(danh_sach))
    print('  co san ten             %5d' % len(co_ten))
    print('  dung lam vi du         %5d  -> 1 lan goi model' % len(mau))
    if args.dry_run:
        print('\n--dry-run: khong goi model.')
        return

    cau_hinh = skill_env.doc_env()
    skill_env.chuan_bi(cau_hinh, args.out)
    try:
        tra_loi = skill_env.hoi(
            cau_hinh, MAU.format(du_lieu='\n'.join(mo_ta(m) for m in mau)), HE_THONG)
    except skill_env.ThieuTraLoi:
        skill_env.chot_hoi_dap('vong-0-hoc-quy-uoc')          # thoat 4, cho agent tra loi

    text = tra_loi.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0]
    dau, cuoi = text.find('{'), text.rfind('}')
    if dau < 0 or cuoi < dau:
        raise SystemExit('model khong tra ve JSON:\n%s' % tra_loi[:400])
    quy_uoc = json.loads(text[dau:cuoi + 1])

    if not quy_uoc.get('cong_thuc_ten'):
        raise SystemExit('model tra JSON nhung thieu cong_thuc_ten - dung lai.')

    quy_uoc['_nguon'] = {'file_ma': str(args.codes), 'so_vi_du': len(mau)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(quy_uoc, ensure_ascii=False, indent=2), encoding='utf-8')

    print('\ncong thuc: %s' % quy_uoc['cong_thuc_ten'])
    print('nhom san pham rut ra: %d' % len(quy_uoc.get('nhom_san_pham', [])))
    print('tu vung thong so:     %d' % len(quy_uoc.get('tu_vung_thong_so', [])))
    print('da ghi %s  <- SOAT FILE NAY truoc khi chay tiep' % args.out)


if __name__ == '__main__':
    main()
