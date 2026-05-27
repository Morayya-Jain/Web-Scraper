"""Greenhouse - public boards API, no auth.

GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true

Response: {"jobs": [
    {"id", "title", "location": {"name": "..."}, "absolute_url",
     "content": "<html-escaped>", "updated_at", ...}, ...]}
"""
from __future__ import annotations

import logging

from htmlstrip import strip_html

from ._ats import for_ats
from ._common import (
    get_json,
    keep_rows,
    make_session,
    passes_prefilter,
    polite_sleep,
    row,
)

log = logging.getLogger(__name__)

_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def fetch() -> list[dict]:
    entries = for_ats("greenhouse")
    if not entries:
        log.info("[greenhouse] no companies configured")
        return []

    session = make_session()
    rows: list[dict] = []
    for entry in entries:
        token = entry.get("token")
        name = entry.get("name") or token
        if not token:
            continue
        data = get_json(session, _URL.format(token=token), params={"content": "true"})
        polite_sleep()
        if not isinstance(data, dict):
            continue
        for j in data.get("jobs", []) or []:
            candidate = row(
                source=f"greenhouse:{token}",
                title=j.get("title", ""),
                company=name,
                location=(j.get("location") or {}).get("name", ""),
                url=j.get("absolute_url", ""),
                description=strip_html(j.get("content", "")),
                posted=j.get("updated_at", ""),
            )
            if candidate and passes_prefilter(candidate):
                rows.append(candidate)

    kept = keep_rows(rows)
    log.info("[greenhouse] %d companies, %d kept", len(entries), len(kept))
    return kept
