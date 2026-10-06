"""Render pages of an xlsx to PNG through Excel COM (always on a temp copy)."""
from __future__ import annotations

import argparse
import gc
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import pathlib as _pathlib, sys as _sys  # noqa: E401
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent))
from pl_common import col_letter, load_theme


class RenderUnavailable(RuntimeError):
    pass


def render(xlsx: str, out_dir: str, pages: list[int] | None = None, theme: dict | None = None) -> list[str]:
    """pages are 1-based; None = all. Returns PNG paths page_01.png ..."""
    try:
        import win32com.client as wc
    except ImportError:
        raise RenderUnavailable("render unavailable: needs Windows + Excel + pywin32 (pip install pywin32)") from None

    theme = theme or load_theme()
    R, last_col = theme["page"]["rows"], col_letter(theme["page"]["cols"])
    out = Path(out_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="plr_"))
    copy = tmp / "render_copy.xlsx"
    shutil.copy2(xlsx, copy)
    xl = wb = None
    files: list[str] = []
    try:
        xl = wc.DispatchEx("Excel.Application")
        xl.Visible = False
        xl.DisplayAlerts = False
        wb = xl.Workbooks.Open(str(copy), 0, True)
        ws = wb.Worksheets(1)
        ws.Activate()
        try:
            xl.ActiveWindow.View = 1
            xl.ActiveWindow.DisplayGridlines = False
        except Exception as e:  # view tweaks are cosmetic
            print("view:", e, file=sys.stderr)
        total = math.ceil((ws.UsedRange.Row + ws.UsedRange.Rows.Count - 1) / R)
        for p in pages or range(1, total + 1):
            if not 1 <= p <= total:
                print(f"page {p} out of range (1..{total})", file=sys.stderr)
                continue
            rng = ws.Range(f"A{(p - 1) * R + 1}:{last_col}{p * R}")
            for attempt in range(4):  # the clipboard is shared with other apps: CopyPicture/Paste fail sporadically
                rng.CopyPicture(1, 2)  # copy BEFORE adding the chart object, or Paste fails with E_FAIL
                co = ws.ChartObjects().Add(0, 0, rng.Width, rng.Height)
                try:
                    co.Activate()
                    co.Chart.Paste()
                    png = str(out / f"page_{p:02d}.png")
                    co.Chart.Export(png, "PNG")
                    files.append(png)
                    break
                except Exception as e:
                    if attempt == 3:
                        raise
                    print(f"page {p}: retry after {e.__class__.__name__}", file=sys.stderr)
                    time.sleep(0.5 * (attempt + 1))
                finally:
                    co.Delete()
    finally:
        if wb is not None:
            try:
                wb.Close(False)
            except Exception:
                pass
        if xl is not None:
            try:
                xl.Quit()
            except Exception:
                pass
        ws = wb = xl = None  # drop COM refs now; lingering refs can hang interpreter shutdown
        gc.collect()
        shutil.rmtree(tmp, ignore_errors=True)
    return files


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="xlsx -> page PNGs via Excel COM")
    ap.add_argument("xlsx")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pages", help="comma list, 1-based (default all)")
    a = ap.parse_args()
    pages = [int(x) for x in a.pages.split(",")] if a.pages else None
    try:
        files = render(a.xlsx, a.out, pages)
    except RenderUnavailable as e:
        print(e, file=sys.stderr)
        sys.stdout.flush()
        os._exit(5)
    except Exception as e:  # Excel missing / COM failure
        print(f"render unavailable: {type(e).__name__}: {e}", file=sys.stderr)
        sys.stdout.flush()
        os._exit(5)
    for f in files:
        print(f)
    sys.stdout.flush()
    os._exit(0)  # pywin32 COM teardown at exit sometimes hangs after Excel quits; work is done


if __name__ == "__main__":
    main()
