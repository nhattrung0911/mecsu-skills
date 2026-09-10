# -*- coding: utf-8 -*-
"""Tang 3 - buoc 1: gom cac o filter con thieu thanh HANG DOI CAU HOI DUY NHAT.

Khong bao gio hoi model theo tung dong. Hai o thieu cung nhom hang, cung thuoc
tinh, va cung gia tri o nhung thuoc tinh QUYET DINH no (bo xac dinh do
learn_deps.py do duoc tu corpus) thi chac chan cung mot dap an -> hoi mot lan roi
trai nguoc lai moi dong.

Truoc khi hoi, moi o deu duoc thu tra bang corpus (learn_deps.lookup). Chi o nao
corpus khong biet moi vao hang doi.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import pickle
import re
from pathlib import Path

from learn_deps import lookup


# Nhung thuoc tinh KHONG phai thong so ky thuat: the phan nganh / thuong hieu /
# xuat xu. Suy duoc thi tang 1 va tang 2 da suy (chung la hang so trong cum hoac
# co phu thuoc ham). Model doan chung la doan chinh sach kinh doanh, khong phai tra
# bang tieu chuan - da bat duoc: tu dien "Nganh Hang: CNC" cho mot mui khoan.
NO_AI_ATTRS = {'Ngành Hàng', 'Brand of Group Home', 'Original'}

# Cung nhung the do KHONG duoc lam BO XAC DINH. Chung tuong quan tinh co trong
# lat cat nho chu khong quyet dinh thong so vat ly. Da cham tay va bat duoc:
# "Vit Col Inox 316" bi dien Vat Lieu = Inox 304 vi suy tu `Nganh Hang`;
# "Phe Gai ... Inox 304" bi dien Inox 420 vi suy tu `Brand of Group Home`.
MERCH_TAGS = {'Ngành Hàng', 'Brand of Group Home', 'Original'}



def parse_kv(text):
    out = {}
    for part in str(text).split('|'):
        part = part.strip()
        if ':' not in part:
            continue
        k, _, v = part.partition(':')
        k, v = k.strip(), v.strip()
        if k.upper() != 'N/A' and v:
            out.setdefault(k, v)
    return out


def known_of(row):
    known = parse_kv(row['filter_goc'])
    known.update({k: v for k, v in parse_kv(row['filter_bo_sung']).items() if k not in known})
    return known


class KeyIndex:
    """Tra cuu theo TUNG KHOA DON, khong qua trung gian quan he da duyet.

    `Be Rong Ranh <- Dung Cho Lo` bi learn_deps loai vi nhat quan tong the < 0.85,
    nhung khoa `lo = 250 mm` trong corpus sach tuyet doi (moi dong deu 5.15 mm).
    Loai ca quan he dong nghia di hoi model mot gia tri file da co san.
    """

    def __init__(self, res):
        self.by_group = collections.defaultdict(list)
        for row in res:
            if not row['group']:
                continue
            kv = parse_kv(row['filter_goc'])
            if kv:
                self.by_group[row['group']].append(kv)
        self.cache = {}
        # Ban ghi gom chung moi nhom: buoc ren cua M14 ren nhuyen la 1.5 mm du la
        # bulong dau tru hay dau luc giac. Nhom "Luc Giac Chim Dau Tru Thep Den"
        # khong co dong M14 nhuyen nao, ca file thi co 16 dong.
        self.pooled = [kv for rows in self.by_group.values() for kv in rows]

    def table(self, group, target):
        key = (group, target)
        if key not in self.cache:
            table = collections.defaultdict(collections.Counter)
            for kv in self.by_group.get(group, []):
                if target not in kv:
                    continue
                for attr, value in kv.items():
                    if attr != target:
                        table[(attr, value)][kv[target]] += 1
            self.cache[key] = table
        return self.cache[key]

    def refine(self, group, known, target, base_det, min_rows=2, purity=0.95,
               base_value=None):
        """Tra lai voi khoa CU THE HON: bo xac dinh goc + mot nhan phan loai cua dong.

        `Size Ren -> Buoc Ren` dat do sach 95% vi ren tho ap dao, nen bulong
        `M14x1.5 Ren Nhuyen` bi tra 2 mm (so cua ren tho). Them `Loai Ren` vao khoa
        thi ra 1.5 mm. Khoa cu the hon luon thang khoa tong quat.

        Uu tien nhanh LAM DOI cau tra loi, khong phai nhanh nhieu dong nhat: them
        `He Kich Thuoc` vao khoa cho ra dung 46 dong nhung van la 2 mm - vo nghia;
        them `Loai Ren` cho it dong hon nhung doi thanh 1.5 mm - do moi la thong tin.

        Thu trong nhom truoc; nhom khong du chung thi tra tren toan file voi nguong
        chung cao hon.
        """
        for rows, need in ((self.by_group.get(group) or [], min_rows),
                           (self.pooled, max(min_rows, 3))):
            best = None
            for extra, extra_value in known.items():
                # The kinh doanh khong duoc lam nhanh phan tach: `Original` (xuat xu)
                # tung doi dung buoc ren 1.5 mm thanh 2 mm chi vi tuong quan tinh co.
                if extra in base_det or extra == target or extra in MERCH_TAGS:
                    continue
                counter = collections.Counter()
                for kv in rows:
                    if target not in kv or kv.get(extra) != extra_value:
                        continue
                    if all(kv.get(d) == known.get(d) for d in base_det):
                        counter[kv[target]] += 1
                if not counter:
                    continue
                top, n_top = counter.most_common(1)[0]
                total = sum(counter.values())
                if n_top < need or n_top / total < purity:
                    continue
                cand = {'value': top, 'det': list(base_det) + [extra], 'rows': n_top,
                        'key_purity': round(n_top / total, 4), 'consistency': None,
                        'support': total}
                rank = (cand['value'] != base_value, cand['rows'])
                if best is None or rank > best[0]:
                    best = (rank, cand)
            if best and best[0][0]:          # chi nhan khi that su doi cau tra loi
                return best[1]
        return None

    def lookup(self, group, known, target, min_rows=2, purity=0.95):
        table = self.table(group, target)
        best = None
        for attr, value in known.items():
            counter = table.get((attr, value))
            if not counter:
                continue
            top, n_top = counter.most_common(1)[0]
            total = sum(counter.values())
            if n_top < min_rows or n_top / total < purity:
                continue
            cand = {'value': top, 'det': [attr], 'rows': n_top,
                    'key_purity': round(n_top / total, 4), 'consistency': None,
                    'support': total}
            if best is None or cand['rows'] > best['rows']:
                best = cand
        return best


def note_attributes(res, min_rows=5, min_words=4):
    """Thuoc tinh dang GHI CHU - khong duoc suy ra tu tuong quan.

    "Ghi Chu Of Chot: San Pham Khong Kem Tan" tung bi suy tu `Vat Lieu`; vat lieu
    khong quyet dinh mot ghi chu ban hang. Nhan dien bang du lieu: gia tri nhieu tu
    VA khong co chu so - thong so ky thuat gan nhu luon co so ("Ma Kem Trang Cr3+",
    "9.85 - 10.1 mm" deu co so nen khong bi chan oan).
    """
    values = collections.defaultdict(list)
    for row in res:
        for attr, value in parse_kv(row['filter_goc']).items():
            values[attr].append(value)
    out = set()
    for attr, vals in values.items():
        if len(vals) < min_rows:
            continue
        wordy = sum(1 for v in vals if len(v.split()) >= min_words)
        digitless = sum(1 for v in vals if not any(c.isdigit() for c in v))
        if wordy / len(vals) >= 0.5 and digitless / len(vals) >= 0.5:
            out.add(attr)
    return out


def group_vocab(res):
    """{nhom: {thuoc tinh: {gia tri}}} - de doc nhan phan loai tu ten san pham."""
    vocab = collections.defaultdict(lambda: collections.defaultdict(set))
    for row in res:
        if row['group']:
            for attr, value in parse_kv(row['filter_goc']).items():
                vocab[row['group']][attr].add(value)
    return vocab


def read_labels_from_name(known, name, vocab):
    """Bo sung nhan phan loai doc duoc tu TEN, chi de LAM BOI CANH tra cuu.

    Bulong `DIN912 M14x1.5x35 Ren Nhuyen` khong co `Loai Ren` trong filter, nen
    tra cuu chi theo `Size Ren` tra ve buoc ren cua ren THO (2 mm thay vi 1.5 mm).
    Ten da noi ro "Nhuyen"; doc no ra thi khoa tra cuu du.

    Gia tri bo sung o day KHONG duoc ghi vao ket qua, chi dung de tra cuu.
    """
    low = str(name).lower()
    out = dict(known)
    for attr, values in vocab.items():
        if attr in out:
            continue
        hits = {v for v in values if v and re.search(
            r'(?<![0-9A-Za-zÀ-ỹ])' + re.escape(v.lower()) + r'(?![0-9A-Za-zÀ-ỹ])', low)}
        if len(hits) == 1:
            out[attr] = hits.pop()
    return out


def base_attr(attr):
    """Bo hau to `Of <Nhom>` / `Cua <Nhom>` de gom von tu chung cua thuoc tinh."""
    m = re.match(r'^(.*?)\s+(?:Of|Của)\s+.+$', attr, re.I)
    return m.group(1).strip() if m else attr


class NameGuard:
    """Chan gia tri bi CHINH TEN SAN PHAM phu dinh.

    Tang 1 da co chot nay cho hang so trong cum; tang 2 thi quen ap. Voi thuoc
    tinh ma >=80% gia tri deu xuat hien trong ten (vat lieu, size ren, loai dau...),
    neu ten chua mot gia tri KHAC cua chinh thuoc tinh do thi gia tri tra ve la sai.
    """

    # 0.8 bo sot `Vat Lieu` (chi ~50% gia tri viet trong ten) va de lot
    # "GR 8 UNC ... -> Vat Lieu: Thep GR 5". 0.3 bat duoc, chi ton them 4/676 o.
    # 0.8 bo sot `Vat Lieu` (chi ~50% gia tri viet trong ten) va de lot
    # "GR 8 UNC ... -> Vat Lieu: Thep GR 5". 0.3 bat duoc, chi ton them 4/676 o.
    def __init__(self, res, min_rows=10, min_in_name=0.3):
        self.values = collections.defaultdict(collections.Counter)
        self.base = collections.defaultdict(collections.Counter)
        in_name, total = collections.Counter(), collections.Counter()
        for row in res:
            name = str(row['ten']).lower()
            for attr, value in parse_kv(row['filter_goc']).items():
                self.values[attr][value] += 1
                self.base[base_attr(attr)][value] += 1
                total[attr] += 1
                if value.lower() in name:
                    in_name[attr] += 1
        self.encoded = {a for a in total
                        if total[a] >= min_rows and in_name[a] / total[a] >= min_in_name}

    def rejects(self, row, attr, value):
        if attr not in self.encoded:
            return False
        name = str(row['ten']).lower()
        if value.lower() in name:
            return False
        # Von tu tra cuu theo TEN THUOC TINH GOC (bo hau to `Of <Nhom>`): nhom
        # U-Bolts khong he co gia tri "Nhung Nong Kem" nen von tu rieng nhom mu
        # truoc san pham "Cum U ... Nhung Nong Kem" bi dien "Ma Kem".
        pool = set(self.values[attr]) | set(self.base[base_attr(attr)])
        return any(v.lower() in name and v != value for v in pool)


def _rejected(hit, guard, row, target, blocked):
    if any(d in MERCH_TAGS for d in hit['det']):
        blocked['bo xac dinh la the kinh doanh'] += 1
        return True
    if guard.rejects(row, target, hit['value']):
        blocked['ten san pham phu dinh'] += 1
        return True
    return False


def best_context(rels, group, target, known):
    """Boi canh TOI THIEU quyet dinh `target` cho dong nay.

    Lay bo xac dinh cua quan he manh nhat ma dong nay co du gia tri, khong lay hop
    cua moi bo - hop khien moi dong thanh mot cau hoi rieng, gom lai bang 1.0x.
    """
    for rel in rels.get(group, []):
        if rel['target'] != target:
            continue
        if all(d in known for d in rel['det']):
            return {d: known[d] for d in rel['det']}
    return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--audit', type=Path, required=True)
    ap.add_argument('--deps', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--filled-out', type=Path, help='ghi cac o corpus tra duoc ra day')
    # 2 dong lam chung la khong du: da bat duoc 'DIN931 M30x180 -> Chieu Dai Ren
    # 52 mm' (dung phai la 72 mm, 52 la so cua M20) suy tu dung 2 dong.
    ap.add_argument('--min-key-rows', type=int, default=3)
    a = ap.parse_args()

    res, _ginfo = pickle.load(open(a.audit, 'rb'))
    rels = json.loads(a.deps.read_text(encoding='utf-8'))

    index = KeyIndex(res)
    guard = NameGuard(res)
    vocab = group_vocab(res)
    notes = note_attributes(res)
    if notes:
        print('thuoc tinh dang ghi chu (khong suy): %d' % len(notes))
    blocked = collections.Counter()
    filled, asks = [], collections.OrderedDict()
    n_cells = 0
    for idx, row in enumerate(res):
        targets = [t.strip() for t in str(row['can_tra_cuu']).split(',') if t.strip()]
        if not targets:
            continue
        known = known_of(row)
        ctx_known = read_labels_from_name(known, row['ten'], vocab.get(row['group'], {}))
        for target in targets:
            n_cells += 1
            if target in notes:
                blocked['thuoc tinh dang ghi chu'] += 1
                continue
            hit = lookup(rels, row['group'], ctx_known, target, a.min_key_rows)
            if hit and _rejected(hit, guard, row, target, blocked):
                hit = None
            if not hit or hit.get('weak'):
                hit = index.lookup(row['group'], ctx_known, target, a.min_key_rows)
                if hit and _rejected(hit, guard, row, target, blocked):
                    hit = None
            if hit and not hit.get('weak'):
                sharper = index.refine(row['group'], ctx_known, target, hit['det'],
                                       a.min_key_rows, base_value=hit['value'])
                if sharper and sharper['value'] != hit['value']:
                    blocked['thay bang khoa cu the hon'] += 1
                    hit = sharper
                filled.append({
                    'row': idx, 'part_id': row['part_id'], 'ma': row['ma'],
                    'attr': target, 'value': hit['value'],
                    'source': 'corpus', 'det': hit['det'], 'rows': hit['rows'],
                    'purity': hit.get('key_purity'), 'consistency': hit['consistency'],
                })
                known.setdefault(target, hit['value'])
                ctx_known.setdefault(target, hit['value'])
                continue
            if target in notes:
                blocked['thuoc tinh dang ghi chu'] += 1
                continue
            if target in NO_AI_ATTRS:
                blocked['thuoc tinh khong cho AI doan'] += 1
                continue
            # `ctx_known`, khong phai `known`: nhan doc tu ten (Ren Nhuyen) da duoc
            # dung de TRA CUU o tren, nhung neu no khong vao KHOA GOM thi M14x1.5
            # nhuyen va M14 tho ve chung mot cau hoi va apply_fills trai mot dap an
            # cho ca hai.
            ctx = best_context(rels, row['group'], target, ctx_known)
            # Khoa gom: cung nhom + cung thuoc tinh + cung boi canh quyet dinh.
            # Khong co boi canh nao thi rot ve chinh ten san pham (khong gom duoc).
            key = json.dumps([row['group'], target, ctx or {'__ten__': row['ten']}],
                             ensure_ascii=False, sort_keys=True)
            ask = asks.get(key)
            if ask is None:
                ask = asks[key] = {
                    # id trong prompt danh theo thu tu, nhung KHOA CACHE phai theo
                    # noi dung: doi hang doi ma van danh so tu 1 thi cau tra loi cu
                    # bi gan nham sang cau hoi khac (da tung xay ra: 16/58 sai).
                    'ask_id': len(asks) + 1,
                    'key_hash': hashlib.sha1(key.encode('utf-8')).hexdigest()[:16],
                    'group': row['group'], 'attr': target,
                    'context': ctx,
                    'sample_name': row['ten'],
                    'sample_known': known.copy(),
                    'rows': [],
                }
            ask['rows'].append(idx)

    queue = {'asks': list(asks.values())}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(queue, ensure_ascii=False), encoding='utf-8')
    if a.filled_out:
        a.filled_out.write_text(json.dumps(filled, ensure_ascii=False), encoding='utf-8')

    n_ask_cells = sum(len(x['rows']) for x in queue['asks'])
    print(f'o filter con thieu        : {n_cells}')
    print(f'  corpus tra duoc         : {len(filled)}')
    print(f'  con lai phai hoi model  : {n_ask_cells}')
    print(f'  gom thanh cau hoi duy nhat: {len(queue["asks"])}'
          f'  (giam {n_ask_cells / max(1, len(queue["asks"])):.1f}x)')
    if blocked:
        for reason, n in blocked.most_common():
            print(f'  chan: {reason:38} {n}')
    top = collections.Counter(x['attr'] for x in queue['asks'])
    for k, v in top.most_common(8):
        print(f'    {v:5d}  {k}')
    print(f'-> {a.out}')


if __name__ == '__main__':
    main()
