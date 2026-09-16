# -*- coding: utf-8 -*-
"""Sinh phan skill cua website tu chinh thu muc skills/.

    python tools/sync_site.py            # cap nhat site/
    python tools/sync_site.py --check    # chi kiem tra, lech thi thoat khac 0

Nguon su that la `skills/<ten>/SKILL.md` (frontmatter `name` + `description`). Muon doi
cach trang gioi thieu skill thi them `skills/<ten>/website.json`:

    {"title": "...", "purpose": "...", "prompt": "..."}

Khong co file do thi lay tam `description` trong SKILL.md. Phan HTML sinh ra nam giua hai
moc `<!-- skills:start -->` va `<!-- skills:end -->`; moi thu ngoai hai moc do viet tay,
script khong dung toi.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from html import escape
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):      # ten skill co dau, console Windows la cp1252
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

START = "<!-- skills:start -->"
END = "<!-- skills:end -->"
CONTRACT = "2.0"


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise SystemExit(f"{path} thieu frontmatter YAML")
    block = text.split("---", 2)[1]
    fields, key = {}, None
    for line in block.splitlines():
        if not line.strip():
            continue
        matched = re.match(r"^([a-zA-Z0-9_-]+):\s*(.*)$", line)
        if matched:
            key, value = matched.group(1), matched.group(2).strip()
            fields[key] = value.strip('"\'')
        elif key:                            # dong noi tiep cua gia tri nhieu dong
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def skills_of(root: Path) -> list[dict]:
    out = []
    for folder in sorted(p for p in (root / "skills").iterdir() if (p / "SKILL.md").exists()):
        meta = frontmatter(folder / "SKILL.md")
        site_file = folder / "website.json"
        site = json.loads(site_file.read_text(encoding="utf-8")) if site_file.exists() else {}
        out.append({
            "skill_id": folder.name,
            "public_title": site.get("title", meta.get("name", folder.name)),
            "purpose": site.get("purpose", meta.get("description", "")),
            "onboarding_prompt": site.get("prompt", f"Dùng skill {folder.name} cho file của tôi."),
            "website_section": folder.name,
            "contract_version": CONTRACT,
            # Chi README dung. Khong co thi lay tam purpose - README van du ten skill,
            # chi la cot do noi chung chung hon.
            "readme_question": site.get("readme_question",
                                        site.get("purpose", meta.get("description", ""))),
            "readme_output": site.get("readme_output", "—"),
            "readme_needs": site.get("readme_needs", "—"),
        })
    return out


CATALOG_KEYS = ("skill_id", "public_title", "purpose", "onboarding_prompt",
                "website_section", "contract_version")


def catalog_text(skills: list[dict]) -> str:
    # Catalog la hop dong cua trang public: chi sau khoa nay, khong day them field
    # rieng cua README vao.
    trimmed = [{key: skill[key] for key in CATALOG_KEYS} for skill in skills]
    return json.dumps({"skills": trimmed}, ensure_ascii=False, indent=2) + "\n"


def sections_html(skills: list[dict]) -> str:
    blocks = []
    for index, skill in enumerate(skills, 1):
        shade = " section-muted" if index % 2 == 0 else ""
        blocks.append(
            f'      <section id="{escape(skill["website_section"])}" class="section-shell{shade}"'
            f' data-skill-id="{escape(skill["skill_id"])}">\n'
            f'        <div class="section-heading compact-heading"><p class="eyebrow">Skill {index}</p>'
            f'<h2>/{escape(skill["skill_id"])} — {escape(skill["public_title"])}.</h2>'
            f'<p>{escape(skill["purpose"])}</p></div>\n'
            f'        <div class="prompt-card prompt-card-light">\n'
            f'          <template id="prompt-{escape(skill["skill_id"])}">'
            f'{escape(skill["onboarding_prompt"])}</template>\n'
            f'          <p class="prompt-text">{escape(skill["onboarding_prompt"])}</p>\n'
            f'          <button class="button button-outline" type="button"'
            f' data-copy-prompt="{escape(skill["skill_id"])}">Sao chép yêu cầu chạy</button>\n'
            f'        </div>\n'
            f'      </section>'
        )
    return "\n".join(blocks)


def rendered_index(root: Path, skills: list[dict]) -> str:
    path = root / "site" / "index.html"
    html = path.read_text(encoding="utf-8")
    if START not in html or END not in html:
        raise SystemExit(f"{path} thieu moc {START} / {END}")
    head, rest = html.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{sections_html(skills)}\n      {END}{tail}"


def splice(text: str, path: Path, name: str, body: str) -> str:
    """Thay doan giua hai moc mang ten `name`, giu nguyen chu hai ben."""
    start, end = f"<!-- skills:{name}:start -->", f"<!-- skills:{name}:end -->"
    if start not in text or end not in text:
        raise SystemExit(f"{path} thieu moc {start} / {end}")
    head, rest = text.split(start, 1)
    _, tail = rest.split(end, 1)
    return f"{head}{start}\n{body}\n{end}{tail}"


def readme_run(skills: list[dict], duong_dan: str = "d:/file.xlsx") -> str:
    width = max(len(s["skill_id"]) for s in skills)
    lines = "\n".join(f"/{s['skill_id']:<{width}}  {duong_dan}" for s in skills)
    return f"```\n{lines}\n```"


def readme_table(skills: list[dict]) -> str:
    rows = "\n".join(
        "| `/{id}` | {question} | {output} | [SKILL.md](skills/{id}/SKILL.md) |".format(
            id=skill["skill_id"], question=skill["readme_question"], output=skill["readme_output"])
        for skill in skills)
    return ("| Skill | Trả lời câu hỏi | Ra file | Luật |\n"
            "|---|---|---|---|\n" + rows)


def rendered_readme(root: Path, skills: list[dict]) -> str:
    path = root / "README.md"
    text = path.read_text(encoding="utf-8")
    text = splice(text, path, "run", readme_run(skills))
    return splice(text, path, "bang", readme_table(skills))


def agents_table(skills: list[dict]) -> str:
    rows = "\n".join(
        "| `/{id}` | {question} | {needs} |".format(
            id=skill["skill_id"], question=skill["readme_question"], needs=skill["readme_needs"])
        for skill in skills)
    return ("| Lệnh | Trả lời câu hỏi | Cần cột gì trong file |\n"
            "|---|---|---|\n" + rows)


def rendered_agents(root: Path, skills: list[dict]) -> str:
    path = root / "AGENTS.md"
    text = path.read_text(encoding="utf-8")
    text = splice(text, path, "run", readme_run(skills, "d:/duong-dan/file.xlsx"))
    return splice(text, path, "bang", agents_table(skills))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check", action="store_true", help="Chi bao lech, khong ghi de.")
    args = parser.parse_args()

    skills = skills_of(args.root)
    targets = {
        args.root / "site" / "public-skill-catalog.json": catalog_text(skills),
        args.root / "site" / "index.html": rendered_index(args.root, skills),
        args.root / "README.md": rendered_readme(args.root, skills),
        args.root / "AGENTS.md": rendered_agents(args.root, skills),
    }

    stale = [path for path, wanted in targets.items()
             if path.read_text(encoding="utf-8") != wanted]
    if args.check:
        for path in stale:
            print(f"LECH: {path.relative_to(args.root)}")
        if stale:
            raise SystemExit(
                f"\n{len(stale)} file cua site khong khop skills/. Chay: python tools/sync_site.py")
        print(f"site khop {len(skills)} skill")
        return

    for path in stale:
        path.write_text(targets[path], encoding="utf-8")
        print(f"cap nhat {path.relative_to(args.root)}")
    print(f"{len(skills)} skill tren site: {', '.join(s['skill_id'] for s in skills)}")


if __name__ == "__main__":
    main()
