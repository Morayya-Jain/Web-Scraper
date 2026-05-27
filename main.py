"""Australian Graduate Job Finder - orchestrator.

Runs every source collector with per-source try/except, dedupes, screens
for visa eligibility + fit, and writes a CSV + Markdown shortlist.

Designed to fail soft per source: one bad collector must not crash the
whole run. The script always produces output files, even if they're empty.
"""
from __future__ import annotations

import logging
import sys
from importlib import import_module
from typing import Callable

from config import OUTPUT_DIR

# --- Logging setup ----------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("main")

# --- .env loading (optional) ------------------------------------------------

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    log.debug("python-dotenv not installed; skipping .env load")


# --- Source registry --------------------------------------------------------

# Order is cosmetic but kept stable for readability of logs.
_SOURCE_MODULES = [
    # Layer A (aggregators)
    "sources.adzuna",
    "sources.jooble",
    "sources.careerjet",
    # Layer B (ATS feeds)
    "sources.greenhouse",
    "sources.lever",
    "sources.ashby",
    "sources.workable",
    "sources.recruitee",
    "sources.smartrecruiters",
    "sources.workday",
    # Layer C (bespoke direct-scrape)
    "sources.bespoke.optiver",
]


def _import_fetcher(modname: str) -> Callable[[], list[dict]] | None:
    try:
        mod = import_module(modname)
    except ImportError as exc:
        log.warning("could not import %s: %s", modname, exc)
        return None
    fetch = getattr(mod, "fetch", None)
    if not callable(fetch):
        log.warning("%s has no fetch()", modname)
        return None
    return fetch


def collect_all() -> list[dict]:
    rows: list[dict] = []
    for modname in _SOURCE_MODULES:
        fetch = _import_fetcher(modname)
        if fetch is None:
            continue
        try:
            fetched = fetch() or []
        except Exception as exc:  # noqa: BLE001 - one bad source can't crash run
            log.exception("%s.fetch() raised: %s", modname, exc)
            continue
        rows.extend(fetched)
    return rows


def main() -> int:
    log.info("starting grad-job-finder run")
    raw = collect_all()
    log.info("collected %d raw rows across all sources", len(raw))

    # Late imports so a typo in a downstream module is reported clearly.
    from dedupe import dedupe
    from screen import screen
    from state import load_seen, mark_new, save_seen
    from output import write_outputs

    deduped = dedupe(raw)
    screened = screen(deduped)

    previously_seen = load_seen()
    flagged = mark_new(screened, previously_seen)
    save_seen(flagged)

    csv_path, md_path = write_outputs(flagged, OUTPUT_DIR)
    log.info("done. CSV=%s MD=%s", csv_path, md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
