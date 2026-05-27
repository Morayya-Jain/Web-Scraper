"""Optiver - WordPress-backed careers page with an exposed admin-ajax endpoint.

Their public job board calls
    POST https://optiver.com/wp-admin/admin-ajax.php
        action=job_archive_get_posts&posts_per_page=<n>&page=<i>
which returns
    {"success": true, "result": [{"html": "<chunk with title + link + tag>"}, ...]}

We POST that endpoint, parse the per-job HTML chunks with BeautifulSoup,
and synthesise a row per posting. Location is parsed out of the chunk;
Optiver tags each role with a region (Amsterdam / Sydney / Chicago / etc.)
which we map to a normalised location string for the pre-filter.
"""
from __future__ import annotations

from ._common import (
    keep_rows,
    log,
    make_session,
    parse_html,
    passes_prefilter,
    polite_sleep,
    row,
)

_AJAX = "https://optiver.com/wp-admin/admin-ajax.php"
_PAGE_SIZE = 50
_MAX_PAGES = 5


def _post_chunk(session, page: int) -> list[dict] | None:
    try:
        resp = session.post(
            _AJAX,
            data={
                "action": "job_archive_get_posts",
                "posts_per_page": _PAGE_SIZE,
                "page": page,
            },
            headers={"Accept": "application/json, text/html"},
            timeout=20,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("[optiver] POST failed: %s", exc)
        return None
    if resp.status_code >= 400:
        log.warning("[optiver] POST -> HTTP %s", resp.status_code)
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    if not data.get("success"):
        return None
    return data.get("result") or []


def _extract_job(chunk_html: str) -> dict | None:
    soup = parse_html(chunk_html)
    if soup is None:
        return None
    a = soup.find("a", href=True)
    if not a:
        return None
    title = a.get_text(strip=True)
    url = a["href"]
    # The chunk renders the experience tag (Graduate / Intern / Experienced)
    # in the first <p class="text-term"> ; the location appears in the
    # subsequent <p> tags. We extract both as plain text.
    text_terms = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    blob = " | ".join(text_terms)
    # Heuristic: any of the AU cities in the blob means it's an AU role.
    location_hint = ""
    for city in ("Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"):
        if city in blob:
            location_hint = city + ", Australia"
            break
    return {
        "title": title,
        "url": url,
        "location": location_hint or blob.split("|")[-1].strip(),
        "description": blob,
    }


def fetch() -> list[dict]:
    session = make_session()
    # admin-ajax expects a Mozilla-like UA - WordPress firewalls often
    # reject the default `python-requests` UA.
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        ),
    })

    rows: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        chunks = _post_chunk(session, page)
        polite_sleep()
        if not chunks:
            break
        for chunk in chunks:
            html = chunk.get("html") if isinstance(chunk, dict) else None
            if not html:
                continue
            extracted = _extract_job(html)
            if not extracted:
                continue
            candidate = row(
                source="bespoke:optiver",
                title=extracted["title"],
                company="Optiver",
                location=extracted["location"],
                url=extracted["url"],
                description=extracted["description"],
                posted="",
            )
            if candidate and passes_prefilter(candidate):
                rows.append(candidate)
        if len(chunks) < _PAGE_SIZE:
            break

    kept = keep_rows(rows)
    log.info("[optiver] %d kept after AU+junior+tech filter", len(kept))
    return kept
