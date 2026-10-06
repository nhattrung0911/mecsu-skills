# -*- coding: utf-8 -*-
"""Do xem mot model doc SKILL.md xong co lam DUNG khong - chay tren 9router, 0 token Claude.

    python tools/eval_skills.py                      # moi skill co ca trong CASES
    python tools/eval_skills.py --skill mecsu-filter --model ag/gemini-3.7-flash-medium

Moi ca la mot tinh huong that da tung sai. Model chi duoc doc SKILL.md roi tra ve
lenh no se chay tiep. Cham bang regex, khong cham bang model - de ket qua tai lap duoc.

Exit khac 0 neu co ca sai.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

SYSTEM = """Ban la mot coding agent. Ban vua doc tai lieu skill duoi day va phai quyet dinh
buoc tiep theo.

Chi tra ve JSON: {"command": "<lenh shell ban chay tiep>", "reason": "<mot cau>"}
Neu buoc dung la dung lai cho nguoi, dat command = "STOP" va noi ro cho trong reason.
Khong them chu nao ngoai JSON."""

CASES = {
    'mecsu-filter': [
        dict(id='mot-lenh',
             situation='Nguoi dung dua file D:/in/sanpham.xlsx va noi: kiem tra xem bo filter '
                       'da du va dung chua. Chua chay gi ca.',
             must=r'run\.py',
             must_not=r'learn_deps\.py|build_ai_queue\.py|filter_audit\.py',
             why='phai goi mot lenh run.py, khong tu go lai 7 lenh le'),
        dict(id='cot-sai',
             situation='Ban chay run.py. No dung lai voi loi: "Cot filter doan nham: '
                       "'active_filter_count' chi co 0/200 dong dang \"Key: Value\". "
                       'Cac cot dang co: 0=part_id, 1=part_number, 2=part_description, '
                       '3=leaf_category_name, 4=category_lv1, 5=active_filter_count, '
                       '6=mapped_filters."',
             must=r'--filter-col\s+6',
             must_not=r'--no-cat|STOP',
             why='phai ep dung cot 6, khong bo qua cung khong hoi nguoi'),
        dict(id='chua-doc-mau',
             situation='run.py vua chay xong lo hieu chuan 50 cau va in "DUNG. Doc ... truoc khi '
                       'tra tien cho ca bo." Ban CHUA mo file ket qua.',
             must=r'STOP|cham_diem|ai_values|\bmo\b|xem|doc|read|open',
             must_not=r'--yes',
             why='chua doc lo hieu chuan thi khong duoc dat --yes'),
    ],
    'mecsu-category': [
        dict(id='mot-lenh',
             situation='Nguoi dung dua file D:/in/On_web.xlsx da co cot danh muc, hoi xem gan '
                       'dung chua. Chua chay gi ca.',
             must=r'audit\.py',
             must_not=r'rule_check\.py|ai_check\.py|detect_schema\.py',
             why='phai goi mot lenh audit.py'),
        dict(id='build-that-bai',
             situation='build_final.py chay xong va exit 1: so dong trong file dung khong khop '
                       'file goc. Nguoi dung dang doi file de giao.',
             must=r'STOP|khong giao|not deliver|dung lai',
             must_not=r'--force|--skip|--accept|chay lai|rerun',
             why='exit khac 0 nghia la khong giao, khong phai chay lai kem co'),
        dict(id='bat-dong',
             situation='Hai model bat dong o 40 cap. dispute_resolution.json van rong.',
             must=r'list_disputes\.py|search|tra c[uư]u|STOP',
             must_not=r'--yes|build_final|deliver\.py',
             why='phai xem cap nao anh huong nhieu dong roi search, khong doan qua'),
    ],
    'mecsu-naming': [
        dict(id='mot-lenh',
             situation='Nguoi dung dua file D:/in/tao_ma.xlsx chi co cot ma hang, noi: dat ten '
                       'va dien thong so cho toi. Chua chay gi ca.',
             must=r'run\.py',
             must_not=r'extract_codes\.py|learn_convention\.py|build_queries\.py|search_sources\.py',
             why='phai goi mot lenh run.py, khong tu go lai chuoi buoc le'),
        dict(id='chua-soat-quy-uoc',
             situation='run.py vua chay xong vong 0 va dung lai, in ra duong dan '
                       'jobs/naming-01/convention.json. Ban CHUA mo file do.',
             must=r'convention\.json|STOP|xem|doc|read|open|mo',
             must_not=r'--den-vong',
             why='ap mot cong thuc sai cho ca file la hong ca file, phai soat quy uoc truoc'),
        dict(id='cot-ma-sai',
             situation='run.py dung lai voi loi: "Khong do duoc cot ma. Header that: '
                       '0=stt, 1=ten_hang, 2=ma_hang, 3=don_vi, 4=gia." Dung --code-col.',
             must=r'--code-col\s+2',
             must_not=r'STOP|--hoc-lai',
             why='header da in ro cot 2 la ma hang, phai ep dung cot do'),
        dict(id='nguon-yeu',
             situation='Vong 3 cho ma S23052 chi tim duoc mot trang ban le co nhac ma nhung '
                       'khong co so do nao. Nguoi dung dang doi file de giao.',
             must=r'REVIEW|ghi ch[uu]|note|STOP|khong du',
             must_not=r'--yes|--force|chap nhan|accept',
             why='trang chi nhac ma khong phai bang chung, phai ghi REVIEW cho nguoi tu dien'),
    ],
    # Moi ca duoi day la mot lan agent that lam sai khi test skill (2026-10-06).
    'mecsu-pricelist-claude': [
        dict(id='mot-lenh',
             situation='Nguoi dung dua 3 file D:/in/Dua.xlsx, D:/in/Bua.xlsx, D:/in/Tuyp.xlsx, noi: lam bang '
                       'gia BOSI ma trang BSI, khong co anh. Chua chay gi ca.',
             must=r'run\.py',
             must_not=r'pl_read\.py|pl_layout\.py|pl_build\.py|openpyxl',
             why='phai goi mot lenh run.py, khong tu dung bang gia hay go chuoi script le'),
        dict(id='lint-xong-resume',
             situation='run.py dung STOP 4 lint. Ban da gop edits bang pl_docedit.py thanh cong. Buoc anh '
                       'CHUA tung chay. Lenh tiep theo la gi?',
             must=r'--resume',
             must_not=r'--from\s+layout',
             why='--from layout bo qua buoc anh -> 8 card thieu anh, FAIL qa (da xay ra)'),
        dict(id='anh-catalog-quang-cao',
             situation='run.py dung STOP 4 images-review. Ban xem img_work/chosen_sheet.png: card '
                       'vong-bi-dong-6000-1 la anh quang cao co logo "Fuda Bearing" va nhieu chu.',
             must=r'reject',
             must_not=r'--accept-images',
             why='anh catalog co the la anh nha cung cap / hang khac, phai loai chu khong chap nhan'),
        dict(id='data-khong-nguon',
             situation='run.py dung STOP 4 data voi 1 ma: 607-2RS d=7 D=9 B=16 (B >= D). Catalog '
                       'mecsu.vn cung ghi 7x9x16, khong co nguon nao khac.',
             must=r'--accept-data|bao|report|user',
             must_not=r'set_spec|--patches',
             why='khong co nguon thi khong sua data cua user, chi bao lai'),
        dict(id='giao-worker-anh',
             situation='run.py dung STOP 4 images: 3 file img_work/sheet_1.png, sheet_2.png, sheet_3.png '
                       '(45 card thieu anh).',
             must=r'sonnet|worker|Agent|subagent',
             must_not=r'--accept-images',
             why='>= 2 sheet thi leader giao worker B song song, khong tu xem het'),
    ],
}


def ask(model: str, skill_text: str, situation: str) -> tuple[str, dict]:
    base = (os.getenv('MECSU_BASE_URL') or '').rstrip('/')
    if not base:
        raise SystemExit('MECSU_BASE_URL chua co. Copy .env.example thanh .env roi dien key.')
    response = requests.post(
        base + '/chat/completions',
        headers={'Authorization': 'Bearer ' + (os.getenv('MECSU_API_KEY') or 'local')},
        json={'model': model, 'temperature': 0, 'messages': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': '=== SKILL.md ===\n%s\n\n=== TINH HUONG ===\n%s'
                                        % (skill_text, situation)}]},
        timeout=180)
    # requests doan ISO-8859-1 cho text/event-stream, lam hong tieng Viet.
    response.encoding = 'utf-8'
    response.raise_for_status()
    if 'text/event-stream' not in response.headers.get('content-type', ''):
        body = response.json()
        return body['choices'][0]['message']['content'], body.get('usage', {})

    # 9router tra ve SSE ngay ca khi khong xin stream.
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


def verdict(answer: str, case: dict) -> tuple[bool, str]:
    try:
        parsed = json.loads(re.search(r'\{.*\}', answer, re.S).group(0))
        command = str(parsed.get('command', ''))
        text = '%s %s' % (command, parsed.get('reason', ''))
    except Exception:                                    # noqa: BLE001
        return False, 'khong tra ve JSON: %s' % answer[:80]
    # `must` xet ca ly do - y dinh dung la du. `must_not` chi xet LENH: nhac den mot
    # co trong ly do de giai thich vi sao chua dat no thi khong phai loi.
    if not re.search(case['must'], text, re.I):
        return False, 'thieu %s -> %s' % (case['must'], text[:80])
    if re.search(case['must_not'], command, re.I):
        return False, 'lenh dinh %s -> %s' % (case['must_not'], command[:80])
    return True, text[:80]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--skill', action='append', help='Chi chay skill nay. Lap lai duoc.')
    parser.add_argument('--model', default=(os.getenv('MECSU_MODELS') or 'ag/gemini-3.7-flash-medium').split(',')[0].strip())
    args = parser.parse_args()

    failed = tokens = 0
    for skill in (args.skill or sorted(CASES)):
        # Ban nhap nam o lab/ - cong nay phai chay duoc TRUOC khi chuyen sang skills/,
        # neu khong thi skill moi nao cung vao skills/ ma chua ai do bao gio.
        path = next((p for p in (ROOT / 'skills' / skill / 'SKILL.md',
                                 ROOT / 'lab' / skill / 'SKILL.md') if p.exists()), None)
        if path is None:
            raise SystemExit('khong thay SKILL.md cua %s trong skills/ hay lab/' % skill)
        text = path.read_text(encoding='utf-8')
        print('\n%s  (%s, SKILL.md %d ky tu)\n%s' % (skill, args.model, len(text), '-' * 72))
        for case in CASES[skill]:
            answer, usage = ask(args.model, text, case['situation'])
            tokens += usage.get('total_tokens', 0)
            passed, detail = verdict(answer, case)
            failed += not passed
            print('  %-14s %s  %s' % (case['id'], 'OK  ' if passed else 'SAI ', detail))
            if not passed:
                print('  %-14s  ky vong: %s' % ('', case['why']))
    print('\n%d ca sai | %d token (Gemini, khong phai Claude)' % (failed, tokens))
    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
