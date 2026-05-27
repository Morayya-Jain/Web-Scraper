"""Careerjet - https://www.careerjet.com/partners/api/

GET http://public.api.careerjet.net/search
  ?keywords=...&location=...&locale_code=en_AU&affid=...
  &pagesize=...&page=...&user_ip=...&user_agent=...

HTTP-only - port 443 is not open on the Careerjet public API host as of 2026.
The affid is also returned in client-side referer headers, so the
server-side cleartext exposure is bounded.
"""
from __future__ import annotations

import logging
import os

from config import LOCATIONS, RESULTS_PER_TERM, SEARCH_TERMS, USER_AGENT
from htmlstrip import strip_html

from ._common import (
    get_json,
    keep_rows,
    make_session,
    passes_prefilter,
    polite_sleep,
    row,
)

log = logging.getLogger(__name__)

_API = "http://public.api.careerjet.net/search"
_CLIENT_IP = "127.0.0.1"


def fetch() -> list[dict]:
    affid = os.getenv("CAREERJET_AFFID")
    if not affid:
        log.info("[careerjet] missing CAREERJET_AFFID, skipping")
        return []

    session = make_session()
    rows: list[dict] = []
    total_calls = 0

    for term in SEARCH_TERMS:
        for loc in LOCATIONS:
            params = {
                "keywords": term,
                "location": loc or "Australia",
                "locale_code": "en_AU",
                "affid": affid,
                "pagesize": RESULTS_PER_TERM,
                "page": 1,
                "user_ip": _CLIENT_IP,
                "user_agent": USER_AGENT,
            }
            data = get_json(session, _API, params=params)
            total_calls += 1
            polite_sleep()
            if not isinstance(data, dict):
                continue
            for r in data.get("jobs", []) or []:
                candidate = row(
                    source="careerjet",
                    title=r.get("title", ""),
                    company=r.get("company", "") or "(unknown)",
                    location=r.get("locations", ""),
                    url=r.get("url", ""),
                    description=strip_html(r.get("description", "")),
                    posted=r.get("date", ""),
                )
                if candidate and passes_prefilter(candidate):
                    rows.append(candidate)

    kept = keep_rows(rows)
    log.info("[careerjet] %d calls, %d kept", total_calls, len(kept))
    return kept
