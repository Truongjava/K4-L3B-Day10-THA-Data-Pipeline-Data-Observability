from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

# Nguong toi thieu de mot record duoc coi la dung duoc. Dat thap hon nhieu so
# voi du lieu that (title ngan nhat 55 ky tu, summary ngan nhat 193 ky tu) nen
# baseline khong bi loai dong nao, nhung van chan duoc du lieu rac.
MIN_TITLE_CHARS = 8
MIN_SUMMARY_CHARS = 40

# Thu tu 5 phan cua `text_for_embedding`.
TEXT_PART_SEPARATOR = "\n"

CLEAN_COLUMNS = (
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "age_days",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "text_for_embedding",
)


def _parse_iso_date(value: str) -> date | None:
    text = normalize_whitespace(str(value or ""))[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _build_text_for_embedding(
    title: str,
    authors_joined: str,
    categories_joined: str,
    published: str,
    summary: str,
) -> str:
    """Ghep 5 phan: Title / Authors / Categories / Published / Abstract."""
    return TEXT_PART_SEPARATOR.join(
        (
            f"Title: {title}",
            f"Authors: {authors_joined}",
            f"Categories: {categories_joined}",
            f"Published: {published}",
            f"Abstract: {summary}",
        )
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    Quy tac:
    - Chuan hoa khoang trang cho moi truong text.
    - Bo record thieu `paper_id`/`title`/`summary`, title/summary qua ngan, hoac
      khong doc duoc ngay xuat ban.
    - Tinh `age_days = (run_date - published).days`.
    - Khur trung lap theo `paper_id` (giu ban moi nhat sau khi sort).
    - Sap xep moi nhat truoc, roi theo `paper_id` cho on dinh giua cac lan chay.
    """
    run_day = run_date.date() if isinstance(run_date, datetime) else run_date

    rows: list[dict] = []
    for record in records:
        paper_id = normalize_whitespace(record.paper_id)
        title = normalize_whitespace(record.title)
        summary = normalize_whitespace(record.summary)
        published_date = _parse_iso_date(record.published)

        if not paper_id or not title or not summary:
            continue
        if len(title) < MIN_TITLE_CHARS or len(summary) < MIN_SUMMARY_CHARS:
            continue
        if published_date is None:
            continue

        authors = [normalize_whitespace(author) for author in record.authors]
        authors = [author for author in authors if author]
        categories = [normalize_whitespace(category) for category in record.categories]
        categories = [category for category in categories if category]

        authors_joined = compact_join(authors)
        categories_joined = compact_join(categories)
        published = published_date.isoformat()
        updated_date = _parse_iso_date(record.updated) or published_date

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": normalize_whitespace(record.primary_category)
                or (categories[0] if categories else ""),
                "published": published,
                "updated": updated_date.isoformat(),
                "abs_url": str(record.abs_url or ""),
                "pdf_url": str(record.pdf_url or ""),
                "comment": str(record.comment or ""),
                "age_days": (run_day - published_date).days,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "text_for_embedding": _build_text_for_embedding(
                    title, authors_joined, categories_joined, published, summary
                ),
            }
        )

    df = pd.DataFrame(rows, columns=list(CLEAN_COLUMNS))
    if df.empty:
        return df

    df = df.sort_values(["published", "paper_id"], ascending=[False, True])
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    return df.reset_index(drop=True)