"""Minimal HTML -> plain-text stripper using only the stdlib.

Greenhouse, Ashby, and Workday all return job descriptions as HTML (often
escaped). bs4 would be cleaner but is an extra dep; html.parser is in the
stdlib and good enough for our purposes (we only need readable text for
the user's eyes and for Claude screening).
"""
from __future__ import annotations

import html
import re
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag in ("br", "p", "li", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in ("p", "li", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6"):
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


_WHITESPACE_RE = re.compile(r"[ \t]+")
_NEWLINE_RE = re.compile(r"\n{3,}")


def strip_html(value: str | None) -> str:
    """Return plain text from an HTML or already-escaped string.

    Safe to call on plain text - it just normalises whitespace.
    """
    if not value:
        return ""
    # Some ATS APIs double-encode (e.g. "&lt;p&gt;Hello&lt;/p&gt;"). One
    # unescape pass turns that back into real tags so the parser can see them.
    unescaped = html.unescape(value)
    parser = _TextExtractor()
    try:
        parser.feed(unescaped)
        parser.close()
    except Exception:
        # html.parser can raise on truly malformed input; fall back to a
        # naive tag-strip rather than crashing the whole pipeline.
        text = re.sub(r"<[^>]+>", " ", unescaped)
    else:
        text = parser.text()
    text = _WHITESPACE_RE.sub(" ", text)
    text = _NEWLINE_RE.sub("\n\n", text)
    return text.strip()
