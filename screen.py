"""Visa-eligibility + fit screening.

Two modes:
1. Claude (preferred). Active when ANTHROPIC_API_KEY is set. Uses the
   verbatim system prompt from the build brief (Section 9). Returns
   {"eligible", "reason", "fit"} per role.
2. Free keyword pre-filter. Active when no API key. Marks roles whose
   description contains any of the VISA_DISQUALIFIERS substrings as
   eligible="no"; everything else is "unclear" with fit=0.

Either way, the pipeline:
- annotates every row with eligible/reason/fit
- drops rows marked eligible="no"
- sorts the rest by fit descending (Claude) or leaves order intact
  (keyword mode)
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import requests

from config import (
    CLAUDE_DESCRIPTION_CHARS,
    CLAUDE_MAX_TOKENS,
    CLAUDE_MODEL,
    CLAUDE_SLEEP_SECONDS,
    REQUEST_TIMEOUT,
    VISA_DISQUALIFIERS,
)

log = logging.getLogger(__name__)

_API = "https://api.anthropic.com/v1/messages"

# The exact wording from the brief, section 9. Do not edit casually -
# the 485 correctness rule is encoded here.
SYSTEM_PROMPT = (
    "You screen Australian job ads for an international student who holds (or "
    "will soon hold) a Temporary Graduate visa, subclass 485. A 485 grants "
    "FULL, UNRESTRICTED work rights for 2 to 4 years and needs NO employer "
    "sponsorship. So the candidate CAN apply to almost everything.\n"
    "\n"
    "Mark eligible=\"no\" ONLY when the ad clearly requires Australian or NZ "
    "citizenship, permanent residency, or a security clearance that requires "
    "citizenship (common in defence and federal government). Treat phrases "
    "like \"full working rights\" or \"valid work rights\" as eligible=\"yes\", "
    "because a 485 satisfies them. If genuinely ambiguous, use \"unclear\".\n"
    "\n"
    "Reply with ONLY a JSON object, no prose, no markdown:\n"
    "{\"eligible\": \"yes|no|unclear\", \"reason\": \"<short>\", \"fit\": <0-10>}\n"
    "\n"
    "fit = how well a final-year engineering / software / tech graduate matches "
    "this role. Score graduate, intern, and entry-level roles across tech, "
    "consulting, banking, mining, and engineering firms, not only pure software "
    "roles."
)


# --- Free keyword pre-filter -----------------------------------------------


def _keyword_screen(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    blocked = 0
    for r in rows:
        haystack = (r.get("description", "") + " " + r.get("title", "")).lower()
        hit = next((kw for kw in VISA_DISQUALIFIERS if kw in haystack), None)
        if hit:
            r = {**r, "eligible": "no", "reason": f"keyword match: {hit}", "fit": 0}
            blocked += 1
        else:
            r = {**r, "eligible": "unclear", "reason": "no claude key", "fit": 0}
        out.append(r)
    log.info("keyword screen: blocked %d, kept %d", blocked, len(out) - blocked)
    return [r for r in out if r.get("eligible") != "no"]


# --- Claude screen ---------------------------------------------------------


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_claude_reply(text: str) -> dict[str, Any]:
    cleaned = _JSON_FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {"eligible": "unclear", "reason": "screen failed", "fit": 0}
    if not isinstance(data, dict):
        return {"eligible": "unclear", "reason": "screen failed", "fit": 0}
    eligible = data.get("eligible")
    if eligible not in ("yes", "no", "unclear"):
        eligible = "unclear"
    try:
        fit = int(data.get("fit", 0))
    except (TypeError, ValueError):
        fit = 0
    fit = max(0, min(10, fit))
    return {
        "eligible": eligible,
        "reason": str(data.get("reason", ""))[:200],
        "fit": fit,
    }


def _claude_screen_one(api_key: str, row: dict) -> dict[str, Any]:
    user_text = (
        f"TITLE: {row.get('title', '')}\n"
        f"COMPANY: {row.get('company', '')}\n"
        f"LOCATION: {row.get('location', '')}\n"
        f"DESCRIPTION: {(row.get('description') or '')[:CLAUDE_DESCRIPTION_CHARS]}\n"
    )
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": CLAUDE_MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_text}],
    }
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    try:
        resp = requests.post(_API, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        log.warning("claude call failed: %s", exc)
        return {"eligible": "unclear", "reason": "screen failed", "fit": 0}
    if resp.status_code >= 400:
        log.warning("claude returned HTTP %s: %s", resp.status_code, resp.text[:200])
        return {"eligible": "unclear", "reason": "screen failed", "fit": 0}
    try:
        body = resp.json()
    except ValueError:
        return {"eligible": "unclear", "reason": "screen failed", "fit": 0}
    text_parts = []
    for block in body.get("content", []) or []:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
    return _parse_claude_reply("".join(text_parts))


def _claude_screen(api_key: str, rows: list[dict]) -> list[dict]:
    annotated: list[dict] = []
    for i, r in enumerate(rows, start=1):
        result = _claude_screen_one(api_key, r)
        annotated.append({**r, **result})
        if i % 25 == 0:
            log.info("claude screen progress: %d / %d", i, len(rows))
        time.sleep(CLAUDE_SLEEP_SECONDS)
    kept = [r for r in annotated if r.get("eligible") != "no"]
    kept.sort(key=lambda r: r.get("fit", 0), reverse=True)
    log.info(
        "claude screen: total %d, dropped %d, kept %d",
        len(annotated),
        len(annotated) - len(kept),
        len(kept),
    )
    return kept


# --- Entry point -----------------------------------------------------------


def screen(rows: list[dict]) -> list[dict]:
    """Annotate + filter `rows`. Returns a new list; never mutates input."""
    if not rows:
        return []
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        log.info("screening %d rows via Claude (%s)", len(rows), CLAUDE_MODEL)
        return _claude_screen(api_key, rows)
    log.info("no ANTHROPIC_API_KEY - falling back to keyword pre-filter")
    return _keyword_screen(rows)
