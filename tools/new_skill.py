# -*- coding: utf-8 -*-
"""Dung khung cho mot skill moi trong lab/.

    python tools/new_skill.py ten-skill --purpose "Viec skill nay lam."

Sinh san SKILL.md dung frontmatter, website.json, mot script co argparse va mot
test khoi dong.

Khung sinh ra CO Y TRUOT lint cho toi khi co nguoi viet noi dung:

    python tools/lint_skills.py --dir lab
    -> SKILL.md con dong TODO - text khuon chua duoc viet lai

Do khong phai loi. Giong `run.py` co y thoat 2 cho toi khi co nguoi viet logic:
khung phai DO o moi cong cho toi khi co nguoi lam viec. Truoc day no xanh, va
mot skill mang nguyen text khuon di qua duoc ca cong 2 lan cong 3.

Xoa dong TODO va viet muc "Khi nao dung" that vao la lint xanh.

Lam bang tay thi lan nao cung quen mot thu: ten trong frontmatter lech ten thu
muc, khong co test nen lint bao loi, hoac trung ten file test voi skill khac
(pytest gom test theo TEN FILE chu khong theo duong dan, trung la nuot mat test).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TEN_HOP_LE = re.compile(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$')
MAX_DESCRIPTION = 500           # phai khop tools/lint_skills.py

SKILL_MD = '''---
name: {ten}
description: {description}
---

# {ten}

{purpose}

## Khi nao dung

- TODO: liet ke tinh huong kich hoat, ke ca tu khoa tieng Viet nguoi dung that su go.

## Cach chay

```bash
python ${{CLAUDE_SKILL_DIR}}/scripts/run.py --input <duong-dan-file.xlsx>
```

Chay khong kem `--yes` thi script dung lai sau lo hieu chuan de nguoi doc truoc.

## Luat khong duoc pha

1. **Do cot tu header.** Khong doan ra thi dung va hoi, in header that kem ten co.
2. **Tang 0 token chay truoc.** rule -> tra chinh file -> moi hoi model -> doi chieu nguoc.
3. **Hong thi exit khac 0.** Buoc sau kiem NOI DUNG file, khong kiem su ton tai cua file.
4. **Khong quote con so chua do.** Moi con so phai sinh lai duoc tu artifact tren dia.
'''

SCRIPT = '''# -*- coding: utf-8 -*-
"""{ten}: {purpose}

    python run.py --input <duong-dan-file.xlsx>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):      # console Windows la cp1252
    sys.stdout.reconfigure(encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, required=True, help='File Excel can xu ly.')
    parser.add_argument('--yes', action='store_true', help='Bo qua chot dung sau lo hieu chuan.')
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit('khong thay file: %s' % args.input)

    # TODO: viet logic o day. Giu nguyen kieu thoat duoi day cho toi khi that su lam xong -
    # bao xong trong khi chua kiem gi la che do hong te nhat.
    print('{ten}: chua cai dat logic')
    raise SystemExit(2)


if __name__ == '__main__':
    main()
'''

TEST = '''# -*- coding: utf-8 -*-
"""Test khoi dong cho {ten}. Chua kiem logic - chi kiem script con chay duoc.

Hai dieu duoi day van dung sau khi logic duoc viet xong, nen khong phai sua lai.
"""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'run.py'


def _chay(*co):
    return subprocess.run([sys.executable, str(SCRIPT), *co],
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=60)


def test_help_chay_duoc():
    ket_qua = _chay('--help')
    assert ket_qua.returncode == 0, ket_qua.stdout + ket_qua.stderr
    assert '--input' in ket_qua.stdout


def test_thieu_input_thi_thoat_khac_0():
    """Thieu tham so bat buoc ma van thoat 0 la che do hong te nhat."""
    assert _chay().returncode != 0
'''

WEBSITE = {
    'title': '',
    'purpose': '',
    'prompt': '',
}


def kiem_ten(ten: str) -> None:
    if not TEN_HOP_LE.match(ten):
        raise SystemExit(
            'ten khong hop le: %r\n'
            'Dung chu thuong, so va dau gach ngang, vi du: mecsu-naming' % ten)


def kiem_trung(root: Path, ten: str) -> None:
    for thu_muc in ('skills', 'lab'):
        if (root / thu_muc / ten).exists():
            raise SystemExit('da co %s/%s roi' % (thu_muc, ten))

    # pytest gom test theo TEN FILE, khong theo duong dan: trung ten la mat test.
    ten_test = 'test_%s_smoke.py' % ten.replace('-', '_')
    trung = [p for p in root.rglob(ten_test) if '.git' not in p.parts]
    if trung:
        raise SystemExit('ten file test %s da ton tai: %s' % (ten_test, trung[0]))


# `--when` bi dan "Use when" o dau. Nguoi goi thuong viet ca cau ("Chi dung khi...")
# va ra "Use when Chi dung khi..." - thua chu, cau hong. Cat phan mo dau thua di.
MO_DAU_THUA = re.compile(
    r'^\s*(use\s+when|chỉ\s+dùng\s+khi|chi\s+dung\s+khi|dùng\s+khi|dung\s+khi|khi)\s+',
    re.IGNORECASE)


def dung(root: Path, ten: str, purpose: str, title: str, when: str) -> Path:
    when = MO_DAU_THUA.sub('', when).strip()
    if not when:
        raise SystemExit('--when rong sau khi cat phan mo dau. Viet menh de noi tiep sau "Use when".')
    description = '%s Use when %s' % (purpose.rstrip('.') + '.', when.rstrip('.') + '.')
    if len(description) > MAX_DESCRIPTION:
        raise SystemExit(
            'description dai %d ky tu > %d. Viet --purpose va --when ngan lai.'
            % (len(description), MAX_DESCRIPTION))

    skill = root / 'lab' / ten
    (skill / 'scripts').mkdir(parents=True)
    (skill / 'tests').mkdir()

    (skill / 'SKILL.md').write_text(
        SKILL_MD.format(ten=ten, description=description, purpose=purpose),
        encoding='utf-8')
    (skill / 'scripts' / 'run.py').write_text(
        SCRIPT.format(ten=ten, purpose=purpose), encoding='utf-8')
    (skill / 'tests' / ('test_%s_smoke.py' % ten.replace('-', '_'))).write_text(
        TEST.format(ten=ten), encoding='utf-8')

    trang = dict(WEBSITE, title=title or purpose, purpose=purpose,
                 prompt='Dung skill %s cho file cua toi.' % ten)
    (skill / 'website.json').write_text(
        json.dumps(trang, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return skill


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('ten', help='Ten skill, cung la ten lenh /... Vi du: mecsu-naming')
    parser.add_argument('--purpose', required=True, help='Mot cau: skill nay lam viec gi.')
    parser.add_argument('--when', default='du lieu san pham can duoc soat lai',
                        help='Tinh huong kich hoat, viet nhu MENH DE NOI TIEP sau "Use when". '
                             'Vi du: --when "file Excel chi co cot ma hang" -> '
                             '"Use when file Excel chi co cot ma hang." '
                             'Dung viet ca cau ("Chi dung khi...") - se thanh "Use when Chi dung khi...".')
    parser.add_argument('--title', default='', help='Ten hien tren web. Mac dinh lay --purpose.')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    kiem_ten(args.ten)
    kiem_trung(args.root, args.ten)
    skill = dung(args.root, args.ten, args.purpose, args.title, args.when)

    print('da dung %s' % skill.relative_to(args.root))
    for duong_dan in sorted(p.relative_to(skill) for p in skill.rglob('*') if p.is_file()):
        print('   %s' % duong_dan)
    print('\nBuoc tiep:')
    print('   1. Viet logic vao scripts/run.py, sua phan TODO trong SKILL.md')
    print('      (khung nay CO Y truot lint cho toi khi ban viet xong - khong phai loi)')
    print('   2. python tools/lint_skills.py --dir lab')
    print('   3. python -m pytest -q')
    print('   4. Bon cong xanh het thi: git mv lab/%s skills/%s' % (args.ten, args.ten))
    print('   5. python tools/sync_site.py      # web tu co muc cho skill moi')


if __name__ == '__main__':
    main()
