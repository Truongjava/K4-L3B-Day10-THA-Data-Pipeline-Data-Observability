from __future__ import annotations

from datetime import timedelta
from math import ceil
from pathlib import Path

import pandas as pd

from core.utils import now_utc, write_json

CORRUPTION_FRACTION = 0.2
FRESHNESS_THRESHOLD_DAYS = 180


def _selected_positions(row_count: int, fraction: float = CORRUPTION_FRACTION, offset: int = 0) -> list[int]:
    count = min(row_count, max(1, ceil(row_count * fraction)))
    if count == row_count:
        return list(range(row_count))
    return sorted({(round(index * row_count / count) + offset) % row_count for index in range(count)})


def _rebuild_embedding_text(df: pd.DataFrame) -> None:
    df["text_for_embedding"] = df.apply(
        lambda row: "\n".join(
            (
                f"Title: {row['title']}",
                f"Authors: {row['authors_joined']}",
                f"Categories: {row['categories_joined']}",
                f"Published: {row['published']}",
                f"Abstract: {row['summary']}",
            )
        ),
        axis=1,
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Return a corrupted copy and log the six deterministic fault injections."""
    required_columns = {
        "paper_id",
        "title",
        "summary",
        "published",
        "age_days",
        "authors_joined",
        "categories_joined",
        "text_for_embedding",
    }
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Clean dataframe is missing required columns: {sorted(missing_columns)}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty clean dataframe.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    operations: list[dict[str, object]] = []

    drop_count = min(max(1, ceil(len(corrupted) * CORRUPTION_FRACTION)), max(0, len(corrupted) - 1))
    latest_positions = list(
        pd.to_datetime(corrupted["published"], errors="coerce", utc=True)
        .sort_values(ascending=False, na_position="last", kind="stable")
        .index[:drop_count]
    )
    dropped_ids = corrupted.loc[latest_positions, "paper_id"].astype(str).tolist()
    corrupted = corrupted.drop(index=latest_positions).reset_index(drop=True)
    operations.append(
        {"name": "drop_latest_records", "count": len(dropped_ids), "paper_ids": dropped_ids}
    )

    mutation_specs = (
        ("blank_summary", 0),
        ("inject_noise", 1),
        ("truncate_title", 2),
    )
    for operation_name, offset in mutation_specs:
        positions = _selected_positions(len(corrupted), offset=offset)
        affected_ids = corrupted.loc[positions, "paper_id"].astype(str).tolist()
        if operation_name == "blank_summary":
            corrupted.loc[positions, "summary"] = ""
        elif operation_name == "inject_noise":
            corrupted.loc[positions, "summary"] = corrupted.loc[positions, "summary"].map(
                lambda summary: f"NOISE_###_@@@ " * 12 + str(summary)
            )
        else:
            corrupted.loc[positions, "title"] = "BROKEN"
        operations.append(
            {"name": operation_name, "count": len(affected_ids), "paper_ids": affected_ids}
        )

    stale_count = min(len(corrupted), max(1, ceil(len(corrupted) * 0.4)))
    stale_positions = _selected_positions(len(corrupted), fraction=0.4, offset=3)
    stale_positions = stale_positions[:stale_count]
    stale_date = (now_utc().date() - timedelta(days=FRESHNESS_THRESHOLD_DAYS + 365)).isoformat()
    corrupted.loc[stale_positions, "published"] = stale_date
    corrupted.loc[stale_positions, "age_days"] = FRESHNESS_THRESHOLD_DAYS + 365
    stale_ids = corrupted.loc[stale_positions, "paper_id"].astype(str).tolist()
    operations.append(
        {
            "name": "stale_date",
            "count": len(stale_ids),
            "published_set_to": stale_date,
            "paper_ids": stale_ids,
        }
    )

    _rebuild_embedding_text(corrupted)
    duplicate_positions = _selected_positions(len(corrupted), offset=4)
    duplicate_rows = corrupted.iloc[duplicate_positions].copy()
    duplicate_ids = duplicate_rows["paper_id"].astype(str).tolist()
    corrupted = pd.concat([corrupted, duplicate_rows], ignore_index=True)
    operations.append(
        {"name": "duplicate_rows", "count": len(duplicate_ids), "paper_ids": duplicate_ids}
    )

    log = {
        "generated_at": now_utc().isoformat(),
        "source_rows": int(len(df)),
        "rows_after_drop": int(len(df) - len(dropped_ids)),
        "output_rows": int(len(corrupted)),
        "operations": operations,
    }
    write_json(Path(output_log_path), log)
    return corrupted
