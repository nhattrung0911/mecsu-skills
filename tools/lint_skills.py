# -*- coding: utf-8 -*-
"""Kiem tra skill bang script, khong goi model - 0 token.

    python tools/lint_skills.py

Bat cac loi lam skill hong ma khong ai thay: link chet, lenh trong tai lieu tro
vao script khong ton tai, co trong tai lieu ma argparse khong nhan, description
qua dai, doc dai khong co muc luc. Exit khac 0 neu co loi.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'skills'

MAX_DESCRIPTION = 500          # khuyen nghi Anthropic
MAX_SKILL_LINES = 500          # nguong hieu nang cua SKILL.md
MIN_LINES_FOR_TOC = 100        # file tham chieu dai hon thi phai co muc luc

LINK = re.compile(r'\[[^\]]*\]\(([^)#][^)]*)\)')
COMMAND = re.compile(r'python\s+(\S*?)([A-Za-z_0-9]+\.py)((?:\s+[^\n`]*)?)')
FLAG = re.compile(r'(?<![-\w])--[a-z][a-z0-9-]*')
STALE = {
    '.agents/skills': 'duong dan cua ban skill cu',
    'jobs/oncheck/$J': 'duong dan job hardcode',
    'chuan-hoa-filter': 'ten skill cu',
    '```powershell': 'khoi PowerShell - dung bash cho chay duoc moi noi',
}


def frontmatter(text: str) -> dict:
    if not text.startswith('---'):
        return {}
    block = text.split('---', 2)[1]
    out, key = {}, None
    for line in block.splitlines():
        if re.match(r'^[a-z-]+:', line):
            key, _, value = line.partition(':')
            out[key.strip()] = value.strip()
        elif key and line.strip():
            out[key] += ' ' + line.strip()
    return out


def script_flags(path: Path) -> set[str]:
    """Co ma argparse cua script that su nhan."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    flags = {'--help'}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'add_argument'):
            for argument in node.args:
                if isinstance(argument, ast.Constant) and str(argument.value).startswith('--'):
                    flags.add(argument.value)
    return flags


def check(skill: Path, fail) -> None:
    name = skill.name
    main = skill / 'SKILL.md'
    if not main.exists():
        return fail(name, 'thieu SKILL.md')
    text = main.read_text(encoding='utf-8')
    meta = frontmatter(text)

    if meta.get('name') != name:
        fail(name, 'frontmatter name=%r khac ten thu muc' % meta.get('name'))
    description = meta.get('description', '')
    if not description:
        fail(name, 'thieu description')
    elif len(description) > MAX_DESCRIPTION:
        fail(name, 'description %d ky tu > %d' % (len(description), MAX_DESCRIPTION))
    for person in (' I ', 'I can ', 'you can ', 'You can '):
        if person in description:
            fail(name, 'description khong o ngoi thu ba: %r' % person)

    docs = sorted(skill.glob('*.md'))
    for doc in docs:
        body = doc.read_text(encoding='utf-8')
        lines = body.count('\n') + 1
        if doc == main and lines > MAX_SKILL_LINES:
            fail(name, 'SKILL.md %d dong > %d' % (lines, MAX_SKILL_LINES))
        if doc != main and lines > MIN_LINES_FOR_TOC and 'Mục lục' not in body and 'Contents' not in body:
            fail(name, '%s dai %d dong nhung khong co muc luc' % (doc.name, lines))
        for marker, why in STALE.items():
            if marker in body:
                fail(name, '%s con %r (%s)' % (doc.name, marker, why))
        for target in LINK.findall(body):
            if target.startswith(('http', '$', '{')):
                continue
            if not (doc.parent / target).exists():
                fail(name, '%s link chet -> %s' % (doc.name, target))
        for _, script, tail in COMMAND.findall(body):
            path = skill / 'scripts' / script
            if not path.exists():
                fail(name, '%s goi %s nhung script khong ton tai' % (doc.name, script))
                continue
            known = script_flags(path)
            for flag in FLAG.findall(tail):
                if flag not in known:
                    fail(name, '%s dung %s %s nhung argparse khong nhan' % (doc.name, script, flag))

    for script in sorted((skill / 'scripts').glob('*.py')):
        head = script.read_text(encoding='utf-8')[:2000]
        if 'print(' in head and 'reconfigure' not in head and '__main__' in script.read_text(encoding='utf-8'):
            fail(name, '%s in ra stdout nhung khong dat utf-8 (console Windows la cp1252)' % script.name)
    if not list(skill.glob('tests/test_*.py')):
        fail(name, 'khong co test nao')


def main() -> None:
    problems: list[tuple[str, str]] = []
    for skill in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        check(skill, lambda n, m: problems.append((n, m)))
    for skill, message in problems:
        print('%-16s %s' % (skill, message))
    print('\n%d loi' % len(problems))
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
