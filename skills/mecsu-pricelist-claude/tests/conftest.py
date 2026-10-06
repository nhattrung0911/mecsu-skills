import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Opt-in groups are enabled by env vars (a subdir conftest cannot add CLI options).
_OPT_IN = {
    "excel": ("PRICELIST_RUN_EXCEL", "PRICELIST_RUN_EXCEL=1"),
    "net": ("PRICELIST_RUN_NET", "PRICELIST_RUN_NET=1"),
    "golden": ("PRICELIST_GOLDEN", "PRICELIST_GOLDEN=<path to Stanley xlsx>"),
}


def pytest_configure(config):
    for m, (_, hint) in _OPT_IN.items():
        config.addinivalue_line("markers", f"{m}: opt-in test (set {hint})")


def pytest_collection_modifyitems(config, items):
    for m, (var, hint) in _OPT_IN.items():
        if os.environ.get(var):
            continue
        skip = pytest.mark.skip(reason=f"needs {hint}")
        for item in items:
            if m in item.keywords:
                item.add_marker(skip)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path_factory, monkeypatch):
    """Never touch the real ~/.mecsu-pricelist from tests."""
    monkeypatch.setenv("MECSU_PRICELIST_HOME", str(tmp_path_factory.mktemp("plhome")))
