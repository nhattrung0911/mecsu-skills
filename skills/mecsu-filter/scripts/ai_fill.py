# -*- coding: utf-8 -*-
"""Tang 3 - buoc 2: hoi model gia tri cho cac o filter con thieu.

Doc jobs/oncheck/ai_queue.json, ghi ai_values_<model>.json (resume duoc) va
ai_fill_report_<model>.xlsx. Cau hinh o .env canh file nay.

Hai thu quyet dinh chat luong, hoc tu skill category-assignment:
  1. Dua VON TU GIA TRI co that cua thuoc tinh do vao prompt, roi doi chieu lai
     cau tra loi voi von tu do. Khong lam vay thi model bia don vi/cach viet
     khong ton tai trong file ("M20x2.5" thay vi "2.5 mm").
  2. Moi request chi chua MOT (nhom hang, thuoc tinh), khong tron lan.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import json
import os
import pickle
import re
import threading
import time
from pathlib import Path

import requests
import skill_env

from verify_values import measure
import sys

if hasattr(sys.stdout, 'reconfigure'):      # console Windows mac dinh la cp1252
    sys.stdout.reconfigure(encoding='utf-8')

HERE = Path(__file__).resolve().parent
SEP = '\x1f'
ENUM_MAX = 40
_lock = threading.Lock()

SYSTEM_PROMPT = """Ban la ky su co khi phu trach du lieu san pham cong nghiep (thi truong Viet Nam).

Moi luot ban nhan cac san pham CUNG mot nhom hang. Moi muc can dien mot thuoc tinh filter.
Moi muc co:
- name: ten san pham day du (da chua tieu chuan, size, vat lieu)
- known: cac filter da biet chac cua san pham do
- need: ten thuoc tinh can dien

Nhiem vu: cho biet gia tri dung cua thuoc tinh `need`.

Nguyen tac:
- Uu tien suy tu TIEU CHUAN + SIZE trong `name`/`known`. Vi du bulong DIN 933 M20 co buoc ren
  tho 2.5 mm va size khoa 30 mm - day la so tra bang tieu chuan, khong phai phong doan.
- Viet gia tri DUNG DINH DANG nhu cac vi du trong `format_examples` (don vi, khoang trang,
  cach ghi so). Neu co `allowed_values`, BAT BUOC sao chep nguyen van mot gia tri trong do.
- Neu co BANG TRA TIEU CHUAN trong prompt: chi duoc dung so CO TRONG BANG. Bang khong co
  cot cho thuoc tinh dang hoi thi de TRONG - TUYET DOI khong tu che cong thuc.
  (Da bat duoc: bang DIN 912 khong co cot chieu dai ren, model bia "b=2d+24=96mm";
  cong thuc do khong ton tai, so dung la 2d+12=84mm.)
- Khong chac thi de value rong va confidence thap. Tra sai te hon bo trong.
- reason ngan gon tieng Viet, toi da 15 tu, neu can cu (tieu chuan nao, bang nao).

Tra ve DUY NHAT mot mang JSON, moi phan tu:
{"id": <int>, "value": "<gia tri hoac chuoi rong>", "confidence": <0.0-1.0>, "reason": "<ngan>"}

Khong them chu nao ngoai mang JSON."""


def load_config():
    """Key dien mot lan o .env goc plugin; NF_* trong .env cu van chay."""
    return skill_env.load_llm_config(legacy_prefix='NF', bat_buoc=False)


def read_completion(response):
    """9router tra ve SSE ngay ca khi khong yeu cau stream."""
    response.encoding = 'utf-8'
    if 'text/event-stream' not in response.headers.get('content-type', ''):
        body = response.json()
        return body['choices'][0]['message']['content'], body.get('usage', {})
    parts, usage = [], {}
    for line in response.text.splitlines():
        if not line.startswith('data:'):
            continue
        payload = line[5:].strip()
        if not payload or payload == '[DONE]':
            continue
        chunk = json.loads(payload)
        usage = chunk.get('usage') or usage
        for choice in chunk.get('choices', []):
            piece = choice.get('delta', {}).get('content')
            if piece:
                parts.append(piece)
    return ''.join(parts), usage


def parse_array(content):
    text = content.strip()
    fence = re.search(r'```(?:json)?\s*(.*?)```', text, re.S)
    if fence:
        text = fence.group(1).strip()
    i, j = text.find('['), text.rfind(']')
    if i == -1 or j == -1:
        raise ValueError('No JSON array in reply: ' + content[:200])
    return json.loads(text[i:j + 1])


def build_vocab(audit_pkl, enum_max=ENUM_MAX, examples=10):
    """Von tu gia tri co that, lay tu chinh file.

    Khoa chinh la (nhom, thuoc tinh). Khi nhom lay tu cot category thi so nhom
    tang manh (391 nhom o Fas+Hand) va nhieu cap (nhom, thuoc tinh) khong con du
    gia tri -> them von tu du phong theo RIENG thuoc tinh. Ten thuoc tinh da chua
    hau to `Of <Nhom>` nen van du cu the.
    """
    res, _g = pickle.load(open(audit_pkl, 'rb'))
    pair = collections.defaultdict(collections.Counter)
    solo = collections.defaultdict(collections.Counter)
    for row in res:
        for part in str(row['filter_goc']).split('|'):
            if ':' not in part:
                continue
            k, _, v = part.partition(':')
            k, v = k.strip(), v.strip()
            if k.upper() != 'N/A' and v:
                pair[(row['group'], k)][v] += 1
                solo[k][v] += 1

    def pack(counter):
        values = [v for v, _c in counter.most_common()]
        # Thuoc tinh DO LUONG (gia tri la so + don vi) khong duoc rang buoc cung.
        # Von tu chi chua gia tri DA CO trong file; ep chon trong do thi gia tri
        # dung nhung chua tung xuat hien se bi bo trong. Do duoc: 300 o bo trong,
        # bo rang buoc thi 12/12 o thu nghiem tra loi duoc va dung cong thuc.
        numeric = sum(1 for v in values if measure(v) is not None)
        if values and numeric / len(values) >= 0.8:
            return {'kind': 'format', 'values': values[:examples], 'all': set(values)}
        if len(values) <= enum_max:
            return {'kind': 'enum', 'values': sorted(values), 'all': set(values)}
        return {'kind': 'format', 'values': values[:examples], 'all': set(values)}

    vocab = {str(g) + SEP + a: pack(c) for (g, a), c in pair.items()}
    for attr, counter in solo.items():
        vocab.setdefault(SEP + attr, pack(counter))
    return vocab


def get_vocab(vocab, group, attr):
    """Von tu cua cap (nhom, thuoc tinh); khong co thi rot ve von tu cua thuoc tinh."""
    return vocab.get(str(group) + SEP + attr) or vocab.get(SEP + attr)


def load_standards(folder):
    """{slug: noi dung bang} tu references/standards/*.md.

    Model bo trong 305/988 cau vi khong nho bang tra. Dua thang bang vao prompt
    thi no tra loi duoc, va Claude cham cuoi doi chieu duoc voi cung bang do.
    """
    out = {}
    if not folder:
        return out
    for path in sorted(Path(folder).glob('*.md')):
        out[path.stem.lower().replace('-', ' ')] = path.read_text(encoding='utf-8')
    return out


def standards_for(batch, standards):
    """Bang tra ung voi tieu chuan cua chinh lo nay, khong dua ca kho."""
    want = set()
    for ask in batch:
        for key, value in ask['sample_known'].items():
            if 'Tiêu Chuẩn' not in key and 'Tiêu chuẩn' not in key:
                continue
            slug = str(value).lower().replace('-', ' ')
            slug = ' '.join(slug.split())
            if slug in standards:
                want.add(slug)
    return [standards[s] for s in sorted(want)]


def build_user_message(batch, group, vocabs, tables=()):
    """Mot request = MOT nhom hang, nhieu thuoc tinh.

    Gom theo (nhom, thuoc tinh) khien 8 cau hoi vo thanh 6 request, moi request
    cong nguyen system prompt + von tu: do duoc 2838 token/cau. Gom theo nhom roi
    dat von tu cua tung thuoc tinh trong cung mot request thi chi phi co dinh chia
    deu cho ca lo.
    """
    items = [{
        'id': a['ask_id'],
        'name': a['sample_name'],
        'known': a['sample_known'],
        'need': a['attr'],
    } for a in batch]
    lines = ['Nhom hang: ' + str(group), '']
    for table in tables:
        lines += ['--- BANG TRA TIEU CHUAN (dung so trong day, uu tien hon tri nho) ---',
                  table, '---', '']
    for attr in sorted({a['attr'] for a in batch}):
        v = vocabs.get(attr)
        if not v:
            continue
        label = ('allowed_values (BAT BUOC chon nguyen van 1 gia tri trong day)'
                 if v['kind'] == 'enum' else
                 'format_examples (gia tri co that, hay viet cung dinh dang)')
        lines.append('- ' + attr + ' | ' + label + ': '
                     + json.dumps(v['values'], ensure_ascii=False))
    lines += ['', 'Cac san pham can dien:', json.dumps(items, ensure_ascii=False)]
    return '\n'.join(lines)


class RateLimited(Exception):
    """9router tra 403 kem "reset after 1m 12s" khi bi bop, khong phai sai key.

    Backoff 1-2s cua retry thuong lam ca lo chet cung luc; phai cho dung thoi gian
    endpoint bao.
    """

    def __init__(self, seconds):
        super().__init__('rate limited, cho %ds' % seconds)
        self.seconds = seconds


RESET_HINT = re.compile(r'reset after\s*(?:(\d+)m)?\s*(?:(\d+)s)?', re.I)


def retry_after(response, default=75, cap=180):
    header = response.headers.get('Retry-After')
    if header and header.strip().isdigit():
        return min(int(header.strip()), cap)
    m = RESET_HINT.search(response.text or '')
    if m and (m.group(1) or m.group(2)):
        seconds = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
        return min(seconds + 5, cap)
    return default


def call_model(config, model, batch, group, vocabs, tables=(), retries=3):
    if not skill_env.co_llm(config):
        # Che do agent: cung SYSTEM_PROMPT, cung user message da gop lo. Cau tra loi
        # di qua dung parse_array nhu cua model - khong uu ai.
        noi_dung = skill_env.hoi_agent(SYSTEM_PROMPT,
                                       build_user_message(batch, group, vocabs, tables))
        return parse_array(noi_dung), {}
    payload = {
        'model': model,
        'temperature': config['temperature'],
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': build_user_message(batch, group, vocabs, tables)},
        ],
    }
    headers = {'Authorization': 'Bearer ' + config['api_key'], 'Content-Type': 'application/json'}
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(config['base_url'] + '/chat/completions', json=payload,
                              headers=headers, timeout=180)
            if r.status_code in (403, 429):
                raise RateLimited(retry_after(r))
            r.raise_for_status()
            content, usage = read_completion(r)
            return parse_array(content), usage
        except RateLimited as error:
            last = error
            if attempt < retries - 1:
                time.sleep(error.seconds)
        except Exception as error:  # noqa: BLE001
            last = error
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError('batch failed after %d attempts: %s' % (retries, last))


def shape(value):
    return re.sub(r'[\d.,]+', '#', value)


def validate(value, vocab):
    """Gia tri model tra ve co that/ dung dinh dang khong."""
    if not value:
        return 'EMPTY'
    if vocab is None:
        return 'NO_VOCAB'
    if vocab['kind'] == 'enum':
        return 'OK' if value in vocab['all'] else 'NOT_IN_VOCAB'
    if value in vocab['all']:
        return 'OK'
    shapes = {shape(s) for s in vocab['all']}
    return 'OK' if shape(value) in shapes else 'BAD_FORMAT'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--queue', type=Path, required=True)
    ap.add_argument('--audit', type=Path, required=True, help='de lay von tu gia tri')
    ap.add_argument('--output-dir', type=Path, required=True)
    ap.add_argument('--model')
    ap.add_argument('--attr', help='chi chay 1 thuoc tinh')
    ap.add_argument('--limit', type=int, help='chi chay N cau hoi dau (do gia truoc)')
    ap.add_argument('--restart', action='store_true')
    ap.add_argument('--standards', help='thu muc references/standards')
    ap.add_argument('--need-standard', action='store_true',
                    help='chi hoi cau co bang tra tieu chuan tuong ung (tiet kiem)')
    ap.add_argument('--retry-empty', action='store_true',
                    help='hoi lai nhung cau model da bo trong (kem bang tra)')
    args = ap.parse_args()

    config = load_config()
    model = args.model or config['models'][0]
    asks = json.loads(args.queue.read_text(encoding='utf-8'))['asks']
    if args.attr:
        asks = [x for x in asks if x['attr'] == args.attr]
    if args.limit:
        asks = asks[:args.limit]
    if not asks:
        raise SystemExit('Hang doi rong sau khi loc.')

    vocab = build_vocab(args.audit)
    standards = load_standards(args.standards)
    if standards:
        print('bang tra co san: %s' % ', '.join(sorted(standards)))
    slug = re.sub(r'[^a-z0-9]+', '-', model.lower()).strip('-')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output_dir / ('ai_values_' + slug + '.json')
    skill_env.chuan_bi(config, out_path)
    done = {}
    if out_path.exists() and not args.restart:
        done = json.loads(out_path.read_text(encoding='utf-8'))
        print('resume: da co %d cau tra loi' % len(done))

    def answered(ask):
        key = ask.get('key_hash', str(ask['ask_id']))
        if key not in done:
            return False
        if args.retry_empty and not str(done[key].get('value') or '').strip():
            return False
        return True

    todo = [x for x in asks if not answered(x)]
    if args.need_standard:
        before = len(todo)
        todo = [x for x in todo if standards_for([x], standards)]
        print('loc theo bang tra: %d -> %d cau' % (before, len(todo)))
    grouped = collections.defaultdict(list)
    for ask in todo:
        grouped[ask['group']].append(ask)
    batches = []
    for group, members in grouped.items():
        members.sort(key=lambda x: x['attr'])       # cung thuoc tinh nam canh nhau
        size = config['batch_size']
        batches += [(group, members[i:i + size]) for i in range(0, len(members), size)]
    print('model=%s  asks=%d  todo=%d  batches=%d' % (model, len(asks), len(todo), len(batches)))

    tokens = collections.Counter()
    failures = completed = 0
    started = time.time()

    def run(group, batch):
        vocabs = {}
        for attr in {a['attr'] for a in batch}:
            v = get_vocab(vocab, group, attr)
            if v:
                vocabs[attr] = {'kind': v['kind'], 'values': v['values']}
        return call_model(config, model, batch, group, vocabs,
                          standards_for(batch, standards))

    with concurrent.futures.ThreadPoolExecutor(max_workers=config['concurrency']) as pool:
        futures = {pool.submit(run, g, b): (g, b) for g, b in batches}
        for future in concurrent.futures.as_completed(futures):
            _g, batch = futures[future]
            try:
                answers, usage = future.result()
                for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                    tokens[key] += int(usage.get(key) or 0)
                by_id = {x['ask_id']: x for x in batch}
                for ans in answers:
                    ask = by_id.get(int(ans.get('id', -1)))
                    if ask:
                        done[ask.get('key_hash', str(ask['ask_id']))] = ans
            except skill_env.ThieuTraLoi:
                pass              # cho agent tra loi, KHONG phai that bai
            except Exception as error:  # noqa: BLE001
                failures += 1
                with _lock:
                    print('  batch %d that bai: %s' % (len(batch), error))
            completed += 1
            if completed % 5 == 0 or completed == len(batches):
                out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1),
                                    encoding='utf-8')
                with _lock:
                    print('  %d/%d batch, %d tra loi' % (completed, len(batches), len(done)))
    out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding='utf-8')
    skill_env.chot_hoi_dap('ai_fill')      # che do agent: thoat 4 neu con cau chua tra loi

    rows, stats = [], collections.Counter()
    for ask in asks:
        ans = done.get(ask.get('key_hash', str(ask['ask_id'])), {})
        value = str(ans.get('value') or '').strip()
        status = validate(value, get_vocab(vocab, ask['group'], ask['attr']))
        stats[status] += 1
        rows.append((ask['ask_id'], ask['group'], ask['attr'], ask['sample_name'],
                     json.dumps(ask['context'], ensure_ascii=False), value,
                     ans.get('confidence', ''), ans.get('reason', ''), status,
                     len(ask['rows'])))
    rows.sort(key=lambda r: (r[8] == 'OK', -r[9]))

    import openpyxl
    wb = openpyxl.Workbook(write_only=True)
    sheet = wb.create_sheet('ai_fill')
    sheet.append(['ask_id', 'nhom', 'thuoc_tinh', 'ten_mau', 'boi_canh', 'gia_tri_ai',
                  'confidence', 'ly_do', 'trang_thai', 'so_dong_anh_huong'])
    for row in rows:
        sheet.append(list(row))
    report = args.output_dir / ('ai_fill_report_' + slug + '.xlsx')
    wb.save(report)

    print('\ntrang thai: %s' % dict(stats))
    if todo:
        print('%d cau hoi trong %.0fs | tokens prompt=%d completion=%d total=%d (%.0f/cau)'
              % (len(todo), time.time() - started, tokens['prompt_tokens'],
                 tokens['completion_tokens'], tokens['total_tokens'],
                 tokens['total_tokens'] / max(1, len(todo))))
    print('\nvalues -> %s\nreport -> %s' % (out_path, report))
    if failures:
        # Exit 0 o day tung cho run.py di tiep: ai_values_*.json CO ton tai (rong `{}`),
        # nen verify/apply/build_review deu chay roi in "Xong." sau khi dien 0 o.
        raise SystemExit(
            '\n%d batch that bai. Cau tra loi da co van duoc giu — chay lai lenh cu de bu '
            '(no resume), roi moi di tiep.' % failures
        )


if __name__ == '__main__':
    main()
