# -*- coding: utf-8 -*-
"""Chot chan cho duong chay chinh: pipeline khong duoc bao thanh cong khi chua cham gi.

Moi test o day ung mot loi that: endpoint chet ma exit 0 -> build_final sua 0 dong,
tu kiem tra pass rong, audit.py in "Audited workbook and changelog are in...".
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

# Cong dong chac chan -> refuse ngay, khong cham mang, khong cho timeout 180s.
DEAD_ENDPOINT = "http://127.0.0.1:1/v1"


def _queue(tmp_path: Path) -> Path:
    queue = {
        "pairs": [
            {
                "pair_id": 1,
                "sample_description": "Bulong luc giac chim M8x20",
                "leaf_category_id": "101",
                "leaf_category_name": "Bulong luc giac chim",
                "level1_category_name": "Bulong",
                "rule_verdict": "unsure",
                "rule_score": 0.5,
                "row_count": 3,
                "part_ids": [11, 12, 13],
            }
        ],
        "leaf_catalog": {"Bulong": ["Bulong luc giac chim", "Bulong dai oc"]},
        "leaf_ids": {"Bulong": {"Bulong luc giac chim": ["101"]}},
    }
    path = tmp_path / "ai_queue.json"
    path.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")
    return path


def test_ai_check_bao_loi_khi_moi_batch_that_bai(tmp_path):
    """Model tier chet 100% ma exit 0 = bao cao thanh cong trong khi chua cham dong nao."""
    env = dict(
        os.environ,
        MECSU_BASE_URL=DEAD_ENDPOINT,
        MECSU_API_KEY="khong-can-that",
        MECSU_MODELS="fake-model",
    )
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "ai_check.py"),
            "--queue",
            str(_queue(tmp_path)),
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )
    assert proc.returncode != 0, "exit 0 du moi batch that bai:\n%s" % proc.stdout[-2000:]


def test_verdict_key_theo_noi_dung_khong_theo_so_thu_tu():
    """Cung (mau mo ta, leaf) thi cung khoa, du pair_id doi."""
    import common

    a = common.verdict_key("Bulong luc giac chim M8x20", "Bulong luc giac chim")
    b = common.verdict_key("Bulong luc giac chim M10x30", "Bulong luc giac chim")
    khac = common.verdict_key("Dai oc luc giac M8", "Dai oc luc giac")
    assert a == b, "hai bien the cua cung san pham phai cung khoa"
    assert a != khac


def test_resume_khong_gan_verdict_cu_sang_cap_khac(tmp_path):
    """Doi thu tu hang doi thi verdict cu phai van dinh dung cap cua no.

    `pair_id = len(pairs) + 1` danh theo thu tu gap, con resume lai tra theo pair_id,
    nen chi can input doi la cau tra loi cu nhay sang san pham khac.
    """
    import common
    import openpyxl

    bulong = ("Bulong luc giac chim M8x20", "Bulong luc giac chim")
    dai_oc = ("Dai oc luc giac M8", "Dai oc luc giac")

    def pair(pair_id, desc, leaf):
        return {
            "pair_id": pair_id,
            "key_hash": common.verdict_key(desc, leaf),
            "sample_description": desc,
            "leaf_category_id": "101",
            "leaf_category_name": leaf,
            "level1_category_name": "Bulong",
            "rule_verdict": "unsure",
            "rule_score": 0.5,
            "row_count": 3,
            "part_ids": [1],
        }

    # Lo dau: bulong la cap 1. Lo sau: dai oc chen len lam cap 1, bulong tut xuong 2.
    queue = {
        "pairs": [pair(1, *dai_oc), pair(2, *bulong)],
        "leaf_catalog": {"Bulong": ["Bulong luc giac chim", "Dai oc luc giac"]},
        "leaf_ids": {"Bulong": {"Bulong luc giac chim": ["101"], "Dai oc luc giac": ["202"]}},
    }
    queue_path = tmp_path / "ai_queue.json"
    queue_path.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")

    # Verdict cu: chi cham BULONG, luc no con la cap so 1.
    verdicts = {
        common.verdict_key(*bulong): {
            "id": 1, "verdict": "wrong", "confidence": 0.9,
            "reason": "sai nhom", "suggested_category": "Dai oc luc giac",
        }
    }
    (tmp_path / "ai_verdicts_fake-model.json").write_text(
        json.dumps(verdicts, ensure_ascii=False), encoding="utf-8"
    )

    env = dict(
        os.environ,
        MECSU_BASE_URL=DEAD_ENDPOINT,
        MECSU_API_KEY="khong-can-that",
        MECSU_MODELS="fake-model",
    )
    subprocess.run(
        [
            sys.executable, str(SCRIPTS / "ai_check.py"),
            "--queue", str(queue_path), "--output-dir", str(tmp_path),
        ],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=120,
    )

    sheet = openpyxl.load_workbook(tmp_path / "ai_report_fake-model.xlsx")["ai_report"]
    rows = list(sheet.values)
    header = list(rows[0])
    by_desc = {r[header.index("sample_description")]: r for r in rows[1:]}
    verdict_col = header.index("ai_verdict")
    assert by_desc[bulong[0]][verdict_col] == "wrong", "verdict cu phai o lai dung cap bulong"
    assert by_desc[dai_oc[0]][verdict_col] == "MISSING", "dai oc chua cham ma da co verdict"


def test_deliver_coi_cap_da_phan_xu_la_da_giai_quyet():
    """reference.md hua co duong thoat khoi chot dispute; deliver.py truoc day tinh lai
    dispute thang tu verdict tho nen giai quyet dung cach van khong giao duoc."""
    import common
    import deliver

    bulong = ("Bulong luc giac chim M8x20", "Bulong luc giac chim")
    key = common.verdict_key(*bulong)
    queue = {"pairs": [{
        "pair_id": 1,
        "key_hash": key,
        "sample_description": bulong[0],
        "leaf_category_name": bulong[1],
    }]}
    sources = [
        ("model-a", {key: {"verdict": "wrong", "suggested_category": "Dai oc luc giac"}}),
        ("model-b", {key: {"verdict": "correct", "suggested_category": ""}}),
    ]

    assert deliver.unsettled(queue, sources, settled=set()) == 1
    assert deliver.unsettled(queue, sources, settled={1}) == 0


def test_audit_dung_thu_muc_that_khi_dung_lenh_build(tmp_path):
    """Doi `verdicts_dir` thanh ham tung de sot mot cho dung no nhu duong dan; buoc build
    la cho duy nhat con lai ghep duong dan nen no phai co test rieng."""
    import audit

    workbook = tmp_path / "in.xlsx"
    one = str(tmp_path / "ai_verdicts_a.json")

    arguments = audit.build_args(workbook, [one], tmp_path)
    assert "--accept-single-model" in arguments
    assert "--resolutions" not in arguments

    (tmp_path / "dispute_resolution.json").write_text("{}", encoding="utf-8")
    arguments = audit.build_args(workbook, [one, str(tmp_path / "ai_verdicts_b.json")], tmp_path)
    assert "--accept-single-model" not in arguments
    assert str(tmp_path / "dispute_resolution.json") in arguments


def test_audit_tim_verdict_dung_cho_ai_check_ghi():
    """audit.py tung tim o skills/jobs/oncheck trong khi ai_check ghi vao job_root()/jobs/oncheck.

    Lech nhau -> lenh mot-phat chet bang "No verdict files in ..." SAU khi da tra tien
    cho ca luot model.
    """
    import ai_check
    import audit

    assert audit.verdicts_dir() == ai_check.DEFAULT_DIR
