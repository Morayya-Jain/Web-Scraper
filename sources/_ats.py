"""Shared helpers for ATS (Layer B) collectors."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import yaml

from config import COMPANIES_FILE

from ._common import looks_australian, looks_junior

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def companies() -> dict[str, list[dict[str, Any]]]:
    """Parse companies.yaml once and cache it."""
    if not COMPANIES_FILE.exists():
        log.warning("companies.yaml not found at %s", COMPANIES_FILE)
        return {}
    with COMPANIES_FILE.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    out: dict[str, list[dict[str, Any]]] = {}
    for k, v in raw.items():
        if isinstance(v, list):
            out[k] = [item for item in v if isinstance(item, dict)]
    return out


def for_ats(name: str) -> list[dict[str, Any]]:
    """Companies configured under the given ATS key."""
    return companies().get(name, []) or []


def passes_ats_filter(title: str, location: str) -> bool:
    """ATS feeds list every open role; keep only AU + junior-titled ones."""
    return looks_australian(location) and looks_junior(title)


def ms_to_iso(ms: int | float | str | None) -> str:
    """Convert millisecond epoch (Lever) to ISO 8601 string."""
    if ms is None or ms == "":
        return ""
    try:
        epoch = float(ms) / 1000.0
        return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
    except (TypeError, ValueError):
        return ""
