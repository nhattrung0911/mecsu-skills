"""Step 1: deterministic lexical check of part_description against leaf_category_name.

Produces a per-row verdict plus a deduplicated queue of pairs that need AI judgement.
No model calls, no cost.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from common import HEADERS, SHEET, fold, job_root, pattern, read_rows, verdict_key, write_rows

ROOT = job_root()
DEFAULT_INPUT = ROOT / "jobs" / "inbox" / "On_web_category.xlsx"
DEFAULT_OUTPUT = ROOT / "jobs" / "oncheck"

# Words carrying no discriminating power when matching a leaf name to a description.
NOISE = {
    "bo", "cai", "loai", "va", "cho", "co", "khong", "cac", "dang", "kieu",
    "phu", "kien", "linh", "vat", "tu", "dung", "cu", "san", "pham", "thiet", "bi",
}

VERDICTS = ("EXACT", "ALL_WORDS", "PARTIAL", "NO_OVERLAP")


def content_words(text: str) -> list[str]:
    return [w for w in fold(text).split() if w not in NOISE and len(w) > 1 and not any(c.isdigit() for c in w)]


def phrase_in(needle: str, haystack: str) -> bool:
    if not needle:
        return False
    return f" {needle} " in f" {haystack} "


def judge(description: object, leaf_name: object) -> tuple[str, float]:
    desc = fold(description)
    leaf = fold(leaf_name)
    if phrase_in(leaf, desc):
        return "EXACT", 1.0

    leaf_words = content_words(leaf_name)
    if not leaf_words:
        return "NO_OVERLAP", 0.0

    desc_words = set(content_words(description))
    hits = sum(word in desc_words for word in leaf_words)
    score = hits / len(leaf_words)
    if hits == len(leaf_words):
        return "ALL_WORDS", score
    if hits == 0:
        return "NO_OVERLAP", 0.0
    return "PARTIAL", score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sheet", default=SHEET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--queue-verdicts",
        default="PARTIAL,NO_OVERLAP",
        help="Verdicts sent to the AI queue (comma separated).",
    )
    parser.add_argument("--level1", help="Only process this level1_category_name.")
    args = parser.parse_args()

    queued = {v.strip().upper() for v in args.queue_verdicts.split(",") if v.strip()}
    unknown = queued - set(VERDICTS)
    if unknown:
        raise SystemExit(f"Unknown verdict(s): {sorted(unknown)}; allowed: {VERDICTS}")

    rows = read_rows(args.input, args.sheet)
    if args.level1:
        rows = [r for r in rows if str(r.level1_name) == args.level1]
        if not rows:
            raise SystemExit(f"No rows for level1_category_name={args.level1!r}")

    report = []
    by_level1: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    pairs: dict[tuple[str, str], dict] = {}
    # Every leaf actually in use under each level1, so the model can only suggest real ones.
    # A name can map to SEVERAL ids: the source reuses 5 leaf names under two different ids each.
    # Keep every id, or rows carrying the loser fail validation and fixes get an arbitrary id.
    catalog: dict[str, dict[str, set]] = collections.defaultdict(lambda: collections.defaultdict(set))

    depth_by_id: dict[str, object] = {}

    for row in rows:
        catalog[str(row.level1_name)][str(row.leaf_name).strip()].add(row.leaf_id)
        depth_by_id[str(row.leaf_id)] = row.leaf_depth
        verdict, score = judge(row.description, row.leaf_name)
        report.append((*row.as_tuple(), verdict, round(score, 3)))
        by_level1[str(row.level1_name)][verdict] += 1
        if verdict not in queued:
            continue
        key = (pattern(row.description), fold(row.leaf_name))
        entry = pairs.get(key)
        if entry is None:
            pairs[key] = {
                # `pair_id` chi de danh so trong prompt cho model doc; no doi khi input doi.
                # `key_hash` moi la khoa cua verdict — theo noi dung cap, khong theo thu tu.
                "pair_id": len(pairs) + 1,
                "key_hash": verdict_key(row.description, row.leaf_name),
                "sample_description": str(row.description),
                "leaf_category_id": row.leaf_id,
                "leaf_category_name": str(row.leaf_name),
                "level1_category_name": str(row.level1_name),
                "rule_verdict": verdict,
                "rule_score": round(score, 3),
                "row_count": 1,
                "part_ids": [row.part_id],
            }
        else:
            entry["row_count"] += 1
            if len(entry["part_ids"]) < 5:
                entry["part_ids"].append(row.part_id)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "rule_report.xlsx"
    write_rows(report_path, report, HEADERS + ["rule_verdict", "rule_score"], sheet="rule_report")

    queue = sorted(pairs.values(), key=lambda item: -item["row_count"])
    queue_path = args.output_dir / "ai_queue.json"
    queue_path.write_text(
        json.dumps(
            {
                "source": args.input.name,
                "level1_filter": args.level1,
                "queued_verdicts": sorted(queued),
                "total_rows": len(rows),
                "queued_rows": sum(item["row_count"] for item in queue),
                "leaf_catalog": {
                    level1: sorted(names) for level1, names in sorted(catalog.items())
                },
                "leaf_ids": {
                    level1: {name: sorted(names[name], key=str) for name in sorted(names)}
                    for level1, names in sorted(catalog.items())
                },
                # A row that moves to another leaf must take that leaf's depth with it.
                "leaf_depth_by_id": dict(sorted(depth_by_id.items())),
                "ambiguous_leaf_names": {
                    level1: {name: sorted(ids, key=str) for name, ids in sorted(names.items()) if len(ids) > 1}
                    for level1, names in sorted(catalog.items())
                    if any(len(ids) > 1 for ids in names.values())
                },
                "pairs": queue,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    totals = collections.Counter()
    for counter in by_level1.values():
        totals.update(counter)

    print(f"{'level1':<28}" + "".join(f"{v:>12}" for v in VERDICTS) + f"{'rows':>9}")
    for level1, counter in sorted(by_level1.items(), key=lambda item: -sum(item[1].values())):
        line = f"{level1[:27]:<28}" + "".join(f"{counter[v]:>12}" for v in VERDICTS)
        print(line + f"{sum(counter.values()):>9}")
    print(f"{'TOTAL':<28}" + "".join(f"{totals[v]:>12}" for v in VERDICTS) + f"{len(rows):>9}")

    reduction = len(queue) / max(1, sum(item["row_count"] for item in queue))
    print(
        f"\nrule_report -> {report_path}"
        f"\nai_queue    -> {queue_path}"
        f"\n{sum(item['row_count'] for item in queue)} flagged rows collapse to {len(queue)} unique pairs"
        f" ({reduction:.1%} of flagged rows need a model call)"
    )


if __name__ == "__main__":
    main()
