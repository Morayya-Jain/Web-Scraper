"""Workable - public widget API, no auth.

GET https://apply.workable.com/api/v1/widget/accounts/{token}

Response shape (simplified):
    {"name": "...", "jobs": [
        {"title", "shortcode", "code", "url", "application_url",
         "location": {"city", "country", "telecommuting"}, ...}, ...]}

The widget API only returns titles + locations. We DON'T pay the cost of
fetching every job detail (extra N requests per company); the title +
location are enough for the dedupe + screening surface.
"""
from __future__ import annotations

import logging

from ._ats import for_ats, passes_ats_filter
from ._common import get_json, keep_rows, make_session, polite_sleep, row

log = logging.getLogger(__name__)

_URL = "https://apply.workable.com/api/v1/widget/accounts/{token}"


def _format_location(loc: dict | None) -> str:
    if not loc:
        return ""
    city = loc.get("city") or ""
    country = loc.get("country") or ""
    if loc.get("telecommuting"):
        return ", ".join([p for p in [city, country, "Remote"] if p])
    return ", ".join([p for p in [city, country] if p])


def fetch() -> list[dict]:
    entries = for_ats("workable")
    if not entries:
        log.info("[workable] no companies configured")
        return []

    session = make_session()
    rows: list[dict] = []
    for entry in entries:
        token = entry.get("token")
        name = entry.get("name") or token
        if not token:
            continue
        data = get_json(session, _URL.format(token=token))
        polite_sleep()
        if not isinstance(data, dict):
            continue
        for j in data.get("jobs", []) or []:
            title = j.get("title", "")
            location = _format_location(j.get("location"))
            if not passes_ats_filter(title, location):
                continue
            rows.append(
                row(
                    source=f"workable:{token}",
                    title=title,
                    company=name,
                    location=location,
                    url=j.get("application_url", "") or j.get("url", ""),
                    description=j.get("description", "") or "",
                    posted=j.get("published_on", "") or j.get("created_at", ""),
                )
            )

    kept = keep_rows(rows)
    log.info(
        "[workable] %d companies, %d kept after AU+junior filter",
        len(entries),
        len(kept),
    )
    return kept
