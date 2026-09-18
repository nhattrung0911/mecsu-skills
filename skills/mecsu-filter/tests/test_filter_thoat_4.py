# -*- coding: utf-8 -*-
"""`run.py` phai TRUYEN NGUYEN ma thoat 4 cua buoc con ra ngoai.

Ma thoat 4 nghia la "dang cho AGENT tra loi", khac han "hong". Truoc day
`run.py` lam `raise SystemExit('<chuoi>')` - Python coi chuoi la thong diep va
thoat **1**, nen chuoi 4 bien thanh 1.

Da do (P3 lan 4, 2026-09-18): `ai_fill.py` in dung "CAN AGENT TRA LOI..." roi
thoat 4, nhung `run.py` bao ra ngoai exit 1. Agent goi skill nay khong phan biet
duoc "toi phai dien tra_loi.json" voi "day chuyen hong, dung lai".
"""
import subprocess
import sys
import textwrap
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _run_py_voi_buoc_gia(tmp_path: Path, ma_thoat: int) -> subprocess.CompletedProcess:
    """Goi run() cua run.py voi mot script con chi viec thoat bang ma cho truoc."""
    con = tmp_path / "buoc_gia.py"
    con.write_text("import sys\nsys.exit(%d)\n" % ma_thoat, encoding="utf-8")
    lai = tmp_path / "goi.py"
    lai.write_text(textwrap.dedent('''
        import importlib.util, sys
        from pathlib import Path
        spec = importlib.util.spec_from_file_location("run_filter", r"%s")
        m = importlib.util.module_from_spec(spec)
        sys.modules["run_filter"] = m
        spec.loader.exec_module(m)
        m.HERE = Path(r"%s")          # tro vao thu muc chua buoc gia
        m.run("buoc_gia.py")
    ''') % (SCRIPTS / "run.py", tmp_path), encoding="utf-8")
    return subprocess.run([sys.executable, str(lai)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def test_buoc_con_thoat_4_thi_run_py_cung_thoat_4():
    """4 = cho agent tra loi. Doi thanh 1 la mat han thong tin do."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ket_qua = _run_py_voi_buoc_gia(Path(d), 4)
    assert ket_qua.returncode == 4, ket_qua.stdout + ket_qua.stderr


def test_buoc_con_thoat_1_thi_van_la_hong():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ket_qua = _run_py_voi_buoc_gia(Path(d), 1)
    assert ket_qua.returncode not in (0, 4), ket_qua.stdout + ket_qua.stderr


def test_buoc_con_thoat_0_thi_di_tiep():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        ket_qua = _run_py_voi_buoc_gia(Path(d), 0)
    assert ket_qua.returncode == 0, ket_qua.stdout + ket_qua.stderr
