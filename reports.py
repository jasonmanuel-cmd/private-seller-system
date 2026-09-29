"""Deterministic, spreadsheet-safe operational intelligence reports."""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Iterable

UNKNOWN = "UNKNOWN"

REPORT_FIELDS = [
    "property_id", "address", "city", "score", "confidence_grade", "decision",
    "seller_pressure_velocity", "seller_capitulation_index", "hidden_optionality_score",
    "renovation_spread", "risks", "conflicts", "triggers", "limitations",
    "rejection_reasons", "next_action",
]

EVENT_FIELDS = ["property_id", "event_type", "observed_at", "old_value", "new_value", "evidence_ids"]
DEEP_FIELDS = REPORT_FIELDS + ["score_breakdown", "micro_market", "counterfactuals", "evidence_summary", "change_timeline"]


def csv_safe(value: Any) -> str:
    if value is None:
        return UNKNOWN
    if isinstance(value, (dict, list, tuple, set)):
        if isinstance(value, set):
            value = sorted(value)
        value = json.dumps(value, sort_keys=True, ensure_ascii=False)
    text = str(value)
    if text == "":
        return UNKNOWN
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def _atomic_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=path.parent) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_safe(row.get(field, UNKNOWN)) for field in fields})
        temp_name = handle.name
    os.replace(temp_name, path)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=path.parent) as handle:
        handle.write(text)
        temp_name = handle.name
    os.replace(temp_name, path)


def _score(row: dict[str, Any]) -> float:
    value = row.get("score")
    return float(value) if isinstance(value, (int, float)) else -1.0


def generate_reports(
    analyses: list[dict[str, Any]],
    events: list[dict[str, Any]],
    report_dir: str | os.PathLike[str],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Create latest and timestamped report sets without manufacturing missing rows."""
    output = Path(report_dir)
    run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ranked = sorted(analyses, key=lambda row: (-_score(row), str(row.get("property_id", ""))))
    top = [row for row in ranked if row.get("decision") == "top"][:10]
    deep = top[:3]
    watch = [row for row in ranked if row.get("decision") == "watchlist"]
    rejected = [row for row in ranked if row.get("decision") == "rejected"]
    buckets = {
        "top-10.csv": top,
        "top-3-deep-dive.csv": deep,
        "watchlist.csv": watch,
        "rejected.csv": rejected,
    }
    archive = output / "runs" / run_id
    for name, rows in buckets.items():
        fields = DEEP_FIELDS if name == "top-3-deep-dive.csv" else REPORT_FIELDS
        expanded = [_deep_row(row) for row in rows] if name == "top-3-deep-dive.csv" else rows
        _atomic_csv(output / name, fields, expanded)
        _atomic_csv(archive / name, fields, expanded)
    sorted_events = sorted(events, key=lambda row: (str(row.get("observed_at", "")), str(row.get("property_id", ""))))
    _atomic_csv(output / "change-events.csv", EVENT_FIELDS, sorted_events)
    _atomic_csv(archive / "change-events.csv", EVENT_FIELDS, sorted_events)
    markdown = _render_markdown(run_id, top, deep, watch, rejected, sorted_events)
    _atomic_text(output / "intelligence-report.md", markdown)
    _atomic_text(archive / "intelligence-report.md", markdown)
    return {
        "run_id": run_id,
        "report_dir": str(output),
        "counts": {"top10": len(top), "top3": len(deep), "watchlist": len(watch),
                   "rejected": len(rejected), "events": len(sorted_events)},
    }


def _render_markdown(run_id: str, top: list[dict[str, Any]], deep: list[dict[str, Any]],
                     watch: list[dict[str, Any]], rejected: list[dict[str, Any]],
                     events: list[dict[str, Any]]) -> str:
    lines = ["# Kern Property Intelligence Report", "", f"Run: `{run_id}`", "",
             "> UNKNOWN means the system does not have sufficient verified evidence. It is not zero.", "",
             f"- Top opportunities: {len(top)}", f"- Deep dives: {len(deep)}",
             f"- Watchlist: {len(watch)}", f"- Rejected: {len(rejected)}",
             f"- Change events detected this run: {len(events)}", ""]
    for title, rows in (("Top 3 deep dives", deep), ("Watchlist", watch), ("Rejected", rejected)):
        lines.extend([f"## {title}", ""])
        if not rows:
            lines.extend(["No properties met this bucket's evidence requirements.", ""])
            continue
        for row in rows:
            address = row.get("address") or UNKNOWN
            lines.extend([f"### {address}", "", f"Score: {csv_safe(row.get('score'))}/100 | Confidence: {csv_safe(row.get('confidence_grade'))}",
                          f"Next verification: {csv_safe(row.get('next_action'))}", ""])
            if title == "Top 3 deep dives":
                analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
                lines.extend([
                    f"- Score components: {csv_safe(analysis.get('score_breakdown'))}",
                    f"- Micro-market: {csv_safe(analysis.get('micro_market'))}",
                    f"- Seller pressure: {csv_safe(row.get('seller_pressure_velocity'))}",
                    f"- Counterfactuals: {csv_safe(analysis.get('counterfactuals'))}",
                    f"- Conflicts: {csv_safe(row.get('conflicts'))}",
                    f"- Limitations/assumptions: {csv_safe(row.get('limitations'))}", ""])
    return "\n".join(lines) + "\n"


def _deep_row(row: dict[str, Any]) -> dict[str, Any]:
    analysis = row.get("analysis") if isinstance(row.get("analysis"), dict) else {}
    return dict(row,
                score_breakdown=analysis.get("score_breakdown", UNKNOWN),
                micro_market=analysis.get("micro_market", UNKNOWN),
                counterfactuals=analysis.get("counterfactuals", UNKNOWN),
                evidence_summary=analysis.get("confidence", UNKNOWN),
                change_timeline=analysis.get("change_events", UNKNOWN))
