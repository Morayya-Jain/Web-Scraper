"""SmartRecruiters - public posting API, no auth.

We DON'T fetch each posting's detail endpoint - the listing-level
title + location is enough for the pre-filter and Claude screening,
and the apply URL has the full text.
"""
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

_URL = "https://api.smartrecruiters.com/v1/companies/{token}/postings"


def _format_location(loc: dict | None) -> str:
    if not loc:
        return ""
    parts = [
        loc.get("city") or "",
        loc.get("region") or "",
        loc.get("country") or "",
    ]
    out = ", ".join(p for p in parts if p)
    if loc.get("remote"):
        out = f"{out} (Remote)".strip(" ,")
    return out


def _posting_url(posting: dict, token: str) -> str:
    direct = posting.get("applyUrl") or posting.get("postingUrl")
    if direct:
        return direct
    posting_id = posting.get("id") or posting.get("uuid")
    if posting_id:
        return f"https://jobs.smartrecruiters.com/{token}/{posting_id}"
    return ""


def fetch() -> list[dict]:
    entries = for_ats("smartrecruiters")
    if not entries:
        log.info("[smartrecruiters] no companies configured")
        return []

    session = make_session()
    rows: list[dict] = []
    for entry in entries:
        token = entry.get("token")
        name = entry.get("name") or token
        if not token:
            continue
        data = get_json(session, _URL.format(token=token), params={"limit": 100})
        polite_sleep()
        if not isinstance(data, dict):
            continue
        for j in data.get("content", []) or []:
            candidate = row(
                source=f"smartrecruiters:{token}",
                title=j.get("name", ""),
                company=name,
                location=_format_location(j.get("location")),
                url=_posting_url(j, token),
                description="",
                posted=j.get("releasedDate", "") or j.get("createdOn", ""),
            )
            if candidate and passes_prefilter(candidate):
                rows.append(candidate)

    kept = keep_rows(rows)
    log.info("[smartrecruiters] %d companies, %d kept", len(entries), len(kept))
    return kept
