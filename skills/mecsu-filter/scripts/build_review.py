# -*- coding: utf-8 -*-
"""Tang 4 - buoc 3: xuat bang CHAM DIEM cho nguoi duyet cuoi.

Cham tay ma phai tu di tra lai boi canh cho tung o thi rat cham va de bo sot.
File nay gom moi bang chung ve mot dong: gia tri, nguon, can cu cua model, ket qua
doi chieu corpus, hai diem lan can trong corpus, va co bang tra tieu chuan hay khong.

Sap xep: o kho cham nhat va anh huong nhieu dong nhat len dau.
"""
from __future__ import annotations

import argparse
import collections
import json
import pickle
import random
from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill

import verify_values as vv
import sys

if hasattr(sys.stdout, 'reconfigure'):      # console Windows mac dinh la cp1252
    sys.stdout.reconfigure(encoding='utf-8')

COLS = [
    ('stt', 'STT', 6), ('cham', 'CHAM (dung/sai/?)', 16),
    ('nguon', 'Nguon', 10), ('do_kho', 'Do kho cham', 13),
    ('ten', 'Ten san pham', 58), ('nhom', 'Nhom hang', 26),
    ('attr', 'Thuoc tinh', 30), ('gia_tri', 'GIA TRI DIEN', 16),
    ('can_cu', 'Can cu cua nguon', 46),
    ('verify', 'Doi chieu corpus', 15),
    ('bang_chung', 'Bang chung doi chieu', 56),
    ('lan_can', 'Lan can trong file', 44),
    ('bang_tra', 'Co bang tra chuan?', 18),
    ('known', 'Filter da biet cua dong', 70),
    ('so_dong', 'So dong anh huong', 12),
]


def neighbours(index, group, attr, known, limit=3):
    """Vai diem gan nhat trong corpus tren truc giai thich duoc attr."""
    per_group, distinct = index
    records = per_group.get(group) or []
    if not records:
        return ''
    axes = [k for k, v in known.items() if k != attr and vv.axis(v) is not None]
    for x_attr in axes:
        curve = vv.curve_from(records, x_attr, attr, vv.MIN_POINTS)
        if not curve:
            continue
        x = vv.axis(known[x_attr])
        pts = sorted(curve['points'], key=lambda p: abs(p[0] - x))[:limit]
        return '%s: ' % x_attr + ', '.join('%g→%g' % p for p in sorted(pts))
    return ''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit', type=Path, required=True)
    ap.add_argument('--queue', type=Path, required=True)
    ap.add_argument('--corpus-filled', type=Path, required=True)
    ap.add_argument('--ai-values', type=Path, nargs='+', required=True)
    ap.add_argument('--ai-verify', type=Path, required=True)
    ap.add_argument('--standards', type=Path)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--sample', type=int, help='chi lay N o ngau nhien de cham')
    ap.add_argument('--seed', type=int, default=0)
    args = ap.parse_args()

    res, _g = pickle.load(open(args.audit, 'rb'))
    index = vv.build_index(res)
    asks = {a['key_hash']: a for a in json.loads(args.queue.read_text(encoding='utf-8'))['asks']}
    values, conflicts = vv.merge_values(args.ai_values)
    if conflicts:
        print('%d o bi bo vi cac model bat dong' % conflicts)
    verdicts = {x['key']: x for x in json.loads(args.ai_verify.read_text(encoding='utf-8'))}
    corpus = json.loads(args.corpus_filled.read_text(encoding='utf-8'))
    have_tables = {p.stem.lower().replace('-', ' ')
                   for p in (args.standards.glob('*.md') if args.standards else [])}

    rows = []
    for item in corpus:
        row = res[item['row']]
        rows.append({
            'nguon': 'corpus', 'ten': row['ten'], 'nhom': row['group'],
            'attr': item['attr'], 'gia_tri': item['value'],
            'can_cu': 'suy tu %s, %d dong trong file lam chung'
                      % (' + '.join(item['det']), item['rows']),
            'verify': '', 'bang_chung': '',
            'known': row['filter_goc'], 'so_dong': 1, 'row': item['row'],
        })
    for key, ask in asks.items():
        ans = values.get(key) or {}
        value = str(ans.get('value') or '').strip()
        if not value:
            continue
        v = verdicts.get(key, {})
        rows.append({
            'nguon': 'gemini', 'ten': ask['sample_name'], 'nhom': ask['group'],
            'attr': ask['attr'], 'gia_tri': value,
            'can_cu': 'confidence %s | %s' % (ans.get('confidence'), ans.get('reason', '')),
            'verify': v.get('verify', 'NO_CHECK'), 'bang_chung': v.get('evidence', ''),
            'known': ' | '.join('%s: %s' % kv for kv in ask['sample_known'].items()),
            'so_dong': len(ask['rows']), 'row': ask['rows'][0],
        })

    name_vocab = vv.name_vocab(index[0])
    for r in rows:
        row = res[r['row']]
        # Tieu chuan hay nam trong TEN chu khong trong filter -> phai doc ra, neu
        # khong thi cot "co bang tra" bao nham la khong co.
        known = vv.augment_from_name(vv.parse_kv(row['filter_goc']), row['ten'],
                                     name_vocab.get(row['group'], {}))
        r['lan_can'] = neighbours(index, r['nhom'], r['attr'], known)
        std = next((v for k, v in known.items() if 'Tiêu Chuẩn' in k), '')
        slug = ' '.join(str(std).lower().replace('-', ' ').split())
        r['bang_tra'] = ('co: %s' % std) if slug in have_tables else (std or '(khong co chuan)')
        # O kho cham nhat: khong doi chieu duoc gi va khong co bang tra
        hard = (not r['lan_can']) + (not r['bang_tra'].startswith('co:')) \
            + (r['verify'] in ('', 'NO_CHECK', 'NO_REFERENCE', 'NOT_NUMERIC'))
        r['do_kho'] = ['de', 'trung binh', 'kho', 'RAT KHO'][min(hard, 3)]
        r['cham'] = ''

    rows.sort(key=lambda r: (-['de', 'trung binh', 'kho', 'RAT KHO'].index(r['do_kho']),
                             -r['so_dong']))
    if args.sample:
        random.seed(args.seed)
        rows = random.sample(rows, min(args.sample, len(rows)))
    for i, r in enumerate(rows, 1):
        r['stt'] = i

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'cham_diem'
    header = Font(bold=True, color='FFFFFF')
    for j, (_k, label, width) in enumerate(COLS, 1):
        c = ws.cell(1, j, label)
        c.font = header
        c.fill = PatternFill('solid', fgColor='C00000' if _k in ('cham', 'gia_tri') else '2F5597')
        c.alignment = Alignment(vertical='center', wrap_text=True)
        ws.column_dimensions[openpyxl.utils.get_column_letter(j)].width = width
    for r in rows:
        ws.append([r.get(k, '') for k, _l, _w in COLS])
    ws.freeze_panes = 'C2'
    ws.auto_filter.ref = 'A1:%s%d' % (openpyxl.utils.get_column_letter(len(COLS)), len(rows) + 1)

    s2 = wb.create_sheet('huong_dan')
    for line in [
        ['Cot CHAM: dien "dung" / "sai" / "?" cho tung dong.'],
        ['Cot "Do kho cham" xep theo so bang chung co san:'],
        ['  de        = co doi chieu corpus + co bang tra tieu chuan'],
        ['  RAT KHO   = khong doi chieu duoc gi, khong co bang tra -> can tra ngoai'],
        ['Cot "Lan can trong file": cac diem that trong file tren truc giai thich duoc'],
        ['  thuoc tinh nay. Vi du "Dung Cho Lo: 48→53, 50→54" nghia la trong file lo 48'],
        ['  co ranh 53. Neu gia tri dien lech han khoi day thi dang ngo - NHUNG chinh'],
        ['  corpus cung co the sai (da bat duoc DIN 472 sai 13 dong).'],
        ['Cot "Doi chieu corpus": OUT_OF_RANGE va AI_TU_MAU_THUAN da bi loai truoc khi'],
        ['  ghi vao file ket qua; chung xuat hien o day de xem lai quyet dinh do co dung.'],
    ]:
        s2.append(line)
    s2.column_dimensions['A'].width = 100

    args.out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(args.out)
    kho = collections.Counter(r['do_kho'] for r in rows)
    print('%d o de cham | do kho: %s' % (len(rows), dict(kho)))
    print('-> %s' % args.out)


if __name__ == '__main__':
    main()
