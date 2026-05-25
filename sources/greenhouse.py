"""Greenhouse - public boards API, no auth.

GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true

Response: {"jobs": [
    {"id", "title", "location": {"name": "..."}, "absolute_url",
     "content": "<html-escaped>", "updated_at", ...}, ...]}
"""
from __future__ import annotations

import logging

from htmlstrip import strip_html

from ._ats import for_ats, passes_ats_filter
from ._common import get_json, keep_rows, make_session, polite_sleep, row

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
            title = j.get("title", "")
            location = (j.get("location") or {}).get("name", "")
            if not passes_ats_filter(title, location):
                continue
            rows.append(
                row(
                    source=f"greenhouse:{token}",
                    title=title,
                    company=name,
                    location=location,
                    url=j.get("absolute_url", ""),
                    description=strip_html(j.get("content", "")),
                    posted=j.get("updated_at", ""),
                )
            )

    kept = keep_rows(rows)
    log.info(
        "[greenhouse] %d companies, %d kept after AU+junior filter",
        len(entries),
        len(kept),
    )
    return kept
