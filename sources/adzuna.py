"""Adzuna - https://developer.adzuna.com

GET https://api.adzuna.com/v1/api/jobs/au/search/1
  ?app_id=...&app_key=...&what=<keywords>&where=<city>
  &results_per_page=<<=50>&max_days_old=<n>&sort_by=date
  &content-type=application/json

Free tier ~250 calls/day. With the v2 SEARCH_TERMS (9 terms) and a single
location pass, that's 9 calls per run.
"""
from __future__ import annotations

import logging
import os

from config import LOCATIONS, MAX_DAYS_OLD, RESULTS_PER_TERM, SEARCH_TERMS
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

_API = "https://api.adzuna.com/v1/api/jobs/au/search/1"


def fetch() -> list[dict]:
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        log.info("[adzuna] missing ADZUNA_APP_ID/KEY, skipping")
        return []

    session = make_session()
    rows: list[dict] = []
    total_calls = 0

    for term in SEARCH_TERMS:
        for loc in LOCATIONS:
            params = {
                "app_id": app_id,
                "app_key": app_key,
                "what": term,
                "results_per_page": RESULTS_PER_TERM,
                "max_days_old": MAX_DAYS_OLD,
                "sort_by": "date",
                "content-type": "application/json",
            }
            if loc:
                params["where"] = loc

            data = get_json(session, _API, params=params)
            total_calls += 1
            polite_sleep()
            if not isinstance(data, dict):
                continue
            for r in data.get("results", []) or []:
                candidate = row(
                    source="adzuna",
                    title=r.get("title", ""),
                    company=(r.get("company") or {}).get("display_name", ""),
                    location=(r.get("location") or {}).get("display_name", ""),
                    url=r.get("redirect_url", ""),
                    description=strip_html(r.get("description", "")),
                    posted=r.get("created", ""),
                )
                if candidate and passes_prefilter(candidate):
                    rows.append(candidate)

    kept = keep_rows(rows)
    log.info("[adzuna] %d calls, %d kept", total_calls, len(kept))
    return kept
