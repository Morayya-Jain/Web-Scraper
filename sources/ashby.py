"""Ashby - public job board API, no auth."""
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

_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def fetch() -> list[dict]:
    entries = for_ats("ashby")
    if not entries:
        log.info("[ashby] no companies configured")
        return []

    session = make_session()
    rows: list[dict] = []
    for entry in entries:
        token = entry.get("token")
        name = entry.get("name") or token
        if not token:
            continue
        data = get_json(
            session,
            _URL.format(token=token),
            params={"includeCompensation": "true"},
        )
        polite_sleep()
        if not isinstance(data, dict):
            continue
        for j in data.get("jobs", []) or []:
            if j.get("isListed") is False:
                continue
            location = j.get("location") or ""
            if j.get("isRemote") and "remote" not in location.lower():
                location = f"{location} (Remote)".strip()
            description = j.get("descriptionPlain") or strip_html(
                j.get("descriptionHtml", "")
            )
            candidate = row(
                source=f"ashby:{token}",
                title=j.get("title", ""),
                company=name,
                location=location,
                url=j.get("applyUrl", "") or j.get("jobUrl", ""),
                description=description,
                posted=j.get("publishedAt", ""),
            )
            if candidate and passes_prefilter(candidate):
                rows.append(candidate)

    kept = keep_rows(rows)
    log.info("[ashby] %d companies, %d kept", len(entries), len(kept))
    return kept
