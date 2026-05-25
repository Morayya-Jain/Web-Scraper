"""Write the daily CSV + Markdown shortlist."""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

CSV_COLUMNS = [
    "fit",
    "eligible",
    "title",
    "company",
    "location",
    "source",
    "posted",
    "reason",
    "url",
]


def _timestamp() -> str:
    # UTC so filenames remain consistent across local dev and CI runners.
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")


def _row_for_csv(r: dict) -> dict:
    return {
        "fit": r.get("fit", ""),
        "eligible": r.get("eligible", ""),
        "title": r.get("title", ""),
        "company": r.get("company", ""),
        "location": r.get("location", ""),
        "source": r.get("source", ""),
        "posted": r.get("posted", ""),
        "reason": r.get("reason", ""),
        "url": r.get("url", ""),
    }


def write_csv(rows: list[dict], output_dir: Path, ts: str) -> Path:
    path = output_dir / f"jobs_{ts}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(_row_for_csv(r))
    log.info("wrote %s (%d rows)", path, len(rows))
    return path


def _md_tag(r: dict, screening_active: bool) -> str:
    parts: list[str] = []
    if r.get("is_new"):
        parts.append("[new]")
    if screening_active:
        eligible = r.get("eligible", "")
        fit = r.get("fit", "")
        parts.append(f"fit {fit}, {eligible}")
    else:
        parts.append(r.get("source", ""))
    return " | ".join(p for p in parts if p)


def write_markdown(rows: list[dict], output_dir: Path, ts: str) -> Path:
    path = output_dir / f"jobs_{ts}.md"
    # Screening runs always set `eligible` on every row (keyword-mode sets
    # "unclear", Claude-mode sets one of yes/no/unclear). If even one row
    # is missing the field we know screening didn't run (e.g. empty pipeline).
    screening_active = bool(rows) and all("eligible" in r for r in rows)
    new_count = sum(1 for r in rows if r.get("is_new"))

    lines: list[str] = []
    lines.append(f"# Australian Graduate Job Finder - {ts}")
    lines.append("")
    lines.append(
        f"{len(rows)} roles after dedupe and screening "
        f"({new_count} new since last run)."
    )
    lines.append("")
    if not rows:
        lines.append("_No roles matched today. Check the logs for per-source counts._")
        lines.append("")
    for r in rows:
        title = r.get("title", "").strip() or "(untitled)"
        company = r.get("company", "").strip() or "(unknown)"
        location = r.get("location", "").strip()
        url = r.get("url", "").strip()
        tag = _md_tag(r, screening_active)
        reason = r.get("reason", "").strip()

        header = f"- **[{title}]({url})** - {company}"
        meta_bits: list[str] = []
        if location:
            meta_bits.append(location)
        if tag:
            meta_bits.append(tag)
        if meta_bits:
            header += "  \n  _" + " - ".join(meta_bits) + "_"
        if reason and screening_active:
            header += f"  \n  _{reason}_"
        lines.append(header)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("wrote %s (%d roles)", path, len(rows))
    return path


def write_outputs(rows: list[dict], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = _timestamp()
    csv_path = write_csv(rows, output_dir, ts)
    md_path = write_markdown(rows, output_dir, ts)
    return csv_path, md_path
