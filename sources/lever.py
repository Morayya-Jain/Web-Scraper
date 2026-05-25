"""Lever - public postings API, no auth.

GET https://api.lever.co/v0/postings/{token}?mode=json

Response: list of postings, each with:
    {"text" (title), "categories": {"location", "team", "commitment"},
     "hostedUrl", "applyUrl", "descriptionPlain", "createdAt" (ms epoch),
     "workplaceType", ...}
"""
from __future__ import annotations

import logging

from ._ats import for_ats, ms_to_iso, passes_ats_filter
from ._common import get_json, keep_rows, make_session, polite_sleep, row

log = logging.getLogger(__name__)

_URL = "https://api.lever.co/v0/postings/{token}"


def fetch() -> list[dict]:
    entries = for_ats("lever")
    if not entries:
        log.info("[lever] no companies configured")
        return []

    session = make_session()
    rows: list[dict] = []
    for entry in entries:
        token = entry.get("token")
        name = entry.get("name") or token
        if not token:
            continue
        data = get_json(session, _URL.format(token=token), params={"mode": "json"})
        polite_sleep()
        if not isinstance(data, list):
            continue
        for j in data:
            title = j.get("text", "")
            categories = j.get("categories") or {}
            location = categories.get("location", "")
            # Lever has a separate workplaceType field; treat "remote" there
            # as an in-scope location too.
            workplace = (j.get("workplaceType") or "").lower()
            if workplace == "remote" and "remote" not in (location or "").lower():
                location = f"{location} (Remote)".strip()
            if not passes_ats_filter(title, location):
                continue
            rows.append(
                row(
                    source=f"lever:{token}",
                    title=title,
                    company=name,
                    location=location,
                    url=j.get("hostedUrl", "") or j.get("applyUrl", ""),
                    description=j.get("descriptionPlain", "") or "",
                    posted=ms_to_iso(j.get("createdAt")),
                )
            )

    kept = keep_rows(rows)
    log.info(
        "[lever] %d companies, %d kept after AU+junior filter",
        len(entries),
        len(kept),
    )
    return kept
