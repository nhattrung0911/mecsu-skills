"""Environment check for the pricelist skill: Python, packages, Excel COM, network.

Exit 0 if every REQUIRED item is present, else 2. Optional items only degrade features.
"""
from __future__ import annotations

import importlib
import importlib.util
import platform
import sys

REQUIRED = [("openpyxl", "openpyxl"), ("PIL", "Pillow"), ("numpy", "numpy"),
            ("jsonschema", "jsonschema"), ("requests", "requests")]
OPTIONAL = [("rembg", "rembg", "background removal (fallback: white flood-fill)"),
            ("ddgs", "ddgs", "web image search (fallback: unavailable)"),
            ("win32com", "pywin32", "render pages to PNG via Excel (fallback: skipped)")]


def has(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is not None
    except (ImportError, ValueError):
        return False


def check_python() -> bool:
    return sys.version_info >= (3, 10)


def check_excel() -> bool:
    if platform.system() != "Windows" or not has("win32com"):
        return False
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, "Excel.Application"))
        return True
    except OSError:
        return False


def check_network(url: str = "https://mecsu.vn", timeout: float = 5.0) -> bool:
    try:
        import requests
        requests.head(url, timeout=timeout, allow_redirects=True)
        return True
    except Exception:
        return False


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-net", action="store_true", help="skip the network check")
    a = ap.parse_args(argv)
    rows, missing_req, missing_opt = [], [], []
    ok = check_python()
    rows.append(("Python >= 3.10", "OK" if ok else "MISSING", platform.python_version()))
    for mod, pip in REQUIRED:
        present = has(mod)
        rows.append((f"{pip} (required)", "OK" if present else "MISSING", ""))
        if not present:
            missing_req.append(pip)
    for mod, pip, why in OPTIONAL:
        present = has(mod)
        rows.append((f"{pip} (optional)", "OK" if present else "MISSING", why))
        if not present:
            missing_opt.append(pip)
    rows.append(("Excel COM (optional)", "OK" if check_excel() else "MISSING", "needed for render"))
    if not a.no_net:
        rows.append(("network mecsu.vn (optional)", "OK" if check_network() else "MISSING", "catalog images"))
    w = max(len(r[0]) for r in rows)
    for name, st, note in rows:
        print(f"{name:<{w}}  {st:<7} {note}".rstrip())
    if missing_req:
        print("\nInstall required:  pip install " + " ".join(missing_req))
    if missing_opt:
        print("Install optional:  pip install " + " ".join(p for p in missing_opt))
    if not ok:
        print("Python 3.10 or newer is required.")
    return 0 if ok and not missing_req else 2


if __name__ == "__main__":
    sys.exit(main())
