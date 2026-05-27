"""Lever - public postings API, no auth."""
from __future__ import annotations

import logging

from ._ats import for_ats, ms_to_iso
from ._common import (
    get_json,
    keep_rows,
    make_session,
    passes_prefilter,
    polite_sleep,
    row,
)

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
            categories = j.get("categories") or {}
            location = categories.get("location", "")
            workplace = (j.get("workplaceType") or "").lower()
            if workplace == "remote" and "remote" not in (location or "").lower():
                location = f"{location} (Remote)".strip()
            candidate = row(
                source=f"lever:{token}",
                title=j.get("text", ""),
                company=name,
                location=location,
                url=j.get("hostedUrl", "") or j.get("applyUrl", ""),
                description=j.get("descriptionPlain", "") or "",
                posted=ms_to_iso(j.get("createdAt")),
            )
            if candidate and passes_prefilter(candidate):
                rows.append(candidate)

    kept = keep_rows(rows)
    log.info("[lever] %d companies, %d kept", len(entries), len(kept))
    return kept
