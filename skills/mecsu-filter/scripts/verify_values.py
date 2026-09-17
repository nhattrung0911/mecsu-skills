# -*- coding: utf-8 -*-
"""Tang 4 - buoc 1: kiem tra gia tri model tra ve, bang chinh du lieu trong file.

Nhieu thuoc tinh so la ham DON DIEU cua mot thuoc tinh so khac trong cung nhom
(duong kinh ranh tang theo duong kinh lo, size khoa tang theo size ren...). Neu
corpus da co diem hai ben, gia tri dung PHAI nam giua chung. Kiem tra nay khong
ton token va bat duoc loi that: model tra "lo 49 -> ranh 51.5 mm" trong khi
corpus co "lo 48 -> 53.0" va "lo 50 -> 54.0".

Khong hard-code cap thuoc tinh nao: cap (x, y) duoc chon bang do don dieu do tren
chinh du lieu.
"""
from __future__ import annotations

import argparse
import collections
import json
import pickle
import re
from pathlib import Path
import sys

if hasattr(sys.stdout, 'reconfigure'):      # console Windows mac dinh la cp1252
    sys.stdout.reconfigure(encoding='utf-8')

NUM = re.compile(r'-?\d+(?:[.,]\d+)?')
# Gia tri DO DUOC: ca chuoi la mot con so kem don vi. Khong dung NUM.search cho
# truc so - no rut "472" ra khoi "DIN 472" va bien ten tieu chuan thanh truc do.
MEASURE = re.compile(r"""^\s*-?\d+(?:[.,]\d+)?\s*[a-zA-Z%°"'/]*\s*$""")
MIN_POINTS = 6          # so diem toi thieu de tin mot quan he so
MIN_MONOTONE = 0.95     # ty le cap sap xep dung chieu


def number(text):
    m = NUM.search(str(text or ''))
    if not m:
        return None
    try:
        return float(m.group(0).replace(',', '.'))
    except ValueError:
        return None


def measure(text):
    """float neu ca gia tri la mot so (kem don vi), nguoc lai None."""
    raw = str(text or '')
    if not MEASURE.match(raw):
        return None
    return number(raw)


# Ma co: M20, DN50, ST4.2 - dung lam TRUC do duoc. Toi da 2 chu cai va khong co
# khoang trang, de "DIN 472" khong bi coi la co 472.
SIZECODE = re.compile(r'^\s*[A-Za-z]{1,2}\s?-?\d+(?:[.,]\d+)?\s*$')


def axis(text):
    """Gia tri dung lam TRUC hoanh: so do duoc, hoac ma co kieu M20/DN50."""
    value = measure(text)
    if value is not None:
        return value
    raw = str(text or '')
    return number(raw) if SIZECODE.match(raw) else None


def parse_kv(text):
    out = {}
    for part in str(text).split('|'):
        if ':' not in part:
            continue
        k, _, v = part.partition(':')
        k, v = k.strip(), v.strip()
        if k.upper() != 'N/A' and v:
            out.setdefault(k, v)
    return out


def monotone_ratio(points):
    """Ty le cap (xi<xj) co yi<=yj. 1.0 = tang chat, 0.0 = giam chat."""
    up = total = 0
    pts = sorted(points)
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            if pts[i][0] == pts[j][0]:
                continue
            total += 1
            if pts[i][1] <= pts[j][1]:
                up += 1
    return (up / total) if total else 0.5, total


MAX_CATEGORY_VALUES = 30   # thuoc tinh co it gia tri -> coi la phan loai


def build_index(res):
    """Giu nguyen ban ghi tung nhom de dung duong cong THEO LAT CAT luc kiem tra."""
    per_group = collections.defaultdict(list)
    for row in res:
        if not row['group']:
            continue
        kv = parse_kv(row['filter_goc'])
        if kv:
            per_group[row['group']].append(kv)
    distinct = collections.defaultdict(lambda: collections.defaultdict(set))
    for group, records in per_group.items():
        for kv in records:
            for attr, value in kv.items():
                distinct[group][attr].add(value)
    return per_group, distinct


def name_vocab(per_group):
    """{nhom: {thuoc tinh: {gia tri}}}.

    Phai tach THEO NHOM. Quet von tu cua moi nhom thi mot cai long den duoc gan
    `Size Ren Of Nut`, `Mau Sac Of Day Rut`, `Size Ren Of Guzong` chi vi ten no co
    chuoi "M14" - roi `best_pair` chon nham truc va `cross_check` mat tac dung.
    """
    vocab = collections.defaultdict(lambda: collections.defaultdict(set))
    for group, records in per_group.items():
        for kv in records:
            for attr, value in kv.items():
                vocab[group][attr].add(value)
    return vocab


def augment_from_name(known, name, vocab):
    """Bo sung thuoc tinh doc duoc tu TEN san pham.

    Nhieu dong thieu `Dung Cho Bulong` trong filter nhung ten ghi ro `M20`. Khong
    doc ra thi khong co truc de doi chieu, va cac cau tra loi cua model khong the
    so voi nhau duoc.
    """
    text = str(name)
    low = text.lower()
    out = dict(known)
    for attr, values in vocab.items():
        if attr in out:
            continue
        hits = [v for v in values
                if v and re.search(r'(?<![0-9A-Za-z])' + re.escape(v.lower())
                                   + r'(?![0-9A-Za-z])', low)]
        if len(set(hits)) == 1:
            out[attr] = hits[0]
    return out


def category_candidates(distinct, group, known, exclude):
    """Cac thuoc tinh PHAN LOAI ma dong nay co (khong phai truc do luong)."""
    out = []
    for attr, value in known.items():
        if attr in exclude or measure(value) is not None:
            continue
        values = distinct[group].get(attr)
        if values and 2 <= len(values) <= MAX_CATEGORY_VALUES:
            out.append((attr, value))
    return out


def curve_from(records, x_attr, y_attr, min_points):
    pts = set()
    for kv in records:
        x, y = axis(kv.get(x_attr)), measure(kv.get(y_attr))
        if x is not None and y is not None:
            pts.add((x, y))
    pts = sorted(pts)
    if len(pts) < min_points:
        return None
    ratio, total = monotone_ratio(pts)
    if total < min_points:
        return None
    if ratio >= MIN_MONOTONE:
        return {'points': pts, 'dir': 1, 'mono': round(ratio, 3)}
    if ratio <= 1 - MIN_MONOTONE:
        return {'points': pts, 'dir': -1, 'mono': round(1 - ratio, 3)}
    return None


def bracket(curve, x):
    """Khoang gia tri hop le cua y tai x, suy tu hai diem ke ben trong corpus."""
    pts = curve['points']
    lows = [p for p in pts if p[0] < x]
    highs = [p for p in pts if p[0] > x]
    exact = [p for p in pts if p[0] == x]
    if exact:
        ys = [p[1] for p in exact]
        return min(ys), max(ys), 'exact'
    if not lows or not highs:
        return None
    lo_y = max(p[1] for p in lows) if curve['dir'] > 0 else min(p[1] for p in lows)
    hi_y = min(p[1] for p in highs) if curve['dir'] > 0 else max(p[1] for p in highs)
    lo, hi = (lo_y, hi_y) if curve['dir'] > 0 else (hi_y, lo_y)
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi, 'interp'


def verify_one(index, group, attr, known, value, tol=0.02, min_points=MIN_POINTS):
    """Tra (trang thai, chi tiet).

    `OUT_OF_RANGE` chi duoc dung khi duong cong da tach dung lat cat. Khong tach
    duoc thi ha xuong `DISAGREE_UNSEGMENTED` - dung de nguoi xem, khong dung de
    tu dong loai bo gia tri.
    """
    per_group, distinct = index
    y = measure(value)
    if y is None:
        return 'NOT_NUMERIC', ''
    records = per_group.get(group) or []
    if not records:
        return 'NO_REFERENCE', ''
    # Thu tung lat cat roi GIU CAI CHO DUONG CONG TOT NHAT. Chon lat cat theo
    # "nhieu gia tri nhat" la sai: no lay `Vat Lieu` thay vi `Tieu Chuan`, trong
    # khi tieu chuan moi la thu doi ca duong cong.
    scopes = [(None, records)]
    for seg_attr, seg_value in category_candidates(distinct, group, known, {attr}):
        subset = [kv for kv in records if kv.get(seg_attr) == seg_value]
        if len(subset) >= min_points:
            scopes.append(((seg_attr, seg_value), subset))

    best = None
    for seg, scoped in scopes:
        for x_attr, x_raw in known.items():
            if x_attr == attr:
                continue
            x = axis(x_raw)
            if x is None:
                continue
            curve = curve_from(scoped, x_attr, attr, min_points)
            if not curve:
                continue
            br = bracket(curve, x)
            if not br:
                continue
            cand = (seg is not None, curve['mono'], len(curve['points']),
                    seg, x_attr, x, br)
            if best is None or cand[:3] > best[:3]:
                best = cand

    if best is None:
        return 'NO_REFERENCE', ''
    segmented, _mono, npts, seg, x_attr, x, (lo, hi, kind) = best
    label = ' | lat cat %s=%s' % seg if seg else ''
    pad = max(abs(lo), abs(hi)) * tol
    detail = '%s=%g -> %s trong [%g, %g] (%s, %d diem)%s' % (
        x_attr, x, attr, lo, hi, kind, npts, label)
    if lo - pad <= y <= hi + pad:
        return 'PLAUSIBLE', detail
    if not label:
        return 'DISAGREE_UNSEGMENTED', detail + ' | model tra %g' % y
    return 'OUT_OF_RANGE', detail + ' | model tra %g' % y


def best_pair(records, y_attr, axis_cands, label_cands, min_rows=6, purity=0.9,
              usable=None):
    """Chon (truc, nhan lat cat) sao cho (nhan, truc) -> y la HAM trong corpus.

    Phai chon cung luc: `Dung Cho Bulong -> Duong Kinh Ngoai` khong phai ham vi
    corpus tron DIN 127 lan DIN 7980; chi sau khi tach theo `Tieu Chuan` no moi
    thanh ham. Chon truc truoc roi moi chon nhan thi loai nham truc dung.

    `usable[x_attr]` = so cau tra loi dung duoc truc do. Truc chi 1 cau dung duoc
    thi khong so duoc cau nao voi cau nao, du bang chung trong corpus co day.
    """
    usable = usable or {}
    best = None
    for x_attr in axis_cands:
        for label in [None] + list(label_cands):
            table = collections.defaultdict(collections.Counter)
            for kv in records:
                x, y = axis(kv.get(x_attr)), measure(kv.get(y_attr))
                if x is None or y is None:
                    continue
                if label is not None and label not in kv:
                    continue
                key = (kv[label], x) if label else x
                table[key][y] += 1
            total = sum(sum(c.values()) for c in table.values())
            if total < min_rows or len(table) < 2:
                continue
            good = sum(c.most_common(1)[0][1] for c in table.values())
            score = good / total
            if score < purity:
                continue
            cand = (usable.get(x_attr, 0), score, total, x_attr, label)
            if best is None or cand[:3] > best[:3]:
                best = cand
    return (best[3], best[4]) if best else (None, None)


def cross_check(index, answers, min_points=MIN_POINTS):
    """So cac cau tra loi cua model VOI NHAU, khong chi voi corpus.

    Corpus khong phai luc nao cung co diem doi chieu. Nhung neu model tra
    "DIN 7980 M14 -> 24.4 mm" o dong nay va "DIN 7980 M14 -> 21.1 mm" o dong khac,
    thi it nhat mot trong hai sai - biet duoc ma khong can biet so dung la bao nhieu.

    `answers`: list dict co attr, known, value, key.
    """
    per_group, _distinct = index
    pooled = collections.defaultdict(list)
    for records in per_group.values():
        for kv in records:
            for a in kv:
                pooled[a].append(kv)

    by_attr = collections.defaultdict(list)
    for item in answers:
        by_attr[item['attr']].append(item)

    flags = {}
    for attr, items in by_attr.items():
        if len(items) < 2:
            continue
        records = pooled.get(attr) or []
        axes = collections.Counter()
        for item in items:
            for x_attr, x_raw in item['known'].items():
                if x_attr != attr and axis(x_raw) is not None:
                    axes[x_attr] += 1
        cats = {k for item in items for k, v in item['known'].items()
                if k != attr and axis(v) is None}
        x_attr, label = best_pair(records, attr, list(axes), cats, usable=axes)
        if not x_attr:
            continue
        curve = curve_from(records, x_attr, attr, min_points)

        pts = []
        for item in items:
            x, y = axis(item['known'].get(x_attr)), measure(item['value'])
            if x is not None and y is not None:
                pts.append((x, y, item['key'], item['known'].get(label) if label else None))
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                a, b = sorted((pts[i], pts[j]), key=lambda p: p[0])
                if label and a[3] != b[3]:
                    continue                      # khac lat cat -> khac bang so
                if a[0] == b[0]:
                    if a[1] != b[1]:
                        why = ('cung %s=%g%s nhung model tra %g va %g'
                               % (x_attr, a[0], ' (%s=%s)' % (label, a[3]) if label else '',
                                  a[1], b[1]))
                        flags.setdefault(a[2], why)
                        flags.setdefault(b[2], why)
                    continue
                if not curve:
                    continue
                bad = (a[1] >= b[1]) if curve['dir'] > 0 else (a[1] <= b[1])
                if bad:
                    why = ('%s tang theo %s trong file, nhung model tra %g cho %g '
                           'va %g cho %g' % (attr, x_attr, a[1], a[0], b[1], b[0]))
                    flags.setdefault(a[2], why)
                    flags.setdefault(b[2], why)
    return flags


def merge_values(paths):
    """Gop nhieu file `ai_values_*.json` thanh mot. Tra ve (gia tri, so o bat dong).

    Cung luat nhu apply_fills.py: hai model tra khac nhau cho cung mot o thi it nhat
    mot cai sai va khong biet cai nao -> bo ca hai. Truoc day tham so nay chi nhan
    MOT file trong khi run.py splat ca danh sach, nen chay 2 model la argparse exit 2
    va gay ca pipeline.
    """
    seen = {}
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        for key, answer in json.loads(path.read_text(encoding='utf-8')).items():
            seen.setdefault(key, []).append(answer)
    merged, conflicts = {}, 0
    for key, variants in seen.items():
        distinct = {str(v.get('value') or '').strip() for v in variants}
        if len(distinct) > 1:
            conflicts += 1
            continue
        merged[key] = min(variants, key=lambda v: float(v.get('confidence') or 0))
    return merged, conflicts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit', type=Path, required=True)
    ap.add_argument('--queue', type=Path, required=True)
    ap.add_argument('--values', type=Path, nargs='+', required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()

    res, _g = pickle.load(open(args.audit, 'rb'))
    asks = json.loads(args.queue.read_text(encoding='utf-8'))['asks']
    values, conflicts = merge_values(args.values)
    if conflicts:
        print('%d o bi bo vi cac model bat dong' % conflicts)
    index = build_index(res)
    vocab = name_vocab(index[0])
    print('nhom co du lieu so: %d' % len(index[0]))

    out, stats = [], collections.Counter()
    for ask in asks:
        ans = values.get(ask.get('key_hash', str(ask['ask_id'])))
        if not ans:
            continue
        value = str(ans.get('value') or '').strip()
        if not value:
            continue
        known = augment_from_name(ask['sample_known'], ask['sample_name'],
                                  vocab.get(ask['group'], {}))
        status, detail = verify_one(index, ask['group'], ask['attr'], known, value)
        stats[status] += 1
        out.append({
            'ask_id': ask['ask_id'], 'key': ask.get('key_hash'), 'group': ask['group'], 'attr': ask['attr'],
            'name': ask['sample_name'], 'value': value,
            'confidence': ans.get('confidence', ''), 'reason': ans.get('reason', ''),
            'verify': status, 'evidence': detail, 'rows': len(ask['rows']),
            'known': known,
        })

    kept = [x for x in out if x['verify'] != 'OUT_OF_RANGE']
    cross = cross_check(index, [{'group': x['group'], 'attr': x['attr'], 'value': x['value'],
                                 'known': x['known'], 'key': x['key']} for x in kept])
    for item in out:
        if item['key'] in cross and item['verify'] != 'OUT_OF_RANGE':
            item['verify'] = 'AI_TU_MAU_THUAN'
            item['evidence'] = cross[item['key']]
            stats['AI_TU_MAU_THUAN'] += 1
            stats[  # tru khoi nhan cu
                'PLAUSIBLE' if item.get('_prev') else 'NO_REFERENCE'] -= 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print('ket qua: %s' % dict(collections.Counter(x['verify'] for x in out)))
    for item in out:
        if item['verify'] in ('OUT_OF_RANGE', 'DISAGREE_UNSEGMENTED', 'AI_TU_MAU_THUAN'):
            print('  [%s] %s | %s = %s' % (item['verify'], item['name'][:46], item['attr'], item['value']))
            print('           %s' % item['evidence'])
    print('-> %s' % args.out)


if __name__ == '__main__':
    main()
