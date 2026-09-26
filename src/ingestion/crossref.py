from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_WORKS_URL = "https://api.crossref.org/works"

# Abstract cua Crossref boc trong the JATS XML, vi du "<jats:p>...</jats:p>".
MARKUP_TAG_RE = re.compile(r"<[^>]+>")

# 429/503 la cac ma Crossref tra ve khi bi gioi han tan suat, nen thu lai.
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2.0
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _strip_markup(value: str) -> str:
    """Bo the JATS XML va gom khoang trang thua thanh mot khoang don."""
    return normalize_whitespace(MARKUP_TAG_RE.sub(" ", value))


def _first_text(value: object) -> str:
    """`title` cua Crossref la list, nhung mot so ban ghi chi tra ve string."""
    if isinstance(value, list):
        value = value[0] if value else ""
    return _strip_markup(str(value or ""))


def _format_authors(raw_authors: object) -> list[str]:
    if not isinstance(raw_authors, list):
        return []

    authors: list[str] = []
    for author in raw_authors:
        if isinstance(author, str):
            name = normalize_whitespace(author)
        elif isinstance(author, dict):
            given = normalize_whitespace(str(author.get("given") or ""))
            family = normalize_whitespace(str(author.get("family") or ""))
            name = normalize_whitespace(f"{given} {family}")
        else:
            continue
        if name:
            authors.append(name)
    return authors


def _format_date(raw_block: object) -> str:
    """Doi khoi ngay cua Crossref thanh chuoi ISO `YYYY-MM-DD`.

    Crossref tra ngay theo hai dang: `{"date-parts": [[2026, 5, 20]]}` (thieu
    ngay/thang thi mac dinh la 1) va `{"date-time": "2026-05-20T10:00:00Z"}`.
    """
    if not isinstance(raw_block, dict):
        return ""

    date_parts = raw_block.get("date-parts")
    if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list):
        parts = [int(part) for part in date_parts[0] if isinstance(part, int)]
        if parts:
            year = parts[0]
            month = parts[1] if len(parts) > 1 else 1
            day = parts[2] if len(parts) > 2 else 1
            return f"{year:04d}-{month:02d}-{day:02d}"

    date_time = raw_block.get("date-time")
    if isinstance(date_time, str) and len(date_time) >= 10:
        return date_time[:10]

    return ""


def _extract_pdf_url(item: dict, fallback: str) -> str:
    links = item.get("link")
    if isinstance(links, list):
        for link in links:
            if not isinstance(link, dict):
                continue
            if "pdf" in str(link.get("content-type") or "").lower():
                url = str(link.get("URL") or "").strip()
                if url:
                    return url
    return fallback


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse payload Crossref thanh list `PaperRecord`.

    Giu nguyen thu tu `message.items` de bao toan data lineage: raw response va
    raw records phai phan anh dung thu tu ma API tra ve.

    Record bi bo qua khi thieu DOI/title/abstract hoac trung DOI.
    """
    message = payload.get("message")
    items = message.get("items") if isinstance(message, dict) else None
    if not isinstance(items, list):
        return []

    records: list[PaperRecord] = []
    seen_paper_ids: set[str] = set()

    for item in items:
        if not isinstance(item, dict):
            continue

        paper_id = normalize_whitespace(str(item.get("DOI") or ""))
        title = _first_text(item.get("title"))
        summary = _strip_markup(str(item.get("abstract") or ""))
        if not paper_id or not title or not summary or paper_id in seen_paper_ids:
            continue
        seen_paper_ids.add(paper_id)

        categories = [
            normalize_whitespace(str(subject))
            for subject in (item.get("subject") or [])
            if normalize_whitespace(str(subject))
        ]
        published = _format_date(item.get("published")) or _format_date(item.get("issued"))
        updated = (
            _format_date(item.get("created"))
            or _format_date(item.get("indexed"))
            or published
        )
        abs_url = str(item.get("URL") or "").strip() or f"https://doi.org/{paper_id}"

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=_format_authors(item.get("author")),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=_extract_pdf_url(item, abs_url),
                comment=f"Crossref record {paper_id}",
            )
        )

    return records


def _request_payload(settings: Settings) -> dict:
    """Goi Crossref API, retry voi cac status code 429/5xx."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }
    headers = {"User-Agent": "day10-data-observability-lab/0.1 (mailto:student@vinuni.edu.vn)"}

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            last_error = exc
        else:
            if response.status_code == 200:
                return response.json()

            last_error = RuntimeError(f"Crossref tra ve HTTP {response.status_code}")
            if response.status_code not in RETRYABLE_STATUS_CODES:
                break

        if attempt < MAX_ATTEMPTS:
            time.sleep(BACKOFF_SECONDS * attempt)

    raise RuntimeError(f"Khong goi duoc Crossref API sau {MAX_ATTEMPTS} lan thu: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Lay raw records, uu tien snapshot offline de ket qua chay lai on dinh.

    `REFRESH_SOURCE=1` moi thuc su goi API. Khi goi API that bai (mat mang,
    429...) thi fallback ve `data/raw/crossref_response.json` da luu.
    """
    paths = settings.paths

    if not settings.refresh_source and paths.raw_records_json.exists():
        return load_raw_records(paths.raw_records_json)

    try:
        payload = _request_payload(settings)
    except RuntimeError as exc:
        if not paths.raw_api_response.exists():
            raise
        print(f"[ingestion] {exc}")
        print(f"[ingestion] Fallback: doc snapshot offline {paths.raw_api_response}")
        payload = read_json(paths.raw_api_response)
    else:
        write_json(paths.raw_api_response, payload)

    records = parse_crossref_payload(payload)
    write_json(paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    payload = read_json(path)
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError(f"Snapshot {path} khong chua danh sach record nao.")

    records: list[PaperRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        categories = [str(category) for category in (item.get("categories") or [])]
        abs_url = str(item.get("abs_url") or "")
        records.append(
            PaperRecord(
                paper_id=str(item.get("paper_id") or ""),
                title=str(item.get("title") or ""),
                summary=str(item.get("summary") or ""),
                authors=[str(author) for author in (item.get("authors") or [])],
                categories=categories,
                primary_category=str(
                    item.get("primary_category") or (categories[0] if categories else "")
                ),
                published=str(item.get("published") or ""),
                updated=str(item.get("updated") or item.get("published") or ""),
                abs_url=abs_url,
                pdf_url=str(item.get("pdf_url") or abs_url),
                comment=str(item.get("comment") or ""),
            )
        )

    return records