"""One command: point it at a workbook, get an audited workbook plus the list of what needs a human.

    python audit.py --input <workbook.xlsx>

Runs schema detection, the free lexical filter, one model pass, a second model for cross-checking,
and the verified build. Stops at any gate that a human must clear rather than guessing past it.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):      # product names are Vietnamese; the Windows console is cp1252
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from common import job_root  # noqa: E402 - needs HERE on sys.path first


def verdicts_dir() -> Path:
    """Where ai_check.py writes. Must resolve exactly like `ai_check.DEFAULT_DIR`.

    This used to be `HERE.parents[1] / "jobs" / "oncheck"`, i.e. `skills/jobs/oncheck`,
    while every other script derives its paths from `common.job_root()`. The two only
    agree when ONCHECK_JOBS is set, so the documented one-command run died with
    "No verdict files in ..." after the whole model pass had been paid for.
    """
    return job_root() / "jobs" / "oncheck"


def build_args(workbook: Path, verdict_files: list[str], jobs_dir: Path) -> list[str]:
    """Arguments for build_final.py: one model needs an explicit opt-in, and an adjudication
    file is passed on only when a human has actually written one."""
    arguments = ["--input", str(workbook), "--verdicts", *verdict_files]
    if len(verdict_files) == 1:
        arguments.append("--accept-single-model")
    resolutions = jobs_dir / "dispute_resolution.json"
    if resolutions.exists():
        arguments += ["--resolutions", str(resolutions)]
    return arguments


def run(script: str, *arguments: str, env: dict | None = None) -> int:
    command = [sys.executable, str(HERE / script), *arguments]
    print(f"\n$ python {script} {' '.join(arguments)}\n{'-' * 72}")
    return subprocess.call(command, env=env)


def dung_neu_loi(ma: int, script: str, thong_diep: str = "") -> None:
    """Truyen nguyen ma thoat 4 ra ngoai; moi ma khac 0 con lai la hong.

    4 = buoc con dang CHO AGENT tra loi, khac han hong. `SystemExit('<chuoi>')`
    lam Python thoat 1, nen 4 bien thanh 1 va agent goi skill khong biet no phai
    dien tra_loi.json hay day chuyen da hong. Da do o P4 tren 102 dong that.
    """
    if ma == 4:
        print(f"\n{script} dang cho agent tra loi. Dien xong chay lai dung lenh nay.")
        raise SystemExit(4)
    if ma:
        raise SystemExit(thong_diep or f"\n{script} that bai (exit {ma}). Dung lai.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="Workbook to audit.")
    parser.add_argument("--sheet", help="Defaults to the only sheet, else the one with most rows.")
    parser.add_argument("--models", nargs="+", help="Two models: one judges, one cross-checks.")
    parser.add_argument("--calibrate", type=int, default=50, help="Pairs to judge first (0 to skip).")
    parser.add_argument(
        "--yes", action="store_true",
        help="Skip the pause after calibration. Only pass this once the sample has been read.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"No such workbook: {args.input}")

    env = dict(os.environ)
    schema = Path(env.get("ONCHECK_SCHEMA", "")) if env.get("ONCHECK_SCHEMA") else None

    # 1. schema -------------------------------------------------------------
    detect = ["--input", str(args.input)]
    if args.sheet:
        detect += ["--sheet", args.sheet]
    if schema:
        detect += ["--output", str(schema)]
    if run("detect_schema.py", *detect, env=env):
        raise SystemExit("\nSchema detection failed. Map the columns by hand before continuing.")

    # 2. free lexical filter ------------------------------------------------
    if run("rule_check.py", "--input", str(args.input), env=env):
        raise SystemExit("\nrule_check failed.")

    # 3. calibration --------------------------------------------------------
    models = args.models or []
    first = ["--model", models[0]] if models else []
    if args.calibrate:
        dung_neu_loi(run("ai_check.py", "--limit", str(args.calibrate), *first, env=env),
                     "ai_check.py", "\nCalibration failed. Check .env and the endpoint.")
        if not args.yes:
            print(
                f"\n{'=' * 72}\nSTOP. Read the {args.calibrate}-pair sample above before paying for the rest.\n"
                "Open the ai_report workbook, check the verdicts are sane for this source, then rerun\n"
                "this command with --yes to continue.\n" + "=" * 72
            )
            return

    # 4. full pass, then a second model -------------------------------------
    dung_neu_loi(run("ai_check.py", *first, env=env), "ai_check.py", "\nMain pass failed.")
    if len(models) > 1:
        dung_neu_loi(run("ai_check.py", "--model", models[1], env=env),
                     "ai_check.py", "\nCross-check pass failed.")

    jobs_dir = verdicts_dir()
    verdict_files = sorted(
        str(p) for p in jobs_dir.glob("ai_verdicts_*.json") if "__nocatalog" not in p.name
    )
    if not verdict_files:
        raise SystemExit(f"No verdict files in {jobs_dir}")

    if len(verdict_files) > 1:
        run("compare_models.py", "--a", verdict_files[0], "--b", verdict_files[1], env=env)
        run("list_disputes.py", "--verdicts", *verdict_files, env=env)

    # 5. build, with its own verification ------------------------------------
    if run("build_final.py", *build_args(args.input, verdict_files, jobs_dir), env=env):
        raise SystemExit("\nThe built workbook failed its own verification. Do not deliver it.")

    print(
        f"\n{'=' * 72}\nAudited workbook and changelog are in {jobs_dir}\n\n"
        "Before delivering:\n"
        "  1. Read the changelog. It is the thing a human approves.\n"
        "  2. Work down disputes_to_research.json, searching the real part codes, and record what\n"
        "     the evidence settles in dispute_resolution.json. Leave the rest alone.\n"
        "  3. taxonomy_gaps.json is not a categorisation problem - those products have no valid\n"
        "     home. Hand it to whoever owns the taxonomy.\n"
        f"  4. python deliver.py --verdicts {' '.join(Path(v).name for v in verdict_files)}\n"
        + "=" * 72
    )


if __name__ == "__main__":
    main()
