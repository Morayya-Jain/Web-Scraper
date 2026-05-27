"""Regression tests for the pre-filter helpers.

These are the rules the v1 scraper got wrong - each case below was a
real false positive / false negative the user surfaced.
"""
from __future__ import annotations

import pytest

from sources._common import (
    has_visa_blocker,
    is_in_au_scope,
    is_tech_role,
    is_truly_junior,
    passes_prefilter,
)


# ---------------------------------------------------------------------------
# is_in_au_scope
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "location",
    [
        "Sydney",
        "Melbourne, Australia",
        "Brisbane, QLD",
        "Australia",
        "Perth, WA",
        "Remote (Australia)",
        "Remote, Australia",
        "Anywhere in Australia",
        "Remote within Australia",
    ],
)
def test_au_scope_accepts(location):
    assert is_in_au_scope(location), location


@pytest.mark.parametrize(
    "location",
    [
        "",
        "US - San Francisco (Remote)",
        "San Francisco, California (Remote)",
        "London, UK",
        "Remote",                       # bare remote, no AU marker -> rejected
        "Bangalore, India",
        "Remote (USA)",
        "Singapore (Remote)",
        "New York, NY",
        "Berlin, Germany",
        # Regression: short AU state codes used to match as bare substrings,
        # so US cities containing "wa"/"sa"/"act"/"nt" leaked through.
        "Newark, NJ",            # "wa" inside "Newark"
        "Waltham, MA",           # "wa" inside "Waltham"
        "Santa Clara, CA",       # "sa" inside "Santa"
        "Sacramento, CA",        # "sa" inside "Sacramento"
        "Salt Lake City, UT",    # "sa" inside "Salt"
        "Wawa, Ontario",         # "wa" inside "Wawa"
        "Contact us",            # "act" / "nt" inside common words
        "Anthropic, Hawaii",     # "nt" inside "Anthropic"
    ],
)
def test_au_scope_rejects(location):
    assert not is_in_au_scope(location), location


@pytest.mark.parametrize(
    "location",
    [
        "Sydney, NSW",
        "Melbourne, VIC",
        "Brisbane, QLD",
        "Perth, WA",
        "Adelaide, SA",
        "Canberra, ACT",
        "Hobart, TAS",
        "Darwin, NT",
    ],
)
def test_au_state_codes_accept_with_word_boundary(location):
    """The AU state codes must still pass when properly delimited."""
    assert is_in_au_scope(location), location


# ---------------------------------------------------------------------------
# is_tech_role
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title,description",
    [
        ("Graduate Software Engineer", ""),
        ("Software Engineer Intern", "Build APIs in Python"),
        ("Graduate Data Scientist", ""),
        ("Cyber Security Graduate", ""),
        ("Quantitative Developer Graduate", ""),
        ("Technology Graduate Program", "Join our tech grad program"),
        ("Backend Engineer - New Grad", ""),
        ("Cloud Engineering Intern", ""),
    ],
)
def test_tech_role_accepts(title, description):
    assert is_tech_role(title, description), title


@pytest.mark.parametrize(
    "title,description",
    [
        ("Graduate Civil Engineer", ""),
        ("Graduate Mechanical Engineer", ""),
        ("Graduate Accountant", ""),
        ("Graduate Lawyer", ""),
        ("Marketing Graduate", ""),
        ("Sales Graduate", ""),
        ("Audit Graduate", ""),
        ("Graduate HR Business Partner", ""),
        ("Tax Graduate", ""),
        ("Trader Graduate", ""),                 # not quant dev
    ],
)
def test_tech_role_rejects(title, description):
    assert not is_tech_role(title, description), title


# ---------------------------------------------------------------------------
# is_truly_junior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "title,description",
    [
        ("Graduate Software Engineer", ""),
        ("Software Engineer Intern", ""),
        ("Trainee Data Scientist", ""),
        ("New Grad Software Engineer", ""),
        ("Cadetship - Technology", ""),
        ("Entry Level Developer", ""),
        ("Cyber Security Graduate", ""),
    ],
)
def test_junior_accepts(title, description):
    assert is_truly_junior(title, description), title


@pytest.mark.parametrize(
    "title,description",
    [
        ("Senior Software Engineer", ""),
        ("Senior Associate", ""),
        ("Associate Director, Engineering", ""),
        ("Staff Engineer", ""),
        ("Engineering Manager", ""),
        ("Lead Data Scientist", ""),
        # Title looks junior but desc demands experience
        ("Graduate Software Engineer", "We need someone with 5+ years experience."),
        ("Engineer", ""),               # no junior signal
    ],
)
def test_junior_rejects(title, description):
    assert not is_truly_junior(title, description), title


@pytest.mark.parametrize(
    "phrase",
    [
        "We expect 0-2 years of relevant experience.",
        "0 - 2 years experience required.",
        "1 to 3 years of experience.",
        "0 to 2 years experience.",
        "1-3 years",
        "Looking for someone with 0–2 years of experience.",   # en-dash
    ],
)
def test_junior_accepts_grad_friendly_year_ranges(phrase):
    """Ranges starting at 0 or 1 should NOT be treated as wants-experience."""
    assert is_truly_junior("Graduate Developer", phrase), phrase


@pytest.mark.parametrize(
    "phrase",
    [
        "Requires 5+ years of relevant experience.",
        "3 years experience minimum.",
        "Minimum 4 years of experience required.",
        "5 to 7 years experience.",                # range not starting at 0/1
    ],
)
def test_junior_rejects_real_years_requirements(phrase):
    assert not is_truly_junior("Graduate Developer", phrase), phrase


# ---------------------------------------------------------------------------
# has_visa_blocker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "description",
    [
        "Must be an Australian citizen.",
        "Permanent residency required.",
        "PR required for this role.",
        "Must hold Australian or New Zealand citizenship.",
        "NV1 clearance required.",
        "Baseline clearance is mandatory.",
        "AGSVA-eligible candidates only.",
        "We are unable to sponsor visas.",
        "No visa sponsorship available.",
        "Sponsorship is not available.",
    ],
)
def test_visa_blocker_catches(description):
    assert has_visa_blocker(description), description


@pytest.mark.parametrize(
    "description",
    [
        "We welcome candidates with full working rights in Australia.",
        "Must have valid work rights.",
        "Open to graduates and recent international students.",
        "",
        # Regression: a 485 visa GRANTS full unrestricted work rights, so
        # these phrasings must NOT be pre-filtered out - they describe what
        # a 485 holder already has.
        "Must have unrestricted right to work in Australia.",
        "Unrestricted right to live and work required.",
        "Must have ongoing work rights in Australia.",
    ],
)
def test_visa_blocker_passes(description):
    assert not has_visa_blocker(description), description


# ---------------------------------------------------------------------------
# passes_prefilter (combined)
# ---------------------------------------------------------------------------


def _row(**kwargs):
    return {
        "source": "test",
        "title": kwargs.get("title", "Graduate Software Engineer"),
        "company": kwargs.get("company", "TestCo"),
        "location": kwargs.get("location", "Sydney, Australia"),
        "url": kwargs.get("url", "https://example.com/job/1"),
        "description": kwargs.get("description", ""),
        "posted": "",
    }


def test_prefilter_passes_clean_grad_tech_au_role():
    assert passes_prefilter(_row())


def test_prefilter_rejects_senior_associate_us_remote():
    """The v1 regression: 'Senior Associate' at a US-remote office."""
    assert not passes_prefilter(
        _row(
            title="Senior Associate, Revenue Operations",
            location="US - San Francisco (Remote)",
        )
    )


def test_prefilter_rejects_civil_engineering_graduate():
    assert not passes_prefilter(_row(title="Graduate Civil Engineer"))


def test_prefilter_rejects_finance_analyst_graduate():
    assert not passes_prefilter(_row(title="Marketing Graduate"))


def test_prefilter_rejects_citizenship_only_role():
    assert not passes_prefilter(
        _row(
            title="Graduate Software Engineer",
            description="You must be an Australian citizen with NV1 clearance.",
        )
    )


def test_prefilter_rejects_san_francisco_remote_software_grad():
    assert not passes_prefilter(
        _row(location="San Francisco, California (Remote)")
    )


def test_prefilter_rejects_director_titled_role():
    assert not passes_prefilter(
        _row(title="Associate Director, Engineering Graduate Programs")
    )
