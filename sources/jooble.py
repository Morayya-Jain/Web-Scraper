"""Jooble - https://jooble.org/api/about

POST https://jooble.org/api/{api_key}
Body: {"keywords": "...", "location": "..."}
"""
from __future__ import annotations

import logging
import os

from config import LOCATIONS, SEARCH_TERMS
from htmlstrip import strip_html

from ._common import (
    keep_rows,
    make_session,
    passes_prefilter,
    polite_sleep,
    post_json,
    row,
)

log = logging.getLogger(__name__)

_API = "https://jooble.org/api/"


def fetch() -> list[dict]:
    api_key = os.getenv("JOOBLE_API_KEY")
    if not api_key:
        log.info("[jooble] missing JOOBLE_API_KEY, skipping")
        return []

    session = make_session()
    rows: list[dict] = []
    total_calls = 0
    url = _API + api_key
    safe_label = _API + "<key>"

    for term in SEARCH_TERMS:
        for loc in LOCATIONS:
            payload = {"keywords": term, "location": loc or "Australia"}
            data = post_json(session, url, payload, log_label=safe_label)
            total_calls += 1
            polite_sleep()
            if not isinstance(data, dict):
                continue
            for r in data.get("jobs", []) or []:
                candidate = row(
                    source="jooble",
                    title=r.get("title", ""),
                    company=r.get("company", "") or "(unknown)",
                    location=r.get("location", ""),
                    url=r.get("link", ""),
                    description=strip_html(r.get("snippet", "")),
                    posted=r.get("updated", ""),
                )
                if candidate and passes_prefilter(candidate):
                    rows.append(candidate)

    kept = keep_rows(rows)
    log.info("[jooble] %d calls, %d kept", total_calls, len(kept))
    return kept
