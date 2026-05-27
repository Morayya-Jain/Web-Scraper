"""Workday - per-tenant CXS endpoint, no auth.

Endpoint shape:
    POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

The search endpoint doesn't return job descriptions - the full text only
lives on the apply page. We leave description="" and let Claude screen
based on title + location, plus the apply URL for the user to click.
"""
from __future__ import annotations

import logging
from urllib.parse import urljoin

from ._ats import for_ats
from ._common import (
    keep_rows,
    make_session,
    passes_prefilter,
    polite_sleep,
    post_json,
    row,
)

log = logging.getLogger(__name__)

_API_TMPL = "https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
_PUBLIC_TMPL = "https://{tenant}.{dc}.myworkdayjobs.com/{site}"

_LIMIT = 20
_MAX_PAGES = 5


def fetch() -> list[dict]:
    entries = for_ats("workday")
    if not entries:
        log.info("[workday] no companies configured")
        return []

    session = make_session()
    rows: list[dict] = []

    for entry in entries:
        tenant = entry.get("tenant")
        dc = entry.get("dc")
        site = entry.get("site")
        name = entry.get("name") or tenant
        if not (tenant and dc and site):
            log.warning("[workday] %s missing tenant/dc/site", name)
            continue
        api = _API_TMPL.format(tenant=tenant, dc=dc, site=site)
        public_root = _PUBLIC_TMPL.format(tenant=tenant, dc=dc, site=site) + "/"

        for page in range(_MAX_PAGES):
            payload = {
                "appliedFacets": {},
                "limit": _LIMIT,
                "offset": page * _LIMIT,
                "searchText": "",
            }
            data = post_json(session, api, payload)
            polite_sleep()
            if not isinstance(data, dict):
                break
            postings = data.get("jobPostings") or []
            if not postings:
                break
            for p in postings:
                external = p.get("externalPath", "") or ""
                if external.startswith(f"/{site}/"):
                    apply_url = f"https://{tenant}.{dc}.myworkdayjobs.com{external}"
                elif external:
                    apply_url = urljoin(public_root, external.lstrip("/"))
                else:
                    apply_url = ""
                candidate = row(
                    source=f"workday:{tenant}",
                    title=p.get("title", ""),
                    company=name,
                    location=p.get("locationsText", ""),
                    url=apply_url,
                    description="",
                    posted=p.get("postedOn", ""),
                )
                if candidate and passes_prefilter(candidate):
                    rows.append(candidate)
            if len(postings) < _LIMIT:
                break

    kept = keep_rows(rows)
    log.info("[workday] %d tenants, %d kept", len(entries), len(kept))
    return kept
