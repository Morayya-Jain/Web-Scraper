# Australian Graduate Tech Job Finder (v2)

A scraper built to surface Australian **graduate-level tech roles** for an
international student who will hold a Temporary Graduate visa (subclass
485) after graduating in December 2026 or later. Manual-run only — hit
the GitHub Actions button (or `python main.py` locally) when you want a
fresh shortlist.

## What v2 fixed (vs v1)

| v1 problem | v2 fix |
|---|---|
| Daily cron eating Claude credits | Cron removed; `workflow_dispatch` only |
| Senior roles slipping through (Senior Associate, Lead, etc.) | Strict title pre-filter + Claude `level_fit` axis |
| Non-AU jobs slipping through | Strict AU-only location filter; bare "Remote" rejected unless AU-marked |
| Non-tech roles surfacing (civil, finance, law, marketing) | Explicit `TECH_ROLE_HINTS` + `NON_TECH_DISQUALIFIERS` |
| Visa filter missing obvious PR/citizen requirements | Expanded keyword pre-filter + stricter Claude visa prompt |
| Limited company coverage | Added Jane Street / IMC (Greenhouse) + Optiver (bespoke) |

## How it filters

```
Layer A: aggregators (Adzuna / Jooble / Careerjet)        9 tech-grad terms
Layer B: standard ATS (Greenhouse / Lever / Ashby /       per-company
         Workable / Recruitee / SmartRecruiters /         seed list
         Workday)
Layer C: bespoke direct-scrape (Optiver via WP AJAX)      ~1 module today
                ↓
        STAGE 1: cheap pre-filter (free, in-process)
                 - is_in_au_scope:      AU city/state OR AU-marked remote
                 - is_truly_junior:     title says grad/intern/trainee/cadet
                                        AND no senior/lead/director word
                                        AND desc doesn't say "3+ years"
                 - is_tech_role:        title or desc says software/data/AI/etc.
                                        AND no civil/mech/finance/law/etc.
                 - has_visa_blocker:    desc doesn't say PR/citizen/clearance
                ↓
        STAGE 2: Claude Haiku 3-axis screening (mandatory)
                 single API call per surviving row, returning JSON:
                 { role_fit: 0-10, level_fit: 0-10,
                   visa_fit: yes|no|unclear, reason: <short> }
                ↓
        STAGE 3: hard cut + sort
                 drop if role_fit<6 || level_fit<6 || visa_fit==no
                 sort by role_fit*level_fit desc
                ↓
        jobs_<ts>.csv + jobs_<ts>.md  +  update seen.json

`seen.json` tracks every role ever output. On the next run, any role
whose key matches an entry in `seen.json` is dropped BEFORE Claude
screening - so you only ever see a role once, and Claude API tokens
are never spent re-screening jobs you've already considered. To
re-surface old roles, delete or edit `seen.json` and re-run.
```

The pre-filter is load-bearing: it removes ~70% of upstream noise so
Claude only screens a handful of plausible rows. `MAX_CLAUDE_CALLS=300`
is a defensive cap; typical runs use 30-80 calls.

## The 485 visa rule

A subclass 485 grants **full unrestricted work rights for 2-4 years
and needs no sponsorship**. The Claude prompt in `screen.py` encodes
this rule explicitly:

- "valid work rights" / "full working rights" → `visa_fit: yes`
- "must be Australian citizen" → `visa_fit: no`
- "permanent residency required" → `visa_fit: no`
- "must hold AU or NZ citizenship" → `visa_fit: no`
- "security clearance / NV1 / NV2" → `visa_fit: no`
- silence on visa → `visa_fit: unclear` (kept and flagged)

## Quickstart (local)

```bash
git clone <this-repo>
cd Web-Scraper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Anthropic key is REQUIRED. Without it the run exits non-zero - there's
# no keyword-only fallback in v2 because it gave you wrong answers in v1.
cp .env.example .env
# edit .env - paste at minimum ANTHROPIC_API_KEY plus any aggregator keys

python main.py
```

Outputs:
- `jobs_<UTC-timestamp>.md` — ranked, human-readable shortlist (committed)
- `jobs_<UTC-timestamp>.csv` — raw rows with scores (gitignored, local only)
- `seen.json` — across-run state; flags `[new]` roles since last run

## Tests

```bash
pytest tests/    # 86 cases covering the four pre-filter helpers,
                 # the Claude JSON parser, and the dedupe tie-break.
```

The tests cover every false-positive that v1 surfaced. If a regression
slips back in, a test breaks before the user sees a bad shortlist.

## Running on GitHub Actions

Manual-only. Push the repo, add these as **Settings → Secrets and
variables → Actions → New repository secret**:

| Secret | Why |
|---|---|
| `ANTHROPIC_API_KEY` | **Required**. Pipeline aborts without it. |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Optional — adds aggregator coverage |
| `JOOBLE_API_KEY` | Optional — adds aggregator coverage |
| `CAREERJET_AFFID` | Optional — adds aggregator coverage |

Then **Actions → grad-jobs → Run workflow**. The workflow:
- runs `python main.py`,
- commits the new `jobs_*.md` + `seen.json` back to the repo,
- exits.

There is **no schedule**. Postings last for weeks; running this
whenever you want is enough.

## Adding a bespoke scraper

The `sources/bespoke/` directory hosts company-specific scrapers for
employers whose careers pages don't expose a standard ATS feed.

1. **Find a static endpoint.** Open the careers page in Chrome devtools
   → Network tab → filter to XHR/Fetch. Hit "Show all jobs" / "Search"
   and look for the URL that returns JSON or HTML chunks.
2. **Make sure it works without a browser.** Try the URL in `curl` with
   `-A "Mozilla/5.0 ..."`. If it returns 403 or empty bodies, the site
   is JS-rendered and you'll need Playwright (out of scope for v2).
3. **Copy `sources/bespoke/optiver.py` as a template.** It shows the
   pattern: a `fetch()` that POSTs/GETs the endpoint, parses each
   posting, calls `row(...)` and `passes_prefilter(...)`, and returns
   the list.
4. **Add the module to `_SOURCE_MODULES` in `main.py`.**
5. **Re-run `python main.py`** to confirm new rows appear.

## Why LinkedIn / GradConnection / Prosple / Seek / Indeed are NOT scraped

Same as v1 — it's a deliberate design choice:

- **LinkedIn**: blocks scrapers, can ban your account, ToS-violating.
- **GradConnection / Prosple**: no public API; HTML scraping breaks terms.
- **Seek / Indeed**: covered indirectly via Adzuna/Careerjet (which crawl
  them with permission).

Run their own email alerts in parallel to catch any LinkedIn-only role.

## Tuning the scope

Most things you'll want to change live in `config.py`:

| Constant | Purpose |
|---|---|
| `SEARCH_TERMS` | Aggregator query keywords (currently 9 tech-grad terms) |
| `LOCATIONS` | Currently `["Australia"]` only |
| `MAX_DAYS_OLD` | How far back the aggregators reach (30 days) |
| `JUNIOR_HINTS` | Title substrings required for grad-level |
| `SENIOR_DISQUALIFIERS` | Title substrings that reject the row |
| `TECH_ROLE_HINTS` | Tech keywords; one match required |
| `NON_TECH_DISQUALIFIERS` | Civil/finance/law/etc. — title rejects |
| `VISA_DISQUALIFIERS` | Cheap visa-blocker substrings |
| `MIN_ROLE_FIT`, `MIN_LEVEL_FIT` | Hard cuts after Claude scoring |
| `MAX_CLAUDE_CALLS` | Per-run cap on Claude API calls |

## File layout

```
.
+- main.py              # orchestrator
+- config.py            # all tunables in one file
+- companies.yaml       # ATS seed list - edit to grow Layer B coverage
+- dedupe.py            # md5(company|title) keying + URL preference
+- screen.py            # mandatory Claude 3-axis screening
+- state.py             # seen.json persistence
+- output.py            # CSV + Markdown writers
+- htmlstrip.py         # stdlib HTML -> text
+- sources/
|  +- _common.py        # HTTP helpers + 4 pre-filter checks + passes_prefilter
|  +- _ats.py           # companies.yaml loader
|  +- adzuna.py, jooble.py, careerjet.py
|  +- greenhouse.py, lever.py, ashby.py, workable.py
|  +- recruitee.py, smartrecruiters.py, workday.py
|  +- bespoke/
|     +- _common.py     # BS4 wrapper + re-exports
|     +- optiver.py     # quant, WordPress AJAX scrape
+- tests/               # pytest - 86 cases
+- .github/workflows/daily.yml   # manual-only workflow
+- requirements.txt
+- .env.example
+- .gitignore
+- README.md
```

## Limitations

- **JS-rendered career pages** (Macquarie, Atlassian, Canva, SIG, Citadel,
  Big 4 banks, Big 4 consulting) need a real browser. Layer A still
  picks most of them up via the aggregators, but direct-scrape coverage
  is incomplete.
- The keyword pre-filter is **conservative on purpose**. Borderline
  cases pass through to Claude; this is by design — we'd rather
  spend a few cents than silently drop a legit role.
- Workday tenants in `companies.yaml` are placeholders. The big AU
  banks (CBA / NAB / ANZ / Westpac) all use Workday but with
  non-guessable site IDs; verify each by visiting their careers page
  in devtools (see README) before relying on those entries.
