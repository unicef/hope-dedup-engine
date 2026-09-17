from __future__ import annotations

import json
from typing import Any

from django.utils.html import format_html, format_html_join

from hope_dedup_engine.apps.api.deduplication.config import DeduplicationSetConfig
from hope_dedup_engine.apps.faces.services.quality import get_active_thresholds

EMPTY = "-"


def pretty_json(value: Any) -> str:
    """Return indented JSON wrapped in a ``<pre>`` tag."""
    if value is None:
        return EMPTY
    text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    return format_html('<pre class="hde-json">{}</pre>', text)


def _log_entry_summary(entry: dict[str, Any]) -> str:
    parts = [entry.get("timestamp"), entry.get("action"), entry.get("state")]
    summary = " · ".join(str(part) for part in parts if part)
    if "error" in entry:
        summary = f"{summary} · error" if summary else "error"
    return summary or "entry"


def _log_entry_args(entry: Any, *, opened: bool) -> tuple[str, str, str, str]:
    if isinstance(entry, dict):
        summary = _log_entry_summary(entry)
        css = " hde-json-log-entry-error" if "error" in entry else ""
    else:
        summary = str(entry)
        css = ""
    return (
        css,
        " open" if opened else "",
        summary,
        json.dumps(entry, indent=2, ensure_ascii=False, default=str),
    )


def format_log(entries: Any) -> str:
    """Render a log JSON array as collapsible entries, newest first."""
    if not entries:
        return EMPTY
    if not isinstance(entries, list):
        return pretty_json(entries)

    return format_html(
        '<div class="hde-json-log">{}</div>',
        format_html_join(
            "",
            '<details class="hde-json-log-entry{}"{}><summary>{}</summary><pre class="hde-json">{}</pre></details>',
            (_log_entry_args(entry, opened=index == 0) for index, entry in enumerate(reversed(entries))),
        ),
    )


def _format_number(value: float) -> str:
    return f"{value:.2f}"


def format_quality_scores(
    scores: dict[str, Any] | None,
    thresholds: dict[str, float] | None = None,
) -> str:
    """Render image quality scores as a table, highlighting metrics below threshold."""
    if not scores:
        return "N/A"

    thresholds = thresholds or {}
    sorted_items = sorted(scores.items(), key=lambda item: item[1] if item[1] is not None else -1)
    rows = []
    for metric, score in sorted_items:
        threshold = thresholds.get(metric)
        failed = threshold is not None and (score is None or score < threshold / 100)
        if failed:
            status = "Failed"
        elif threshold is not None:
            status = "Passed"
        else:
            status = EMPTY
        rows.append(
            (
                "hde-quality-score-fail" if failed else "",
                metric,
                EMPTY if score is None else _format_number(score),
                EMPTY if threshold is None else _format_number(threshold / 100),
                status,
            )
        )

    return format_html(
        '<table class="hde-quality-scores">'
        "<thead><tr><th>Metric</th><th>Score</th><th>Threshold</th><th>Status</th></tr></thead>"
        "<tbody>{}</tbody>"
        "</table>",
        format_html_join(
            "",
            '<tr class="{}"><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>',
            rows,
        ),
    )


def quality_thresholds_for_encoding(encoding: Any) -> dict[str, float]:
    """Return active OFIQ thresholds (0-100) for the encoding's group, if available."""
    ds = getattr(encoding, "deduplication_set", None)
    group = getattr(ds, "group", None) if ds is not None else None
    settings = getattr(group, "settings", None) if group is not None else None
    if ds is None or group is None or (settings is not None and not isinstance(settings, dict)):
        return {}
    return get_active_thresholds(DeduplicationSetConfig.from_deduplication_set(ds))
