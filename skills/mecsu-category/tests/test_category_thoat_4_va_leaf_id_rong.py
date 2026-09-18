# -*- coding: utf-8 -*-
"""Hai lo do lan chay P4 tren 102 dong that (2026-09-18) lam lo ra.

1. `audit.py` boc moi ma thoat khac 0 thanh SystemExit chuoi -> Python thoat 1.
   `ai_check.py` thoat 4 de xin agent tra loi, ben ngoai nhan duoc 1. Dung loi
   `run.py` cua mecsu-filter da vá o `af9b068`, nhung audit.py chua.

2. `build_final.py` coi "mot leaf_id ung voi nhieu ten" la xung dot. File khong co
   cot `leaf_id` thi MOI dong deu co leaf_id None, nen 2 danh muc that
   (`Cua Tay`, `Co Le 2 Dau Mieng`) cung dung id None -> tu bao xung dot.
   Do duoc: ca hai che do bat dung 15/15 dong bi gan sai, 0 bao dong gia, nhung
   pipeline TU CHOI GIAO vi loi tu-kiem nay. SKILL.md hua "layout cot nao cung
   chay", con build_final.py ngam doi phai co cot leaf_id.
"""
import importlib.util
import subprocess
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _nap(ten: str):
    """Kem scripts/ vao sys.path: build_final.py import apply_fixes, common cua cung skill."""
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("cat_" + ten, SCRIPTS / (ten + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules["cat_" + ten] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


# ── 1. ma thoat 4 ────────────────────────────────────────────────────────────

def test_audit_truyen_nguyen_ma_thoat_4_cua_buoc_con(tmp_path):
    """4 = cho agent tra loi. Doi thanh 1 la agent khong biet phai lam gi."""
    con = tmp_path / "buoc_gia.py"
    con.write_text("import sys\nsys.exit(4)\n", encoding="utf-8")
    lai = tmp_path / "goi.py"
    lai.write_text(textwrap.dedent('''
        import importlib.util, sys
        from pathlib import Path
        spec = importlib.util.spec_from_file_location("audit_cat", r"%s")
        m = importlib.util.module_from_spec(spec)
        sys.modules["audit_cat"] = m
        spec.loader.exec_module(m)
        m.HERE = Path(r"%s")
        ma = m.run("buoc_gia.py")
        m.dung_neu_loi(ma, "buoc_gia.py")
        print("KHONG DUNG LAI - SAI")
    ''') % (SCRIPTS / "audit.py", tmp_path), encoding="utf-8")
    ket_qua = subprocess.run([sys.executable, str(lai)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120)
    assert ket_qua.returncode == 4, ket_qua.stdout + ket_qua.stderr


def test_audit_van_coi_ma_khac_la_hong(tmp_path):
    con = tmp_path / "buoc_gia.py"
    con.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    lai = tmp_path / "goi.py"
    lai.write_text(textwrap.dedent('''
        import importlib.util, sys
        from pathlib import Path
        spec = importlib.util.spec_from_file_location("audit_cat", r"%s")
        m = importlib.util.module_from_spec(spec)
        sys.modules["audit_cat"] = m
        spec.loader.exec_module(m)
        m.HERE = Path(r"%s")
        m.dung_neu_loi(m.run("buoc_gia.py"), "buoc_gia.py")
    ''') % (SCRIPTS / "audit.py", tmp_path), encoding="utf-8")
    ket_qua = subprocess.run([sys.executable, str(lai)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120)
    assert ket_qua.returncode not in (0, 4), ket_qua.stdout + ket_qua.stderr


# ── 2. leaf_id rong ──────────────────────────────────────────────────────────

def test_leaf_id_rong_khong_bi_coi_la_xung_dot():
    """File khong co cot leaf_id: moi dong leaf_id None, nhieu ten -> KHONG phai xung dot."""
    bf = _nap("build_final")
    xung_dot = defaultdict(set)
    xung_dot["None"] = {"Cưa Tay", "Cờ Lê 2 Đầu Miệng"}
    assert bf.id_ten_xung_dot(xung_dot) == {}


def test_leaf_id_that_ung_nhieu_ten_VAN_la_xung_dot():
    """Co id that ma hai ten thi dung la du lieu hong - khong duoc vá qua."""
    bf = _nap("build_final")
    xung_dot = defaultdict(set)
    xung_dot["4821"] = {"Cưa Tay", "Cờ Lê 2 Đầu Miệng"}
    assert list(bf.id_ten_xung_dot(xung_dot)) == ["4821"]


def test_id_rong_duoi_moi_dang_deu_duoc_bo_qua():
    bf = _nap("build_final")
    for rong in ("None", "", "  ", "none", "NONE"):
        xung_dot = defaultdict(set)
        xung_dot[rong] = {"A", "B"}
        assert bf.id_ten_xung_dot(xung_dot) == {}, repr(rong)
