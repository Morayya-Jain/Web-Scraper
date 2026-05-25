"""Ashby - public job board API, no auth.

GET https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=true

Response: {"apiVersion": "...", "jobs": [
    {"id", "title", "location" (string), "secondaryLocations": [...],
     "descriptionHtml", "descriptionPlain", "jobUrl", "applyUrl",
     "publishedAt", "isRemote", "isListed", ...}, ...]}
"""
from __future__ import annotations

import logging

from htmlstrip import strip_html

from ._ats import for_ats, passes_ats_filter
from ._common import get_json, keep_rows, make_session, polite_sleep, row

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
            title = j.get("title", "")
            location = j.get("location") or ""
            if j.get("isRemote") and "remote" not in location.lower():
                location = f"{location} (Remote)".strip()
            if not passes_ats_filter(title, location):
                continue
            description = j.get("descriptionPlain") or strip_html(
                j.get("descriptionHtml", "")
            )
            rows.append(
                row(
                    source=f"ashby:{token}",
                    title=title,
                    company=name,
                    location=location,
                    url=j.get("applyUrl", "") or j.get("jobUrl", ""),
                    description=description,
                    posted=j.get("publishedAt", ""),
                )
            )

    kept = keep_rows(rows)
    log.info(
        "[ashby] %d companies, %d kept after AU+junior filter",
        len(entries),
        len(kept),
    )
    return kept
