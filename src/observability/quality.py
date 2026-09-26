from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import now_utc, read_json, write_json
from ingestion.cleaning import MIN_SUMMARY_CHARS, MIN_TITLE_CHARS

# Freshness SLA: corpus bi coi la khong con tuoi neu ty le bai bao qua han
# (`age_days > freshness_threshold_days`) vuot qua nguong nay.
STALE_RATIO_LIMIT = 0.25

MAX_TITLE_CHARS = 400
MAX_SUMMARY_CHARS = 5000


def _json_safe(value: Any) -> Any:
    """Chuan hoa ket qua GX thanh kieu ghi duoc ra JSON chuan.

    Bao ve hop dong JSON cua report o ranh gioi serialize: `NaN`/`inf` bi quy ve
    `None` vi `json.dumps` xuat chung thanh `NaN`/`Infinity` — khong phai JSON
    hop le — va moi gia tri khong phai kieu built-in deu duoc chuyen thanh chuoi.
    """
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value) if math.isfinite(value) else None
    return str(value)


def _report_path(settings: Settings, report_name: str) -> Path:
    known_paths = {
        "baseline": settings.paths.baseline_quality_report,
        "corrupted": settings.paths.corrupted_quality_report,
    }
    return known_paths.get(
        report_name, settings.paths.quality_dir / f"{report_name}_quality_report.json"
    )


def _expected_row_count(settings: Settings) -> int:
    """So dong corpus tin cay, lay tu raw snapshot da luu.

    Quality Gate doi chieu so dong hien tai voi nguon raw thay vi hard-code,
    nho vay bat duoc kich ban drop record ma khong phu thuoc so bai API tra ve.
    """
    try:
        raw_records = read_json(settings.paths.raw_records_json)
    except (OSError, ValueError):
        return settings.max_results
    return len(raw_records) if isinstance(raw_records, list) else settings.max_results


def _build_expectations(settings: Settings) -> list[Any]:
    """4 nhom expectation thiet yeu cua GX 1.x + nguong freshness."""
    expected_rows = _expected_row_count(settings)
    return [
        gx.expectations.ExpectTableRowCountToBeBetween(
            min_value=expected_rows,
            max_value=expected_rows * 2,
        ),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"),
        gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="title"),
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="title",
            min_value=MIN_TITLE_CHARS,
            max_value=MAX_TITLE_CHARS,
        ),
        gx.expectations.ExpectColumnValuesToNotBeNull(column="summary"),
        gx.expectations.ExpectColumnValueLengthsToBeBetween(
            column="summary",
            min_value=MIN_SUMMARY_CHARS,
            max_value=MAX_SUMMARY_CHARS,
        ),
    ]


def _summarize_check(expectation: Any, result: Any) -> dict[str, Any]:
    details = getattr(result, "result", None)
    details = details if isinstance(details, dict) else {}
    return {
        "expectation": type(expectation).__name__,
        "column": getattr(expectation, "column", None),
        "success": bool(getattr(result, "success", False)),
        "observed_value": _json_safe(details.get("observed_value")),
        "unexpected_count": _json_safe(details.get("unexpected_count", 0)),
        "unexpected_percent": _json_safe(details.get("unexpected_percent", 0.0)),
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay bo Data Quality Gate theo Great Expectations 1.x va ghi report JSON.

    Tra ve payload co `success` = True khi tat ca expectation deu pass.
    """
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_definition.get_batch(batch_parameters={"dataframe": df})

    expectations = _build_expectations(settings)
    checks = [_summarize_check(expectation, batch.validate(expectation)) for expectation in expectations]
    failed_checks = [check["expectation"] for check in checks if not check["success"]]

    payload: dict[str, Any] = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "gx_version": gx.__version__,
        "row_count": int(len(df)),
        "expected_row_count": _expected_row_count(settings),
        "success": not failed_checks,
        "failed_checks": failed_checks,
        "checks": checks,
    }

    write_json(_report_path(settings, report_name), payload)
    # Luu them vet kiem dinh GX de doi chieu khi bao ve tren bang.
    write_json(settings.paths.gx_dir / f"{report_name}_gx_result.json", payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report theo nguong `freshness_threshold_days`."""
    threshold = settings.freshness_threshold_days
    total_rows = int(len(df))

    published = pd.to_datetime(df["published"], errors="coerce")
    age_days = pd.to_numeric(df["age_days"], errors="coerce").fillna(0)
    stale_rows = int((age_days > threshold).sum())
    stale_ratio = (stale_rows / total_rows) if total_rows else 0.0

    latest = published.max()
    oldest = published.min()
    payload: dict[str, Any] = {
        "generated_at": now_utc().isoformat(),
        "threshold_days": threshold,
        "stale_ratio_limit": STALE_RATIO_LIMIT,
        "latest_published": latest.date().isoformat() if pd.notna(latest) else None,
        "oldest_published": oldest.date().isoformat() if pd.notna(oldest) else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "is_fresh": stale_ratio <= STALE_RATIO_LIMIT,
    }

    write_json(report_path, payload)
    return payload