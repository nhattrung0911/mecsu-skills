# -*- coding: utf-8 -*-
"""Mot lenh: tro vao file Excel, nhan ve bang cham diem va file da dien filter.

    python run.py --input <file.xlsx> --job <thu muc lam viec>

Chay tang 1 (rule) va tang 2 (tra chinh file) - deu 0 token - roi hoi model dung
mot lo hieu chuan va DUNG LAI. Doc lo do xong moi chay lai kem --yes cho het.

Khong buoc nao doan qua mot cho can nguoi quyet.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STANDARDS = HERE.parent / 'references' / 'standards'

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')


def run(script: str, *arguments: str) -> None:
    """Chay mot buoc. Buoc nao that bai thi dung han - chay tiep chi tao rac."""
    printable = ' '.join(str(a) for a in arguments)
    print('\n$ python %s %s\n%s' % (script, printable, '-' * 72))
    code = subprocess.call([sys.executable, str(HERE / script), *[str(a) for a in arguments]])
    # 4 = dang CHO AGENT tra loi, khac han hong. Phai truyen nguyen so ra ngoai:
    # `SystemExit('<chuoi>')` lam Python thoat 1 va 4 bien thanh 1, agent goi skill
    # nay khong biet no phai dien tra_loi.json hay day chuyen da hong.
    if code == 4:
        print('\n%s dang cho agent tra loi. Dien xong chay lai dung lenh nay.' % script)
        raise SystemExit(4)
    if code:
        raise SystemExit('\n%s that bai (exit %d). Dung lai, khong chay buoc sau.' % (script, code))


def ai_values(job: Path) -> list[Path]:
    return sorted((job / 'ai').glob('ai_values_*.json'))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--input', type=Path, required=True, help='File Excel can kiem tra.')
    parser.add_argument('--job', type=Path, required=True, help='Thu muc lam viec, tu dat.')
    parser.add_argument('--model', help='Bo trong thi lay model dau tien trong .env.')
    parser.add_argument('--calibrate', type=int, default=50,
                        help='So cau hoi lo hieu chuan (0 de bo qua).')
    parser.add_argument('--yes', action='store_true',
                        help='Bo qua cho dung sau lo hieu chuan. Chi dat sau khi da DOC lo do.')
    parser.add_argument('--filter-col', type=int, help='Ep cot filter (0-based) neu tu do sai.')
    parser.add_argument('--name-col', type=int, help='Ep cot ten san pham (0-based).')
    parser.add_argument('--cat-col', type=int, help='Ep cot category (0-based).')
    parser.add_argument('--min-confidence', type=float, default=0.8,
                        help='Nguong nhan gia tri model tra ve.')
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit('Khong co file: %s' % args.input)
    job = args.job
    (job / 'ai').mkdir(parents=True, exist_ok=True)
    (job / 'review').mkdir(parents=True, exist_ok=True)

    audit = job / 'audit.pkl'
    queue = job / 'queue.json'
    corpus = job / 'corpus.json'
    verify = job / 'ai' / 'verify.json'

    # --- tang 1: rule, 0 token ---------------------------------------------
    detect = []
    for flag, value in (('--filter-col', args.filter_col), ('--name-col', args.name_col),
                        ('--cat-col', args.cat_col)):
        if value is not None:
            detect += [flag, value]
    run('filter_audit.py', args.input, '--out', job / 'audit', '--xlsx-out', job / 'audit.xlsx',
        *detect)

    # --- tang 2: tra chinh file, 0 token ------------------------------------
    run('learn_deps.py', '--audit', audit, '--out', job / 'deps.json')
    run('build_ai_queue.py', '--audit', audit, '--deps', job / 'deps.json',
        '--out', queue, '--filled-out', corpus)

    # --- tang 3: hoi model, lo hieu chuan truoc -----------------------------
    model = ['--model', args.model] if args.model else []
    common = ['--queue', queue, '--audit', audit, '--output-dir', job / 'ai',
              '--standards', STANDARDS, *model]
    if args.calibrate:
        run('ai_fill.py', *common, '--limit', args.calibrate)
        if not args.yes:
            print('\n%s\nDUNG. Doc %s truoc khi tra tien cho ca bo.\n'
                  'Mo %s, kiem vai gia tri xem co dung dinh dang va dung don vi khong.\n'
                  'On thi chay lai lenh nay kem --yes.\n%s'
                  % ('=' * 72, ', '.join(p.name for p in ai_values(job)) or 'lo hieu chuan',
                     job / 'ai', '=' * 72))
            return
    run('ai_fill.py', *common)

    values = ai_values(job)
    if not values:
        raise SystemExit('Khong co ai_values_*.json trong %s' % (job / 'ai'))

    # --- tang 4a: doi chieu bang chinh file, 0 token ------------------------
    run('verify_values.py', '--audit', audit, '--queue', queue,
        '--values', *values, '--out', verify)

    # --- ghep + tu kiem tra --------------------------------------------------
    run('apply_fills.py', '--input', args.input, '--audit', audit, '--queue', queue,
        '--corpus-filled', corpus, '--ai-values', *values, '--ai-verify', verify,
        '--out-dir', job / 'review', '--min-confidence', args.min_confidence)
    run('build_review.py', '--audit', audit, '--queue', queue, '--corpus-filled', corpus,
        '--ai-values', *values, '--ai-verify', verify, '--standards', STANDARDS,
        '--out', job / 'review' / 'cham_diem.xlsx')

    print('\n%s\nXong. Ket qua o %s\n\n'
          'Truoc khi giao:\n'
          '  1. Mo cham_diem.xlsx - moi o mot dong, xep san theo do kho cham.\n'
          '  2. O danh dau REVIEW la cho corpus khong dong y, KHONG phai o sai.\n'
          '     Doi chieu bang tra hoac tra web roi moi quyet.\n'
          '  3. Con o chua quyet thi de nguyen o review/, khong day sang delivered/.\n%s'
          % ('=' * 72, job / 'review', '=' * 72))


if __name__ == '__main__':
    main()
