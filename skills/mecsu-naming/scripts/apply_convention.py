# -*- coding: utf-8 -*-
"""Vong 1: chuan hoa ten theo quy uoc da hoc. Chi xu ly dong DA CO thong tin.

    python apply_convention.py --codes codes.json --convention convention.json --out names.json

Khong ra internet o vong nay. Dong nao thieu thong tin thi de vong 2 di tra web -
day chi sap xep lai thu da co cho dung cong thuc.

`_quyet_dinh_cua_nguoi` trong convention.json THANG moi thu model tu suy ra.
Model doc du lieu roi de xuat; nguoi chot; file ghi lai ca hai.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_env                                              # noqa: E402

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

THAM_CHIEU = Path(__file__).resolve().parents[1] / 'references'
TRAN_KY_TU = 80          # do tren 5.730 ten Mecsu: TB 45, p90 59, dai nhat 80
CHUAN_MECSU = '{Loại sản phẩm} {Đặc trưng} {Thông số quan trọng để khách lựa chọn} {Hãng} {Mã}'

HE_THONG = (
    'Bạn chuẩn hoá tên sản phẩm công nghiệp cho một nhà phân phối Việt Nam. '
    'Bạn CHỈ được sắp xếp lại và chuẩn hoá thông tin ĐÃ CÓ. '
    'Tuyệt đối không thêm thông số, kích thước, vật liệu hay đặc điểm mà dữ liệu không nói. '
    'Thiếu thì để thiếu và ghi vào "con_thieu". Viết tiếng Việt có dấu.'
)

MAU = '''QUY ƯỚC ĐẶT TÊN CỦA KHÁCH HÀNG

Công thức chuẩn (người phụ trách đã chốt, ưu tiên cao nhất):
  {cong_thuc}

Ràng buộc bắt buộc:
{rang_buoc}

Quy ước khác rút ra từ chính dữ liệu của họ:
{quy_tac}

NHIỆM VỤ

Với mỗi sản phẩm dưới đây, viết lại tên cho đúng công thức chuẩn. Trả về JSON:

{{"ket_qua": [{{
  "ma": "mã y nguyên như đề bài",
  "ten_moi": "tên đã chuẩn hoá",
  "doi_gi": "một câu ngắn: đã đổi gì so với tên cũ, hoặc 'giữ nguyên'",
  "con_thieu": ["thành phần của công thức mà dữ liệu không cung cấp"]
}}]}}

Chỉ trả JSON.

SẢN PHẨM:
{du_lieu}'''


def mo_ta(muc: dict) -> str:
    # Dua ma HANG cho model, khong dua ma co tien to noi bo. Do 2026-09-11 tren
    # 200 dong that: dua `SAT-62817` thi 99/200 ten ban hang chua luon `SAT-`.
    ma_hang = muc.get('ma_hang') or muc['ma_goc']
    dong = ['- mã: %s' % muc['ma_goc'],
            '  mã hãng PHẢI dùng trong tên: %s' % ma_hang,
            '  tên hiện tại: %s' % muc.get('ten_file', '')]
    if muc.get('tien_to'):
        dong.append('  (%s- là tiền tố nội bộ, KHÔNG được xuất hiện trong tên)' % muc['tien_to'])
    for t in muc.get('dong_thong_so', []):
        dong.append('  thông số: %s' % t)
    if not muc.get('dong_thong_so'):
        dong.append('  thông số: (không có dòng nào)')
    return '\n'.join(dong)


def ma_dung_trong_ten(ma: str, ten: str, ma_hang: str = '') -> bool:
    """Ten moi PHAI chua dung MA HANG, khong phai mot bien the cua no.

    Do 2026-09-11 tren 20 dong: ma that la `C-1 450x16x21`, model viet vao ten
    `C1-450x16x21` du rang buoc ghi ro giu nguyen. So sanh lang le thi 4 dong sai
    di thang vao file giao.

    Do lai tren 200 dong that: so voi `ma_goc` lam 97/100 dong bao dong gia. Mot so
    file dung TIEN TO NOI BO (`SAT-12913`, `BSI-BS522015`) ma tien to do khong duoc
    xuat hien trong ten ban hang - ten dung phai chua `12913`, `BS522015`. Vi vay
    can cu la MA HANG; ma_goc chi dung khi khong tach duoc tien to.
    """
    ten = ten or ''
    can = ma_hang or ma
    if not can or can not in ten:
        return False
    # Chua ma hang van CHUA du: `SATA SAT-70303A` co chua `70303A` nhung tien to
    # noi bo da lot vao ten ban hang. Do 2026-09-11: 99/200 dong dinh loi nay va
    # TAT CA deu duoc cham OK vi cau kiem chi hoi "co chua ma hang khong".
    if ma_hang and ma and ma != ma_hang and ma in ten:
        return False
    return True


def sua_ma_trong_ten(ten: str, ma_hang: str) -> str:
    """Thay bien the cua ma bang dung ma goc. Khong tim thay bien the thi de nguyen.

    Nhac trong prompt khong du: model chep lai dang ma trong TEN CU (`C1-450x16x21`)
    thay vi dung ma o cot ma (`C-1 450x16x21`) - 4/20 dong, lap lai qua nhieu lan
    chay. Sua bang code thi chac chan.

    Chi thay khi hai chuoi GIONG NHAU sau khi bo ky tu ngan cach - tuc cung mot ma
    viet khac cach. Khong bao gio ghep hai ma khac nhau.
    """
    if not ma_hang or ma_hang in ten:
        return ten
    don = lambda s: re.sub(r'[^0-9a-z]', '', s.lower())
    goc = don(ma_hang)
    if not goc:
        return ten

    # Quet theo TU, ghep dan toi 4 tu. Regex tham lam nuot ca cum dai nen khong
    # bao gio khop dung mot minh ma - da thu va no tra ve ten y nguyen.
    tu = list(re.finditer(r'\S+', ten))
    for i in range(len(tu)):
        for j in range(i, min(i + 4, len(tu))):
            dau, cuoi = tu[i].start(), tu[j].end()
            if don(ten[dau:cuoi]) == goc:
                return ten[:dau] + ma_hang + ten[cuoi:]
    return ten


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
    parser.add_argument('--convention', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--batch', type=int, default=20)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    for duong_dan in (args.codes, args.convention):
        if not duong_dan.exists():
            raise SystemExit('khong thay %s' % duong_dan)

    danh_sach = json.loads(args.codes.read_text(encoding='utf-8'))
    quy_uoc = json.loads(args.convention.read_text(encoding='utf-8'))

    # Chuan Mecsu di KEM SKILL - khong hoi lai o moi lan chay. Job nao muon de
    # rieng thi dien `_quyet_dinh_cua_nguoi` trong convention.json, no thang chuan.
    quyet_dinh = quy_uoc.get('_quyet_dinh_cua_nguoi', {})
    if not quyet_dinh.get('cong_thuc_chuan'):
        quyet_dinh = dict(quyet_dinh, cong_thuc_chuan=CHUAN_MECSU)
        print('dung chuan Mecsu co san trong skill (references/naming_convention.md)')

    can_lam = [m for m in danh_sach if str(m.get('ten_file', '')).strip()]
    so_lo = (len(can_lam) + args.batch - 1) // args.batch
    print('san pham co ten          %5d  -> %d lan goi (batch %d)'
          % (len(can_lam), so_lo, args.batch))
    print('san pham khong co ten    %5d  -> de vong 2' % (len(danh_sach) - len(can_lam)))
    if args.dry_run:
        print('\n--dry-run: khong goi model.')
        return

    rang_buoc = '\n'.join(
        '  - %s' % v for k, v in quyet_dinh.items() if k not in ('_ghi_chu', 'cong_thuc_chuan'))

    # Chuan Mecsu: don vi, hoa thuong, ten hang, kich thuoc. Doc thang tu file
    # tham chieu de sua chuan chi phai sua mot cho.
    chuan = THAM_CHIEU / 'naming_convention.md'
    if chuan.exists():
        rang_buoc += '\n\nCHUAN MECSU (bat buoc tuan theo):\n' + chuan.read_text(encoding='utf-8')
    hang_file = THAM_CHIEU / 'brands.json'
    if hang_file.exists():
        ds = json.loads(hang_file.read_text(encoding='utf-8')).get('hang', {})
        rang_buoc += ('\n\nCach viet hoa ten hang da chot: %s'
                      '\nHang KHONG co trong danh sach nay thi giu nguyen cach viet trong file '
                      'va ghi vao "con_thieu" la "hang moi chua chot cach viet".'
                      % ', '.join(sorted(ds.values())))

    quy_tac = '\n'.join('  - %s' % r for r in quy_uoc.get('quy_tac', [])[:8])

    cau_hinh = skill_env.doc_env()
    skill_env.phai_co_key(cau_hinh)

    theo_ma: dict[str, dict] = {}
    for i in range(0, len(can_lam), args.batch):
        lo = can_lam[i:i + args.batch]
        print('  lo %d/%d (%d san pham)...' % (i // args.batch + 1, so_lo, len(lo)), flush=True)
        prompt = MAU.format(
            cong_thuc=quyet_dinh['cong_thuc_chuan'], rang_buoc=rang_buoc, quy_tac=quy_tac,
            du_lieu='\n\n'.join(mo_ta(m) for m in lo))
        goi = doc_json(skill_env.hoi(cau_hinh, prompt, HE_THONG))
        for r in goi.get('ket_qua', []):
            theo_ma[str(r.get('ma', '')).strip()] = r

    ket_qua, thieu = [], 0
    for muc in can_lam:
        r = theo_ma.get(muc['ma_goc'])
        if not r:
            thieu += 1
            continue
        ten_moi = sua_ma_trong_ten(r.get('ten_moi', ''), muc.get('ma_hang', ''))
        # Doi chieu nguoc, 0 token: ten moi PHAI chua dung ma goc.
        # Do 2026-09-11: model doi tu `C-1 450x16x21` sang `C1-450x16x21` du rang
        # buoc da ghi ro giu nguyen ma - no chep lai dang ma trong ten cu.
        ma_dung = ma_dung_trong_ten(muc['ma_goc'], ten_moi, muc.get('ma_hang', ''))
        ket_qua.append({
            'ma': muc['ma_goc'], 'ten_cu': muc.get('ten_file', ''),
            'ten_moi': ten_moi, 'doi_gi': r.get('doi_gi', ''),
            'con_thieu': r.get('con_thieu', []),
            'co_thong_so': bool(muc.get('dong_thong_so')),
            'ma_trong_ten_dung': ma_dung,
            'trang_thai': 'OK' if ma_dung else 'REVIEW',
            'so_ky_tu': len(ten_moi),
            'ghi_chu': ' '.join(x for x in (
                '' if ma_dung else 'Tên không chứa đúng mã hãng %r - người soát lại.'
                                   % (muc.get('ma_hang') or muc['ma_goc']),
                '' if len(ten_moi) <= TRAN_KY_TU else
                'Tên %d ký tự, vượt trần %d - cân nhắc bỏ bớt thông số ít quan trọng.'
                % (len(ten_moi), TRAN_KY_TU),
            ) if x),
        })

    doi = sum(1 for r in ket_qua if r['ten_moi'] and r['ten_moi'] != r['ten_cu'])
    can_soat = [r for r in ket_qua if r['trang_thai'] == 'REVIEW']
    print('\nco ket qua       %5d' % len(ket_qua))
    print('  ten bi doi     %5d' % doi)
    print('  giu nguyen     %5d' % (len(ket_qua) - doi))
    print('model bo sot     %5d' % thieu)
    dai = [r for r in ket_qua if r['so_ky_tu'] > TRAN_KY_TU]
    so = sorted(r['so_ky_tu'] for r in ket_qua)
    print('do dai ten       TB %.1f | p90 %d | max %d ky tu'
          % (sum(so) / len(so), so[int(len(so) * .9)], so[-1]))
    print('  vuot tran %d   %5d' % (TRAN_KY_TU, len(dai)))
    print('  REVIEW         %5d  (ten khong chua dung ma goc)' % len(can_soat))
    for r in can_soat[:5]:
        print('     %s -> %s' % (r['ma'], r['ten_moi'][:58]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding='utf-8')
    print('da ghi %s' % args.out)

    if can_lam and not ket_qua:
        raise SystemExit('goi model xong nhung khong san pham nao co ket qua - dung lai.')


if __name__ == '__main__':
    main()
