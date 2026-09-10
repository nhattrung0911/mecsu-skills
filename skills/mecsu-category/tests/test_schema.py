# -*- coding: utf-8 -*-
"""Header spellings that must resolve for free, without spending a model call."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import detect_schema as ds          # noqa: E402

HANDTOOLS_HEADER = ["part_id", "part_number", "part_description", "leaf_category_name",
                    "category_lv1", "active_filter_count", "mapped_filters"]


def test_every_required_role_resolves_by_name():
    found = ds.match_by_name(HANDTOOLS_HEADER)
    missing = [role for role in ds.REQUIRED_ROLES if role not in found]
    assert missing == [], f"would burn a model call for {missing}"


def test_category_lv1_is_the_level1_column():
    found = ds.match_by_name(HANDTOOLS_HEADER)
    assert HANDTOOLS_HEADER[found["level1_name"]] == "category_lv1"
    assert HANDTOOLS_HEADER[found["leaf_name"]] == "leaf_category_name"
