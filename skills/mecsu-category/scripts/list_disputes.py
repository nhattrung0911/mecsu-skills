"""Build the worklist for pairs the models disagreed about. No network, no model calls.

Splits the disputes into the two kinds that need different handling, and for the researchable ones
extracts the manufacturer code to search for. The searching itself is the agent's job, with its own
web search tool, working down the list until the covered-rows target is met.

Scraping a search engine from here was tried and abandoned: it got the IP blocked and returned
nothing for 73 of 73 lookups. A handful of deliberate searches on the highest-impact pairs beats
an automated sweep that gets throttled into silence.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from common import fold, job_root, pair_key, write_rows

ROOT = job_root()
DEFAULT_DIR = ROOT / "jobs" / "oncheck"

# Dimensions look like part codes but identify nothing: M3x6, 4.8x25mm, 15x35x11.75, 1/4-20.
DIMENSION = re.compile(
    r"^(m?\d+([.,]\d+)?([x×]\d+([.,]\d+)?)+(mm|cm|m)?"
    r"|m\d+([.,]\d+)?"
    r"|\d+/\d+(-\d+)?"
    r"|\d+([.,]\d+)?(mm|cm|m|kg|g|w|v|a|inch|in)"
    r"|#\d+-\d+)$",
    re.I,
)
NOT_BRAND = {"dong", "series", "loai", "model", "ma", "type", "kieu", "so"}


def query_for(description: str) -> str:
    """The manufacturer code plus its brand - what actually identifies the product."""
    tokens = [t.strip(" ,.()[]") for t in description.split()]
    tokens = [t for t in tokens if t]

    def is_code(token: str) -> bool:
        if DIMENSION.match(token) or "/" in token:
            return False
        letters = sum(c.isalpha() for c in token)
        digits = sum(c.isdigit() for c in token)
        if letters >= 1 and digits >= 1 and len(token) >= 3:
            return True  # BS365017, PVU4SUS
        if token.isupper() and "-" in token and letters >= 3:
            return True  # SSH-EL
        return digits >= 4 and letters == 0  # SATA 47208, Koyo 30202

    codes = [t for t in tokens if is_code(t)]
    if not codes:
        return " ".join(tokens[:8])

    code = codes[-1]
    brand = ""
    for previous in reversed(tokens[: tokens.index(code)]):
        if is_code(previous) or fold(previous) in NOT_BRAND or not previous[:1].isupper():
            continue
        if any(c.isdigit() for c in previous) or len(previous) < 2:
            continue
        brand = previous
        break
    return f"{brand} {code}".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_DIR / "ai_queue.json")
    parser.add_argument("--verdicts", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    pairs = {pair_key(p): p for p in queue["pairs"]}
    resolvers = {lv: {fold(n): n for n in names} for lv, names in queue["leaf_catalog"].items()}
    total_rows = queue["total_rows"]

    sources = [
        (path.stem.replace("ai_verdicts_", ""), json.loads(path.read_text(encoding="utf-8")))
        for path in args.verdicts
    ]

    def target_of(verdict: dict, level1: str) -> str:
        if str(verdict.get("verdict")) != "wrong":
            return ""
        return resolvers.get(level1, {}).get(fold(str(verdict.get("suggested_category") or "").strip()), "")

    researchable, gaps = [], []
    for key, pair in pairs.items():
        level1 = pair["level1_category_name"]
        opinions = []
        for name, source in sources:
            verdict = source.get(key, {})
            opinions.append(
                {
                    "model": name,
                    "verdict": str(verdict.get("verdict", "")),
                    "confidence": verdict.get("confidence", ""),
                    "suggested": target_of(verdict, level1),
                    "reason": verdict.get("reason", ""),
                }
            )
        if len({o["verdict"] for o in opinions}) == 1 and len({o["suggested"] for o in opinions}) == 1:
            continue

        entry = {
            "pair_id": pair["pair_id"],
            "level1_category_name": level1,
            "description": pair["sample_description"],
            "current_leaf_name": pair["leaf_category_name"].strip(),
            "row_count": pair["row_count"],
            "search_query": query_for(pair["sample_description"]),
            "opinions": opinions,
        }
        # An "unsure", or a "wrong" with no valid replacement, means the taxonomy has no home for
        # this product. No amount of searching conjures a category that does not exist.
        gap = any(o["verdict"] == "unsure" for o in opinions) or any(
            o["verdict"] == "wrong" and not o["suggested"] for o in opinions
        )
        (gaps if gap else researchable).append(entry)

    researchable.sort(key=lambda e: -e["row_count"])
    gaps.sort(key=lambda e: -e["row_count"])

    args.output_dir.mkdir(parents=True, exist_ok=True)
    todo_path = args.output_dir / "disputes_to_research.json"
    gap_path = args.output_dir / "taxonomy_gaps.json"
    todo_path.write_text(json.dumps(researchable, ensure_ascii=False, indent=2), encoding="utf-8")
    gap_path.write_text(json.dumps(gaps, ensure_ascii=False, indent=2), encoding="utf-8")

    write_rows(
        args.output_dir / "disputes_to_research.xlsx",
        [
            (
                e["pair_id"], e["level1_category_name"], e["description"], e["current_leaf_name"],
                e["search_query"],
                " | ".join(f"{o['model']}:{o['verdict']}->{o['suggested'] or '-'}" for o in e["opinions"]),
                " | ".join(f"{o['model']}: {o['reason']}" for o in e["opinions"]),
                e["row_count"],
            )
            for e in researchable
        ],
        ["pair_id", "level1_category_name", "description", "current_leaf_name",
         "search_query", "opinions", "reasons", "row_count"],
        sheet="disputes",
    )

    research_rows = sum(e["row_count"] for e in researchable)
    gap_rows = sum(e["row_count"] for e in gaps)
    print(f"disputed pairs {len(researchable) + len(gaps)}, {research_rows + gap_rows} rows"
          f" ({(research_rows + gap_rows) / total_rows:.1%} of the workbook)")
    print(f"  researchable   {len(researchable):>4} pairs, {research_rows:>4} rows -> {todo_path.name}")
    print(f"  taxonomy gaps  {len(gaps):>4} pairs, {gap_rows:>4} rows -> {gap_path.name} (leave for a human)")

    if researchable:
        print("\nrows covered if you search the top N pairs:")
        running = 0
        for index, entry in enumerate(researchable, start=1):
            running += entry["row_count"]
            if index in (5, 10, 15, 20, 30) or index == len(researchable):
                print(f"  top {index:>3} -> {running:>4}/{research_rows} rows ({running / research_rows:.0%})")

        print("\nhighest impact first:")
        for entry in researchable[:10]:
            opinions = " | ".join(
                f"{o['model'][-6:]}:{o['verdict']}->{o['suggested'] or '-'}" for o in entry["opinions"]
            )
            print(f"  n={entry['row_count']:<4} [{entry['search_query']}] {entry['description'][:52]}")
            print(f"        now={entry['current_leaf_name']}  || {opinions}")

    print(
        "\nSearch these codes yourself, then write jobs/oncheck/dispute_resolution.json:\n"
        '  {"<pair_id>": {"decision": "keep"|"change", "new_leaf_name": "...", "new_leaf_id": <id>,\n'
        '                 "confidence": 0.0-1.0, "reason": "which evidence decided it"}}\n'
        "Anything you leave out keeps its current category. Record no decision the evidence\n"
        "does not support - a pair left alone is safe, a wrong ruling is applied to every row."
    )


if __name__ == "__main__":
    main()
