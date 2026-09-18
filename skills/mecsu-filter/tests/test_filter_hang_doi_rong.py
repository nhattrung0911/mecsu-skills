# -*- coding: utf-8 -*-
"""Hang doi rong la KET QUA HOP LE, khong phai hong.

File da day du filter -> `build_ai_queue.py` bao 0 o thieu -> `ai_fill.py` khong co
gi de hoi. Truoc day no `raise SystemExit('Hang doi rong sau khi loc.')`, `run.py`
coi exit != 0 la hong nen dung ca day voi exit 1 -> KHONG dung ra duoc file giao.

Do duoc (P3 lan 1, 2026-09-17) tren 100 dong that da du filter: khong chay duoc
den file giao o ca hai che do. Ma file da sach chinh la loai file nguoi ta dem QC.

Luat so 4 cua repo la "hong thi exit != 0", khong phai "khong co viec thi exit != 0".
"""
import json
import pickle
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _hang_doi_rong(thu_muc: Path) -> tuple[Path, Path]:
    queue = thu_muc / "queue.json"
    queue.write_text(json.dumps({"asks": []}), encoding="utf-8")
    audit = thu_muc / "audit.pkl"
    with open(audit, "wb") as f:
        pickle.dump(([], {}), f)
    return queue, audit


def _chay_ai_fill(thu_muc: Path) -> subprocess.CompletedProcess:
    queue, audit = _hang_doi_rong(thu_muc)
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "ai_fill.py"), "--queue", str(queue),
         "--audit", str(audit), "--output-dir", str(thu_muc / "ai")],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)


def test_hang_doi_rong_thi_thoat_0(tmp_path):
    ket_qua = _chay_ai_fill(tmp_path)
    assert ket_qua.returncode == 0, ket_qua.stdout + ket_qua.stderr


def test_hang_doi_rong_van_ghi_file_ai_values_de_buoc_sau_di_tiep(tmp_path):
    """run.py chet neu khong thay ai_values_*.json - o trong cung phai co file."""
    _chay_ai_fill(tmp_path)
    ra = sorted((tmp_path / "ai").glob("ai_values_*.json"))
    assert ra, "khong co ai_values_*.json nao"
    assert json.loads(ra[0].read_text(encoding="utf-8")) == {}


def test_noi_ro_la_khong_co_viec_chu_khong_im_lang(tmp_path):
    """Thoat 0 im lang de nguoi doc tuong da dien xong. Phai noi ro."""
    ket_qua = _chay_ai_fill(tmp_path)
    ra = (ket_qua.stdout + ket_qua.stderr).lower()
    assert "khong co o nao" in ra or "khong co viec" in ra, ket_qua.stdout
