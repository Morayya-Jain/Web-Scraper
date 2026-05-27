"""Tests for the dedupe priority tie-break."""
from __future__ import annotations

from dedupe import dedupe, key


def _row(source, title="Graduate Software Engineer", company="TestCo", url=None):
    return {
        "source": source,
        "title": title,
        "company": company,
        "location": "Sydney, Australia",
        "url": url or f"https://example.com/{source}",
        "description": "",
        "posted": "",
    }


def test_drops_url_less_rows():
    rows = [_row("adzuna", url=""), _row("greenhouse:atlassian")]
    out = dedupe(rows)
    assert len(out) == 1
    assert out[0]["source"] == "greenhouse:atlassian"


def test_keeps_ats_over_aggregator():
    rows = [
        _row("adzuna"),
        _row("greenhouse:atlassian"),
    ]
    out = dedupe(rows)
    assert len(out) == 1
    # ATS priority 100 beats aggregator priority 40
    assert "greenhouse" in out[0]["source"]


def test_keeps_careerjet_over_jooble():
    rows = [
        _row("jooble"),
        _row("careerjet"),
    ]
    out = dedupe(rows)
    assert len(out) == 1
    assert out[0]["source"] == "careerjet"


def test_keeps_bespoke_over_aggregator():
    """Bespoke scrapers must outrank aggregators - they have cleaner URLs
    and more accurate metadata."""
    rows = [
        _row("adzuna"),
        _row("bespoke:optiver"),
    ]
    out = dedupe(rows)
    assert len(out) == 1
    assert out[0]["source"] == "bespoke:optiver"


def test_keeps_bespoke_over_standard_ats():
    """Bespoke is also preferred over standard ATS when both have the role."""
    rows = [
        _row("greenhouse:janestreet"),
        _row("bespoke:optiver"),
    ]
    out = dedupe(rows)
    assert len(out) == 1
    assert out[0]["source"] == "bespoke:optiver"


def test_different_titles_dont_collapse():
    rows = [
        _row("adzuna", title="Graduate Software Engineer"),
        _row("adzuna", title="Graduate Data Scientist"),
    ]
    out = dedupe(rows)
    assert len(out) == 2


def test_key_is_case_insensitive():
    a = key({"company": "ACME", "title": "Graduate Engineer"})
    b = key({"company": "acme", "title": "graduate engineer"})
    assert a == b
