# Phase 2: Idempotent Repair & Data Observability Report

Generated: 2026-09-26T04:13:55.356221+00:00

## Performance Comparison
| Metric | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| Retrieval hit rate | 1.0000 | 0.8000 | 1.0000 |
| Mean token F1 | 1.0000 | 0.6960 | 1.0000 |
| Judge accuracy | 1.0000 | 0.7000 | 1.0000 |
| Mean judge score | 5 | 3.8000 | 5 |

## Data Quality Comparison
| Check | Corrupted | Repaired |
| --- | --- | --- |
| Quality Gate | FAIL | PASS |
| Freshness | STALE | FRESH |

## Conclusion
The comparison table demonstrates that the pipeline successfully detects silent data corruption (e.g. dropped metrics, failed quality gates) and is capable of an idempotent repair from the raw data source, fully recovering its original performance.
