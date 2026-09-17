"""Step 2: send the deduplicated suspect pairs to a model via 9router and record verdicts.

Reads jobs/oncheck/ai_queue.json, writes ai_verdicts.json (resumable) and ai_report.xlsx.
Config comes from .env next to this file.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import threading
import time
from pathlib import Path

import requests
import skill_env

from common import fold, job_root, pair_key, write_rows

HERE = Path(__file__).resolve().parent
ROOT = job_root()
DEFAULT_DIR = ROOT / "jobs" / "oncheck"

SYSTEM_PROMPT = """Bạn là chuyên gia phân loại danh mục sản phẩm công nghiệp (thị trường Việt Nam).

Mỗi lượt bạn nhận sản phẩm thuộc CÙNG MỘT danh mục cấp 1, kèm danh sách đầy đủ các danh mục lá
hợp lệ của cấp 1 đó. Với mỗi mục:
- description: tên/mô tả sản phẩm
- leaf_category: danh mục lá đang được gán

Nhiệm vụ: xác định danh mục lá đã gán CÓ ĐÚNG với sản phẩm không.

Nguyên tắc:
- Xét ngữ nghĩa, không xét trùng chữ. Danh mục tiếng Anh gán cho mô tả tiếng Việt vẫn ĐÚNG nếu
  cùng nghĩa ("Vít Bi Nhún" = "Ball Plunger", "Chốt Định Vị" = "Locating Pins",
  "Bulong Vặn Tay" = "Knurled Knob"). Đây là chuẩn đặt tên của nguồn, không phải lỗi.
- Danh mục phải mô tả đúng LOẠI sản phẩm, không chỉ trùng một từ lẻ.
- Máy móc không được nằm trong danh mục linh kiện/bulong/vật tư thô, và ngược lại.
- Nếu danh mục đúng loại nhưng chưa phải mức cụ thể nhất, vẫn trả "correct" và nói rõ trong reason.
- Chỉ trả "wrong" khi trong danh sách hợp lệ CÓ một danh mục khác đúng hơn rõ rệt.
- suggested_category BẮT BUỘC sao chép nguyên văn một tên trong danh sách hợp lệ. Nếu không có
  danh mục nào phù hợp thì trả verdict "unsure" và để suggested_category rỗng.

Trả về DUY NHẤT một mảng JSON, mỗi phần tử:
{"id": <int>, "verdict": "correct" | "wrong" | "unsure", "confidence": <0.0-1.0>, "reason": "<ngắn gọn, tiếng Việt, tối đa 20 từ>", "suggested_category": "<nguyên văn từ danh sách hợp lệ, hoặc chuỗi rỗng>"}

Không thêm chữ nào ngoài mảng JSON."""

_print_lock = threading.Lock()


def load_config() -> dict:
    """Key goes in the plugin-root .env once; an old ONCHECK_* .env still works."""
    return skill_env.load_llm_config(legacy_prefix="ONCHECK", bat_buoc=False)


def read_completion(response: requests.Response) -> tuple[str, dict]:
    """Return (assistant text, usage). The 9router endpoint answers with SSE even unasked."""
    # requests falls back to ISO-8859-1 for text/event-stream, which mangles Vietnamese.
    response.encoding = "utf-8"
    if "text/event-stream" not in response.headers.get("content-type", ""):
        body = response.json()
        return body["choices"][0]["message"]["content"], body.get("usage", {})

    parts: list[str] = []
    usage: dict = {}
    for line in response.text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        chunk = json.loads(payload)
        usage = chunk.get("usage") or usage
        for choice in chunk.get("choices", []):
            piece = choice.get("delta", {}).get("content")
            if piece:
                parts.append(piece)
    return "".join(parts), usage


def parse_verdicts(content: str) -> list[dict]:
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array in model reply: {content[:200]}")
    return json.loads(text[start : end + 1])


def build_user_message(batch: list[dict], level1: str, leaves: list[str] | None) -> str:
    # Strip: 11 leaf names carry a stray trailing space, and showing the padded form next to the
    # stripped catalog made the model report a difference that does not exist.
    items = [
        {
            "id": item["pair_id"],
            "description": item["sample_description"],
            "leaf_category": item["leaf_category_name"].strip(),
        }
        for item in batch
    ]
    if leaves is None:  # ablation: no catalog, the model must invent the replacement name
        return (
            f"Danh mục cấp 1: {level1}\n\nCác sản phẩm cần kiểm tra:\n"
            + json.dumps(items, ensure_ascii=False)
        )
    return (
        f"Danh mục cấp 1: {level1}\n\n"
        f"Danh sách {len(leaves)} danh mục lá hợp lệ của cấp 1 này:\n"
        + json.dumps(leaves, ensure_ascii=False)
        + "\n\nCác sản phẩm cần kiểm tra:\n"
        + json.dumps(items, ensure_ascii=False)
    )


def call_model(
    config: dict, model: str, batch: list[dict], level1: str, leaves: list[str] | None, retries: int = 3
) -> tuple[list[dict], dict]:
    if not skill_env.co_llm(config):
        # Che do agent: cung SYSTEM_PROMPT, cung user message da gop lo. Cau tra loi
        # di qua dung parse_verdicts nhu cua model - khong uu ai.
        noi_dung = skill_env.hoi_agent(SYSTEM_PROMPT, build_user_message(batch, level1, leaves))
        return parse_verdicts(noi_dung), {}
    payload = {
        "model": model,
        "temperature": config["temperature"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(batch, level1, leaves)},
        ],
    }
    headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{config['base_url']}/chat/completions", json=payload, headers=headers, timeout=180
            )
            response.raise_for_status()
            content, usage = read_completion(response)
            return parse_verdicts(content), usage
        except Exception as error:  # noqa: BLE001 - retry on any transport/parse failure
            last_error = error
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"batch failed after {retries} attempts: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_DIR / "ai_queue.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--model", help="Override ONCHECK_MODELS; defaults to the first entry.")
    parser.add_argument("--level1", help="Only check pairs in this level1_category_name.")
    parser.add_argument("--limit", type=int, help="Only check the first N pairs (dry run / cost probe).")
    parser.add_argument("--restart", action="store_true", help="Ignore existing verdicts and redo everything.")
    parser.add_argument(
        "--no-catalog",
        action="store_true",
        help="Ablation: withhold the level1 leaf list, to measure what supplying it is worth.",
    )
    parser.add_argument("--tag", default="", help="Suffix for the output files, to keep experiments apart.")
    args = parser.parse_args()

    config = load_config()
    model = args.model or config["models"][0]

    queue = json.loads(args.queue.read_text(encoding="utf-8"))
    pairs = queue["pairs"]
    if args.level1:
        pairs = [p for p in pairs if p["level1_category_name"] == args.level1]
    if args.limit:
        pairs = pairs[: args.limit]
    if not pairs:
        raise SystemExit("Queue is empty after filtering.")

    slug = re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")
    if args.tag:
        slug = f"{slug}__{re.sub(r'[^a-z0-9]+', '-', args.tag.lower()).strip('-')}"
    verdict_path = args.output_dir / f"ai_verdicts_{slug}.json"
    skill_env.chuan_bi(config, verdict_path)
    done: dict[str, dict] = {}
    if verdict_path.exists() and not args.restart:
        done = {str(k): v for k, v in json.loads(verdict_path.read_text(encoding="utf-8")).items()}
        print(f"resuming: {len(done)} pairs already judged by {model}")

    catalog = queue.get("leaf_catalog", {})
    if not catalog:
        raise SystemExit("ai_queue.json has no leaf_catalog; rerun rule_check.py to regenerate it.")

    todo = [p for p in pairs if pair_key(p) not in done]
    # One batch never mixes level1 groups: the prompt carries that group's whole leaf catalog.
    grouped: dict[str, list[dict]] = {}
    for pair in todo:
        grouped.setdefault(pair["level1_category_name"], []).append(pair)
    batches: list[tuple[str, list[dict]]] = []
    for level1, members in grouped.items():
        size = config["batch_size"]
        batches.extend((level1, members[i : i + size]) for i in range(0, len(members), size))
    print(
        f"model={model}  pairs={len(pairs)}  todo={len(todo)}"
        f"  level1_groups={len(grouped)}  batches={len(batches)}"
    )

    by_id = {p["pair_id"]: p for p in pairs}
    failures = 0
    completed = 0
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    started = time.time()

    def run(level1: str, batch: list[dict]) -> tuple[list[dict], dict]:
        leaves = None if args.no_catalog else catalog.get(level1, [])
        return call_model(config, model, batch, level1, leaves)

    with concurrent.futures.ThreadPoolExecutor(max_workers=config["concurrency"]) as pool:
        futures = {pool.submit(run, level1, batch): batch for level1, batch in batches}
        for future in concurrent.futures.as_completed(futures):
            batch = futures[future]
            try:
                verdicts, usage = future.result()
                for key in tokens:
                    tokens[key] += int(usage.get(key) or 0)
                for verdict in verdicts:
                    pair = by_id.get(int(verdict["id"]))
                    if pair is not None:
                        # Filed under the pair's content key, never its ordinal: the ordinal
                        # is reassigned whenever the input changes, and a resumed run then
                        # hands old answers to different products.
                        done[pair_key(pair)] = verdict
            except skill_env.ThieuTraLoi:
                pass              # cho agent tra loi, KHONG phai that bai
            except Exception as error:  # noqa: BLE001 - a dead batch must not kill the run
                failures += 1
                with _print_lock:
                    print(f"  batch of {len(batch)} failed: {error}")
            completed += 1
            if completed % 10 == 0 or completed == len(batches):
                verdict_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
                with _print_lock:
                    print(f"  {completed}/{len(batches)} batches, {len(done)} verdicts")

    verdict_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    skill_env.chot_hoi_dap("ai_check")     # che do agent: thoat 4 neu con cau chua tra loi

    # A suggestion is only actionable if it names a leaf that really exists under that level1.
    leaf_ids = queue.get("leaf_ids", {})
    resolvers = {
        level1: {fold(name): name for name in names} for level1, names in catalog.items()
    }

    report = []
    counts: dict[str, int] = {}
    rows_by_verdict: dict[str, int] = {}
    invalid_suggestions = 0
    for pair in pairs:
        verdict = done.get(pair_key(pair), {})
        label = str(verdict.get("verdict", "MISSING"))
        counts[label] = counts.get(label, 0) + 1
        rows_by_verdict[label] = rows_by_verdict.get(label, 0) + pair["row_count"]

        level1 = pair["level1_category_name"]
        suggested = str(verdict.get("suggested_category") or "").strip()
        resolved = resolvers.get(level1, {}).get(fold(suggested), "") if suggested else ""
        candidate_ids = leaf_ids.get(level1, {}).get(resolved, []) if resolved else []
        suggested_id = candidate_ids[0] if len(candidate_ids) == 1 else ""
        if suggested and not resolved:
            invalid_suggestions += 1

        report.append(
            (
                pair["pair_id"],
                level1,
                pair["sample_description"],
                pair["leaf_category_id"],
                pair["leaf_category_name"],
                pair["rule_verdict"],
                pair["rule_score"],
                label,
                verdict.get("confidence", ""),
                verdict.get("reason", ""),
                suggested,
                resolved,
                suggested_id,
                "" if not suggested else ("YES" if resolved else "NOT_IN_CATALOG"),
                pair["row_count"],
                ", ".join(str(p) for p in pair["part_ids"]),
            )
        )

    report.sort(key=lambda r: (r[7] != "wrong", r[7] != "unsure", -r[14]))
    report_path = args.output_dir / f"ai_report_{slug}.xlsx"
    write_rows(
        report_path,
        report,
        [
            "pair_id", "level1_category_name", "sample_description",
            "leaf_category_id", "leaf_category_name",
            "rule_verdict", "rule_score",
            "ai_verdict", "ai_confidence", "ai_reason",
            "ai_suggested_raw", "ai_suggested_leaf_name", "ai_suggested_leaf_id", "ai_suggested_valid",
            "row_count", "sample_part_ids",
        ],
        sheet="ai_report",
    )

    print(f"\n{'verdict':<12}{'pairs':>8}{'rows':>10}")
    for label in sorted(counts, key=lambda k: -counts[k]):
        print(f"{label:<12}{counts[label]:>8}{rows_by_verdict[label]:>10}")
    if invalid_suggestions:
        print(f"\n{invalid_suggestions} suggestion(s) name a leaf outside the catalog (ai_suggested_valid=NOT_IN_CATALOG)")
    elapsed = time.time() - started
    if todo:
        print(
            f"\n{len(todo)} pairs in {elapsed:.0f}s"
            f" | tokens prompt={tokens['prompt_tokens']} completion={tokens['completion_tokens']}"
            f" total={tokens['total_tokens']}"
            f" ({tokens['total_tokens'] / max(1, len(todo)):.0f}/pair)"
        )
    print(f"\nverdicts -> {verdict_path}\nreport   -> {report_path}")
    if failures:
        # Exiting 0 here let audit.py carry on: build_final changed 0 rows, its own
        # verification passed on an empty diff, and the run reported success having
        # judged nothing. A partial pass must never reach the downstream stages.
        raise SystemExit(
            f"\n{failures} batch(es) failed. Verdicts written so far are kept — rerun the same "
            f"command to fill the gaps (it resumes), then continue."
        )


if __name__ == "__main__":
    main()
