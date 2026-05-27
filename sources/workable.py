"""Workable - public widget API, no auth."""
from __future__ import annotations

import logging

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
            candidate = row(
                source=f"workable:{token}",
                title=j.get("title", ""),
                company=name,
                location=_format_location(j.get("location")),
                url=j.get("application_url", "") or j.get("url", ""),
                description=j.get("description", "") or "",
                posted=j.get("published_on", "") or j.get("created_at", ""),
            )
            if candidate and passes_prefilter(candidate):
                rows.append(candidate)

    kept = keep_rows(rows)
    log.info("[workable] %d companies, %d kept", len(entries), len(kept))
    return kept
