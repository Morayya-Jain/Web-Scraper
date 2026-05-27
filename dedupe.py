"""Dedupe a normalised job list.

Key = md5(lower(company) + "|" + lower(title)).

When the same role appears from multiple sources, we keep the one with
the most-direct apply URL. Priority (high to low):
    direct ATS feeds (greenhouse:, lever:, ashby:, workable:,
                      recruitee:, smartrecruiters:, workday:)
    careerjet
    adzuna
    jooble
"""
from __future__ import annotations

import hashlib
import logging

log = logging.getLogger(__name__)

_PRIORITY = {
    # Direct-from-source layers (bespoke + standard ATS) have the most
    # accurate metadata and the cleanest apply URLs - keep these over any
    # aggregator copy of the same role.
    "bespoke": 110,
    "greenhouse": 100,
    "lever": 100,
    "ashby": 100,
    "workable": 100,
    "recruitee": 100,
    "smartrecruiters": 100,
    "workday": 100,
    "careerjet": 50,
    "adzuna": 40,
    "jooble": 30,
}


def key(row: dict) -> str:
    raw = (row.get("company", "") + "|" + row.get("title", "")).lower()
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _priority(source: str) -> int:
    if not source:
        return 0
    head = source.split(":", 1)[0]
    return _PRIORITY.get(head, 0)


def dedupe(rows: list[dict]) -> list[dict]:
    """Return one row per (company, title), preferring the most-direct URL."""
    best: dict[str, dict] = {}
    dropped = 0
    for r in rows:
        if not r.get("url"):
            dropped += 1
            continue
        k = key(r)
        current = best.get(k)
        if current is None:
            best[k] = r
            continue
        if _priority(r.get("source", "")) > _priority(current.get("source", "")):
            best[k] = r
            dropped += 1
        else:
            dropped += 1
    log.info("dedupe: kept %d, dropped %d", len(best), dropped)
    return list(best.values())
