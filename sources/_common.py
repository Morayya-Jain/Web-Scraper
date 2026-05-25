"""Helpers shared by every source collector.

Kept tiny on purpose; per-source logic lives in each collector. Importing
this module from a source must not have side effects.
"""
from __future__ import annotations

import logging
import time
from typing import Iterable

import requests

from config import (
    AU_LOCATION_HINTS,
    INTER_REQUEST_SLEEP,
    JUNIOR_HINTS,
    NON_AU_LOCATION_PREFIXES,
    REQUEST_TIMEOUT,
    SENIOR_DISQUALIFIERS,
    USER_AGENT,
)

log = logging.getLogger(__name__)


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


def polite_sleep(seconds: float = INTER_REQUEST_SLEEP) -> None:
    time.sleep(seconds)


def get_json(session: requests.Session, url: str, **kwargs) -> dict | list | None:
    """GET a JSON endpoint, returning the decoded body or None on any error."""
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        log.warning("GET %s failed: %s", url, exc)
        return None
    if resp.status_code >= 400:
        log.warning("GET %s -> HTTP %s", url, resp.status_code)
        return None
    try:
        return resp.json()
    except ValueError as exc:
        log.warning("GET %s returned non-JSON: %s", url, exc)
        return None


def post_json(
    session: requests.Session,
    url: str,
    payload: dict,
    **kwargs,
) -> dict | list | None:
    """POST JSON and decode the response, returning None on any error."""
    try:
        resp = session.post(url, json=payload, timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        log.warning("POST %s failed: %s", url, exc)
        return None
    if resp.status_code >= 400:
        log.warning("POST %s -> HTTP %s", url, resp.status_code)
        return None
    try:
        return resp.json()
    except ValueError as exc:
        log.warning("POST %s returned non-JSON: %s", url, exc)
        return None


def looks_australian(location: str) -> bool:
    """Decide whether a job location is in-scope.

    Accepts: explicit AU city or "Australia"; or a bare "Remote" / "Anywhere"
    with no non-AU region prefix.
    Rejects: anything tagged with a non-AU country/region prefix (e.g.
    "US - San Francisco (Remote)", "EU - Berlin").
    """
    if not location:
        return False
    loc = location.lower()
    if any(prefix in loc for prefix in NON_AU_LOCATION_PREFIXES):
        return False
    if any(hint in loc for hint in AU_LOCATION_HINTS):
        return True
    # Bare "remote" without a region qualifier - give it the benefit of the
    # doubt; Claude screening or the user will reject if needed.
    if "remote" in loc:
        return True
    return False


def looks_junior(title: str) -> bool:
    """Title contains a graduate / intern / entry-level keyword and is NOT
    senior-flavoured.

    "Associate Director" matches the loose `associate` hint but is clearly
    not a grad role - SENIOR_DISQUALIFIERS filters it out.
    """
    if not title:
        return False
    t = title.lower()
    if any(bad in t for bad in SENIOR_DISQUALIFIERS):
        return False
    return any(hint in t for hint in JUNIOR_HINTS)


def row(
    *,
    source: str,
    title: str,
    company: str,
    location: str,
    url: str,
    description: str,
    posted: str,
) -> dict:
    """Build a normalised row. Returns an empty dict if `url` is missing -
    those get filtered out before dedupe."""
    if not url or not title or not company:
        return {}
    return {
        "source": source,
        "title": title.strip(),
        "company": company.strip(),
        "location": (location or "").strip(),
        "url": url.strip(),
        "description": (description or "").strip(),
        "posted": (posted or "").strip(),
    }


def keep_rows(rows: Iterable[dict]) -> list[dict]:
    """Drop empty / URL-less rows."""
    return [r for r in rows if r and r.get("url")]
