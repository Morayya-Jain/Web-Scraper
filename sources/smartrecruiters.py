"""SmartRecruiters - public posting API, no auth.

GET https://api.smartrecruiters.com/v1/companies/{token}/postings

Response: {"offset", "limit", "totalFound", "content": [
    {"id", "name" (title), "ref", "company", "location":
        {"city", "region", "country", "remote"},
     "industry", "department", "function", "typeOfEmployment",
     "experienceLevel", "customField", "releasedDate", "createdOn",
     "ref", "applyUrl"? ...}, ...]}

The detail endpoint gives the full job description, but it costs an
extra request per posting. The brief permits "follow each posting's
detail link for full text if needed" - we default to skipping it to
keep the call budget small. The title + location are enough for the
dedupe + screening surface; users follow the link for full text.
"""
from __future__ import annotations

import logging

from ._ats import for_ats, passes_ats_filter
from ._common import get_json, keep_rows, make_session, polite_sleep, row

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
            title = j.get("name", "")
            location = _format_location(j.get("location"))
            if not passes_ats_filter(title, location):
                continue
            rows.append(
                row(
                    source=f"smartrecruiters:{token}",
                    title=title,
                    company=name,
                    location=location,
                    url=_posting_url(j, token),
                    # Full description omitted to save call budget; the
                    # apply URL has it. Title + location still inform
                    # dedupe and Claude screening.
                    description="",
                    posted=j.get("releasedDate", "") or j.get("createdOn", ""),
                )
            )

    kept = keep_rows(rows)
    log.info(
        "[smartrecruiters] %d companies, %d kept after AU+junior filter",
        len(entries),
        len(kept),
    )
    return kept
