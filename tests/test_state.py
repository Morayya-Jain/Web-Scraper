"""Tests for the seen.json filter+persist logic."""
from __future__ import annotations

from dedupe import key as dedupe_key
from state import filter_seen


def _row(title="Graduate Software Engineer", company="TestCo", url=None):
    return {
        "source": "test",
        "title": title,
        "company": company,
        "location": "Sydney, Australia",
        "url": url or "https://example.com/job/1",
        "description": "",
        "posted": "",
    }


def test_filter_seen_empty_previous_keeps_all():
    rows = [_row(title="A"), _row(title="B")]
    out = filter_seen(rows, set())
    assert out == rows


def test_filter_seen_drops_known_keys():
    a = _row(title="Graduate Software Engineer")
    b = _row(title="Graduate Data Scientist")
    seen = {dedupe_key(a)}
    out = filter_seen([a, b], seen)
    assert len(out) == 1
    assert out[0]["title"] == "Graduate Data Scientist"


def test_filter_seen_is_case_insensitive():
    """Two rows that differ only in casing must collapse to one key, so
    a previously-seen lowercase row blocks an uppercase variant."""
    seen_row = _row(title="graduate developer", company="acme")
    seen = {dedupe_key(seen_row)}
    incoming = _row(title="Graduate Developer", company="ACME")
    out = filter_seen([incoming], seen)
    assert out == []


def test_filter_seen_handles_empty_row_list():
    assert filter_seen([], {"some_key"}) == []
