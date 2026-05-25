"""Central configuration for the grad-job-finder pipeline.

All collectors and helpers import constants from here, so this is the one
place to tune scope without touching code.
"""
from __future__ import annotations

import os
from pathlib import Path

# --- Search scope -----------------------------------------------------------

# Wide-net role focus: tech + data + cloud + grad programs. 17 terms.
SEARCH_TERMS: list[str] = [
    "software engineer",
    "software developer",
    "graduate software",
    "data analyst",
    "data scientist",
    "data engineer",
    "machine learning",
    "devops",
    "platform engineer",
    "site reliability",
    "cloud engineer",
    "security engineer",
    "graduate program",
    "technology graduate",
    "engineering graduate",
    "intern",
    "associate",
]

# "" = Australia-wide pass (no city filter). "Remote" = explicit remote pass.
# 17 terms x 2 locations x 3 aggregators ~= 102 calls (Adzuna free tier is 250/day).
LOCATIONS: list[str] = ["", "Remote"]

# How far back to look. The brief defaults wide (30 days) so the daily run
# still catches roles posted on weekends or while CI was down.
MAX_DAYS_OLD: int = 30

# Pagination cap per (term, location) on aggregators that support it.
RESULTS_PER_TERM: int = 50

# Title-substring filter applied to ATS feeds (Layer B). Aggregator results
# are already keyword-filtered by the search term itself, but ATS feeds dump
# every open role for a company, so we keep only the junior-flavoured ones.
JUNIOR_HINTS: list[str] = [
    "graduate",
    "grad",
    "junior",
    "entry level",
    "entry-level",
    "intern",
    "associate",
    "early career",
    "new grad",
]

# Title substrings that override a JUNIOR_HINT match. "Associate Director"
# matches `associate` but is decidedly NOT a grad role.
SENIOR_DISQUALIFIERS: list[str] = [
    "senior",
    "staff",
    "principal",
    "lead",
    "head of",
    "head,",
    "director",
    "manager",
    "vp,",
    "vp ",
    "chief",
    "architect",
]

# Locations we consider in-scope. Used by ATS collectors.
AU_LOCATION_HINTS: list[str] = [
    "australia",
    "melbourne",
    "sydney",
    "brisbane",
    "perth",
    "adelaide",
    "canberra",
    "hobart",
    "darwin",
    "gold coast",
    "newcastle",
    "wollongong",
    "anywhere",
]

# Locations to explicitly reject. A "Remote" job tagged with a non-AU
# country / state / major-city name is almost always restricted to that
# region in practice. We check via simple lowercase substring match -
# false positives are rare because AU cities are listed in AU_LOCATION_HINTS
# (and AU_LOCATION_HINTS is checked AFTER this rejection list).
NON_AU_LOCATION_PREFIXES: list[str] = [
    # country / region tags
    "us -", "us-", "u.s.", "usa", "united states",
    "eu -", "eu-",
    "uk -", "uk-", "united kingdom",
    "emea", "latam", "apac (",
    "canada",
    "india -", "india-",
    "singapore -", "singapore-",
    "germany", "france", "ireland",
    "philippines", "vietnam", "indonesia",
    "japan", "china", "hong kong", "korea",
    "brazil", "mexico", "spain",
    "netherlands", "poland", "sweden", "denmark", "finland",
    "switzerland", "austria", "italy", "portugal",
    # US cities (most common in tech postings)
    "san francisco", "new york", "los angeles", "boston",
    "chicago", "seattle", "austin", "denver", "atlanta",
    "miami", "san diego", "portland", "philadelphia",
    "minneapolis", "dallas", "houston", "phoenix",
    # US states
    "california", "texas", "florida", "illinois", "massachusetts",
    "washington state", "oregon", "georgia, us", "georgia, usa",
    "virginia", "colorado", "new jersey", "new hampshire",
    # EU/UK/India cities (tech-heavy)
    "london", "dublin", "berlin", "munich", "paris", "amsterdam",
    "stockholm", "barcelona", "madrid", "bangalore", "bengaluru",
    "mumbai", "hyderabad", "delhi", "gurgaon", "pune",
    # Asia
    "tokyo", "shanghai", "beijing", "shenzhen", "seoul",
    "ho chi minh", "hanoi", "jakarta", "manila",
]

# --- Visa keyword pre-filter (free fallback when no ANTHROPIC_API_KEY) ------

# Phrases whose presence in a description strongly indicates the role is
# closed to non-citizens / non-PRs. NOT a substitute for Claude screening;
# this only catches the most blatant cases.
VISA_DISQUALIFIERS: list[str] = [
    "australian citizen",
    "australian citizenship",
    "must be a citizen",
    "permanent resident",
    "pr required",
    "must hold pr",
    "must have pr",
    "security clearance",
    "baseline clearance",
    "nv1 clearance",
    "nv2 clearance",
    "agsva",
]

# --- Claude screening -------------------------------------------------------

CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
CLAUDE_MAX_TOKENS: int = 200
CLAUDE_DESCRIPTION_CHARS: int = 4000
CLAUDE_SLEEP_SECONDS: float = 0.3

# --- I/O paths --------------------------------------------------------------

ROOT_DIR: Path = Path(__file__).resolve().parent
COMPANIES_FILE: Path = ROOT_DIR / "companies.yaml"
SEEN_FILE: Path = ROOT_DIR / "seen.json"
OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", str(ROOT_DIR))).resolve()

# --- HTTP -------------------------------------------------------------------

USER_AGENT: str = (
    "grad-job-finder/0.1 (+https://github.com/; contact via repo) "
    "python-requests"
)
REQUEST_TIMEOUT: float = 20.0
INTER_REQUEST_SLEEP: float = 0.2  # be polite between calls within a source
