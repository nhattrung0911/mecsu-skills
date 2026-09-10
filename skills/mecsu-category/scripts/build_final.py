"""Write the corrected workbook, then verify it against the source before declaring it usable.

Only rows both models agree are wrong AND that name the same replacement leaf are changed, unless
--accept-single-model is passed. Every check below must pass or the script exits non-zero.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from apply_fixes import is_generic
from common import HEADERS, SHEET, fold, job_root, pair_key, pattern, read_rows, write_rows

ROOT = job_root()
DEFAULT_DIR = ROOT / "jobs" / "oncheck"
DEFAULT_INPUT = ROOT / "jobs" / "inbox" / "On_web_category.xlsx"


def key_of(description: object, leaf_name: object) -> tuple[str, str]:
    return pattern(description), fold(leaf_name)


def index_verdicts(queue: dict, verdicts: dict[str, dict]) -> dict[tuple[str, str], dict]:
    indexed = {}
    for pair in queue["pairs"]:
        verdict = verdicts.get(pair_key(pair))
        if verdict:
            indexed[key_of(pair["sample_description"], pair["leaf_category_name"])] = verdict
    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sheet", default=SHEET)
    parser.add_argument("--queue", type=Path, default=DEFAULT_DIR / "ai_queue.json")
    parser.add_argument("--verdicts", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_DIR / "On_web_category_FINAL.xlsx")
    parser.add_argument("--min-confidence", type=float, default=0.8)
    parser.add_argument(
        "--exclude-pairs",
        type=Path,
        help="JSON list of pair_ids a human rejected; those rows keep their original category.",
    )
    parser.add_argument(
        "--accept-single-model",
        action="store_true",
        help="Apply fixes backed by only one verdict file (default requires all of them to agree).",
    )
    parser.add_argument(
        "--resolutions",
        type=Path,
        help="dispute_resolution.json. For pairs it names, its adjudicated answer wins over the "
             "agreement rule - those pairs were settled against web evidence about the real part.",
    )
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    catalog = queue["leaf_catalog"]
    leaf_ids = queue["leaf_ids"]
    resolvers = {level1: {fold(n): n for n in names} for level1, names in catalog.items()}
    valid_ids = {str(i) for names in leaf_ids.values() for ids in names.values() for i in ids}
    depth_by_id = queue.get("leaf_depth_by_id", {})
    if not depth_by_id:
        raise SystemExit("ai_queue.json has no leaf_depth_by_id; rerun rule_check.py to regenerate it.")
    ambiguous = queue.get("ambiguous_leaf_names", {})
    if ambiguous:
        total = sum(len(names) for names in ambiguous.values())
        print(f"{total} leaf name(s) map to several ids in the source; fixes into them are refused")

    pair_key = {key_of(p["sample_description"], p["leaf_category_name"]): p["pair_id"] for p in queue["pairs"]}
    excluded = set()
    if args.exclude_pairs:
        excluded = {int(x) for x in json.loads(args.exclude_pairs.read_text(encoding="utf-8"))}
        print(f"excluding {len(excluded)} human-rejected pair(s)")

    indexes = []
    for path in args.verdicts:
        indexes.append((path.stem.replace("ai_verdicts_", ""), index_verdicts(queue, json.loads(path.read_text(encoding="utf-8")))))
    print(f"verdict sources: {', '.join(name for name, _ in indexes)}")

    resolutions: dict[int, dict] = {}
    if args.resolutions:
        resolutions = {int(k): v for k, v in json.loads(args.resolutions.read_text(encoding="utf-8")).items()}
        changes = sum(1 for v in resolutions.values() if v["decision"] == "change")
        print(f"adjudicated pairs: {len(resolutions)} ({changes} change, {len(resolutions) - changes} keep)")

    rows = read_rows(args.input, args.sheet)
    final = []
    changelog = []
    counts: collections.Counter = collections.Counter()

    for row in rows:
        key = key_of(row.description, row.leaf_name)
        level1 = str(row.level1_name)
        # An adjudicated pair short-circuits the agreement rule: it was decided against evidence
        # about the actual part, which beats two models voting from the description alone.
        ruling = resolutions.get(pair_key.get(key, -1))
        targets = []
        confidences = []
        reasons = []
        for name, index in indexes:
            verdict = index.get(key)
            if not verdict or str(verdict.get("verdict")) != "wrong":
                targets.append(None)
                continue
            resolved = resolvers.get(level1, {}).get(fold(str(verdict.get("suggested_category") or "").strip()), "")
            targets.append(resolved or None)
            confidences.append(float(verdict.get("confidence") or 0))
            reasons.append(f"{name}: {verdict.get('reason', '')}")

        if ruling is not None:
            target = ruling["new_leaf_name"] if ruling["decision"] == "change" else None
            if target:
                confidences = [float(ruling.get("confidence") or 0)]
                reasons = [f"adjudicated: {ruling.get('reason', '')}"]
            counts["ADJUDICATED"] += 1
        else:
            voted = [t for t in targets if t]
            agreed = bool(voted) and (args.accept_single_model or len(voted) == len(indexes))
            agreed = agreed and len({fold(t) for t in voted}) == 1
            target = voted[0] if agreed else None
        if target and (
            fold(target) == fold(row.leaf_name)
            or is_generic(target)
            or (confidences and min(confidences) < args.min_confidence)
            or pair_key.get(key) in excluded
            # An ambiguous name gives no way to pick the right id; guessing would corrupt the data.
            or len(leaf_ids.get(level1, {}).get(target, [])) != 1
        ):
            if target and len(leaf_ids.get(level1, {}).get(target, [])) != 1:
                counts["REFUSED_AMBIGUOUS_TARGET"] += 1
            target = None

        if target:
            new_id = leaf_ids[level1][target][0]
            new_depth = depth_by_id.get(str(new_id), row.leaf_depth)
            counts["CHANGED"] += 1
            changelog.append(
                (
                    row.part_id, row.part_number, row.description, level1,
                    row.leaf_id, row.leaf_name, new_id, target,
                    min(confidences) if confidences else "", " | ".join(reasons),
                )
            )
            final.append(row.replacing(leaf_id=new_id, leaf_name=target, leaf_depth=new_depth))
        else:
            counts["KEPT"] += 1
            final.append(row.as_tuple())

    write_rows(args.output, final, HEADERS, sheet=SHEET)
    change_path = args.output.with_name(f"{args.output.stem}_changelog.xlsx")
    changelog.sort(key=lambda r: (str(r[3]), str(r[5])))
    write_rows(
        change_path,
        changelog,
        ["part_id", "part_number", "part_description", "level1_category_name",
         "old_leaf_id", "old_leaf_name", "new_leaf_id", "new_leaf_name",
         "min_confidence", "reasons"],
        sheet="changelog",
    )

    # ---- verification: every check must hold, or the file is not usable ----
    written = read_rows(args.output, SHEET)
    problems: list[str] = []

    if len(written) != len(rows):
        problems.append(f"row count changed: {len(rows)} -> {len(written)}")

    source_by_id = {r.part_id: r for r in rows}
    if len(source_by_id) != len(rows):
        problems.append("source part_id is not unique; cannot verify row identity")

    changed_ids = {c[0] for c in changelog}
    drifted = 0
    bad_leaf = 0
    bad_depth = 0
    # Every (id, name, depth) triple written must be one the source already uses. This is the check
    # that catches a moved row keeping its old depth.
    source_triples = {(str(r.leaf_id), str(r.leaf_name).strip(), r.leaf_depth) for r in rows}
    id_name_conflict: dict[str, set] = collections.defaultdict(set)
    for row in written:
        source = source_by_id.get(row.part_id)
        if source is None:
            problems.append(f"part_id {row.part_id} absent from source")
            break
        # Nothing outside the changelog may differ, in any column.
        if row.part_id not in changed_ids and row.as_tuple() != source.as_tuple():
            drifted += 1
        # Immutable columns must survive even on changed rows.
        if (row.description, row.part_number, row.sku, row.level1_id, row.level1_name) != (
            source.description, source.part_number, source.sku, source.level1_id, source.level1_name
        ):
            drifted += 1
        if str(row.leaf_id) not in valid_ids:
            bad_leaf += 1
        if (str(row.leaf_id), str(row.leaf_name).strip(), row.leaf_depth) not in source_triples:
            bad_depth += 1
        id_name_conflict[str(row.leaf_id)].add(str(row.leaf_name).strip())

    if drifted:
        problems.append(f"{drifted} row(s) changed outside the changelog")
    if bad_leaf:
        problems.append(f"{bad_leaf} row(s) carry a leaf_category_id not in the catalog")
    if bad_depth:
        problems.append(f"{bad_depth} row(s) carry an id/name/depth triple the source never uses")
    split_ids = {i: n for i, n in id_name_conflict.items() if len(n) > 1}
    if split_ids:
        problems.append(f"{len(split_ids)} leaf_category_id map to several names: {list(split_ids)[:3]}")

    print(f"\n{'KEPT':<10}{counts['KEPT']:>8}")
    print(f"{'CHANGED':<10}{counts['CHANGED']:>8}")
    print(f"{'TOTAL':<10}{len(rows):>8}")

    print("\nverification")
    print(f"  rows in == rows out ............ {len(rows)} == {len(written)}")
    print(f"  rows changed == changelog ...... {counts['CHANGED']} == {len(changelog)}")
    print(f"  untouched rows byte-identical .. {'FAIL' if drifted else 'OK'}")
    print(f"  every leaf_category_id valid ... {'FAIL' if bad_leaf else 'OK'}")
    print(f"  id/name/depth triple known ..... {'FAIL' if bad_depth else 'OK'}")
    print(f"  leaf id/name one-to-one ........ {'FAIL' if split_ids else 'OK'}")

    print(f"\nfinal     -> {args.output}\nchangelog -> {change_path}")
    if problems:
        print("\nVERIFICATION FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)
    print("\nall verification checks passed")


if __name__ == "__main__":
    main()
