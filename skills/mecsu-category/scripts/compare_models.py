"""Cross-check two models over the same pair queue.

Agreement is not proof of correctness, but disagreement reliably marks the pairs worth a human
(or Claude) reading. Emits an agreement matrix plus a disagreement sheet ordered by blast radius.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from common import fold, job_root, pair_key, write_rows

ROOT = job_root()
DEFAULT_DIR = ROOT / "jobs" / "oncheck"


def load(path: Path) -> dict[str, dict]:
    return {str(k): v for k, v in json.loads(path.read_text(encoding="utf-8")).items()}


def decision(verdict: dict) -> tuple[str, str]:
    """(label, target). The target only means anything on a 'wrong' verdict - models often leave a
    stale suggestion attached to a 'correct' one, and comparing that invents disagreements."""
    label = str(verdict.get("verdict", "MISSING"))
    if label != "wrong":
        return label, ""
    return label, fold(str(verdict.get("suggested_category") or "").strip())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_DIR / "ai_queue.json")
    parser.add_argument("--a", type=Path, required=True, help="first ai_verdicts_*.json")
    parser.add_argument("--b", type=Path, required=True, help="second ai_verdicts_*.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    pairs = {pair_key(p): p for p in queue["pairs"]}
    a_name = args.a.stem.replace("ai_verdicts_", "")
    b_name = args.b.stem.replace("ai_verdicts_", "")
    a, b = load(args.a), load(args.b)

    matrix: collections.Counter = collections.Counter()
    rows_agree = rows_disagree = 0
    disagreements = []

    for key, pair in pairs.items():
        va, vb = a.get(key, {}), b.get(key, {})
        la, ta = decision(va)
        lb, tb = decision(vb)
        matrix[(la, lb)] += 1

        same_label = la == lb
        same_target = ta == tb
        # Two 'wrong' verdicts that name different replacements still disagree in practice.
        if same_label and same_target:
            rows_agree += pair["row_count"]
            continue
        rows_disagree += pair["row_count"]
        disagreements.append(
            (
                pair["pair_id"],
                pair["level1_category_name"],
                pair["sample_description"],
                pair["leaf_category_name"],
                la,
                va.get("confidence", ""),
                str(va.get("suggested_category") or ""),
                va.get("reason", ""),
                lb,
                vb.get("confidence", ""),
                str(vb.get("suggested_category") or ""),
                vb.get("reason", ""),
                "LABEL" if not same_label else "TARGET",
                pair["row_count"],
            )
        )

    disagreements.sort(key=lambda r: -r[13])
    out = args.output_dir / f"disagreements_{a_name}__vs__{b_name}.xlsx"
    write_rows(
        out,
        disagreements,
        [
            "pair_id", "level1_category_name", "sample_description", "current_leaf_name",
            f"{a_name}_verdict", f"{a_name}_conf", f"{a_name}_suggested", f"{a_name}_reason",
            f"{b_name}_verdict", f"{b_name}_conf", f"{b_name}_suggested", f"{b_name}_reason",
            "disagree_on", "row_count",
        ],
        sheet="disagreements",
    )

    labels = sorted({label for pair in matrix for label in pair})
    total = sum(matrix.values())
    print(f"rows: {a_name} (down) vs {b_name} (across)\n")
    print(f"{'':<10}" + "".join(f"{label:>10}" for label in labels))
    for la in labels:
        print(f"{la:<10}" + "".join(f"{matrix[(la, lb)]:>10}" for lb in labels))

    agreed_pairs = sum(count for (la, lb), count in matrix.items() if la == lb)
    print(
        f"\npairs: {total} | same label: {agreed_pairs} ({agreed_pairs / total:.1%})"
        f" | fully agreed (label+target): {total - len(disagreements)}"
        f" ({(total - len(disagreements)) / total:.1%})"
    )
    print(f"rows:  agreed {rows_agree} | disputed {rows_disagree}")
    print(f"\ndisagreements -> {out}  ({len(disagreements)} pairs)")


if __name__ == "__main__":
    main()
