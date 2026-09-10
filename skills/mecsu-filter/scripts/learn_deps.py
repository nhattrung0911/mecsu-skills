# -*- coding: utf-8 -*-
"""Tang 2: hoc PHU THUOC HAM giua cac filter tu chinh corpus, roi tra gia tri.

Y tuong: `Size Khoa Of Bulong` khong suy duoc tu ten, nhung no la HAM cua
(`Size Ren`, `Tieu Chuan`). Neu trong 67k dong, moi to hop (Size Ren, Tieu Chuan)
deu ung voi dung MOT gia tri Size Khoa, thi dong thieu Size Khoa tra bang bang do
la chac chan - khong can hoi AI.

Khong hard-code cap thuoc tinh nao ca: moi cap/bo deu duoc thu va chi giu lai khi
do duoc do nhat quan >= nguong tren du so dong chung.
"""
from __future__ import annotations

import argparse
import collections
import itertools
import json
import pickle
from pathlib import Path

MIN_SUPPORT = 8        # so dong lam chung toi thieu cho 1 quan he
MIN_CONSISTENCY = 0.85  # nhat quan tong the (loc quan he rac)
KEY_PURITY = 0.95       # do sach cua RIENG to hop dem tra cuu
PAIR_POOL = 14          # so thuoc tinh ung vien khi thu bo xac dinh 2 cot
SEP = ''


def mine(group_rows, min_support=MIN_SUPPORT, min_cons=MIN_CONSISTENCY, keep=8):
    """group_rows: list[dict attr->value] cua CUNG mot nhom hang.

    Tra ve list quan he: {'target', 'det': [attrs], 'table': {key: value},
    'support', 'consistency'}. Giu nhieu quan he cho moi target lam duong lui:
    dong thieu filter thuong cung thieu luon thuoc tinh xac dinh, nen mot quan he
    duy nhat se tra truot.
    """
    cov = collections.Counter()
    for d in group_rows:
        for k in d:
            cov[k] += 1
    n_rows = len(group_rows)
    attrs = [a for a, c in cov.items() if c >= min_support]
    # ung vien cho bo 2: thuoc tinh phu >= 20% dong (khong chi top-8 co dinh, vi
    # `Tieu Chuan` chi phu 41% nhung lai la thu quyet dinh `Size Khoa`).
    pool = [a for a in attrs if cov[a] / n_rows >= 0.2]
    if len(pool) > PAIR_POOL:
        pool = [a for a, _c in cov.most_common() if a in pool][:PAIR_POOL]

    rels = []
    for target in attrs:
        cands = [[a] for a in attrs if a != target]
        cands += [list(p) for p in itertools.combinations([a for a in pool if a != target], 2)]
        found = []
        for det in cands:
            table = collections.defaultdict(collections.Counter)
            for d in group_rows:
                if target not in d or any(a not in d for a in det):
                    continue
                table[tuple(d[a] for a in det)][d[target]] += 1
            n = sum(sum(c.values()) for c in table.values())
            if n < min_support:
                continue
            good = sum(c.most_common(1)[0][1] for c in table.values())
            cons = good / n
            if cons < min_cons:
                continue
            found.append({
                'minority': [
                    {'key': SEP.join(k), 'value': v, 'n': c[v],
                     'dominant': c.most_common(1)[0][0], 'n_dominant': c.most_common(1)[0][1]}
                    for k, c in table.items() if len(c) > 1
                    for v in c if v != c.most_common(1)[0][0]
                ] if len(det) == 1 else [],
                'target': target,
                'det': det,
                'table': {SEP.join(k): c.most_common(1)[0][0] for k, c in table.items()},
                'keys': {SEP.join(k): [c.most_common(1)[0][1], sum(c.values())]
                         for k, c in table.items()},
                'support': n,
                'consistency': round(cons, 4),
            })
        # Xep theo DO DUNG DUOC x nhat quan, khong phai nhat quan don thuan.
        # `Size Khoa <- Kich Thuoc (C)` dat cons 1.0 nhung `Kich Thuoc (C)` chi phu
        # 15% dong nen gan nhu khong bao gio tra duoc; `Size Khoa <- (Size Ren,
        # Tieu Chuan)` cons 0.998 nhung dung duoc cho hau het dong.
        for rel in found:
            rel['usable'] = round(min(cov[a] / n_rows for a in rel['det']), 4)
        found.sort(key=lambda r: (-(r['usable'] * r['consistency']), len(r['det']),
                                  -r['support']))
        rels.extend(found[:keep])
    rels.sort(key=lambda r: (r['target'], -(r['usable'] * r['consistency']),
                             len(r['det'])))
    return rels


def lookup(rels_by_group, group, known, target, min_key_rows=2, key_purity=KEY_PURITY):
    """Tra gia tri `target` tu cac filter da biet. Duyet quan he theo do manh.

    Do tin duoc xet o TUNG TO HOP, khong phai o ca quan he. Mot quan he nhat quan
    91% van co the co to hop hoan toan sach; loai ca quan he thi mat luon nhung
    to hop do va phai di hoi model gia tri ma file da co san.

    `min_key_rows`: to hop phai duoc it nhat ngan nay dong lam chung. Mot dong duy
    nhat khong du - da bat duoc sai that (DIN2093 M36 -> "M35" suy tu 1 dong).
    """
    weak = None
    for rel in rels_by_group.get(group, []):
        if rel['target'] != target or any(a not in known for a in rel['det']):
            continue
        key = SEP.join(known[a] for a in rel['det'])
        entry = rel['keys'].get(key)
        if not entry:
            continue
        n_dom, n_tot = entry
        hit = {
            'value': rel['table'][key],
            'det': rel['det'],
            'rows': n_dom,
            'key_purity': round(n_dom / n_tot, 4),
            'consistency': rel['consistency'],
            'support': rel['support'],
        }
        if n_dom >= min_key_rows and hit['key_purity'] >= key_purity:
            return hit
        weak = weak or dict(hit, weak=True)
    return weak


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit', type=Path, required=True, help='file .pkl do filter_audit.py sinh ra')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--min-support', type=int, default=MIN_SUPPORT)
    ap.add_argument('--min-consistency', type=float, default=MIN_CONSISTENCY)
    a = ap.parse_args()

    res, _ginfo = pickle.load(open(a.audit, 'rb'))
    by_group = collections.defaultdict(list)
    for r in res:
        if not r['group']:
            continue
        d = {}
        for part in str(r['filter_goc']).split('|'):
            part = part.strip()
            if not part or ':' not in part:
                continue
            k, _, v = part.partition(':')
            k, v = k.strip(), v.strip()
            if k.upper() != 'N/A' and v:
                d.setdefault(k, v)
        if d:
            by_group[r['group']].append(d)

    out = {}
    for g, rows in sorted(by_group.items(), key=lambda x: -len(x[1])):
        if len(rows) < a.min_support:
            continue
        rels = mine(rows, a.min_support, a.min_consistency)
        if rels:
            out[g] = rels
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, ensure_ascii=False), encoding='utf-8')
    tot = sum(len(v) for v in out.values())
    print(f'nhom co quan he: {len(out)}  |  tong quan he: {tot}')
    print(f'-> {a.out}')


if __name__ == '__main__':
    main()
