"""Central configuration for the grad-job-finder pipeline.

All collectors and helpers import constants from here, so this is the
single place to tune scope. v2 is intentionally strict: the user's main
complaint about v1 was that everything leaked through the filters.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Search scope (Layer A - aggregator query terms)
# ---------------------------------------------------------------------------
# v2: tech-only, grad-phrased. Each term is a phrase the aggregator
# matches against the title + description. Generic "intern" or
# "associate" was dropped because it caught civil engineering interns,
# senior associates, etc.
SEARCH_TERMS: list[str] = [
    "graduate software engineer",
    "graduate developer",
    "software engineer intern",
    "graduate data scientist",
    "graduate data analyst",
    "graduate machine learning",
    "technology graduate program",
    "quantitative developer graduate",
    "cyber security graduate",
]

# Single AU pass per term. v1 also did a "Remote" pass which dragged in
# US-Remote roles; v2 rejects those at the filter, so the extra pass
# adds noise without value.
LOCATIONS: list[str] = ["Australia"]

# How far back to look (aggregator parameter).
MAX_DAYS_OLD: int = 30

# Aggregator pagination cap.
RESULTS_PER_TERM: int = 50

# ---------------------------------------------------------------------------
# Junior / senior title filters
# ---------------------------------------------------------------------------
# Title MUST contain one of these to be considered grad-level. v2 drops
# the loose "associate" and "junior" because "Senior Associate" and
# "Junior Manager" (yes, that exists) were slipping through.
JUNIOR_HINTS: list[str] = [
    "graduate",
    "grad program",
    "grad role",
    "grad opportunity",
    "intern",
    "internship",
    "trainee",
    "cadet",
    "cadetship",
    "new grad",
    "early career",
    "entry level",
    "entry-level",
    "no experience",
    "campus hire",
]

# Title with any of these terms is rejected outright - they signal
# experienced-only roles and override JUNIOR_HINTS matches.
SENIOR_DISQUALIFIERS: list[str] = [
    "senior",
    "sr.",
    "sr ",
    "staff",
    "principal",
    "lead ",
    " lead",
    "head of",
    "head,",
    "director",
    "manager",
    "architect",
    "chief",
    "vp ",
    "vp,",
    " ii",
    " iii",
    " iv",
    "level 3",
    "level 4",
    "level 5",
    "experienced",
]

# ---------------------------------------------------------------------------
# Tech-role gate
# ---------------------------------------------------------------------------
# Title or description MUST contain at least one of these. Stops
# "Graduate Mechanical Engineer" / "Graduate Civil Engineer" /
# "Graduate Accountant" from being surfaced.
TECH_ROLE_HINTS: list[str] = [
    "software",
    "developer",
    "data scien",      # scientist + science (uni grads sometimes phrased this way)
    "data analy",      # analyst + analytics
    "data engineer",
    "machine learning",
    "deep learning",
    "ai engineer",
    "ai/ml",
    "artificial intelligence",
    "analytics engineer",
    "devops",
    "site reliability",
    "platform engineer",
    "cloud engineer",
    "infrastructure engineer",
    "security engineer",
    "cyber",
    "quant",                      # quant analyst, quant developer
    "backend",
    "back-end",
    "frontend",
    "front-end",
    "full stack",
    "fullstack",
    "mobile engineer",
    "ios engineer",
    "android engineer",
    "embedded engineer",
    "technology graduate",
    "tech graduate",
    "computer science",
]

# Title hits any of these and the role is rejected even if it has a
# tech-flavoured word elsewhere. The "engineer" alone isn't enough -
# civil/mech engineers are also "engineers".
NON_TECH_DISQUALIFIERS: list[str] = [
    "civil engineer",
    "mechanical engineer",
    "electrical engineer",
    "chemical engineer",
    "mining engineer",
    "petroleum engineer",
    "structural engineer",
    "environmental engineer",
    "biomedical engineer",
    "aerospace engineer",
    "process engineer",
    "field engineer",
    "geotechnical",
    "lawyer",
    "legal counsel",
    "paralegal",
    "law graduate",
    "law clerk",
    "accountant",
    "accounting graduate",
    "auditor",
    "audit graduate",
    "audit & assurance",
    "tax graduate",
    "tax consultant",
    "financial planner",
    "financial planning",
    "actuarial",
    "actuary",
    "marketing",
    "sales graduate",
    "business development",
    "recruitment",
    "hr graduate",
    "human resources",
    "people & culture",
    "customer service",
    "nursing",
    "registered nurse",
    "teacher",
    "policy adviser",
    "policy officer",
    "social worker",
    "supply chain graduate",
    "logistics graduate",
    "operations graduate",       # too vague; tech ops use "platform"/"infra"/"sre"
    "investment banking",
    "trader",                    # not quant dev
    "trading analyst",
]

# ---------------------------------------------------------------------------
# Visa pre-filter (cheap regex; Claude does the nuanced call)
# ---------------------------------------------------------------------------
VISA_DISQUALIFIERS: list[str] = [
    # citizenship
    "australian citizen",
    "australian citizenship",
    "must be a citizen",
    "must be an australian citizen",
    "citizens only",
    "citizenship is required",
    "citizenship required",
    "australian or new zealand citizen",
    "australian or nz citizen",
    "australian / nz citizen",
    "aussie citizen",
    "nz citizen",
    # permanent residency
    "permanent resident",
    "permanent residency",
    "pr required",
    "pr or citizen",
    "must hold pr",
    "must have pr",
    "must hold permanent residency",
    "australian permanent resident",
    "au pr ",
    "must hold australian permanent residency",
    # clearances (overwhelmingly citizenship-gated)
    "security clearance",
    "baseline clearance",
    "nv1 clearance",
    "nv2 clearance",
    "positive vetting",
    "agsva",
    "defence clearance",
    "must be eligible for clearance",
    "must be able to obtain clearance",
    # work-rights phrasings that ARE satisfied by a 485 visa.
    # Deliberately NOT pre-filtered here - they're ambiguous in isolation
    # ("ongoing" can mean indefinite OR just continuous over the contract;
    # "unrestricted right to work" is exactly what a 485 grants). Claude's
    # 3-axis screen has the context to make the right call.
    #   - "must have ongoing work rights"          -> let Claude judge
    #   - "must have unrestricted right to work"   -> 485 satisfies
    #   - "unrestricted right to live and work"    -> 485 satisfies
    #
    # We KEEP the unambiguous "we will not sponsor" phrasings: a 485 doesn't
    # need sponsorship, but in practice this wording is used by employers
    # who mean "PR-only" in shorthand.
    "no visa sponsorship",
    "we are unable to sponsor",
    "sponsorship is not available",
    "must not require sponsorship",
]

# ---------------------------------------------------------------------------
# Location gating
# ---------------------------------------------------------------------------
# Region scope. v2 is AU only; SG/HK can be added by extending this list
# (the matcher does a strict substring check).
REGION_SCOPE: list[str] = ["australia"]

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
    "geelong",
]

# Short AU state codes need word-boundary matching - bare substring
# matching causes false positives ("wa" matches "Newark", "sa" matches
# "Sacramento", "Salt Lake City"). The pre-filter applies these with
# a `\b<code>\b` regex.
AU_STATE_CODES: list[str] = [
    "nsw",
    "vic",
    "qld",
    "wa",
    "sa",
    "act",
    "nt",
    "tas",
]

# Substrings that mark a location as NOT in scope, even if "remote"
# appears later in the string. "remote" + any of these = US/EU role.
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
    # US cities
    "san francisco", "new york", "los angeles", "boston",
    "chicago", "seattle", "austin", "denver", "atlanta",
    "miami", "san diego", "portland", "philadelphia",
    "minneapolis", "dallas", "houston", "phoenix",
    # US states
    "california", "texas", "florida", "illinois", "massachusetts",
    "washington state", "oregon", "georgia, us", "georgia, usa",
    "virginia", "colorado", "new jersey", "new hampshire",
    # EU / UK / India / Asia tech hubs
    "london", "dublin", "berlin", "munich", "paris", "amsterdam",
    "stockholm", "barcelona", "madrid",
    "bangalore", "bengaluru", "mumbai", "hyderabad", "delhi",
    "gurgaon", "pune", "chennai", "noida",
    "tokyo", "shanghai", "beijing", "shenzhen", "seoul",
    "ho chi minh", "hanoi", "jakarta", "manila",
]

# Phrases that mark a "remote" listing as AU-targeted. If a row says
# "Remote" AND one of these is present, it stays in scope.
AU_REMOTE_MARKERS: list[str] = [
    "remote (australia",
    "remote, australia",
    "remote australia",
    "remote - australia",
    "remote within australia",
    "australia remote",
    "anywhere in australia",
    "remote anz",
    "remote (anz)",
    "remote, anz",
    "remote - anz",
    "remote (au)",
    "remote - au",
    "remote anywhere",  # generous, see has_visa_blocker for the second filter
]

# ---------------------------------------------------------------------------
# Claude screening (v2: mandatory)
# ---------------------------------------------------------------------------
CLAUDE_MODEL: str = "claude-haiku-4-5-20251001"
CLAUDE_MAX_TOKENS: int = 250
CLAUDE_DESCRIPTION_CHARS: int = 3000   # down from 4000 to trim token spend
CLAUDE_SLEEP_SECONDS: float = 0.3

# Safety cap on Claude calls per run. With a tight pre-filter the actual
# number should be much smaller; this protects against an unexpectedly
# leaky pre-filter (e.g. a new ATS dumping hundreds of rows).
MAX_CLAUDE_CALLS: int = 300

# Per-axis cut-offs. Anything below 6 on either fit axis is dropped;
# visa_fit == "no" is dropped; "unclear" is kept and flagged.
MIN_ROLE_FIT: int = 6
MIN_LEVEL_FIT: int = 6

# ---------------------------------------------------------------------------
# I/O paths
# ---------------------------------------------------------------------------
ROOT_DIR: Path = Path(__file__).resolve().parent
COMPANIES_FILE: Path = ROOT_DIR / "companies.yaml"
SEEN_FILE: Path = ROOT_DIR / "seen.json"
OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", str(ROOT_DIR))).resolve()

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
USER_AGENT: str = (
    "grad-job-finder/0.2 (+https://github.com/; contact via repo) "
    "python-requests"
)
REQUEST_TIMEOUT: float = 20.0
INTER_REQUEST_SLEEP: float = 0.2
