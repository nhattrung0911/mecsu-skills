import subprocess
import sys
from pathlib import Path

import pl_doctor

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def test_doctor_ok_when_required_present(capsys):
    assert pl_doctor.main(["--no-net"]) == 0
    out = capsys.readouterr().out
    assert "OK" in out and "openpyxl" in out


def test_doctor_exit_2_when_required_missing(monkeypatch, capsys):
    real = pl_doctor.has
    monkeypatch.setattr(pl_doctor, "has", lambda m: False if m == "jsonschema" else real(m))
    assert pl_doctor.main(["--no-net"]) == 2
    out = capsys.readouterr().out
    assert "MISSING" in out and "pip install jsonschema" in out


def test_render_exit_5_when_unavailable(tmp_path):
    # simulate missing pywin32 by shadowing the module with a broken one
    shadow = tmp_path / "win32com"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("raise ImportError('x')")
    x = tmp_path / "a.xlsx"
    x.write_bytes(b"")
    env = {**__import__("os").environ, "PYTHONPATH": str(tmp_path)}
    r = subprocess.run([sys.executable, str(SCRIPTS / "pl_render.py"), str(x), "--out", str(tmp_path / "r")],
                       capture_output=True, text=True, env=env)
    assert r.returncode == 5 and "render unavailable" in r.stderr


def test_search_unavailable_message(monkeypatch):
    import builtins
    import pl_images
    real = builtins.__import__

    def fake(name, *a, **k):
        if name in ("ddgs", "duckduckgo_search"):
            raise ImportError(name)
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    try:
        pl_images._image_urls("q", 1)
    except RuntimeError as e:
        assert "web search unavailable" in str(e)
    else:
        raise AssertionError("expected RuntimeError")
