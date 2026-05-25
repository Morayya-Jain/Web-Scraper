"""Workday - per-tenant CXS endpoint, no auth.

Endpoint shape:
    POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs

Request body (minimum):
    {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}

Response: {"total": N, "jobPostings": [
    {"title", "externalPath", "locationsText", "postedOn", ...}, ...]}

Per-tenant discovery is documented in companies.yaml and README.
Each entry needs `tenant`, `dc` (e.g. wd1/wd3/wd5), and `site` keys.

Apply URL is built from the externalPath: it's a relative path under the
tenant's public careers domain (NOT the cxs API host), of the form:
    https://{tenant}.{dc}.myworkdayjobs.com/{site}{externalPath}
"""
from __future__ import annotations

import logging
from urllib.parse import urljoin

from ._ats import for_ats, passes_ats_filter
from ._common import keep_rows, make_session, polite_sleep, post_json, row

log = logging.getLogger(__name__)

_API_TMPL = "https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
_PUBLIC_TMPL = "https://{tenant}.{dc}.myworkdayjobs.com/{site}"

# Page size and how many pages to scan per tenant. We cap to stay polite.
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
                title = p.get("title", "")
                location = p.get("locationsText", "")
                if not passes_ats_filter(title, location):
                    continue
                external = p.get("externalPath", "") or ""
                # externalPath today is of the form "/job/{loc}/{title}_{id}"
                # but Workday could change it to "/{site}/job/..." - detect
                # and don't double the {site} segment in that case.
                if external.startswith(f"/{site}/"):
                    apply_url = (
                        f"https://{tenant}.{dc}.myworkdayjobs.com{external}"
                    )
                elif external:
                    apply_url = urljoin(public_root, external.lstrip("/"))
                else:
                    apply_url = ""
                # bulletFields is a list (typically just the req number).
                # The real description only exists on the apply page itself;
                # leave description empty - title + location are enough for
                # dedupe + screening, and the URL has the full text.
                rows.append(
                    row(
                        source=f"workday:{tenant}",
                        title=title,
                        company=name,
                        location=location,
                        url=apply_url,
                        description="",
                        posted=p.get("postedOn", ""),
                    )
                )
            if len(postings) < _LIMIT:
                break

    kept = keep_rows(rows)
    log.info(
        "[workday] %d tenants, %d kept after AU+junior filter",
        len(entries),
        len(kept),
    )
    return kept
