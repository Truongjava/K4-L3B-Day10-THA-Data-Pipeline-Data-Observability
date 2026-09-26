from __future__ import annotations

import pandas as pd

from core.config import load_settings
from core.utils import read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.corruption import corrupt_clean_dataframe
from observability.quality import build_freshness_report, run_data_quality_checks
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Run CP4 corruption and evaluation; repair/comparison are completed in CP5."""
    settings = load_settings()
    required_paths = (
        settings.paths.clean_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
    )
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        raise FileNotFoundError(
            "CP4 requires completed CP1-CP3 artifacts: " + ", ".join(missing_paths)
        )

    clean_df = pd.read_json(settings.paths.clean_json)
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))

    index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    evaluation = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    freshness_path = settings.paths.quality_dir / "corrupted_freshness_report.json"
    freshness = build_freshness_report(corrupted_df, settings, freshness_path)

    print("CP4 results (baseline vs corrupted):")
    print(
        "Retrieval hit rate: "
        f"{baseline_metrics.get('retrieval_hit_rate', 0.0):.3f} -> "
        f"{evaluation.summary['retrieval_hit_rate']:.3f}"
    )
    print(
        f"Mean token F1: {baseline_metrics.get('mean_token_f1', 0.0):.3f} -> "
        f"{evaluation.summary['mean_token_f1']:.3f}"
    )
    print(f"Quality gate: {'PASS' if quality['success'] else 'FAIL (expected for injected corruption)'}")
    print(f"Freshness: {'FRESH' if freshness['is_fresh'] else 'STALE (expected for injected stale dates)'}")
    print(f"Corruption log: {settings.paths.corruption_log}")
    print(f"Corrupted metrics: {settings.paths.corrupted_metrics}")
    print(f"Corrupted quality: {settings.paths.corrupted_quality_report}")
    print(f"Corrupted freshness: {freshness_path}")
