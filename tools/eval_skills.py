# -*- coding: utf-8 -*-
"""Do xem mot model doc SKILL.md xong co lam DUNG khong - chay tren 9router, 0 token Claude.

    python tools/eval_skills.py                      # ca hai skill
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
        text = (ROOT / 'skills' / skill / 'SKILL.md').read_text(encoding='utf-8')
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
