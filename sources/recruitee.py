"""Recruitee - public offers API, no auth."""
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

_URL = "https://{token}.recruitee.com/api/offers/"


def _build_location(offer: dict) -> str:
    explicit = offer.get("location") or ""
    if explicit:
        return explicit
    parts = [offer.get("city") or "", offer.get("country") or ""]
    loc = ", ".join(p for p in parts if p)
    if offer.get("remote"):
        loc = f"{loc} (Remote)".strip(" ,")
    return loc


def fetch() -> list[dict]:
    entries = for_ats("recruitee")
    if not entries:
        log.info("[recruitee] no companies configured")
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
        for j in data.get("offers", []) or []:
            candidate = row(
                source=f"recruitee:{token}",
                title=j.get("title", ""),
                company=name,
                location=_build_location(j),
                url=j.get("careers_apply_url", "") or j.get("careers_url", ""),
                description=strip_html(j.get("description", "")),
                posted=j.get("published_at", ""),
            )
            if candidate and passes_prefilter(candidate):
                rows.append(candidate)

    kept = keep_rows(rows)
    log.info("[recruitee] %d companies, %d kept", len(entries), len(kept))
    return kept
