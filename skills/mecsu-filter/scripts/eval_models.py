# -*- coding: utf-8 -*-
"""Chon model bang DO DAC, khong chon bang ten.

Bo cau hoi co dap an DA XAC MINH tu bang tieu chuan trong references/standards/
(hoac tu chinh file khi file va bang tra khop nhau). Cham diem tung model tren
cung bo cau hoi -> biet model nao dang tin cho viec nay, va model nao du re.

Chay:
    python eval_models.py --models ag/gemini-3.7-flash-medium,ag/gemini-3.1-pro-low
    python eval_models.py --with-tables      # do them: dua bang tra vao prompt
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

import requests

import ai_fill
import sys

if hasattr(sys.stdout, 'reconfigure'):      # console Windows mac dinh la cp1252
    sys.stdout.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent

# (ten san pham, thuoc tinh, dap an dung, can cu)
CASES = [
    ('Phe Gài Lỗ Thép 65Mn DIN472 D48x1.75', 'Đường Kính Rãnh Sử Dụng', '50.5 mm', 'DIN 472 bang tra'),
    ('Phe Gài Lỗ Thép 65Mn DIN472 D50x2.0', 'Đường Kính Rãnh Sử Dụng', '53 mm', 'DIN 472 bang tra'),
    ('Phe Gài Lỗ Thép 65Mn DIN472 D52x2.0', 'Đường Kính Rãnh Sử Dụng', '55 mm', 'DIN 472 bang tra'),
    ('Phe Gài Lỗ Thép 65Mn DIN472 D12x1.0', 'Bề Rộng Rãnh Sử Dụng', '1.1 mm', 'DIN 472 bang tra'),
    ('Phe Gài Trục Thép 65Mn DIN471 D40x2.5', 'Đường Kính Rãnh Sử Dụng', '37.5 mm', 'DIN 471 bang tra'),
    ('Phe Gài Trục Thép 65Mn DIN471 D50x2.5', 'Đường Kính Rãnh Sử Dụng', '47 mm', 'DIN 471 bang tra'),
    ('Bulong Thép Đen 8.8 DIN931 M20x70 Ren Lửng', 'Chiều Dài Ren', '46 mm', 'DIN 931 b=2d+6'),
    ('Bulong Thép Đen 8.8 DIN931 M24x90 Ren Lửng', 'Chiều Dài Ren', '54 mm', 'DIN 931 b=2d+6'),
    ('Bulong Thép Đen 8.8 DIN931 M30x180 Ren Lửng', 'Chiều Dài Ren', '72 mm', 'DIN 931 b=2d+12'),
    ('Bulong Thép Đen 8.8 DIN931 M20x250 Ren Lửng', 'Chiều Dài Ren', '65 mm', 'DIN 931 b=2d+25'),
    ('Bulong Thép Đen 8.8 DIN931 M16x100 Ren Lửng', 'Size Khóa', '24 mm', 'DIN 931 bang tra'),
    ('Bulong Thép Đen 8.8 DIN933 M30x80', 'Size Khóa', '46 mm', 'DIN 933 = DIN 931 s'),
    ('Bulong Thép Đen 8.8 DIN933 M12x40', 'Chiều Cao Đầu', '7.5 mm', 'DIN 931/933 k'),
    ('Lục Giác Chìm Đầu Trụ Thép Đen 12.9 DIN912 M20x60', 'Size Khóa', '17 mm', 'DIN 912 bang tra'),
    ('Lục Giác Chìm Đầu Trụ Thép Đen 12.9 DIN912 M10x40', 'Chiều Cao Đầu', '10 mm', 'DIN 912 k=d'),
    ('Lục Giác Chìm Đầu Trụ Thép Đen 12.9 DIN912 M30x70', 'Đường Kính Đầu', '45 mm', 'DIN 912 dk'),
    ('Lục Giác Chìm Đầu Trụ Thép Đen 12.9 DIN912 M36x100', 'Size Khóa', '27 mm', 'DIN 912 bang tra'),
    ('Lục Giác Chìm Đầu Trụ Thép Đen 12.9 DIN912 M14x1.5x35 Ren Nhuyễn',
     'Bước Ren', '1.5 mm', 'ten ghi ro x1.5'),
]

SYSTEM = """Ban la ky su co khi. Voi moi san pham, cho biet gia tri cua thuoc tinh duoc hoi.

- Suy tu TIEU CHUAN + SIZE trong ten san pham. Day la so tra bang tieu chuan.
- Don vi viet dang "12.5 mm". Khong chac thi de chuoi rong.
- Neu prompt co BANG TRA thi chi dung so trong bang, khong tu che cong thuc.

Tra ve DUY NHAT mot mang JSON: [{"id": <int>, "value": "<gia tri>", "confidence": <0-1>}]"""


def number(text):
    m = re.search(r'-?\d+(?:[.,]\d+)?', str(text or ''))
    return float(m.group(0).replace(',', '.')) if m else None


def ask(config, model, tables):
    items = [{'id': i, 'name': n, 'need': a} for i, (n, a, _v, _w) in enumerate(CASES)]
    lines = []
    for table in tables:
        lines += ['--- BANG TRA ---', table, '---', '']
    lines += ['San pham can dien:', json.dumps(items, ensure_ascii=False)]
    payload = {'model': model, 'temperature': 0,
               'messages': [{'role': 'system', 'content': SYSTEM},
                            {'role': 'user', 'content': '\n'.join(lines)}]}
    headers = {'Authorization': 'Bearer ' + config['api_key'],
               'Content-Type': 'application/json'}
    r = requests.post(config['base_url'] + '/chat/completions', json=payload,
                      headers=headers, timeout=300)
    r.raise_for_status()
    content, usage = ai_fill.read_completion(r)
    return ai_fill.parse_array(content), usage


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--models', help='cach nhau dau phay; mac dinh lay tu .env')
    ap.add_argument('--with-tables', action='store_true')
    ap.add_argument('--standards', type=Path,
                    default=Path(os.environ.get('MECSU_FILTER_STANDARDS')
                                 or HERE.parent / 'references' / 'standards'))
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()

    config = ai_fill.load_config()
    models = ([m.strip() for m in args.models.split(',')] if args.models
              else config['models'])
    tables = list(ai_fill.load_standards(args.standards).values()) if args.with_tables else []

    print('%d cau hoi | bang tra trong prompt: %s\n' % (len(CASES), bool(tables)))
    report = {}
    for model in models:
        started = time.time()
        try:
            answers, usage = ask(config, model, tables)
        except Exception as error:                       # noqa: BLE001
            print('%-30s LOI %s' % (model, str(error)[:70]))
            continue
        by_id = {int(a.get('id', -1)): str(a.get('value') or '').strip() for a in answers}
        right = wrong = blank = 0
        details = []
        for i, (name, attr, truth, why) in enumerate(CASES):
            got = by_id.get(i, '')
            if not got:
                blank += 1
                mark = 'trong'
            elif number(got) is not None and number(truth) is not None \
                    and abs(number(got) - number(truth)) < 0.011:
                right += 1
                mark = 'dung'
            else:
                wrong += 1
                mark = 'SAI'
            details.append((mark, name, attr, truth, got, why))
        report[model] = {'dung': right, 'sai': wrong, 'trong': blank,
                         'tokens': usage.get('total_tokens'), 'chi_tiet': details}
        print('%-30s dung %2d | SAI %2d | trong %2d | %5s token | %4.0fs'
              % (model, right, wrong, blank, usage.get('total_tokens'), time.time() - started))
        for mark, name, attr, truth, got, why in details:
            if mark == 'SAI':
                print('      SAI  %s | %s: tra "%s", dung la "%s" (%s)'
                      % (name[:46], attr, got, truth, why))
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
        print('\n-> %s' % args.out)


if __name__ == '__main__':
    main()
