"""Persisted across-run state: `seen.json`.

Used to flag roles that are new since the last run. Not used for
filtering - the user still sees old roles in each digest; new ones just
get a [new] marker in the Markdown.
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


def save_seen(rows: list[dict]) -> None:
    """Persist the union of previously-seen keys and this run's keys.

    Union (not overwrite) is the load-bearing detail: if a run returns
    zero rows because every source was down, we must NOT wipe history -
    otherwise the next run would mark every old role as [new].
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
            "seen.json updated: %d keys (%d new this run)",
            len(merged),
            len(current - previously),
        )
    except OSError as exc:
        log.warning("could not write seen.json: %s", exc)


def mark_new(rows: list[dict], previously_seen: set[str]) -> list[dict]:
    """Annotate each row with is_new=True/False based on previously_seen."""
    out = []
    new_count = 0
    for r in rows:
        k = dedupe_key(r)
        is_new = k not in previously_seen
        if is_new:
            new_count += 1
        out.append({**r, "is_new": is_new})
    log.info("flagged %d new roles since last run", new_count)
    return out
