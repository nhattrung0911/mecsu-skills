"""Final step: write the approved workbook to jobs/delivered/.

Keeps all original columns untouched and appends the review columns. Refuses to deliver while any
pair is still disputed unless --allow-disputed is passed, because jobs/delivered/ is defined as
fully reviewed output.
"""

from __future__ import annotations

import argparse
import collections
import json
from datetime import datetime
from pathlib import Path

from common import HEADERS, SHEET, fold, job_root, pair_key, pattern, read_rows, write_rows

ROOT = job_root()
DEFAULT_DIR = ROOT / "jobs" / "oncheck"
DEFAULT_INPUT = ROOT / "jobs" / "inbox" / "On_web_category.xlsx"
DELIVERED = ROOT / "jobs" / "delivered"

EXTRA_COLUMNS = [
    "new_leaf_category_id",
    "new_leaf_category_name",
    "is_changed",
    "confidence_pct",
]


def target_of(verdict: dict) -> str:
    if str(verdict.get("verdict")) != "wrong":
        return ""
    return fold(str(verdict.get("suggested_category") or "").strip())


def unsettled(queue: dict, sources: list[tuple[str, dict]], settled: set[int]) -> int:
    """Pairs the sources still disagree on and nobody has adjudicated.

    A pair listed in dispute_resolution.json (or in the excluded list) has been decided by a
    human; recomputing the disagreement from the raw verdicts and blocking on it again means
    resolving disputes correctly still never unblocks delivery.
    """
    count = 0
    for pair in queue["pairs"]:
        if pair["pair_id"] in settled:
            continue
        verdicts = [source.get(pair_key(pair), {}) for _, source in sources]
        labels = {str(v.get("verdict")) for v in verdicts}
        targets = {target_of(v) for v in verdicts}
        if len(labels) > 1 or len(targets) > 1:
            count += 1
    return count


def load_ids(path: Path | None) -> set[int]:
    """pair_ids out of either file a human produced: the resolutions map or the excluded list."""
    if not path:
        return set()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {int(k) for k in (payload.keys() if isinstance(payload, dict) else payload)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sheet", default=SHEET)
    parser.add_argument("--queue", type=Path, default=DEFAULT_DIR / "ai_queue.json")
    parser.add_argument("--final", type=Path, default=DEFAULT_DIR / "On_web_category_FINAL.xlsx")
    parser.add_argument("--verdicts", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, default=DELIVERED)
    parser.add_argument(
        "--allow-disputed",
        action="store_true",
        help="Deliver even though the verdict sources still disagree somewhere.",
    )
    parser.add_argument(
        "--resolutions",
        type=Path,
        help="dispute_resolution.json - pairs a human adjudicated no longer count as disputed.",
    )
    parser.add_argument(
        "--exclude-pairs",
        type=Path,
        help="Same JSON list of pair_ids passed to build_final.py; those pairs keep their "
             "original category and no longer block delivery.",
    )
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    sources = []
    for path in args.verdicts:
        sources.append((path.stem.replace("ai_verdicts_", ""), json.loads(path.read_text(encoding="utf-8"))))

    # pair key -> per-source verdicts, so a row can look up what every model said about it.
    index: dict[tuple[str, str], list[dict]] = {}
    for pair in queue["pairs"]:
        key = (pattern(pair["sample_description"]), fold(pair["leaf_category_name"]))
        index[key] = [source.get(pair_key(pair), {}) for _, source in sources]

    settled = load_ids(args.resolutions) | load_ids(args.exclude_pairs)
    if settled:
        print(f"{len(settled)} pair(s) already adjudicated by a human")
    disputed = unsettled(queue, sources, settled)
    if disputed and not args.allow_disputed:
        raise SystemExit(
            f"{disputed} pair(s) still disputed between {len(sources)} verdict sources.\n"
            f"Resolve them into dispute_resolution.json and pass --resolutions, exclude them with\n"
            f"--exclude-pairs, or pass --allow-disputed, before writing to {args.output_dir.name}/."
        )

    source_rows = read_rows(args.input, args.sheet)
    final_rows = {r.part_id: r for r in read_rows(args.final, args.sheet)}
    if len(final_rows) != len(source_rows):
        raise SystemExit("final workbook and source do not have the same rows; rerun build_final.py")

    out = []
    counts: collections.Counter = collections.Counter()
    for row in source_rows:
        final = final_rows[row.part_id]
        changed = str(final.leaf_id) != str(row.leaf_id)

        verdicts = index.get((pattern(row.description), fold(row.leaf_name)), [])
        scores = [float(v.get("confidence") or 0) for v in verdicts if v.get("confidence") is not None]
        # A row settled by the lexical filter never saw a model; report blank, not a made-up 100%.
        confidence = round(min(scores) * 100) if scores else ""

        counts["CHANGED" if changed else "KEPT"] += 1
        out.append((*row.as_tuple(), final.leaf_id, final.leaf_name, "YES" if changed else "NO", confidence))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = args.output_dir / f"{args.input.stem}_categorized_{stamp}.xlsx"
    write_rows(path, out, HEADERS + EXTRA_COLUMNS, sheet=args.sheet)

    scored = sum(1 for r in out if r[-1] != "")
    print(f"rows            {len(out)}")
    print(f"  changed       {counts['CHANGED']}")
    print(f"  kept          {counts['KEPT']}")
    print(f"  model-scored  {scored} ({scored / len(out):.1%}); the rest were settled by the rule filter")
    print(f"verdict sources {', '.join(name for name, _ in sources)}")
    print(f"\ndelivered -> {path}")


if __name__ == "__main__":
    main()
