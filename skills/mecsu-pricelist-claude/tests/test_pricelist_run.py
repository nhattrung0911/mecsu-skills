import json
import sys

import openpyxl
import pytest
from PIL import Image

import run

HDR = ["Mã Hãng", "Tên Bảng Giá", "Order ID", "Varin Price", "d\nmm", "D\nmm", "B\nmm", "Nắp chắn"]
ROWS = [["6204-2RS", "Vòng Bi Cầu", 1000001, 5200, 20, 47, 14, "2 Phớt"],
        ["6205-2RS", "Vòng Bi Cầu", 1000002, 6100, 25, 52, 15, "2 Phớt"],
        ["6206-2RS", "Vòng Bi Cầu", 1000003, 7300, 30, 62, 16, "2 Phớt"]]


def make_xlsx(tmp_path, name="data.xlsx"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(HDR)
    for r in ROWS:
        ws.append(r)
    p = tmp_path / name
    wb.save(p)
    return p


def make_images(tmp_path):
    d = tmp_path / "imgs"
    d.mkdir()
    for r in ROWS:
        Image.new("RGB", (60, 40), (200, 30, 30)).save(d / f"{r[0]}.png")
    return d


def go(capsys, *argv):
    code = run.main([str(a) for a in argv])
    return code, capsys.readouterr().out


@pytest.fixture
def data(tmp_path):
    return make_xlsx(tmp_path)


def test_happy_path(tmp_path, data, capsys):
    imgs = make_images(tmp_path)
    before = data.read_bytes()
    out = tmp_path / "out"
    code, text = go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--images", imgs, "--out", out,
                    "--accept-plan", "--no-render", "--offline")
    assert code == 0, text
    xlsx = out / "BẢNG GIÁ BOSI.xlsx"
    assert xlsx.exists() and "=== DONE ===" in text and "cards:" in text
    assert data.read_bytes() == before
    assert (out / "doc.placed.json").exists() and (out / "qa_report.md").exists()


def test_default_out_dir(tmp_path, data, capsys):
    imgs = make_images(tmp_path)
    code, _ = go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--images", imgs, "--accept-plan",
                 "--no-render", "--offline")
    assert code == 0
    assert (tmp_path / "output" / "bsi" / "doc.json").exists()


def test_stop_on_plan_flags_then_continue(tmp_path, data, capsys):
    out = tmp_path / "out"
    base = [data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--no-render", "--offline"]
    code, text = go(capsys, *base)  # no images: if plan has flags we stop there, else at images
    if "PLAN HAS FLAGS" in text:
        assert code == 4 and "plan.md" in text and "--resume" in text
        code, text = go(capsys, *base, "--resume")
    assert code == 4 and "no image" in text  # images missing, offline


def test_stop_on_lint_error(tmp_path, capsys):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR)
    for r in ROWS:  # a 85-char title is a lint error (> 40)
        ws.append([r[0], "Vòng Bi Cầu Rất Rất Rất Dài Dòng Không Hợp Lệ Cho Một Tiêu Đề Card Nào Cả"] + r[2:])
    p = tmp_path / "long.xlsx"
    wb.save(p)
    code, text = go(capsys, p, "--brand", "BOSI", "--code", "BSI", "--out", tmp_path / "out", "--accept-plan",
                    "--offline", "--no-render")
    assert code == 4 and "LINT ERRORS" in text and "--resume" in text and "title 85 chars" in text
    assert not list((tmp_path / "out").glob("*.xlsx"))


def test_stop_on_missing_images_offline(tmp_path, data, capsys):
    out = tmp_path / "out"
    code, text = go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--accept-plan",
                    "--offline", "--no-render")
    assert code == 4 and "no image" in text and "picks.json" in text
    assert not list(out.glob("*.xlsx"))


def test_picks_zero_means_no_image(tmp_path, data, capsys):
    out = tmp_path / "out"
    go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--accept-plan", "--offline", "--no-render")
    missing = json.loads((out / "img_work" / "missing.json").read_text(encoding="utf-8"))
    (out / "picks.json").write_text(json.dumps({m["card_id"]: 0 for m in missing}), encoding="utf-8")
    code, text = go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--offline", "--no-render",
                    "--from", "images")
    assert code in (0, 1), text  # built; QA may complain about missing image
    assert (out / "BẢNG GIÁ BOSI.xlsx").exists()


def test_from_layout_reuses_doc(tmp_path, data, capsys):
    imgs = make_images(tmp_path)
    out = tmp_path / "out"
    base = [data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--no-render", "--offline"]
    assert go(capsys, *base, "--images", imgs, "--accept-plan")[0] == 0
    doc = json.loads((out / "doc.json").read_text(encoding="utf-8"))
    doc["cards"][0]["note"] = "SENTINEL NOTE"
    (out / "doc.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    assert go(capsys, *base, "--from", "layout")[0] == 0
    assert "SENTINEL NOTE" in (out / "doc.placed.json").read_text(encoding="utf-8")


def test_missing_input(tmp_path, capsys):
    assert run.main([str(tmp_path / "nope.xlsx"), "--brand", "B", "--code", "BB"]) == 2


def test_default_logo_order(tmp_path, monkeypatch):
    assert run.default_logo("bsi").replace("\\", "/").endswith("assets/logos/bsi.png")
    (tmp_path / "plhome2" / "logos").mkdir(parents=True)
    (tmp_path / "plhome2" / "logos" / "bsi.png").write_bytes(b"x")
    monkeypatch.setenv("MECSU_PRICELIST_HOME", str(tmp_path / "plhome2"))
    assert run.default_logo("BSI").startswith(str(tmp_path / "plhome2"))
    assert run.default_logo("zzzz") is None


def test_stop_first_line_is_machine_readable(tmp_path, data, capsys):
    out = tmp_path / "out"
    code, text = go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--accept-plan", "--offline",
                    "--no-render")
    assert code == 4 and text.splitlines()[0] == "STOP 4 images" and "brief B" in text
    assert (out / "team").is_dir()


def test_stop_data_on_suspicious_warning(tmp_path, capsys):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR)
    ws.append(["6204-2RS", "Vòng Bi Cầu", 1000001, 5200, 50, 47, 14, "2 Phớt"])  # d >= D
    ws.append(["6205-2RS", "Vòng Bi Cầu", 1000001, 5200, 25, 52, 15, "2 Phớt"])  # duplicate order id: ignorable
    p = tmp_path / "d.xlsx"
    wb.save(p)
    out = tmp_path / "out"
    code, text = go(capsys, p, "--brand", "B", "--code", "BSI", "--out", out, "--offline", "--no-render")
    assert code == 4 and text.splitlines()[0] == "STOP 4 data" and "brief A" in text
    warn = (out / "items_warnings.txt").read_text(encoding="utf-8")
    assert "d (50)" in warn and "duplicate" not in warn
    code, text = go(capsys, p, "--brand", "B", "--code", "BSI", "--out", out, "--offline", "--no-render",
                    "--accept-data", "--accept-plan")
    assert text.splitlines()[0] != "STOP 4 data"


def test_stop_plan_kind(tmp_path, capsys, monkeypatch):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR)
    for i in range(45):  # large group without split rule -> plan flag
        ws.append([f"ZZ{i}", "Thứ Lạ", 1000100 + i, 100, 1, 2, 3, "x"])
    p = tmp_path / "p.xlsx"
    wb.save(p)
    code, text = go(capsys, p, "--brand", "B", "--code", "BSI", "--out", tmp_path / "o", "--offline", "--no-render")
    assert code == 4 and text.splitlines()[0] in ("STOP 4 plan", "STOP 4 data")


def test_team_picks_merge_later_wins(tmp_path, data, capsys):
    out = tmp_path / "out"
    go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--accept-plan", "--offline", "--no-render")
    cid = json.loads((out / "img_work" / "missing.json").read_text(encoding="utf-8"))[0]["card_id"]
    (out / "picks.json").write_text(json.dumps({cid: 1}), encoding="utf-8")
    (out / "team" / "picks_1.json").write_text(json.dumps({cid: 2}), encoding="utf-8")
    (out / "team" / "picks_2.json").write_text(json.dumps({cid: 0}), encoding="utf-8")
    code, text = go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--offline", "--no-render",
                    "--from", "images")
    assert "pick conflict" in text and "picks_2.json" in text
    assert json.loads((out / "picks.json").read_text(encoding="utf-8"))[cid] == 0


def test_review_batches():
    assert run.review_batches(4, 3) == [{"worker": 1, "pages": [2]}, {"worker": 2, "pages": [3]}]
    b = run.review_batches(10, 3)
    assert [x["pages"] for x in b] == [[2, 3, 4], [5, 6, 7], [8, 9]]
    assert 1 not in sum((x["pages"] for x in b), []) and 10 not in sum((x["pages"] for x in b), [])


# ---------------------------------------------------------------- resume / state / review
def long_title_xlsx(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR)
    for r in ROWS:
        ws.append([r[0], "Vòng Bi Cầu Rất Rất Rất Dài Dòng Không Hợp Lệ Cho Một Tiêu Đề Card Nào Cả"] + r[2:])
    p = tmp_path / "long.xlsx"
    wb.save(p)
    return p


def test_from_trap_refused_and_resume_reruns_lint(tmp_path, capsys):
    p, out, imgs = long_title_xlsx(tmp_path), tmp_path / "out", make_images(tmp_path)
    base = [p, "--brand", "BOSI", "--code", "BSI", "--out", out, "--accept-plan", "--offline", "--no-render",
            "--images", imgs]
    code, text = go(capsys, *base)
    assert code == 4 and text.splitlines()[0] == "STOP 4 lint" and "--resume" in text.splitlines()[-1]
    assert json.loads((out / "run_state.json").read_text(encoding="utf-8"))["stop"] == "lint"
    code, text = go(capsys, *base, "--from", "layout")  # the trap: images never ran
    assert code == 2 and "refused" in text and "lint" in text and not list(out.glob("*.xlsx"))
    doc = json.loads((out / "doc.json").read_text(encoding="utf-8"))
    for c in doc["cards"]:
        c["title"] = "VÒNG BI CẦU"
    (out / "doc.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    code, text = go(capsys, *base, "--resume")
    assert code == 0, text
    assert (out / "BẢNG GIÁ BOSI.xlsx").exists() and "=== DONE ===" in text


def test_resume_without_state_starts_at_read(tmp_path, data, capsys):
    imgs = make_images(tmp_path)
    code, _ = go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--out", tmp_path / "o", "--accept-plan",
                 "--offline", "--no-render", "--images", imgs, "--resume")
    assert code == 0


def test_fail_qa_prints_no_done(tmp_path, data, capsys, monkeypatch):
    import subprocess
    imgs = make_images(tmp_path)
    real = run.sh

    def fake(script, *args, check=True):
        if script == "pl_qa.py":
            return subprocess.CompletedProcess([], 1, "errors=1 warnings=0", "")
        return real(script, *args, check=check)
    monkeypatch.setattr(run, "sh", fake)
    code, text = go(capsys, data, "--brand", "BOSI", "--code", "BSI", "--out", tmp_path / "o", "--accept-plan",
                    "--offline", "--no-render", "--images", imgs)
    assert code == 1 and text.splitlines()[0] == "FAIL qa" and "=== DONE ===" not in text
    assert "RERUN:" in text and "--resume" in text


def test_items_warnings_one_line_per_code_and_row_note(tmp_path, capsys):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR)
    ws.append(["6204-2RS", "Vòng Bi Cầu", 1000001, 5200, 50, 47, 60, "2 Phớt"])  # d>=D and B>=D: one code, 2 warnings
    ws.append(["6205-2RS", "Vòng Bi Cầu", 1000002, 5200, 60, 52, 15, "2 Phớt"])
    ws.append(["6206-2RS", "Vòng Bi Cầu", 1000002, 5200, 30, 62, 16, "2 Phớt"])  # duplicate order id
    p = tmp_path / "w.xlsx"
    wb.save(p)
    out = tmp_path / "o"
    code, text = go(capsys, p, "--brand", "B", "--code", "BSI", "--out", out, "--offline", "--no-render")
    assert code == 4 and text.splitlines()[0] == "STOP 4 data" and text.count("2 data code(s)") == 1
    lines = (out / "items_warnings.txt").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and lines[0].startswith("6204-2RS | order 1000001 |")
    assert "d (50)" in lines[0] and "B (60)" in lines[0] and "Sheet!2" in lines[0]
    code, text = go(capsys, p, "--brand", "B", "--code", "BSI", "--out", out, "--offline", "--no-render",
                    "--accept-data", "--accept-plan")
    assert "3 dòng → 2 mã (1 trùng)" in text


def test_brand_line(tmp_path, capsys):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR + ["Thương Hiệu"])
    for i, r in enumerate(ROWS):
        ws.append(r + ["Bosi" if i < 2 else None])
    p = tmp_path / "b.xlsx"
    wb.save(p)
    code, text = go(capsys, p, "--brand", "Bosi", "--code", "BSI", "--out", tmp_path / "o", "--offline",
                    "--no-render", "--accept-plan")
    st = json.loads((tmp_path / "o" / "run_state.json").read_text(encoding="utf-8"))
    assert any("Bosi 2" in n and "(không ghi hãng) 1" in n and "giữ lại" in n for n in st["notes"]), st["notes"]


def _with_catalog_source(out):
    doc = json.loads((out / "doc.json").read_text(encoding="utf-8"))
    for c in doc["cards"]:
        c["image"]["source"] = "catalog:test"
    (out / "doc.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return [c["id"] for c in doc["cards"]]


def test_images_review_once_then_resume(tmp_path, data, capsys):
    imgs, out = make_images(tmp_path), tmp_path / "o"
    base = [data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--offline", "--no-render", "--accept-plan",
            "--images", imgs]
    assert go(capsys, *base)[0] == 0
    _with_catalog_source(out)
    code, text = go(capsys, *base, "--from", "images")
    assert code == 4 and text.splitlines()[0] == "STOP 4 images-review"
    assert (out / "img_work" / "chosen_sheet.png").exists() and "RERUN:" in text
    code, text = go(capsys, *base, "--resume")
    assert code == 0, text  # shown once only


def test_accept_images_skips_review(tmp_path, data, capsys):
    imgs, out = make_images(tmp_path), tmp_path / "o"
    base = [data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--offline", "--no-render", "--accept-plan",
            "--images", imgs]
    go(capsys, *base)
    _with_catalog_source(out)
    assert go(capsys, *base, "--from", "images", "--accept-images")[0] == 0


def test_reject_clears_image_and_stops_for_pick(tmp_path, data, capsys):
    imgs, out = make_images(tmp_path), tmp_path / "o"
    base = [data, "--brand", "BOSI", "--code", "BSI", "--out", out, "--offline", "--no-render", "--accept-plan"]
    go(capsys, *base, "--images", imgs)
    ids = _with_catalog_source(out)
    go(capsys, *base, "--images", imgs, "--from", "images")  # review stop
    (out / "team" / "reject_1.json").write_text(json.dumps([ids[0]]), encoding="utf-8")
    code, text = go(capsys, *base, "--resume")  # no --images here: the rejected card has nothing local
    assert code == 4 and text.splitlines()[0] == "STOP 4 images" and ids[0] in text
    st = json.loads((out / "run_state.json").read_text(encoding="utf-8"))
    assert st["rejected"] == [ids[0]]
    doc = json.loads((out / "doc.json").read_text(encoding="utf-8"))
    assert not (doc["cards"][0].get("image") or {}).get("path")


def test_identical_rows_report_only_never_stops(tmp_path, capsys):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR[:7] + ["Description"])
    ws.append(["A1", "Vòng Bi Cầu", 1000001, 5200, 20, 47, 14, "same"])
    ws.append(["A2", "Vòng Bi Cầu", 1000002, 5200, 20, 47, 14, "same"])  # identical desc + specs
    p = tmp_path / "i.xlsx"
    wb.save(p)
    out = tmp_path / "o"
    code, text = go(capsys, p, "--brand", "B", "--code", "BSI", "--out", out, "--offline", "--no-render",
                    "--accept-plan")
    assert text.splitlines()[0] != "STOP 4 data"
    txt = (out / "items_warnings.txt").read_text(encoding="utf-8")
    assert "chỉ báo user" in txt and "identical" in txt


def test_data_stop_offers_all_options_and_resolves_after_patch(tmp_path, capsys):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR)
    ws.append(["6204-2RS", "Vòng Bi Cầu", 1000001, 5200, 50, 47, 14, "2 Phớt"])  # d >= D
    p = tmp_path / "d.xlsx"
    wb.save(p)
    out = tmp_path / "o"
    base = [p, "--brand", "B", "--code", "BSI", "--out", str(out) + "//", "--offline", "--no-render", "--accept-plan"]
    code, text = go(capsys, p, *base[1:])
    assert code == 4 and "--patches" in text and "--accept-data --resume" in text and "//" not in text
    patch = tmp_path / "pa.json"
    patch.write_text(json.dumps([{"op": "set_spec", "code": "6204-2RS", "label": "d", "value": "20 mm",
                                  "source": "catalog"}]), encoding="utf-8")
    code, text = go(capsys, *base, "--patches", patch)
    assert text.splitlines()[0] != "STOP 4 data"  # resolved by the patch


def test_unresolved_after_patch_message(tmp_path, capsys):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HDR)
    ws.append(["6204-2RS", "Vòng Bi Cầu", 1000001, 5200, 50, 47, 14, "2 Phớt"])
    p = tmp_path / "d.xlsx"
    wb.save(p)
    patch = tmp_path / "pa.json"  # patch fixes a different spec only
    patch.write_text(json.dumps([{"op": "set_spec", "code": "6204-2RS", "label": "B", "value": 15, "source": "s"}]),
                     encoding="utf-8")
    code, text = go(capsys, p, "--brand", "B", "--code", "BSI", "--out", tmp_path / "o", "--offline", "--no-render",
                    "--patches", patch)
    assert code == 4 and "STILL unresolved" in text and "--accept-data --resume" in text
    assert "--patches" in text.splitlines()[-1] or "--accept-data" in text
