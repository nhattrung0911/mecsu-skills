"""Derive every effectiveness number in the docs from the artifacts on disk.

Nothing here is typed in by hand: rerun it and the figures regenerate. Anything it cannot measure
is labelled as an extrapolation rather than printed as a measurement.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from apply_fixes import is_generic
from common import SHEET, fold, job_root, pair_key, pattern, read_rows
from rule_check import judge
import sys

if hasattr(sys.stdout, "reconfigure"):      # product names are Vietnamese; the Windows console is cp1252
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = job_root()
DEFAULT_DIR = ROOT / "jobs" / "oncheck"
DEFAULT_INPUT = ROOT / "jobs" / "inbox" / "On_web_category.xlsx"


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sheet", default=SHEET)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--primary", default="ag-gemini-3-7-flash-medium")
    parser.add_argument("--secondary", default="ag-gemini-3-7-flash-high")
    parser.add_argument("--ablation", default="ag-gemini-3-7-flash-medium__nocatalog")
    args = parser.parse_args()

    queue = json.loads((args.dir / "ai_queue.json").read_text(encoding="utf-8"))
    pairs = {str(p["pair_id"]): p for p in queue["pairs"]}
    catalog = queue["leaf_catalog"]
    resolvers = {lv: {fold(n): n for n in names} for lv, names in catalog.items()}

    def verdicts(name: str) -> dict[str, dict]:
        path = args.dir / f"ai_verdicts_{name}.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    primary = verdicts(args.primary)
    secondary = verdicts(args.secondary)
    ablation = verdicts(args.ablation)

    rows = read_rows(args.input, args.sheet)

    # 1. deduplication -------------------------------------------------------
    section("1. Deduplication (bo token co chu so khoi mo ta)")
    all_pairs = {(pattern(r.description), fold(r.leaf_name)) for r in rows}
    rule_labels = [judge(r.description, r.leaf_name)[0] for r in rows]
    flagged = [r for r, label in zip(rows, rule_labels) if label in ("PARTIAL", "NO_OVERLAP")]
    flagged_pairs = {(pattern(r.description), fold(r.leaf_name)) for r in flagged}
    print(f"  all rows                {len(rows):>8}  -> unique pairs {len(all_pairs):>6}"
          f"   reduction {len(rows) / len(all_pairs):>5.1f}x")
    print(f"  rows needing a model    {len(flagged):>8}  -> unique pairs {len(flagged_pairs):>6}"
          f"   reduction {len(flagged) / len(flagged_pairs):>5.1f}x")

    # 2. rule filter ---------------------------------------------------------
    section("2. Rule filter (mien phi, chan truoc khi goi model)")
    counts = collections.Counter(rule_labels)
    passed = counts["EXACT"] + counts["ALL_WORDS"]
    for label in ("EXACT", "ALL_WORDS", "PARTIAL", "NO_OVERLAP"):
        print(f"  {label:<12}{counts[label]:>8}{counts[label] / len(rows):>8.1%}")
    print(f"  rows never sent to a model: {passed} ({passed / len(rows):.1%})")

    # 3. catalog injection A/B ----------------------------------------------
    section("3. A/B: dua danh sach leaf vao prompt hay khong (cung bo cap)")
    shared = sorted(set(primary) & set(ablation), key=int)
    if not shared:
        print("  no overlapping pairs between the two arms; run the ablation first")
    else:
        print(f"  compared on {len(shared)} pairs judged by both arms\n")
        print(f"  {'arm':<14}{'wrong':>7}{'unsure':>8}{'suggested':>11}{'invalid':>9}{'invalid %':>11}")
        for name, source in (("with catalog", primary), ("no catalog", ablation)):
            wrong = unsure = suggested = invalid = 0
            for pair_id in shared:
                verdict = source[pair_id]
                label = str(verdict.get("verdict"))
                wrong += label == "wrong"
                unsure += label == "unsure"
                if label != "wrong":
                    continue
                text = str(verdict.get("suggested_category") or "").strip()
                if not text:
                    continue
                suggested += 1
                level1 = pairs[pair_id]["level1_category_name"]
                if fold(text) not in resolvers.get(level1, {}):
                    invalid += 1
            share = f"{invalid / suggested:.1%}" if suggested else "n/a"
            print(f"  {name:<14}{wrong:>7}{unsure:>8}{suggested:>11}{invalid:>9}{share:>11}")
        print("\n  invalid = danh muc goi y khong ton tai trong leaf catalog cua level1 do")

    # 4. guards --------------------------------------------------------------
    section("4. Guard chan sua rac (dem tren toan bo 67k dong)")
    blocked_noop = blocked_generic = would_fix = 0
    index = {}
    for pair in queue["pairs"]:
        verdict = primary.get(pair_key(pair))
        if verdict:
            index[(pattern(pair["sample_description"]), fold(pair["leaf_category_name"]))] = verdict
    for row in rows:
        verdict = index.get((pattern(row.description), fold(row.leaf_name)))
        if not verdict or str(verdict.get("verdict")) != "wrong":
            continue
        level1 = str(row.level1_name)
        resolved = resolvers.get(level1, {}).get(fold(str(verdict.get("suggested_category") or "").strip()), "")
        if not resolved:
            continue
        if fold(resolved) == fold(row.leaf_name):
            blocked_noop += 1
        elif is_generic(resolved):
            blocked_generic += 1
        else:
            would_fix += 1
    print(f"  blocked: doi sang chinh no (chi khac khoang trang)  {blocked_noop:>6} rows")
    print(f"  blocked: day vao thung Other / Chua Phan Loai       {blocked_generic:>6} rows")
    print(f"  survive as real fixes                               {would_fix:>6} rows")
    total_blocked = blocked_noop + blocked_generic
    if would_fix + total_blocked:
        print(f"  guards removed {total_blocked / (would_fix + total_blocked):.1%} of proposed changes")

    # 5. cross-model ---------------------------------------------------------
    section("5. Doi chieu 2 model")
    if not secondary:
        print("  secondary model not run")
    else:
        def target(verdict: dict) -> str:
            if str(verdict.get("verdict")) != "wrong":
                return ""
            return fold(str(verdict.get("suggested_category") or "").strip())

        same_label = full = 0
        disputed_rows = 0
        for pair_id, pair in pairs.items():
            a, b = primary.get(pair_id, {}), secondary.get(pair_id, {})
            la, lb = str(a.get("verdict")), str(b.get("verdict"))
            same_label += la == lb
            if la == lb and target(a) == target(b):
                full += 1
            else:
                disputed_rows += pair["row_count"]
        total = len(pairs)
        print(f"  same verdict label            {same_label:>6}/{total}  {same_label / total:.1%}")
        print(f"  same label AND same target    {full:>6}/{total}  {full / total:.1%}")
        print(f"  disputed pairs {total - full}, covering {disputed_rows} rows"
              f" ({disputed_rows / len(rows):.1%} of the workbook)")

    # 6. cost ----------------------------------------------------------------
    section("6. Chi phi")
    # Khong in lai so token nho duoc: chung khong nam trong artifact nao tren dia, va
    # doc thuoc long thi dung la thu luat 6 cua SKILL.md cam. ai_check.py in so that
    # cua chinh lan chay do.
    print("  So pair/giay/token cua tung lan chay do ai_check.py in ra o cuoi lan do;")
    print("  khong luu lai o dau nen khong in lai o day.")
    print(f"\n  EXTRAPOLATION (not measured): without dedup the same medium pass would judge")
    print(f"  {len(flagged)} items instead of {len(flagged_pairs)}; token cost scales with item")
    print(f"  count, so roughly {len(flagged) / len(flagged_pairs):.1f}x the tokens above.")


if __name__ == "__main__":
    main()
