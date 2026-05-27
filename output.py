"""Write the run's CSV + Markdown shortlist.

v2 schema additions:
  role_fit  (0-10)
  level_fit (0-10)
  visa_fit  (yes|no|unclear)
The legacy `fit` and `eligible` columns are gone.
"""
from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

CSV_COLUMNS = [
    "role_fit",
    "level_fit",
    "visa_fit",
    "title",
    "company",
    "location",
    "source",
    "posted",
    "reason",
    "url",
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")


def _row_for_csv(r: dict) -> dict:
    return {col: r.get(col, "") for col in CSV_COLUMNS}


def write_csv(rows: list[dict], output_dir: Path, ts: str) -> Path:
    path = output_dir / f"jobs_{ts}.csv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(_row_for_csv(r))
    log.info("wrote %s (%d rows)", path, len(rows))
    return path


def _md_tag(r: dict) -> str:
    role = r.get("role_fit")
    level = r.get("level_fit")
    visa = r.get("visa_fit")
    if role is not None and level is not None:
        return f"role {role}/10 - level {level}/10 - visa {visa}"
    if "source" in r:
        return r.get("source", "")
    return ""


def write_markdown(rows: list[dict], output_dir: Path, ts: str) -> Path:
    path = output_dir / f"jobs_{ts}.md"

    lines: list[str] = []
    lines.append(f"# Australian Graduate Tech Job Finder - {ts} UTC")
    lines.append("")
    lines.append(
        f"{len(rows)} roles new since the last run. Roles you've already "
        f"seen are tracked in `seen.json` and excluded from this list."
    )
    lines.append("")
    if not rows:
        lines.append(
            "_No new roles. Either nothing fresh has been posted, or every "
            "match has been shown in a previous run. To re-surface old roles, "
            "delete or edit `seen.json` and re-run._"
        )
        lines.append("")
    for r in rows:
        title = r.get("title", "").strip() or "(untitled)"
        company = r.get("company", "").strip() or "(unknown)"
        location = r.get("location", "").strip()
        url = r.get("url", "").strip()
        tag = _md_tag(r)
        reason = r.get("reason", "").strip()

        header = f"- **[{title}]({url})** - {company}"
        meta_bits: list[str] = []
        if location:
            meta_bits.append(location)
        if tag:
            meta_bits.append(tag)
        if meta_bits:
            header += "  \n  _" + " - ".join(meta_bits) + "_"
        if reason:
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
