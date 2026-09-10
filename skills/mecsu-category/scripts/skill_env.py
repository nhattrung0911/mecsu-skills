# -*- coding: utf-8 -*-
"""Nap cau hinh LLM cho skill nay.

Doc theo thu tu uu tien: bien moi truong cua may > .env canh script > .env o goc
plugin. Nho vay nguoi dung dien key MOT lan o goc, moi skill dung chung, nhung
skill van chay doc lap khi bi copy ra ngoai plugin.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent


def _plugin_root(start: Path) -> Path | None:
    """Thu muc chua .claude-plugin/, di len tu thu muc script."""
    for parent in start.parents:
        if (parent / ".claude-plugin").is_dir():
            return parent
    return None


def load_llm_config(legacy_prefix: str | None = None) -> dict:
    """Tra ve dict cau hinh. legacy_prefix giu .env cu (NF_/ONCHECK_) van chay."""
    load_dotenv(HERE / ".env")                    # dien rieng cho skill thi thang
    root = _plugin_root(HERE)
    if root:
        load_dotenv(root / ".env")                # khong ghi de gia tri da co

    def get(name: str, default: str = "") -> str:
        value = os.getenv("MECSU_" + name)
        if not value and legacy_prefix:
            value = os.getenv(legacy_prefix + "_" + name)
        return value if value else default

    base_url = get("BASE_URL").rstrip("/")
    if not base_url:
        raise SystemExit(
            "MECSU_BASE_URL chua co. Copy %s thanh .env roi dien key."
            % ((root / ".env.example") if root else (HERE / ".env.example"))
        )
    models = [m.strip() for m in get("MODELS").split(",") if m.strip()]
    if not models:
        raise SystemExit("MECSU_MODELS chua co trong .env")
    return {
        "base_url": base_url,
        "api_key": get("API_KEY", "local"),
        "models": models,
        "batch_size": int(get("BATCH_SIZE", "25")),
        "concurrency": int(get("CONCURRENCY", "4")),
        "temperature": float(get("TEMPERATURE", "0")),
    }
