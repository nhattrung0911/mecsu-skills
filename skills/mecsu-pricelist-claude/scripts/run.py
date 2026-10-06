"""One command for the whole pricelist pipeline: data.xlsx -> A4 price-list .xlsx (+ page PNGs).

Exit codes: 0 done | 1 QA errors (first line `FAIL qa`) | 2 bad usage / a stage crashed
            4 STOP, agent action needed (first line `STOP 4 <plan|data|lint|images|images-review>`)
Stages: read(+patch, analyze) > draft(+kb apply) > lint > images > layout(+build, qa, render)
State : <out>/run_state.json. After any STOP fix the cause and run the printed RERUN command (`--resume`).
        `--from X` is refused when an earlier stage never completed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from pl_common import SKILL_DIR, user_home  # noqa: E402

STAGES = ["read", "draft", "lint", "images", "layout"]
STATE_NAME = "run_state.json"


class Stop(Exception):
    def __init__(self, code: int, msg: str, kind: str = "", stage: str | None = None):
        super().__init__(msg)
        self.code, self.msg, self.kind, self.stage = code, msg, kind, stage


# warnings that are normal in real data and never stop the run (still shown in the summary)
IGNORABLE = ("duplicate order id", "missing price", "non-numeric price", "invalid order id")


def sh(script: str, *args, check=True) -> subprocess.CompletedProcess:
    """Run a sibling pl_* script. With check, a non-zero exit raises Stop(2)."""
    cmd = [sys.executable, str(HERE / script), *map(str, args)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise Stop(2, f"{script} failed (exit {r.returncode}):\n{(r.stdout + r.stderr).strip()[-1500:]}")
    return r


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def jdump(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def default_logo(code: str) -> str | None:
    for base in (user_home() / "logos", SKILL_DIR / "assets" / "logos"):
        p = base / f"{code.lower()}.png"
        if p.exists():
            return str(p)
    return None


# ------------------------------------------------------------------ state
def load_state(out: Path) -> dict:
    f = out / STATE_NAME
    base = {"completed": [], "stop": None, "stop_kind": None, "review_done": False, "rejected": [], "notes": []}
    if f.exists():
        try:
            base.update(jload(f))
        except Exception:
            pass
    return base


def save_state(out: Path, st: dict):
    jdump(out / STATE_NAME, st)


def mark(a, stage: str):
    if stage not in a.state["completed"]:
        a.state["completed"].append(stage)


def norm_tok(t: str) -> str:
    return str(Path(t)) if ("/" in t or "\\" in t) and not t.startswith("-") else t


def quote(x: str) -> str:
    return f'"{x}"' if re.search(r"[^\w./\\:=@%+-]", x) else x


def rerun_cmd(argv: list[str], extra: list[str] | None = None) -> str:
    """Original command with --from X / --resume replaced by `extra` + a single --resume."""
    keep, skip = [], False
    for t in argv:
        if skip:
            skip = False
        elif t == "--from":
            skip = True
        elif t.startswith("--from=") or t == "--resume":
            continue
        else:
            keep.append(norm_tok(t))
    return ("python " + quote(str(HERE / "run.py")) + " " + " ".join(quote(t) for t in keep) +
            "".join(" " + quote(norm_tok(x)) for x in (extra or [])) + " --resume")


def rows_note(rows_in: int, n_out: int, dups: int) -> str:
    other = rows_in - n_out - dups
    return (f"{rows_in} dòng → {n_out} mã ({dups} trùng" +
            (f"; {other} dòng khác đã bỏ: thiếu/sai order id hoặc lọc hãng" if other > 0 else "") + ")")


def set_note(st: dict, prefix: str, text: str):
    st["notes"] = [n for n in st["notes"] if not n.startswith(prefix)] + [text]


RE_DB = re.compile(r"([dB]) \(([-\d.]+)\) >= D")


def patchable_still_wrong(w: str, items: dict) -> bool:
    """Re-evaluate a patchable warning against the (possibly patched) items."""
    from pl_read import _num
    rows = [(g, r) for g in items["groups"] for r in g["rows"]]
    m = re.search(r" (\S+): (?:spec missing|[dB] \()", w)
    if not m:
        return True
    code = m.group(1)
    hits = [(g, r) for g, r in rows if r["code"] == code]
    if not hits:
        return True
    for g, r in hits:
        if "spec missing" in w:
            labs = re.search(r"\(([^)]*) empty\)\s*$", w)
            names = [x.strip().lower() for x in labs.group(1).split(",")] if labs else []
            for c in g["spec_columns"]:
                if c["label"].split("\n")[0].strip().lower() in names and r["specs"].get(c["key"]) in (None, ""):
                    return True
        else:
            D = _num(r["specs"].get("D_mm"))
            v = _num(r["specs"].get(RE_DB.search(w).group(1) + "_mm"))
            if D is not None and v is not None and v >= D:
                return True
    return False


# ------------------------------------------------------------------ stages
def affected_codes(w: str, codes: set[str]) -> list[str]:
    if "cannot tell apart:" in w:
        tail = w.split("cannot tell apart: ", 1)[1].rsplit(" (", 1)[0]
        return [c for c in tail.split(", ") if c in codes]
    best = None
    for c in codes:
        i = w.find(f" {c}: ")
        if i >= 0 and (best is None or i < best[0] or (i == best[0] and len(c) > len(best[1]))):
            best = (i, c)
    return [best[1]] if best else []


def is_patchable(w: str) -> bool:
    return "spec missing" in w or bool(RE_DB.search(w))


def write_items_warnings(out: Path, items: dict, bad: list[str], report_only: list[str] | None = None) -> int:
    """items_warnings.txt: one line per affected code (patchable), then a 'chỉ báo user' section."""
    orders: dict[str, list[str]] = {}
    for g in items["groups"]:
        for r in g["rows"]:
            orders.setdefault(r["code"], []).append(r.get("order_code") or "?")
    codes, per, other = set(orders), {}, []
    for w in bad:
        hit = affected_codes(w, codes)
        if not hit:
            other.append(w)
        for c in hit:
            loc = w.split(f" {c}: ")[0] if f" {c}: " in w else w.split(": ")[0]
            per.setdefault(c, []).append((loc, w.split(f" {c}: ", 1)[1] if f" {c}: " in w else w))
    lines = [f"{c} | order {','.join(dict.fromkeys(orders[c]))} | {'; '.join(dict.fromkeys(l for l, _ in v))} | "
             f"{' / '.join(dict.fromkeys(m for _, m in v))}" for c, v in per.items()]
    lines += [f"(sheet) | | | {w}" for w in other]
    if report_only:
        lines += ["", "# chỉ báo user (worker không sửa được, không chặn chạy)"] + [f"- {w}" for w in report_only]
    (out / "items_warnings.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(per) + len(other)


def stage_read(a, out: Path, log):
    items = out / "items.json"
    log(sh("pl_read.py", *a.data, "-o", items).stdout.strip())
    for pf in a.patches or []:
        log("patched: " + sh("pl_patch.py", items, pf, "-o", items).stdout.strip())
    data = jload(items)
    rows_in = sum(len(g["rows"]) for g in data["groups"])
    dups = sum(1 for w in data.get("warnings", []) if "duplicate order id" in w)
    a.state["rows_in"], a.state["dups"] = rows_in, dups
    set_note(a.state, "rows:", "rows: " + rows_note(rows_in, rows_in - dups, dups))
    brands = data.get("brands") or {}
    nobrand = rows_in - sum(brands.values())
    if brands or nobrand:
        parts = [f"{b} {n}" for b, n in brands.items()] + ([f"(không ghi hãng) {nobrand}"] if nobrand else [])
        tail = f" - lọc theo '{a.brand_filter}' (dòng không ghi hãng vẫn giữ)" if a.brand_filter else " — giữ lại"
        a.state["notes"] = [n for n in a.state["notes"] if not n.startswith("hãng:")] + [
            "hãng: " + ", ".join(parts) + tail]
    rest = [w for w in data.get("warnings", []) if not any(k in w for k in IGNORABLE)]
    bad = [w for w in rest if is_patchable(w) and patchable_still_wrong(w, data)]  # re-checked after patches
    report_only = [w for w in rest if not is_patchable(w)]
    a.state["report_only"] = report_only
    n_bad = write_items_warnings(out, data, bad, report_only) if (bad or report_only) else 0
    n_bad = n_bad if bad else 0
    plan, md = out / "plan.json", out / "plan.md"
    r = sh("pl_analyze.py", items, "-o", plan, "--md", md)
    log(r.stdout.strip())
    flags = [ln for ln in r.stdout.splitlines() if ln.startswith("FLAG")]
    if n_bad and not a.accept_data:
        head = (f"{n_bad} data code(s) STILL unresolved after --patches: report them to the user, then "
                if a.patches else f"{n_bad} data code(s) look wrong (spec missing / d>=D / B>=D), ")
        opts = [f"Không có nguồn / user chấp nhận data như hiện tại: RERUN: {rerun_cmd(a.orig, ['--accept-data'])}"]
        if not a.patches:
            opts.insert(0, "Có patches (worker A ghi team/patches_A.json, brief A, từ >= 3 mã): "
                           f"RERUN: {rerun_cmd(a.orig, ['--patches', str(out / 'team' / 'patches_A.json')])}")
        raise Stop(4, head + f"one line per code in {out / 'items_warnings.txt'}\n" + "\n".join(opts),
                   "data", "read")
    mark(a, "read")
    if flags and not a.accept_plan:
        raise Stop(4, "PLAN HAS FLAGS - review before drafting.\n"
                      f"  plan.md  : {md}\n  plan.json: {plan}\n" + "\n".join("  " + f for f in flags) + "\n"
                      f"Đã sửa plan.json (family / split / sort / title_suffix / legend_defaults): RERUN: {rerun_cmd(a.orig)}\n"
                      f"Giữ nguyên plan: RERUN: {rerun_cmd(a.orig, ['--accept-plan'])}", "plan", "draft")


def stage_draft(a, out: Path, log):
    items, plan, doc = out / "items.json", out / "plan.json", out / "doc.json"
    for f in (items, plan):
        if not f.exists():
            raise Stop(2, f"{f} missing - run without --from first")
    args = [items, "--brand", a.brand, "--code", a.code, "--plan", plan, "-o", doc]
    logo = a.logo or default_logo(a.code)
    if logo:
        args += ["--logo", str(Path(logo).resolve())]
    else:
        log(f"WARNING: no logo for {a.code} (looked in {user_home() / 'logos'} and bundled assets/logos); pass --logo")
    if a.brand_filter:
        args += ["--brand-filter", a.brand_filter]
    log(sh("pl_draft.py", *args).stdout.strip())
    log("kb apply: " + sh("pl_kb.py", "apply", doc, "--brand", a.code).stdout.strip())
    rows_in = a.state.get("rows_in")
    if rows_in is not None:
        n_out = sum(len(c.get("rows", [])) for c in jload(doc)["cards"])
        dups = a.state.get("dups", 0)
        set_note(a.state, "rows:", "rows: " + rows_note(rows_in, n_out, dups))
    mark(a, "draft")


def stage_lint(a, out: Path, log):
    doc = out / "doc.json"
    if not doc.exists():
        raise Stop(2, f"{doc} missing - run an earlier stage first")
    r = sh("pl_lint.py", doc, "--fix", "-o", out / "lint_report.md", check=False)
    log("lint: " + r.stdout.strip())
    if r.returncode != 0:
        try:
            errs = json.loads(r.stdout.strip().splitlines()[-1]).get("first_errors", [])
        except Exception:
            errs = [(r.stdout + r.stderr).strip()[-800:]]
        raise Stop(4, "LINT ERRORS in doc.json:\n" + "\n".join("  - " + e for e in errs) +
                      f"\nfull report: {out / 'lint_report.md'}\n"
                      "sửa doc.json (title_source 'data' thì giữ tiêu đề), rồi chạy RERUN bên dưới "
                      "(lint chạy lại, sau đó ảnh và layout).\n"
                      "Team brief C (fix cards, >= 10 error cards): up to 3 workers each write team/edits_<n>.json; "
                      f"merge: pl_docedit.py {doc} team/edits_*.json", "lint", "lint")
    mark(a, "lint")


def merge_json_lists(files, base):
    out = list(base)
    for f in files:
        for x in jload(f):
            if x not in out:
                out.append(x)
    return out


def stage_images(a, out: Path, log):
    doc, work, picks_f = out / "doc.json", out / "img_work", out / "picks.json"
    if not doc.exists():
        raise Stop(2, f"{doc} missing - run an earlier stage first")
    work.mkdir(exist_ok=True)
    st = a.state
    # rejected catalog images: clear them, skip the catalog for them, fall through to web candidates
    rej_files = sorted((out / "team").glob("reject_*.json"))
    rej_all = merge_json_lists(rej_files, jload(out / "reject.json") if (out / "reject.json").exists() else [])
    new_rej = [c for c in rej_all if c not in st["rejected"]]
    if new_rej:
        d = jload(doc)
        known = {c["id"] for c in d["cards"]}
        for c in d["cards"]:
            if c["id"] in new_rej:
                c["image"] = None
        for c in new_rej:
            if c not in known:
                log(f"WARNING: reject.json names unknown card {c}")
        jdump(doc, d)
        st["rejected"] += new_rej
        log(f"rejected {len(new_rej)} catalog image(s): {', '.join(new_rej[:10])}")
    skipped: set[str] = set()
    team_picks = sorted((out / "team").glob("picks_*.json"))
    if team_picks:
        merged = jload(picks_f) if picks_f.exists() else {}
        origin = {k: "picks.json" for k in merged}
        for tf in team_picks:
            for k, v in jload(tf).items():
                if k in merged and merged[k] != v:
                    log(f"WARNING: pick conflict for {k}: {origin[k]}={merged[k]!r} vs {tf.name}={v!r}; using {tf.name}")
                merged[k], origin[k] = v, tf.name
        jdump(picks_f, merged)
        log(f"merged {len(team_picks)} team picks file(s) into {picks_f}")
    if picks_f.exists():
        picks = jload(picks_f)
        skipped = {k for k, v in picks.items() if v in (0, None, "none")}
        real = {k: v for k, v in picks.items() if k not in skipped}
        if real:
            applied = out / "picks.applied.json"
            applied.write_text(json.dumps(real, ensure_ascii=False), encoding="utf-8")
            log("picks: " + sh("pl_images.py", "pick", applied, "--work", work, "--doc", doc).stdout.strip())
    args = ["resolve", doc, "--work", work]
    if a.images:
        args += ["--folder", a.images]
    if a.no_catalog or a.offline:
        args.append("--no-catalog")
    if st["rejected"]:
        nc = out / "img_work" / "no_catalog_cards.json"
        jdump(nc, st["rejected"])
        args += ["--no-catalog-cards", nc]
    log(sh("pl_images.py", *args).stdout.strip())
    missing = [m for m in jload(work / "missing.json") if m["card_id"] not in skipped]
    if not missing:
        review_images(a, out, log)
        return
    if not a.offline:
        r = sh("pl_images.py", "search", work / "missing.json", "--work", work, check=False)
        log(r.stdout.strip())
        if "unavailable" in r.stderr:
            log("WARNING: web search unavailable (pip install ddgs)")
    sheets = sorted(work.glob("sheet_*.png")) if not a.offline else []
    ids = ", ".join(m["card_id"] for m in missing[:12]) + (" ..." if len(missing) > 12 else "")
    if sheets:
        how = ("View the contact sheets with the Read tool:\n" + "\n".join("  " + str(s) for s in sheets) +
               f"\nThen write {picks_f} as {{card_id: index}} (index = number on the sheet; 0 = leave without image) "
               "and run RERUN below.")
    else:
        how = (f"No candidates (offline / search unavailable). Put images named <code>.png in a folder and rerun with "
               f"--images DIR --resume, or write {picks_f} as {{card_id: \"path/to/image\"}} "
               "(0 = leave without image) and run RERUN below.")
    raise Stop(4, f"{len(missing)} card(s) still have no image: {ids}\n{how}\n"
                  "Team brief B (pick images): one worker per sheet (max 3) writes team/picks_<k>.json "
                  "{card_id: index}; the rerun merges them into picks.json.", "images", "images")


def review_images(a, out: Path, log):
    """Catalog photos can be supplier infographics / other brands: show ONE sheet of all chosen images, once."""
    st = a.state
    if a.accept_images:
        st["review_done"] = True
    cards = jload(out / "doc.json")["cards"]
    catalog = [c for c in cards if str((c.get("image") or {}).get("source", "")).startswith("catalog")]
    if st["review_done"] or not catalog:
        return
    from pl_images import chosen_sheet
    items = []
    for c in cards:
        img = c.get("image") or {}
        if img.get("path"):
            src = img.get("source") or ("web" if img.get("status") == "review" else "local")
            items.append((f"{c['id']} [{src}]", img["path"]))
    sheets = chosen_sheet(items, str(out / "img_work" / "chosen_sheet.png"))
    st["review_done"] = True  # shown once; the rerun proceeds unless reject.json names cards
    ids = ", ".join(lbl.split(" [")[0] for lbl, _ in items)
    raise Stop(4, f"{len(catalog)} catalog image(s) not yet checked (may be infographics, other brands, text).\n"
                  "View with the Read tool (one worker B for the sheet is enough):\n" +
                  "\n".join("  " + s for s in sheets) + f"\nCards on the sheet ({len(items)}): {ids}\n"
                  f"Ổn hết: RERUN: {rerun_cmd(a.orig, ['--accept-images'])}\n"
                  f"Có ảnh xấu: ghi {out / 'reject.json'} = [\"card_id\", ...] (hoặc team/reject_<k>.json) rồi "
                  f"RERUN: {rerun_cmd(a.orig)}", "images-review", "images")


def review_batches(pages: int, n: int) -> list[dict]:
    """Split pages 2..pages-1 (leader views first and last) into <= n contiguous batches."""
    mid = list(range(2, pages))
    n = max(1, min(n, len(mid)))
    k, m = divmod(len(mid), n)
    out, i = [], 0
    for w in range(n):
        size = k + (1 if w < m else 0)
        out.append({"worker": w + 1, "pages": mid[i:i + size]})
        i += size
    return out


def stage_layout(a, out: Path, log) -> dict:
    doc = out / "doc.json"
    if not doc.exists():
        raise Stop(2, f"{doc} missing - run an earlier stage first")
    placed, xlsx = out / "doc.placed.json", out / f"BẢNG GIÁ {a.brand}.xlsx"
    if xlsx.resolve() in {Path(p).resolve() for p in a.data}:
        raise Stop(2, "output xlsx would overwrite an input file; choose another --out")
    log(sh("pl_layout.py", doc, "-o", placed).stdout.strip())
    log(sh("pl_build.py", placed, "-o", xlsx).stdout.strip())
    r = sh("pl_qa.py", xlsx, "--doc", placed, "-o", out / "qa_report.md", check=False)
    log("qa: " + r.stdout.strip())
    renders = None
    if a.no_render:
        log("render skipped (--no-render)")
    else:
        rr = sh("pl_render.py", xlsx, "--out", out / "renders", check=False)
        if rr.returncode == 0:
            renders = out / "renders"
        else:
            note = rr.stderr.strip().splitlines()[-1] if rr.stderr.strip() else f"exit {rr.returncode}"
            log(f"WARNING: render skipped ({note}); run pl_doctor.py to check Excel/pywin32")
    batches = None
    pages = jload(placed)["meta"].get("page_count") or 0
    if renders and pages > 4:
        batches = review_batches(pages, a.review_batches)
        jdump(out / "team" / "review_batches.json", batches)
        log("review batches (team brief D): " + json.dumps(batches))
    return {"xlsx": xlsx, "placed": placed, "renders": renders, "qa_err": r.returncode != 0, "batches": batches}


def summary(out: Path, res: dict, warns: list[str], report_only: list[str]):
    placed = jload(res["placed"])
    cards = placed["cards"]
    rows = sum(len(c.get("rows", [])) for c in cards)
    review = [f"image from web, needs approval: card {c['id']}" for c in cards
              if (c.get("image") or {}).get("status") == "review"]
    unk = out / "kb_unknown.json"
    if unk.exists():
        n = len({u["code"] for u in jload(unk)})
        if n:
            review.append(f"{n} code(s) not in KB yet (kb_unknown.json); store with pl_kb.py learn after approval")
    try:
        warns = warns + [f"data: {w}" for w in jload(out / "items.json").get("warnings", [])]
    except Exception:
        pass
    print("\n=== SUMMARY (QA FAILED) ===" if res["qa_err"] else "\n=== DONE ===")
    print(f"xlsx    : {res['xlsx']}")
    print(f"pages   : {placed['meta'].get('page_count')}   cards: {len(cards)}   rows: {rows}")
    print(f"renders : {res['renders'] or '(none)'}")
    print(f"qa      : {out / 'qa_report.md'}")
    print(f"warnings: {len(warns)}")
    for w in warns[:15]:
        print("  - " + w)
    print(f"Cần user quyết: {len(report_only)}")
    for w in report_only[:15]:
        print("  - " + w)
    print(f"review  : {len(review)}")
    for r in review[:15]:
        print("  - " + r)


RUNNERS = {"read": stage_read, "draft": stage_draft, "lint": stage_lint, "images": stage_images}


def main(argv=None) -> int:
    orig = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("data", nargs="+", help="data .xlsx file(s); never modified")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--code", required=True, help="page code, 2-4 capitals (BSI)")
    ap.add_argument("--logo")
    ap.add_argument("--images", help="folder of images named <code>.png or <group slug>.png")
    ap.add_argument("--out", help="default: <first data dir>/output/<code lower>")
    ap.add_argument("--brand-filter")
    ap.add_argument("--patches", nargs="+", help="patches.json file(s) for pl_patch (applied in order)")
    ap.add_argument("--accept-data", action="store_true", help="do not stop on suspicious data warnings")
    ap.add_argument("--accept-images", action="store_true", help="skip the one-time catalog image review stop")
    ap.add_argument("--review-batches", type=int, default=3, help="max page-review workers when pages > 4")
    ap.add_argument("--from", dest="start", choices=STAGES, default=None,
                    help="restart at this stage; refused if an earlier stage never completed")
    ap.add_argument("--resume", action="store_true", help="restart at the stage that stopped last time")
    ap.add_argument("--accept-plan", action="store_true")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-catalog", action="store_true", help="skip the mecsu.vn catalog image lookup")
    ap.add_argument("--offline", action="store_true", help="no network at all (implies --no-catalog, no web search)")
    a = ap.parse_args(argv)
    a.code = a.code.upper()
    for p in a.data:
        if not Path(p).is_file():
            print(f"input not found: {p}", file=sys.stderr)
            return 2
    out = Path(a.out) if a.out else Path(a.data[0]).resolve().parent / "output" / a.code.lower()
    out.mkdir(parents=True, exist_ok=True)
    (out / "team").mkdir(exist_ok=True)
    a.orig = orig
    a.state = st = load_state(out)
    if a.resume:
        start = st["stop"] if st["stop"] in STAGES else ("layout" if st["completed"] else "read")
    else:
        start = a.start or "read"
    si = STAGES.index(start)
    for prev in STAGES[:si]:
        if prev not in st["completed"]:
            print(f"ERROR: --from {start} refused: stage '{prev}' never completed "
                  f"(completed: {', '.join(st['completed']) or 'none'}). Use --resume to restart at the stage that "
                  f"stopped (last stop: {st['stop'] or 'none'}).")
            return 2
    st["completed"] = [s for s in st["completed"] if STAGES.index(s) < si]
    st["stop"] = st["stop_kind"] = None
    warns: list[str] = []
    buf: list[str] = []

    def log(msg):  # buffered so the machine-readable STOP/FAIL line can come first
        if msg:
            buf.append(msg)
            if msg.startswith("WARNING"):
                warns.append(msg)

    try:
        for s in STAGES[si:-1]:
            RUNNERS[s](a, out, log)
            mark(a, s)
        res = stage_layout(a, out, log)
    except Stop as s:
        if s.stage:
            st["stop"], st["stop_kind"] = s.stage, s.kind
        save_state(out, st)
        print(f"STOP 4 {s.kind}" if s.code == 4 else "ERROR")
        print("\n".join(f"note: {n}" for n in st["notes"]))
        print("\n".join(buf))
        print(s.msg)
        if s.code == 4 and "RERUN:" not in s.msg:
            print("RERUN: " + rerun_cmd(orig))
        return s.code
    if res["qa_err"]:
        st["stop"], st["stop_kind"] = "layout", "qa"
    else:
        mark(a, "layout")
    save_state(out, st)
    if res["qa_err"]:
        print("FAIL qa")
    print("\n".join(f"note: {n}" for n in st["notes"]))
    print("\n".join(buf))
    summary(out, res, warns, st.get("report_only", []))
    if res["qa_err"]:
        print(f"QA ERRORS - see {out / 'qa_report.md'}; fix doc.json then run RERUN below (restarts at layout)")
        print("RERUN: " + rerun_cmd(orig))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
