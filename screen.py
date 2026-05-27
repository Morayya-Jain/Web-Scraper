"""Claude Haiku 3-axis screening - mandatory in v2.

Three scores per role:
  role_fit  (0-10): how clearly tech / AI / data / quant. <6 = not tech.
  level_fit (0-10): how grad-friendly. <6 = needs years of experience.
  visa_fit  (yes / no / unclear): 485-visa compatibility.

Hard cut after scoring:
  drop if role_fit < MIN_ROLE_FIT
       or level_fit < MIN_LEVEL_FIT
       or visa_fit == "no"
  sort surviving rows by (role_fit * level_fit) desc.

If ANTHROPIC_API_KEY is missing the run fails fast - the user explicitly
said they have the key and want strict screening, so silently falling
back to a keyword pre-filter (v1 behaviour) would hide bugs.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from typing import Any

import requests

from config import (
    CLAUDE_DESCRIPTION_CHARS,
    CLAUDE_MAX_TOKENS,
    CLAUDE_MODEL,
    CLAUDE_SLEEP_SECONDS,
    MAX_CLAUDE_CALLS,
    MIN_LEVEL_FIT,
    MIN_ROLE_FIT,
    REQUEST_TIMEOUT,
)

log = logging.getLogger(__name__)

_API = "https://api.anthropic.com/v1/messages"

# Pricing (USD per million tokens) as of 2026 for claude-haiku-4-5.
# Used only for the per-run cost estimate logged at the end. Numbers are
# conservative; actual billing comes from your Anthropic dashboard.
_INPUT_USD_PER_MTOK = 1.0
_OUTPUT_USD_PER_MTOK = 5.0


SYSTEM_PROMPT = (
    "You screen Australian graduate-tech job ads for an international student "
    "who will hold a Temporary Graduate visa (subclass 485) after graduating "
    "in December 2026 or later. The 485 grants FULL UNRESTRICTED work rights "
    "for 2 to 4 years and needs NO sponsorship. They can apply to almost "
    "anything that doesn't require AU/NZ citizenship or permanent residency.\n"
    "\n"
    "Score each ad on three axes and return ONE JSON object, no prose, no "
    "markdown fences:\n"
    "\n"
    "{\n"
    "  \"role_fit\": <0-10>,\n"
    "  \"level_fit\": <0-10>,\n"
    "  \"visa_fit\": \"yes|no|unclear\",\n"
    "  \"reason\": \"<one short sentence>\"\n"
    "}\n"
    "\n"
    "role_fit: how clearly the role is technology / software / AI / machine "
    "learning / data science / data engineering / quantitative development / "
    "cyber-security. <=5 means clearly NOT tech (civil eng, mechanical eng, "
    "accounting, legal, marketing, sales, HR, recruitment, customer service, "
    "trading non-quant, policy, nursing, teaching). 10 = explicit software / "
    "data / ML / quant role.\n"
    "\n"
    "level_fit: how grad-friendly the role is. The candidate has NO industry "
    "experience and graduates in late 2026. <=5 means the ad requires years "
    "of experience (senior, lead, principal, '3+ years', '5+ years', "
    "'experienced engineer', etc.). 10 = explicit graduate program, intern, "
    "trainee, cadetship, or 'no experience required'.\n"
    "\n"
    "visa_fit: be STRICT. Mark \"no\" if the ad clearly requires Australian "
    "or NZ citizenship, permanent residency, or a security clearance that "
    "requires citizenship. Examples that map to \"no\":\n"
    "  - \"must be an Australian citizen\"\n"
    "  - \"PR required\" / \"permanent residency required\"\n"
    "  - \"must hold Australian or New Zealand citizenship\"\n"
    "  - \"baseline / NV1 / NV2 / positive vetting clearance required\"\n"
    "  - \"no visa sponsorship available\" (a 485 doesn't need sponsorship "
    "but this phrasing usually means PR-only in practice)\n"
    "Treat \"valid working rights\" / \"full working rights\" as \"yes\" "
    "because a 485 satisfies them. If the ad says nothing about visa or "
    "citizenship, return \"unclear\".\n"
    "\n"
    "reason: one short sentence explaining the lowest-scoring axis."
)


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _parse_claude_reply(text: str) -> dict[str, Any]:
    cleaned = _JSON_FENCE_RE.sub("", text).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return _default_failure("malformed JSON")
    if not isinstance(data, dict):
        return _default_failure("non-object JSON")
    return _normalise(data)


def _default_failure(reason: str) -> dict[str, Any]:
    return {
        "role_fit": 0,
        "level_fit": 0,
        "visa_fit": "unclear",
        "reason": f"screen failed: {reason}",
    }


def _clip(value: Any, lo: int, hi: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 0
    return max(lo, min(hi, n))


def _normalise(data: dict[str, Any]) -> dict[str, Any]:
    visa = data.get("visa_fit")
    if visa not in ("yes", "no", "unclear"):
        visa = "unclear"
    return {
        "role_fit": _clip(data.get("role_fit"), 0, 10),
        "level_fit": _clip(data.get("level_fit"), 0, 10),
        "visa_fit": visa,
        "reason": str(data.get("reason", ""))[:200],
    }


def _claude_screen_one(
    api_key: str,
    row: dict,
    usage_acc: dict[str, int],
) -> dict[str, Any]:
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
        resp = requests.post(
            _API, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
        )
    except requests.RequestException as exc:
        log.warning("claude call failed: %s", exc)
        return _default_failure(f"network: {exc}")
    if resp.status_code >= 400:
        log.warning("claude HTTP %s: %s", resp.status_code, resp.text[:200])
        return _default_failure(f"http {resp.status_code}")
    try:
        body = resp.json()
    except ValueError:
        return _default_failure("non-JSON response")

    usage = body.get("usage") or {}
    usage_acc["input_tokens"] += int(usage.get("input_tokens") or 0)
    usage_acc["output_tokens"] += int(usage.get("output_tokens") or 0)

    text_parts = [
        b.get("text", "")
        for b in body.get("content", []) or []
        if isinstance(b, dict) and b.get("type") == "text"
    ]
    return _parse_claude_reply("".join(text_parts))


def _ensure_key() -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        log.error(
            "ANTHROPIC_API_KEY not set. v2 requires Claude screening; "
            "no fallback is provided. Aborting."
        )
        sys.exit(2)
    return api_key


def screen(rows: list[dict]) -> list[dict]:
    """Annotate + filter rows. Returns survivors sorted by role_fit*level_fit."""
    if not rows:
        return []

    api_key = _ensure_key()
    log.info("screening %d rows via Claude (%s)", len(rows), CLAUDE_MODEL)

    usage_acc = {"input_tokens": 0, "output_tokens": 0}
    annotated: list[dict] = []
    for i, r in enumerate(rows, start=1):
        if i > MAX_CLAUDE_CALLS:
            log.warning(
                "MAX_CLAUDE_CALLS (%d) hit; remaining %d rows skipped",
                MAX_CLAUDE_CALLS,
                len(rows) - MAX_CLAUDE_CALLS,
            )
            annotated.append({
                **r,
                "role_fit": 0,
                "level_fit": 0,
                "visa_fit": "unclear",
                "reason": "skipped: call cap reached",
            })
            continue
        result = _claude_screen_one(api_key, r, usage_acc)
        annotated.append({**r, **result})
        if i % 25 == 0:
            log.info("claude screen progress: %d / %d", i, len(rows))
        time.sleep(CLAUDE_SLEEP_SECONDS)

    # Hard cut
    kept = [
        r
        for r in annotated
        if r["role_fit"] >= MIN_ROLE_FIT
        and r["level_fit"] >= MIN_LEVEL_FIT
        and r["visa_fit"] != "no"
    ]
    kept.sort(
        key=lambda r: (r.get("role_fit", 0) * r.get("level_fit", 0)),
        reverse=True,
    )

    # Cost estimate (rough)
    cost = (
        usage_acc["input_tokens"] / 1_000_000 * _INPUT_USD_PER_MTOK
        + usage_acc["output_tokens"] / 1_000_000 * _OUTPUT_USD_PER_MTOK
    )
    log.info(
        "claude usage: input=%d output=%d  est. cost ~$%.4f USD",
        usage_acc["input_tokens"],
        usage_acc["output_tokens"],
        cost,
    )
    log.info(
        "screen: total %d, dropped %d (role/level/visa cuts), kept %d",
        len(annotated),
        len(annotated) - len(kept),
        len(kept),
    )
    return kept
