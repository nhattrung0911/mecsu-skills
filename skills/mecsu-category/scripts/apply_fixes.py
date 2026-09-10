"""Step 3: fan the per-pair AI verdicts back out to all 67k rows.

Writes a full annotated workbook plus a fix sheet listing only the rows whose leaf category the
model rejected and for which it named a real replacement leaf. Nothing is auto-applied to the
source workbook; the fix sheet is the thing a human approves.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

from common import HEADERS, SHEET, fold, job_root, pair_key, pattern, read_rows, write_rows
from rule_check import judge

ROOT = job_root()
DEFAULT_DIR = ROOT / "jobs" / "oncheck"
DEFAULT_INPUT = ROOT / "jobs" / "inbox" / "On_web_category.xlsx"

# Catch-all leaves. Moving a product INTO one of these is a downgrade, not a fix.
GENERIC_LEAVES = ("other", "chua phan loai", "dang xu ly", "khac")


def is_generic(leaf_name: str) -> bool:
    folded = fold(leaf_name)
    return any(folded == g or folded.startswith(f"{g} ") for g in GENERIC_LEAVES)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sheet", default=SHEET)
    parser.add_argument("--queue", type=Path, default=DEFAULT_DIR / "ai_queue.json")
    parser.add_argument("--verdicts", type=Path, required=True, help="ai_verdicts_<model>.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=0.8,
        help="A 'wrong' verdict below this confidence goes to review instead of the fix sheet.",
    )
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    verdicts = json.loads(args.verdicts.read_text(encoding="utf-8"))
    catalog = queue["leaf_catalog"]
    leaf_ids = queue["leaf_ids"]
    resolvers = {level1: {fold(n): n for n in names} for level1, names in catalog.items()}

    # pair key -> verdict, so every row sharing a description pattern inherits one judgement.
    by_key: dict[tuple[str, str], dict] = {}
    for pair in queue["pairs"]:
        verdict = verdicts.get(pair_key(pair))
        if verdict:
            by_key[(pattern(pair["sample_description"]), fold(pair["leaf_category_name"]))] = verdict

    rows = read_rows(args.input, args.sheet)
    annotated = []
    fixes = []
    counts: collections.Counter = collections.Counter()

    for row in rows:
        rule_verdict, rule_score = judge(row.description, row.leaf_name)
        verdict = by_key.get((pattern(row.description), fold(row.leaf_name)), {})
        label = str(verdict.get("verdict", "")) if verdict else ""
        confidence = verdict.get("confidence", "") if verdict else ""

        level1 = str(row.level1_name)
        suggested = str(verdict.get("suggested_category") or "").strip() if verdict else ""
        resolved = resolvers.get(level1, {}).get(fold(suggested), "") if suggested else ""
        # A name the source reuses across ids resolves to nothing: there is no right id to pick.
        candidate_ids = leaf_ids.get(level1, {}).get(resolved, []) if resolved else []
        suggested_id = candidate_ids[0] if len(candidate_ids) == 1 else ""

        if not verdict:
            status = "PASS_RULE" if rule_verdict in ("EXACT", "ALL_WORDS") else "NOT_CHECKED"
        elif label == "correct":
            status = "AI_OK"
        elif label != "wrong":
            status = "REVIEW_UNSURE"
        elif resolved and fold(resolved) == fold(row.leaf_name):
            # Same leaf, different whitespace/casing - nothing to change.
            status = "AI_OK"
        elif not resolved:
            status = "REVIEW_WRONG_NO_TARGET"
        elif is_generic(resolved):
            # Never demote a specific leaf into a catch-all bucket.
            status = "REVIEW_GENERIC_TARGET"
        elif not suggested_id:
            # The name exists but under several ids; there is no way to choose.
            status = "REVIEW_AMBIGUOUS_TARGET"
        elif float(confidence or 0) < args.min_confidence:
            status = "REVIEW_LOW_CONFIDENCE"
        else:
            status = "FIX"
        counts[status] += 1

        annotated.append(
            (
                *row.as_tuple(),
                rule_verdict,
                round(rule_score, 3),
                label,
                confidence,
                verdict.get("reason", "") if verdict else "",
                resolved,
                suggested_id,
                status,
            )
        )
        if status == "FIX":
            fixes.append(
                (
                    row.part_id,
                    row.part_number,
                    row.description,
                    level1,
                    row.leaf_id,
                    row.leaf_name,
                    suggested_id,
                    resolved,
                    confidence,
                    verdict.get("reason", ""),
                )
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", args.verdicts.stem.replace("ai_verdicts_", "")).strip("-")

    annotated_path = args.output_dir / f"annotated_{slug}.xlsx"
    write_rows(
        annotated_path,
        annotated,
        HEADERS
        + [
            "rule_verdict", "rule_score",
            "ai_verdict", "ai_confidence", "ai_reason",
            "ai_suggested_leaf_name", "ai_suggested_leaf_id",
            "status",
        ],
        sheet="annotated",
    )

    fixes.sort(key=lambda r: (str(r[3]), str(r[5])))
    fix_path = args.output_dir / f"fixes_{slug}.xlsx"
    write_rows(
        fix_path,
        fixes,
        [
            "part_id", "part_number", "part_description", "level1_category_name",
            "current_leaf_id", "current_leaf_name",
            "new_leaf_id", "new_leaf_name",
            "ai_confidence", "ai_reason",
        ],
        sheet="fixes",
    )

    print(f"{'status':<26}{'rows':>9}{'share':>9}")
    for status, count in counts.most_common():
        print(f"{status:<26}{count:>9}{count / len(rows):>8.1%}")
    print(f"{'TOTAL':<26}{len(rows):>9}")

    moves = collections.Counter((str(f[5]), str(f[7])) for f in fixes)
    if moves:
        print(f"\ntop leaf moves proposed ({len(fixes)} rows, {len(moves)} distinct moves):")
        for (old, new), count in moves.most_common(15):
            print(f"  {count:>6}  {old}  ->  {new}")

    print(f"\nannotated -> {annotated_path}\nfixes     -> {fix_path}")


if __name__ == "__main__":
    main()
