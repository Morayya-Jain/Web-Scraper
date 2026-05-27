"""Bespoke direct-scrape collectors (Layer C).

These are one-off scrapers for companies whose careers pages don't
expose a standard ATS feed. Each module is a self-contained
`fetch() -> list[dict]` that returns the common schema, just like
Layer A/B sources. main.py wraps each call in try/except so a broken
scraper never crashes the run.

To add a new bespoke scraper, see README ("Adding a bespoke scraper").
"""
