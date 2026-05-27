"""Persisted across-run state: `seen.json`.

v3 semantics: roles whose dedupe key is in `seen.json` are FILTERED OUT
of the next run's output entirely. This is stronger than the old
"tag as [new]" behaviour and serves the user's actual workflow - once
you've seen a role you've decided whether to apply, and don't want it
clogging up the shortlist on subsequent runs.

The filter is applied BEFORE Claude screening to save API spend - no
point re-screening a role we're going to drop anyway.

seen.json grows monotonically: save_seen() unions the just-output rows
into the existing key set. If a future run finds nothing, the file is
NOT wiped.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from config import SEEN_FILE
from dedupe import key as dedupe_key

log = logging.getLogger(__name__)


def load_seen() -> set[str]:
    if not SEEN_FILE.exists():
        return set()
    try:
        with SEEN_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("seen.json unreadable, starting fresh: %s", exc)
        return set()
    keys = data.get("keys") if isinstance(data, dict) else None
    return set(keys or [])


def filter_seen(rows: list[dict], previously_seen: set[str]) -> list[dict]:
    """Drop any row whose dedupe key has been output in a previous run.

    This is the user-facing "don't show me jobs I've already considered"
    rule. It runs after dedupe and before Claude screening, so old roles
    don't burn API tokens.
    """
    if not previously_seen:
        return rows
    out: list[dict] = []
    skipped = 0
    for r in rows:
        if dedupe_key(r) in previously_seen:
            skipped += 1
            continue
        out.append(r)
    log.info(
        "filter_seen: skipped %d already-seen rows, %d new rows survive",
        skipped,
        len(out),
    )
    return out


def save_seen(rows: list[dict]) -> None:
    """Persist the union of previously-seen keys and this run's output keys.

    Union (not overwrite) is the load-bearing detail: if a run returns
    zero rows we must NOT wipe history - otherwise next run would
    re-surface every old role.
    """
    current = {dedupe_key(r) for r in rows if r.get("title") and r.get("company")}
    previously = load_seen()
    merged = sorted(current | previously)
    payload = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "keys": merged,
    }
    try:
        with SEEN_FILE.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        log.info(
            "seen.json updated: %d total keys (%d added this run)",
            len(merged),
            len(current - previously),
        )
    except OSError as exc:
        log.warning("could not write seen.json: %s", exc)
