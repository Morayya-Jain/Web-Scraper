"""Shared helpers for bespoke scrapers.

Re-exports the strict pre-filter so each bespoke module can call
`passes_prefilter(row)` exactly like the standard collectors. Also
adds a thin BeautifulSoup wrapper so individual modules don't have to
import bs4 directly.
"""
from __future__ import annotations

import logging

from bs4 import BeautifulSoup

from htmlstrip import strip_html

from .._common import (
    get_html,
    get_json,
    keep_rows,
    make_session,
    passes_prefilter,
    polite_sleep,
    post_json,
    row,
)

log = logging.getLogger(__name__)


def parse_html(text: str | None) -> BeautifulSoup | None:
    """Wrap BeautifulSoup so callers don't have to import bs4 themselves."""
    if not text:
        return None
    try:
        return BeautifulSoup(text, "lxml")
    except Exception as exc:  # noqa: BLE001
        log.warning("BeautifulSoup parse failed: %s", exc)
        return None


__all__ = [
    "BeautifulSoup",
    "get_html",
    "get_json",
    "keep_rows",
    "log",
    "make_session",
    "parse_html",
    "passes_prefilter",
    "polite_sleep",
    "post_json",
    "row",
    "strip_html",
]
