"""Helpers shared by every source collector.

The v2 pre-filter is intentionally strict. The four checks together drop
~70% of incoming rows before any expensive Claude call:

  1. is_in_au_scope(location)       - Australia (or AU-remote) only
  2. is_tech_role(title, desc)      - tech keyword present, non-tech absent
  3. is_truly_junior(title, desc)   - grad/intern/trainee signal, no senior signal
  4. has_visa_blocker(desc)         - obvious citizen/PR/clearance ads dropped early

Each is a substring match against curated lists in `config.py`. The
helpers log at DEBUG when they reject a row, so turning DEBUG on shows
exactly why anything gets dropped.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Iterable

import requests

from config import (
    AU_LOCATION_HINTS,
    AU_REMOTE_MARKERS,
    INTER_REQUEST_SLEEP,
    JUNIOR_HINTS,
    NON_AU_LOCATION_PREFIXES,
    NON_TECH_DISQUALIFIERS,
    REQUEST_TIMEOUT,
    SENIOR_DISQUALIFIERS,
    TECH_ROLE_HINTS,
    USER_AGENT,
    VISA_DISQUALIFIERS,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return s


def polite_sleep(seconds: float = INTER_REQUEST_SLEEP) -> None:
    time.sleep(seconds)


def get_json(
    session: requests.Session,
    url: str,
    *,
    log_label: str | None = None,
    **kwargs,
) -> dict | list | None:
    """GET a JSON endpoint, returning the decoded body or None on any error.

    `log_label` lets callers pass a sanitised URL string for log messages -
    useful when the real URL embeds a secret (e.g. Jooble's path-based key).
    """
    label = log_label or url
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        log.warning("GET %s failed: %s", label, exc)
        return None
    if resp.status_code >= 400:
        log.warning("GET %s -> HTTP %s", label, resp.status_code)
        return None
    try:
        return resp.json()
    except ValueError as exc:
        log.warning("GET %s returned non-JSON: %s", label, exc)
        return None


def post_json(
    session: requests.Session,
    url: str,
    payload: dict,
    *,
    log_label: str | None = None,
    **kwargs,
) -> dict | list | None:
    """POST JSON and decode the response, returning None on any error."""
    label = log_label or url
    try:
        resp = session.post(url, json=payload, timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        log.warning("POST %s failed: %s", label, exc)
        return None
    if resp.status_code >= 400:
        log.warning("POST %s -> HTTP %s", label, resp.status_code)
        return None
    try:
        return resp.json()
    except ValueError as exc:
        log.warning("POST %s returned non-JSON: %s", label, exc)
        return None


def get_html(
    session: requests.Session,
    url: str,
    **kwargs,
) -> str | None:
    """Plain GET expecting text/HTML. Used by bespoke direct-scrape modules."""
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        log.warning("GET %s failed: %s", url, exc)
        return None
    if resp.status_code >= 400:
        log.warning("GET %s -> HTTP %s", url, resp.status_code)
        return None
    return resp.text


# ---------------------------------------------------------------------------
# Pre-filter: location
# ---------------------------------------------------------------------------


def is_in_au_scope(location: str) -> bool:
    """Strict AU-only with AU-targeted remote.

    Accept: explicit AU city / state / "Australia"; or "Remote" with an
            AU-specific qualifier (e.g. "Remote (Australia)").
    Reject: bare "Remote" (no AU qualifier), and any location tagged with
            a non-AU country or city.
    """
    if not location:
        return False
    loc = location.lower()

    # Hard reject: non-AU country / state / city
    if any(prefix in loc for prefix in NON_AU_LOCATION_PREFIXES):
        return False

    # AU city / state / "Australia"
    if any(hint in loc for hint in AU_LOCATION_HINTS):
        return True

    # Remote, but only with AU marker
    if "remote" in loc and any(m in loc for m in AU_REMOTE_MARKERS):
        return True

    return False


# ---------------------------------------------------------------------------
# Pre-filter: tech-role
# ---------------------------------------------------------------------------


def is_tech_role(title: str, description: str = "") -> bool:
    """Title or description must signal tech AND not signal non-tech.

    Non-tech wins: "Graduate Civil Engineer" contains "engineer" (no longer
    in TECH_ROLE_HINTS - we require more specific terms) but also contains
    the non-tech disqualifier "civil engineer", so it's rejected.
    """
    t = (title or "").lower()
    d = (description or "").lower()
    haystack = t + " " + d

    if any(bad in t for bad in NON_TECH_DISQUALIFIERS):
        return False
    # Also reject if description leads with a non-tech discipline
    if any(bad in d[:500] for bad in NON_TECH_DISQUALIFIERS):
        return False

    return any(hint in haystack for hint in TECH_ROLE_HINTS)


# ---------------------------------------------------------------------------
# Pre-filter: junior
# ---------------------------------------------------------------------------

# "3+ years" / "5 years experience" / "Minimum 2 years" - any of these in
# the description means the role wants experience and is dropped.
# We DON'T reject ranges that include 0 ("0-2 years" / "1-3 years").
_YEARS_RE = re.compile(
    r"(?<![0-1][-\s])"        # not preceded by "0-" or "1-"
    r"\b([2-9]|[1-9]\d)\s*\+?\s*years?\b",
    re.IGNORECASE,
)


def is_truly_junior(title: str, description: str = "") -> bool:
    """Title must signal grad-level AND not signal senior-level AND
    description must not require multiple years of experience."""
    t = (title or "").lower()
    d = (description or "").lower()

    if any(bad in t for bad in SENIOR_DISQUALIFIERS):
        return False
    if not any(hint in t for hint in JUNIOR_HINTS):
        return False
    if _YEARS_RE.search(d):
        return False

    return True


# ---------------------------------------------------------------------------
# Pre-filter: visa
# ---------------------------------------------------------------------------


def has_visa_blocker(description: str) -> bool:
    """Description contains an obvious citizenship / PR / clearance phrase.

    Conservative - only the clearest no-go phrases. Claude handles nuance
    afterwards. False positives here would silently kill legit roles.
    """
    if not description:
        return False
    d = description.lower()
    return any(phrase in d for phrase in VISA_DISQUALIFIERS)


# ---------------------------------------------------------------------------
# Combined pre-filter
# ---------------------------------------------------------------------------


def passes_prefilter(row: dict) -> bool:
    """Apply all four pre-filter checks. Logs the reason on rejection."""
    title = row.get("title", "")
    location = row.get("location", "")
    description = row.get("description", "")

    if not is_in_au_scope(location):
        log.debug("reject location: %r (%s)", location, title)
        return False
    if not is_truly_junior(title, description):
        log.debug("reject seniority: %r", title)
        return False
    if not is_tech_role(title, description):
        log.debug("reject non-tech: %r", title)
        return False
    if has_visa_blocker(description):
        log.debug("reject visa: %r", title)
        return False
    return True


# ---------------------------------------------------------------------------
# Row construction
# ---------------------------------------------------------------------------


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
    """Build a normalised row. Returns an empty dict if `url`/`title`/
    `company` is missing - those get filtered out before dedupe."""
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
    """Drop empty / URL-less rows. Used after the source-level loop."""
    return [r for r in rows if r and r.get("url")]
