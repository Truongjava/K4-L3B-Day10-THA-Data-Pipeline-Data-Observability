from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text


def _metric_value(metrics: dict[str, Any], key: str) -> str:
    value = metrics.get(key)
    if isinstance(value, (int, float)):
        return f"{value:.4f}" if isinstance(value, float) else str(value)
    return "N/A" if value is None else str(value)


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write a baseline report using only artifacts produced by the pipeline."""
    failed_checks = quality.get("failed_checks") or []
    ragas = metrics.get("ragas") or {}
    ragas_status = ragas.get("skipped") or ragas.get("error") or "completed"
    lines = [
        "# Phase 1: Baseline Report",
        "",
        f"Generated: {now_utc().isoformat()}",
        "",
        "## Source",
        f"- Input source: {source_summary.get('source_mode', 'N/A')}",
        f"- Configured API: {source_summary.get('api', 'N/A')}",
        f"- Query: {source_summary.get('query', 'N/A')}",
        f"- Refresh requested: {source_summary.get('refresh_requested', False)}",
        f"- Raw records loaded: {source_summary.get('raw_records', 'N/A')}",
        f"- Clean records: {source_summary.get('clean_records', 'N/A')}",
        "",
        "## Evaluation",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Samples | {_metric_value(metrics, 'samples')} |",
        f"| Retrieval hit rate | {_metric_value(metrics, 'retrieval_hit_rate')} |",
        f"| Mean token F1 | {_metric_value(metrics, 'mean_token_f1')} |",
        f"| Judge accuracy | {_metric_value(metrics, 'judge_accuracy')} |",
        f"| Mean judge score | {_metric_value(metrics, 'mean_judge_score')} |",
        f"| LLM provider | {source_summary.get('llm_provider', 'N/A')} |",
        f"| Ragas | {ragas_status} |",
        "",
        "## Data Quality",
        f"- Great Expectations version: {quality.get('gx_version', 'N/A')}",
        f"- Status: {'PASS' if quality.get('success') else 'FAIL'}",
        f"- Rows checked: {quality.get('row_count', 'N/A')}",
        f"- Failed checks: {', '.join(failed_checks) if failed_checks else 'None'}",
        "",
        "## Freshness",
        f"- Status: {'FRESH' if freshness.get('is_fresh') else 'STALE'}",
        f"- Threshold: {freshness.get('threshold_days', 'N/A')} days",
        f"- Stale rows: {freshness.get('stale_rows', 'N/A')} / {freshness.get('total_rows', 'N/A')}",
        f"- Stale ratio: {_metric_value(freshness, 'stale_ratio')}",
        f"- Latest publication: {freshness.get('latest_published', 'N/A')}",
        f"- Oldest publication: {freshness.get('oldest_published', 'N/A')}",
        "",
    ]
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """TODO(student): viet markdown report so sanh baseline/corrupted/repaired."""
    raise NotImplementedError("Student task: implement corruption comparison report.")
