from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import QUESTION_COUNT, QUESTION_TYPES, build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def _load_or_build_test_set(settings, clean_df) -> list[dict]:
    test_set_path = settings.paths.eval_testset
    paper_ids = set(clean_df["paper_id"].astype(str))
    if settings.refresh_source or settings.refresh_test_set or not test_set_path.exists():
        return build_test_set(clean_df, test_set_path)

    try:
        test_set = read_json(test_set_path)
    except (OSError, ValueError):
        test_set = None

    required_keys = {"id", "question_type", "question", "ground_truth", "ground_truth_doc_ids"}
    compatible = False
    if isinstance(test_set, list) and len(test_set) == QUESTION_COUNT:
        try:
            compatible = all(
                isinstance(item, dict)
                and required_keys.issubset(item)
                and item["question_type"] in QUESTION_TYPES
                and item["ground_truth_doc_ids"]
                and set(item["ground_truth_doc_ids"]).issubset(paper_ids)
                for item in test_set
            ) and set(item["question_type"] for item in test_set) == set(QUESTION_TYPES)
        except (KeyError, TypeError):
            compatible = False

    if compatible:
        return test_set
    return build_test_set(clean_df, test_set_path)


def main() -> None:
    """Build the clean baseline, quality artifacts, vector index, and report."""
    settings = load_settings()
    records = fetch_source_records(settings)
    clean_df = build_clean_dataframe(records, now_utc())
    if clean_df.empty:
        raise RuntimeError("Cleaning produced no usable paper records.")

    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))

    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    if not quality["success"]:
        failed_checks = ", ".join(quality.get("failed_checks", [])) or "unknown checks"
        raise RuntimeError(f"Baseline data quality gate failed: {failed_checks}")

    index = LocalEmbeddingIndex.build(
        clean_df,
        settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    _load_or_build_test_set(settings, clean_df)
    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    source_summary = {
        "api": settings.source_api,
        "source_mode": (
            "Crossref REST API"
            if settings.refresh_source or not settings.paths.raw_records_json.exists()
            else "Local raw snapshot"
        ),
        "query": settings.source_query,
        "refresh_requested": settings.refresh_source,
        "llm_provider": settings.llm_provider,
        "raw_records": len(records),
        "clean_records": len(clean_df),
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary,
        evaluation.summary,
        quality,
        freshness,
    )

    print(f"Baseline ready: {len(clean_df)} clean records, {evaluation.summary['samples']} evaluation questions")
    print(f"Quality gate: {'PASS' if quality['success'] else 'FAIL'}")
    print(f"Freshness: {'FRESH' if freshness['is_fresh'] else 'STALE'}")
    print(f"Retrieval hit rate: {evaluation.summary['retrieval_hit_rate']:.3f}")
    print(f"Artifacts: {settings.paths.baseline_report}")
