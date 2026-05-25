# Australian Graduate Job Finder

A daily web pull for Australian graduate / entry-level tech roles, built
for a final-year University of Melbourne engineering/tech student who
will hold a Temporary Graduate visa (subclass 485) after graduation.

The goal is to cast the widest practical net so you don't have to hand-
check hundreds of career pages each morning. Overlap between sources is
deliberate - I'd rather see a role twice than miss it.

## What it does

```
Layer A: aggregators (Adzuna, Jooble, Careerjet)
Layer B: public ATS feeds (Greenhouse, Lever, Ashby, Workable,
                           Recruitee, SmartRecruiters, Workday)
                                |
                       normalise to one schema
                                |
                             dedupe
                                |
       optional Claude screening (485 eligibility + fit, 0-10)
                                |
                  drop ineligible, rank by fit
                                |
                  jobs_<YYYYMMDD_HHMM>.{csv,md}
                                |
              optional: GitHub Actions runs it daily
```

## The 485 correctness rule

A subclass 485 grants **full, unrestricted work rights for 2-4 years
and needs no employer sponsorship**. So you can apply to almost
everything.

- Phrases like "must have full working rights", "valid work rights",
  "unrestricted work rights" mean **eligible**.
- A role is **ineligible** only when it clearly requires Australian or
  NZ citizenship, permanent residency, or a security clearance that
  requires citizenship (common in defence / federal government).
- When genuinely unclear, the role is kept and flagged `unclear` for
  manual review.

The Claude screening prompt is encoded in `screen.py` and enforces this.

## Quickstart

```bash
git clone <this-repo>
cd <this-repo>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy the env template and fill in whatever keys you have. Missing
# keys gracefully skip their source - the pipeline still runs.
cp .env.example .env
# edit .env

python main.py
```

Outputs land in the current directory as:
- `jobs_YYYYMMDD_HHMM.md` - ranked, human-readable shortlist (committed)
- `jobs_YYYYMMDD_HHMM.csv` - raw rows for spreadsheet review (gitignored)

## Free API signups

| Source    | Sign-up URL                                    | Notes |
| --------- | ----------------------------------------------- | ----- |
| Adzuna    | https://developer.adzuna.com                    | Free, ~250 calls/day |
| Jooble    | https://jooble.org/api/about                    | Free key on email request |
| Careerjet | https://www.careerjet.com/partners/api/         | Free `affid` on signup |
| Anthropic | https://console.anthropic.com                   | Optional, used by `screen.py`; falls back to a free keyword filter if absent |

Without any aggregator keys, only the ATS layer runs (still useful -
that's ~20 named Australian tech companies polled directly).

## Growing `companies.yaml`

The ATS layer's coverage is the seed list - to add a company:

1. Visit the company's careers / open roles page.
2. Look at the URL pattern to identify the ATS:

   | URL pattern                              | ATS              | Token field |
   | ---------------------------------------- | ---------------- | ----------- |
   | `boards.greenhouse.io/<slug>`            | `greenhouse`     | `<slug>`    |
   | `jobs.lever.co/<slug>`                   | `lever`          | `<slug>`    |
   | `jobs.ashbyhq.com/<slug>`                | `ashby`          | `<slug>`    |
   | `apply.workable.com/<slug>`              | `workable`       | `<slug>`    |
   | `<slug>.recruitee.com`                   | `recruitee`      | `<slug>`    |
   | `jobs.smartrecruiters.com/<slug>`        | `smartrecruiters`| `<slug>`    |
   | `<tenant>.<dc>.myworkdayjobs.com/<site>` | `workday`        | see below   |

3. Add an entry under the matching key in `companies.yaml`.
4. Re-run `python main.py`.

### Workday tenant discovery

Workday is fiddly because every tenant has its own subdomain, datacenter
(`wd1`, `wd3`, `wd5`, ...), and site name. To find the right triple:

1. Visit the company's careers page (it usually redirects to
   `<tenant>.<dc>.myworkdayjobs.com/<site>`).
2. Open browser devtools - Network tab. Filter on `cxs`.
3. Submit any search or scroll to load roles; you'll see an XHR to
   `https://<tenant>.<dc>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs`.
4. Copy the three slugs into a new entry in `companies.yaml` under
   `workday:`.

Entries marked `# verify` in the shipped `companies.yaml` are best-effort
guesses for the largest Australian employers (Telstra, NAB, BHP, Westpac,
Coles) - confirm each one's URL once before trusting it.

## Why LinkedIn, GradConnection, Prosple, Seek, Indeed are **not** scraped

This is a deliberate design choice, not a missing feature.

- **LinkedIn**: actively blocks scrapers, can ban your account, and has
  litigated over scraping. The only programmatic access is paid third-
  party aggregators. Companies cross-post: a LinkedIn graduate role is
  almost always also on the company's own ATS (covered by Layer B) and
  on Seek/Indeed (covered by Adzuna/Indeed via Layer A).
- **GradConnection / Prosple**: no clean public API; HTML scraping
  violates their terms and is brittle. They aggregate company grad
  programs that already surface via Layers A and B.
- **Seek / Indeed**: same story - both are covered indirectly via
  Adzuna and Careerjet, which crawl them with permission.

Run LinkedIn's own email alerts and GradConnection's email alerts in
parallel to catch the rare role that only appears there. This script
is the broad daily sweep; those alerts are the long-tail safety net.

## Daily run via GitHub Actions

A workflow ships in `.github/workflows/daily.yml`. It runs only on
manual `workflow_dispatch` by default - the `schedule:` cron line is
commented out so you can verify it works once before enabling.

To enable:

1. In your repo's Settings - Secrets - Actions, add each of the four
   API key secrets you have (`ADZUNA_APP_ID`, `ADZUNA_APP_KEY`,
   `JOOBLE_API_KEY`, `CAREERJET_AFFID`, `ANTHROPIC_API_KEY`).
2. Push the repo to GitHub.
3. Go to Actions - "daily-grad-jobs" - Run workflow. Verify it commits
   a `jobs_*.md` file back.
4. Uncomment the `schedule:` line in `daily.yml`. The default
   `0 22 * * *` UTC runs at 08:00 AEST (winter) / 09:00 AEDT (summer).

The workflow only commits `jobs_*.md` and `seen.json` - CSV files stay
in the runner. If you want CSVs preserved, upload them as workflow
artifacts in a separate step.

## File layout

```
.
+- main.py              # orchestrator
+- config.py            # search terms, locations, recency, filter words
+- companies.yaml       # ATS seed list (edit this to grow coverage)
+- dedupe.py            # md5(company|title) keying + URL-preference tie-break
+- screen.py            # Claude or keyword fallback screening
+- state.py             # seen.json persistence + new-since-last-run flag
+- output.py            # CSV + Markdown writers
+- htmlstrip.py         # stdlib HTML -> plain-text helper
+- sources/
|  +- _common.py        # session, get_json, looks_australian, looks_junior
|  +- _ats.py           # companies.yaml loader + ATS-shared filters
|  +- adzuna.py, jooble.py, careerjet.py
|  +- greenhouse.py, lever.py, ashby.py, workable.py
|  +- recruitee.py, smartrecruiters.py, workday.py
+- .github/workflows/daily.yml
+- requirements.txt
+- .env.example
+- .gitignore
+- seen.json            # produced on first run; tracks new-roles diff
+- README.md
```

## Tuning the scope

Most things you'll want to change live in `config.py`:

- `SEARCH_TERMS` - keywords passed to aggregator APIs.
- `LOCATIONS` - currently `["", "Remote"]` (Australia-wide + Remote).
- `MAX_DAYS_OLD = 30` - how far back the aggregators reach.
- `RESULTS_PER_TERM = 50` - aggregator pagination cap.
- `JUNIOR_HINTS` - title substrings required for ATS results.
- `VISA_DISQUALIFIERS` - phrases that trigger keyword-mode `eligible="no"`.

## Limitations

- Big consulting / banking / mining firms that use bespoke career sites
  (custom Workday Adaptive, SAP SuccessFactors) won't be covered by
  Layer B - Layer A picks them up via the aggregators instead.
- The Adzuna free tier caps at ~250 calls/day; the default config
  budgets ~34 calls/day, leaving plenty of room.
- The keyword pre-filter is crude. Enable Claude screening for real
  visa-rule enforcement.
- Workday's `descriptionPlain` isn't returned by the search endpoint -
  to get full text, the apply page itself is the source of truth.

## Acceptance checklist (from the build brief)

- [x] `python main.py` runs all 3 aggregators + all 7 ATS feeds, dedupes,
      and writes CSV + Markdown.
- [x] With `ANTHROPIC_API_KEY` set, ineligible roles are removed and the
      rest ranked by fit; `unclear` are kept and flagged.
- [x] Without it, the keyword pre-filter runs.
- [x] `companies.yaml` ships with a multi-industry starter list.
- [x] GitHub Actions workflow uses secrets and stores output.
- [x] No HTML scraping of LinkedIn / GradConnection / Prosple / Seek /
      Indeed anywhere.
- [x] README covers setup, API signups, ATS-slug discovery,
      growing the seed list, and the rationale for the excluded sources.
