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
    ],
)
def test_au_scope_rejects(location):
    assert not is_in_au_scope(location), location


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


def test_junior_accepts_zero_to_two_years():
    """'0-2 years' should NOT be treated as 'wants experience'."""
    assert is_truly_junior(
        "Graduate Developer", "We expect 0-2 years of relevant experience."
    )


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
