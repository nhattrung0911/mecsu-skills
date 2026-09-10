# -*- coding: utf-8 -*-
"""Audit cot C (ten san pham) + cot E (filter mapping) cua on_web_filter.xlsx.

Nguyen tac: MOI quy uoc/schema deu HOC TU DATA (majority cua corpus / cua cum
san pham cung skeleton), khong hard-code rule nganh.
"""
import re, sys, json, pickle, argparse, collections, unicodedata

if hasattr(sys.stdout, 'reconfigure'):      # ten san pham co dau, console Windows la cp1252
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

NUM = re.compile(r'\d+(?:[.,]\d+)?')
SEP = re.compile(r'\s*\|\s*')
GRP = re.compile(r'^(.*?)\s+(?:Of|Của)\s+(.+)$', re.I)

# ---------- parse ----------
def parse_filters(e):
    """-> list[(key, value)] giu thu tu, va co the trung key."""
    out = []
    for p in SEP.split(str(e)):
        p = p.strip()
        if not p:
            continue
        k, _, v = p.partition(':')
        out.append((k.strip(), v.strip()))
    return out

def is_empty_filter(pairs):
    return len(pairs) <= 1 and all(k.upper() == 'N/A' for k, _ in pairs)

def key_group(k):
    """-> (group|None, attr). 'Group Home' la key toan cuc, khong phai nhom."""
    m = GRP.match(k)
    if not m:
        return None, k
    attr, g = m.group(1).strip(), m.group(2).strip()
    if g.lower() == 'group home':
        return None, k
    return g, attr

def row_group(pairs):
    c = collections.Counter()
    for k, _ in pairs:
        g, _a = key_group(k)
        if g:
            c[g] += 1
    return c.most_common(1)[0][0] if c else None

# ---------- skeleton / cluster ----------
def norm_space(s):
    return re.sub(r'\s+', ' ', str(s).strip())

def skeleton(c):
    return NUM.sub('#', norm_space(c)).lower()

def numbers(c):
    return [m.group(0) for m in NUM.finditer(str(c))]

def tokens(c):
    return set(re.findall(r'[0-9A-Za-zÀ-ỹ]+', norm_space(c).lower()))

# ---------- value template learning ----------
def sub_first_num(val, n):
    for m in NUM.finditer(val):
        if m.group(0) == n:
            return val[:m.start()] + '{N}' + val[m.end():]
    return None

def render(tpl, n):
    return tpl.replace('{N}', n)

def learn_cluster(rows, idx, min_support, allow_slot=True):
    """Hoc schema + cach sinh gia tri cho 1 cum.

    Tra ve dict: key -> {'cov':float, 'mode':'CONST'|'SLOT', 'const':str,
                         'slot':int, 'tpl':str, 'acc':float}
    """
    parsed = {i: parse_filters(rows[i][4]) for i in idx}
    good = [i for i in idx if not is_empty_filter(parsed[i])]
    n = len(good)
    if n == 0:
        return {}, good, 0
    keycov = collections.Counter()
    vals = collections.defaultdict(collections.Counter)
    for i in good:
        seen = set()
        for k, v in parsed[i]:
            if k in seen:
                continue
            seen.add(k)
            keycov[k] += 1
            vals[k][v] += 1
    schema = {}
    for k, cov in keycov.items():
        if cov / n < min_support:
            continue
        info = {'cov': cov / n, 'n_have': cov, 'n_peers': n}
        top_v, top_c = vals[k].most_common(1)[0]
        if top_c == cov:                      # hang so trong cum
            # Neu gia tri nay von duoc VIET TRONG TEN o cac peer thi no la dac
            # trung phan biet san pham -> khong duoc copy mu sang dong khac,
            # phai kiem tra ten dong do co chua gia tri do khong.
            hit = sum(1 for i in good
                      if k in dict(parse_filters(rows[i][4]))
                      and top_v.lower() in str(rows[i][2]).lower())
            info.update(mode='CONST', value=top_v, acc=1.0,
                        in_name=(cov > 0 and hit / cov >= 0.8))
            schema[k] = info
            continue
        # thu suy tu vi tri so trong ten
        if not allow_slot:
            info.update(mode='NONE', value=top_v, acc=top_c / cov)
            schema[k] = info
            continue
        cand = collections.Counter()
        for i in good:
            d = dict(parse_filters(rows[i][4]))
            if k not in d:
                continue
            ns = numbers(rows[i][2])
            for si, nn in enumerate(ns):
                t = sub_first_num(d[k], nn)
                if t and t != d[k]:
                    cand[(si, t)] += 1
        best = None
        for (si, tpl), _c in cand.most_common(12):
            ok = tot = 0
            for i in good:
                d = dict(parse_filters(rows[i][4]))
                if k not in d:
                    continue
                ns = numbers(rows[i][2])
                if si >= len(ns):
                    continue
                tot += 1
                if render(tpl, ns[si]) == d[k]:
                    ok += 1
            if tot and (best is None or ok / tot > best[2]):
                best = (si, tpl, ok / tot)
            if best and best[2] > 0.995:
                break
        if allow_slot and best and best[2] >= 0.98:
            info.update(mode='SLOT', slot=best[0], tpl=best[1], acc=best[2],
                        ncount=len(numbers(rows[good[0]][2])))
        else:
            info.update(mode='NONE', value=top_v, acc=top_c / cov)
        schema[k] = info
    return schema, good, n

# ---------- corpus-level format conventions (hoc tu data) ----------
DIM_SP = re.compile(r'\d\s[xX]\s\d')
DIM_NS = re.compile(r'\dx\d')
UNIT_SP = re.compile(r'\d\s(?:mm|cm|inch|kg|ml|oz)\b')
UNIT_NS = re.compile(r'\d(?:mm|cm|inch|kg|ml|oz)\b')
WORD = re.compile(r'[0-9A-Za-zÀ-ỹ/#]+')


_LEAK = {'x'}
_HASD = re.compile(r'\d')
_HASA = re.compile(r'[a-zà-ỹ]')


def _marker_model(names, pos_re, neg_re, min_n=25, margin=0.3):
    """Hoc token nao bao hieu quy uoc nao, tu chinh corpus.

    Vi du: 'unc', 'unf', '1/2' -> he inch -> 'x' CO space; nguoc lai he met.
    Tra ve (dict token->P(pos), P_global).
    """
    st = collections.defaultdict(lambda: [0, 0])
    gp = gn = 0
    for s in names:
        a, b = bool(pos_re.search(s)), bool(neg_re.search(s))
        if a == b:
            continue
        gp, gn = gp + a, gn + b
        for w in set(WORD.findall(s.lower())):
            if w in _LEAK or (_HASD.search(w) and _HASA.search(w)):
                continue      # token ro ri nhan (vd 'x', 'm8x20', '5mm')
            st[w][0 if a else 1] += 1
    mk = {}
    for w, (a, b) in st.items():
        n = a + b
        if n < min_n:
            continue
        pp = a / n
        if abs(pp - 0.5) >= margin:
            mk[w] = (pp, n)
    return mk, (gp / (gp + gn) if gp + gn else 0.5)


def _predict(mk, gdef, name, conf=0.8):
    """Vote token cua chinh dong. Tra True/False khi DU TIN, None khi khong chac.

    Khong chac -> khong sua gi (tranh false positive kieu ap quy uoc he met
    cho ten he inch).
    """
    import math
    num = den = 0.0
    for w in set(WORD.findall(str(name).lower())):
        if w in mk:
            pp, n = mk[w]
            wgt = math.log(n + 1) * abs(pp - 0.5)
            num += pp * wgt
            den += wgt
    if den == 0:
        return None
    pp = num / den
    if pp >= conf:
        return True
    if pp <= 1 - conf:
        return False
    return None


def learn_conventions(all_names):
    conv = {}
    conv['dim'] = _marker_model(all_names, DIM_SP, DIM_NS)      # True = x CO space
    conv['unit'] = _marker_model(all_names, UNIT_SP, UNIT_NS)   # True = unit CO space
    tok = collections.Counter()
    for s in all_names:
        for w in re.findall(r'[A-Za-zÀ-ỹ]{2,}', s):
            tok[w] += 1
    byl = collections.defaultdict(dict)
    for w, n in tok.items():
        byl[w.lower()][w] = n
    canon = {}
    for lw, vs in byl.items():
        if len(vs) < 2:
            continue
        tot = sum(vs.values())
        best = max(vs, key=vs.get)
        if tot < 30:
            continue
        for v, n in vs.items():
            if v != best and n / tot < 0.2:
                canon[v] = best
    conv['casing'] = canon
    return conv

UNIT_RE = re.compile(r'(?<=\d)(mm|cm|inch|kg|ml|oz)\b')
def cluster_conv(rows, idx):
    """Hoc quy uoc space cua RIENG cum (tranh ap quy uoc he met cho he inch)."""
    names = [str(rows[i][2]) for i in idx]
    def c(pat):
        p = re.compile(pat)
        return sum(1 for s in names if p.search(s))
    a = sum(1 for x in names if UNIT_SP.search(x))
    b = sum(1 for x in names if UNIT_NS.search(x))
    d = sum(1 for x in names if DIM_NS.search(x))
    e = sum(1 for x in names if DIM_SP.search(x))

    def decide(p, q):
        # chi tin quy uoc cum khi cum du lon VA gan nhu dong nhat
        if p + q < 5 or min(p, q) / (p + q) > 0.1:
            return None
        return p > q
    return {'unit_space': decide(a, b), 'dim_nospace': decide(d, e)}

def fix_name(name, conv, local=None):
    """Tra ve (ten_de_xuat, [ly do]). `local` (quy uoc cum) uu tien hon corpus."""
    s = str(name)
    fixes = []
    t = norm_space(s)
    if t != s:
        fixes.append('space thua/dau-cuoi')
    if '×' in t or '✕' in t:
        t = t.replace('×', 'x').replace('✕', 'x')
        fixes.append('ky tu × -> x')
    local = local or {}
    us = local.get('unit_space')
    ds = local.get('dim_nospace')
    if us is None:
        us = _predict(conv['unit'][0], conv['unit'][1], t)
    # Quy uoc dinh/tach 'x' KHAC nhau giua he met va he inch va khong doan duoc
    # dang tin cay tu token => chi sua khi chinh cum san pham da dong nhat.
    if us is True:
        t2 = UNIT_RE.sub(lambda m: ' ' + m.group(1), t)
        if t2 != t:
            t, _ = t2, fixes.append('them space truoc don vi')
    if ds is True:
        t2 = re.sub(r'(?<=\d)\s+[xX]\s+(?=\d)', 'x', t)
        if t2 != t:
            t, _ = t2, fixes.append('bo space quanh x giua kich thuoc')
    parts = t.split(' ')
    changed = False
    for i, w in enumerate(parts):
        core = re.sub(r'[^0-9A-Za-zÀ-ỹ]', '', w)
        if core in conv['casing']:
            parts[i] = w.replace(core, conv['casing'][core])
            changed = True
    if changed:
        t = ' '.join(parts)
        fixes.append('chuan hoa hoa/thuong theo majority corpus')
    t = norm_space(t)
    return t, fixes


# ---------- nhan dien cot (khong hardcode vi tri) ----------
COL_HINTS = {
    'name': ('ten_san_pham', 'description', 'ten sp', 'product_name', 'ten'),
    'filt': ('filter_mapping', 'danh_sach_filter', 'filter', 'mapping', 'thuoc_tinh'),
    'cat': ('ten_cate', 'category_name', 'leaf_category_name', 'category', 'nganh_hang_leaf'),
    'count': ('so_luong_filter', 'filter_count'),
    'code': ('ma_san_pham', 'part_number', 'sku', 'ma_sp'),
    'pid': ('part_id', 'id'),
}


def _score(hint, h):
    """Do do khop giua mot hint va mot ten cot. Khop chinh xac luon thang khop
    mot phan; giua hai khop mot phan thi hint phu kin ten cot nhieu hon thang."""
    if h == hint:
        return 3.0
    if hint not in h:
        return 0.0
    return 1.0 + len(hint) / len(h)


def detect_columns(header, overrides=None):
    """Do vi tri cot tu ten header. Cot filter khong phai luon o vi tri E:
    Fas+Hand_check_all.xlsx dat no o G va chen them 2 cot category.

    Gan theo diem cao nhat truoc, khong theo thu tu role. Duyet theo thu tu role
    thi hint 'filter' cua vai 'filt' cuop mat cot 'active_filter_count' (cot DEM)
    truoc khi 'mapped_filters' kip duoc xet - da ra file rac that."""
    low = [str(h or '').strip().lower() for h in header]
    forced = {r: i for r, i in (overrides or {}).items() if i is not None}
    candidates = []
    for rank, (role, hints) in enumerate(COL_HINTS.items()):
        if role in forced:
            continue
        for hint in hints:
            for i, h in enumerate(low):
                if i in forced.values():
                    continue
                score = _score(hint, h)
                if score:
                    candidates.append((-score, rank, i, role))
    found = dict(forced)
    taken = set(forced.values())
    for _, _, index, role in sorted(candidates):
        if role in found or index in taken:
            continue
        found[role] = index
        taken.add(index)
    missing = [r for r in ('name', 'filt') if r not in found]
    if missing:
        raise SystemExit('Khong nhan ra cot %s trong header: %s' % (missing, header))
    return found


def check_filter_column(rows, cols, header):
    """Cot filter phai chua 'Key: Value | Key: Value'. Doan nham cot so ma van
    audit tiep thi ket qua la file rac nhung exit 0 - khong duoc phep."""
    index = cols['filt']
    sample = [str(r[index]) for r in rows[:200] if index < len(r) and r[index] not in (None, '')]
    if not sample:
        raise SystemExit('Cot filter %r rong tren 200 dong dau. Ep bang --filter-col.'
                         % (header[index] if index < len(header) else index))
    ok = sum(1 for v in sample if ':' in v)
    if ok < len(sample) * 0.5:
        others = ', '.join('%d=%s' % (i, h) for i, h in enumerate(header))
        raise SystemExit(
            'Cot filter doan nham: %r chi co %d/%d dong dang "Key: Value". '
            'Cac cot dang co: %s. Ep dung cot bang --filter-col <chi so 0-based>.'
            % (header[index] if index < len(header) else index, ok, len(sample), others))


def canonical(rows, cols):
    """Dua ve khuon (pid, code, ten, count, filter) de phan con lai khong doi."""
    def pick(row, role, default=None):
        i = cols.get(role)
        return row[i] if i is not None and i < len(row) else default
    return [(pick(r, 'pid'), pick(r, 'code'), pick(r, 'name'),
             pick(r, 'count'), pick(r, 'filt')) for r in rows]


# ---------- clustering voi fallback ----------
def build_clusters(rows, groups, min_peers):
    """L1: skeleton. L2: Jaccard token trong cung nhom. L3: nhom."""
    sk = collections.defaultdict(list)
    for i, r in enumerate(rows):
        sk[skeleton(r[2])].append(i)
    assign = {}          # row -> (cluster_id, level)
    clusters = {}        # cluster_id -> list[row]
    small = []
    for k, idx in sk.items():
        if len(idx) >= min_peers:
            cid = 'L1:' + k
            clusters[cid] = idx
            for i in idx:
                assign[i] = (cid, 1)
        else:
            small.extend(idx)
    by_group = collections.defaultdict(list)
    for i, g in enumerate(groups):
        if g:
            by_group[g].append(i)
    tokcache = {}
    def tk(i):
        if i not in tokcache:
            tokcache[i] = tokens(rows[i][2])
        return tokcache[i]
    for i in small:
        g = groups[i]
        peers = []
        if g:
            ti = tk(i)
            for j in by_group[g]:
                if j == i:
                    continue
                tj = tk(j)
                u = len(ti | tj)
                if u and len(ti & tj) / u >= 0.6:
                    peers.append(j)
        if len(peers) + 1 >= min_peers:
            cid = 'L2:%d' % i
            clusters[cid] = [i] + peers
            assign[i] = (cid, 2)
        elif g and len(by_group[g]) >= min_peers:
            cid = 'L3:' + g
            clusters.setdefault(cid, by_group[g])
            assign[i] = (cid, 3)
        else:
            assign[i] = (None, 0)
    return clusters, assign

MIN_SUPPORT = {1: 0.90, 2: 0.90, 3: 0.95}


def _slot_ok(rows, idx, lvl):
    """Suy gia tri theo VI TRI so trong ten chi an toan khi moi peer co cung
    so luong so (cung khuon ten). Cum L1 luon thoa; cum fallback thi phai kiem."""
    if lvl == 1:
        return True
    cnts = {len(numbers(rows[i][2])) for i in idx}
    return len(cnts) == 1

def audit(xlsx, only_group=None, out=None, min_peers=5, limit=None, overrides=None):
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    it = ws.iter_rows(min_row=1, values_only=True)
    header = list(next(it))
    cols = detect_columns(header, overrides)
    raw = list(it)
    if limit:
        raw = raw[:limit]
    check_filter_column(raw, cols, header)
    rows = canonical(raw, cols)
    parsed = [parse_filters(r[4]) for r in rows]
    # Nhom hang: uu tien cot category cua file neu co - no dung cho ca dong
    # co cot filter rong, thu ma hau to `Of <Nhom>` khong lam duoc.
    cat_index = cols.get('cat')
    if cat_index is not None:
        groups = [str(raw[i][cat_index]).strip() if raw[i][cat_index] else row_group(parsed[i])
                  for i in range(len(rows))]
    else:
        groups = [row_group(p) for p in parsed]
    conv = learn_conventions([str(r[2]) for r in rows])
    clusters, assign = build_clusters(rows, groups, min_peers)
    # Dong co cot E rong khong tu bao nhom (nhom nam trong key cua E). Lay nhom
    # da so cua cum peer, neu khong co thi lay tu ten thuoc tinh ma cum dang dung.
    for _cid, idxs in clusters.items():
        votes = collections.Counter(groups[j] for j in idxs if groups[j])
        if not votes:
            continue
        win = votes.most_common(1)[0][0]
        for j in idxs:
            if groups[j] is None:
                groups[j] = win
    schema_cache = {}
    conv_cache = {}
    rescue_cache = {}
    results = []
    # index token -> cac dong CO filter, de cuu nhung dong ma ca cum deu rong
    filled_rows = [j for j, pp in enumerate(parsed) if not is_empty_filter(pp)]
    inv = collections.defaultdict(list)
    tok_of = {}
    for j in filled_rows:
        t = tokens(rows[j][2])
        tok_of[j] = t
        for w in t:
            inv[w].append(j)

    def rescue_peers(i, min_j=0.5):
        ti = tokens(rows[i][2])
        cand = collections.Counter()
        for w in ti:
            if len(inv[w]) > 4000:      # token qua pho bien -> bo qua
                continue
            for j in inv[w]:
                cand[j] += 1
        out = []
        for j, _c in cand.most_common(400):
            tj = tok_of[j]
            u = len(ti | tj)
            if u and len(ti & tj) / u >= min_j:
                out.append(j)
        return out
    # --- Tier B: vote theo CUM trong cung nhom (mien nhiem voi cum lon lan at) ---
    grp_clusters = collections.defaultdict(list)
    for cid, idxs in clusters.items():
        gs = collections.Counter(groups[j] for j in idxs if groups[j])
        if gs:
            grp_clusters[gs.most_common(1)[0][0]].append(cid)
    for cid in list(clusters):
        if cid not in schema_cache:
            lv = 1 if cid.startswith('L1') else 2 if cid.startswith('L2') else 3
            schema_cache[cid] = learn_cluster(rows, clusters[cid], MIN_SUPPORT[lv],
                                              allow_slot=_slot_ok(rows, clusters[cid], lv))
    grp_attr_vote = {}
    for g, cids in grp_clusters.items():
        big = [c for c in cids if len(clusters[c]) >= min_peers]
        if len(big) < 3:
            continue
        v = collections.Counter()
        for c in big:
            for k in schema_cache[c][0]:
                v[k] += 1
        grp_attr_vote[g] = (v, len(big))
    for i, r in enumerate(rows):
        g = groups[i]
        cid, lvl = assign.get(i, (None, 0))
        if only_group:
            nm = str(r[2]).lower()
            if not (g == only_group or nm.startswith(only_group.lower())):
                continue
        if cid and cid not in schema_cache:
            schema_cache[cid] = learn_cluster(rows, clusters[cid], MIN_SUPPORT[lvl],
                                              allow_slot=_slot_ok(rows, clusters[cid], lvl))
        schema, good, npeer = schema_cache.get(cid, ({}, [], 0))
        if npeer == 0:                  # ca cum deu rong E -> cuu bang peer toan corpus
            if i not in rescue_cache:
                pr = rescue_peers(i)
                rescue_cache[i] = (learn_cluster(rows, pr, 0.9,
                                                 allow_slot=_slot_ok(rows, pr, 2))
                                   if len(pr) >= min_peers else ({}, [], 0))
            schema, good, npeer = rescue_cache[i]
            if npeer:
                lvl, cid = 4, 'L4:cuu-bang-peer-tuong-tu'
        if cid and lvl == 1 and cid not in conv_cache:
            conv_cache[cid] = cluster_conv(rows, clusters[cid])
        lconv = conv_cache.get(cid, {}) if lvl == 1 else {}
        have = collections.OrderedDict()
        multi = collections.defaultdict(list)
        for k, v in parsed[i]:
            multi[k].append(v)
            if k not in have:
                have[k] = v
        # key lap voi value KHAC nhau = filter multi-value hop le, khong phai loi.
        # Chi bao khi lap y het (du thua that su).
        dup = [k for k, vs in multi.items() if len(vs) > len(set(vs))]
        empty = is_empty_filter(parsed[i])
        ns = numbers(r[2])
        missing, filled, need_lookup, ref = [], [], [], []
        for k, info in schema.items():
            if k in have and not empty:
                continue
            missing.append(k)
            if info['mode'] == 'CONST':
                if info.get('in_name') and info['value'].lower() not in str(r[2]).lower():
                    need_lookup.append(k)
                    ref.append('%s ~ %s (peer dung gia tri nay nhung ten dong nay khac)'
                               % (k, info['value']))
                    continue
                filled.append((k, info['value'], 'const-cum %.0f%%' % (100 * info['cov'])))
            elif info['mode'] == 'SLOT' and info['slot'] < len(ns) and (
                    lvl == 1 or len(ns) == info.get('ncount', len(ns))):
                filled.append((k, render(info['tpl'], ns[info['slot']]),
                               'suy tu ten (so thu %d, acc %.0f%%)' % (info['slot'] + 1, 100 * info['acc'])))
            else:
                need_lookup.append(k)
                ref.append('%s ~ %s (%.0f%% peer)' % (k, info.get('value', ''), 100 * info.get('acc', 0)))
        # mau thuan C <-> E
        conflict = []
        for k, v in have.items():
            info = schema.get(k)
            if not info:
                continue
            if info['mode'] == 'SLOT' and info['slot'] < len(ns):
                exp = render(info['tpl'], ns[info['slot']])
                if exp != v:
                    conflict.append('%s: ten C ngu y "%s" nhung E ghi "%s"' % (k, exp, v))
            elif info['mode'] == 'CONST' and v != info['value']:
                conflict.append('%s: cum dung "%s" nhung E ghi "%s"' % (k, info['value'], v))
        # filter la (co trong dong nhung hiem trong cum)
        odd = []
        na_key = [k for k in have if k.upper() == 'N/A']
        if na_key and not empty:
            odd.append('key rac "N/A"')
        if npeer >= min_peers:
            cnt = collections.Counter()
            for j in good:
                for k, _ in parse_filters(rows[j][4]):
                    cnt[k] += 1
            for k in have:
                if k.upper() == 'N/A':
                    continue
                if cnt[k] / npeer < 0.05:
                    odd.append('%s (chi %.0f%% peer co)' % (k, 100 * cnt[k] / npeer))
        # Tier B: ca cum cung thieu filter ma da so cum khac trong nhom deu co
        tier_b = []
        if g in grp_attr_vote and lvl == 1:
            v, nb = grp_attr_vote[g]
            for k, c in v.items():
                if k in schema or k in have:
                    continue
                if c / nb >= 0.8:
                    tier_b.append('%s (%.0f%% cum khac trong nhom co)' % (k, 100 * c / nb))
        if empty:
            odd = []
        newname, fixes = fix_name(r[2], conv, lconv)
        merged = list(have.items()) if not empty else []
        merged += [(k, v) for k, v, _s in filled]
        results.append({
            'row': i + 2, 'part_id': r[0], 'ma': r[1], 'ten': r[2],
            'so_luong_filter': r[3], 'filter_goc': r[4],
            'group': g, 'cluster': cid, 'level': lvl, 'n_peer': npeer,
            'ten_de_xuat': newname if newname != str(r[2]) else '',
            'loi_ten': '; '.join(fixes),
            'e_rong': 'X' if empty else '',
            'd_lech': '' if (r[3] is None or int(r[3]) == len(parsed[i])) else 'D=%s nhung dem duoc %d' % (r[3], len(parsed[i])),
            'key_trung': ', '.join(dup),
            'mau_thuan': ' | '.join(conflict),
            'filter_thieu': ', '.join(missing),
            'filter_bo_sung': ' | '.join('%s: %s' % (k, v) for k, v, _s in filled),
            'nguon_suy': ' | '.join('%s <- %s' % (k, s) for k, _v, s in filled),
            'can_tra_cuu': ', '.join(need_lookup),
            'goi_y_tham_khao': ' | '.join(ref),
            'filter_nghi_thua': ' | '.join(odd),
            'filter_thieu_ca_cum': ' | '.join(tier_b),
            'e_de_xuat': ' | '.join('%s: %s' % (k, v) for k, v in merged) if (missing or empty) else '',
        })
    ginfo = []
    seen = set()
    want = {r['cluster'] for r in results}
    for g, (v, nb) in grp_attr_vote.items():
        for cid in grp_clusters[g]:
            if not cid.startswith('L1') or cid not in want or cid in seen or len(clusters[cid]) < min_peers:
                continue
            seen.add(cid)
            sch = schema_cache[cid][0]
            for k, c in v.items():
                if k not in sch and c / nb >= 0.8:
                    ginfo.append([g, cid[3:], len(clusters[cid]), k, '%.0f%%' % (100 * c / nb)])
    ginfo.sort(key=lambda x: (-x[2], x[0]))
    return results, conv, ginfo

# ---------- xuat Excel ----------
COLS = [
    ('part_id', 'part_id', 10), ('ma', 'ma_san_pham', 18),
    ('ten', 'C: ten_san_pham (goc)', 60),
    ('ten_de_xuat', 'C DE XUAT SUA', 60), ('loi_ten', 'Loi ten (ly do)', 30),
    ('mau_thuan', 'MAU THUAN C <-> E', 50),
    ('so_luong_filter', 'D goc', 7), ('d_lech', 'D sai so luong', 22),
    ('filter_goc', 'E: filter goc', 70),
    ('e_rong', 'E RONG', 7),
    ('filter_thieu', 'FILTER THIEU (so voi peer)', 40),
    ('filter_bo_sung', 'FILTER BO SUNG (key: value)', 70),
    ('nguon_suy', 'Nguon suy gia tri', 50),
    ('can_tra_cuu', 'CAN TRA CUU (khong suy duoc)', 40),
    ('goi_y_tham_khao', 'Gia tri tham khao (CHUA ap dung)', 45),
    ('e_de_xuat', 'E DE XUAT (day du)', 90),
    ('filter_nghi_thua', 'Filter nghi thua/sai', 35),
    ('key_trung', 'Key trung lap', 20),
    ('filter_thieu_ca_cum', 'Ca cum thieu (>=80% cum khac co)', 45),
    ('group', 'Nhom', 18), ('cluster', 'Cum', 45),
    ('level', 'Peer level', 8), ('n_peer', 'So peer', 8),
]

def export(res, path, clusters_info=None):
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'audit'
    hdr = Font(bold=True, color='FFFFFF')
    fill = PatternFill('solid', fgColor='2F5597')
    fill2 = PatternFill('solid', fgColor='C00000')
    for j, (_k, label, w) in enumerate(COLS, 1):
        c = ws.cell(1, j, label)
        c.font = hdr
        c.fill = fill2 if label.isupper() or label.split(' ')[0].isupper() else fill
        c.alignment = Alignment(vertical='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = 'D2'
    for i, r in enumerate(res, 2):
        for j, (k, _l, _w) in enumerate(COLS, 1):
            ws.cell(i, j, r.get(k))
    ws.auto_filter.ref = 'A1:%s%d' % (get_column_letter(len(COLS)), len(res) + 1)

    s2 = wb.create_sheet('tong_hop')
    stats = [
        ('Tong dong audit', len(res)),
        ('E rong hoan toan (N/A)', sum(1 for r in res if r['e_rong'])),
        ('D sai so luong filter', sum(1 for r in res if r['d_lech'])),
        ('Ten C de xuat sua', sum(1 for r in res if r['ten_de_xuat'])),
        ('Mau thuan C <-> E', sum(1 for r in res if r['mau_thuan'])),
        ('Dong thieu filter (so voi peer)', sum(1 for r in res if r['filter_thieu'])),
        ('  -> bo sung duoc gia tri', sum(1 for r in res if r['filter_bo_sung'])),
        ('  -> can tra cuu them', sum(1 for r in res if r['can_tra_cuu'])),
        ('Filter nghi thua/sai', sum(1 for r in res if r['filter_nghi_thua'])),
        ('Key trung lap', sum(1 for r in res if r['key_trung'])),
        ('Ca cum thieu filter', sum(1 for r in res if r['filter_thieu_ca_cum'])),
    ]
    s2.append(['Chi tieu', 'So dong'])
    s2['A1'].font = Font(bold=True); s2['B1'].font = Font(bold=True)
    for a, b in stats:
        s2.append([a, b])
    s2.column_dimensions['A'].width = 40
    s2.column_dimensions['B'].width = 12

    if clusters_info:
        s3 = wb.create_sheet('gap_theo_cum')
        s3.append(['Nhom', 'Cum (skeleton ten)', 'So dong', 'Filter ca cum THIEU', '% cum khac trong nhom co'])
        for c in s3[1]:
            c.font = Font(bold=True)
        for row in clusters_info:
            s3.append(row)
        for col, w in zip('ABCDE', (18, 60, 9, 45, 22)):
            s3.column_dimensions[col].width = w
        s3.auto_filter.ref = 'A1:E%d' % (len(clusters_info) + 1)
    wb.save(path)
    return path


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('xlsx')
    ap.add_argument('--group')
    ap.add_argument('--out')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--xlsx-out', dest='xlsx_out')
    ap.add_argument('--name-col', type=int, help='vi tri cot ten (0-based), neu tu do sai')
    ap.add_argument('--filter-col', type=int, help='vi tri cot filter (0-based)')
    ap.add_argument('--cat-col', type=int, help='vi tri cot nhom hang/category')
    ap.add_argument('--no-cat', action='store_true', help='bo qua cot category, suy nhom tu key')
    a = ap.parse_args()
    overrides = {'name': a.name_col, 'filt': a.filter_col, 'cat': a.cat_col}
    res, conv, ginfo = audit(a.xlsx, a.group, a.out, limit=a.limit,
                             overrides=None if a.no_cat else overrides)
    pickle.dump((res, ginfo), open((a.out or 'artifacts/filter-audit/res') + '.pkl', 'wb'))
    print('rows audited:', len(res))
    if a.xlsx_out:
        export(res, a.xlsx_out, ginfo)
        print('written:', a.xlsx_out)
