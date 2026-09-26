from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

# Bo test set co dinh 10 cau, trai deu tren 4 nhom nghiep vu.
QUESTION_COUNT = 10
QUESTION_TYPES = ("summary", "authors", "date", "categories")
MIN_DOCUMENTS = 10

# Cau hoi phai chua tieu de trong cap nhap don `'...'` de `answer_question`
# trong retrieval/qa.py tra cuu chinh xac duoc tai lieu, va phai khop cach
# dien dat ma `_extract_answer` nhan dien theo tung nhom cau hoi.
QUESTION_TEMPLATES = {
    "summary": "What is the paper '{title}' about?",
    "authors": "Who authored the paper '{title}'?",
    "date": "When was the paper '{title}' published?",
    "categories": "What categories does the paper '{title}' belong to?",
}


def _select_rows(df: pd.DataFrame, count: int) -> list[dict[str, Any]]:
    """Chon `count` bai bao trai deu tren corpus, on dinh giua cac lan chay."""
    rows = df.to_dict(orient="records")
    if count >= len(rows):
        return rows

    last_position = len(rows) - 1
    return [rows[round(index * last_position / (count - 1))] for index in range(count)]


def _ground_truth(question_type: str, row: dict[str, Any]) -> str:
    if question_type == "authors":
        return str(row["authors_joined"])
    if question_type == "date":
        return str(row["published"])
    if question_type == "categories":
        return str(row["categories_joined"])
    return first_sentence(str(row["summary"]))


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Sinh bo evaluation set tu cleaned dataframe va ghi ra `output_path`.

    Moi cau gom: `id`, `question_type`, `question`, `ground_truth`,
    `ground_truth_doc_ids`. Bon nhom cau hoi duoc xoay vong de phu du
    `summary`, `authors`, `date`, `categories`.
    """
    if len(df) < MIN_DOCUMENTS:
        raise RuntimeError(
            f"Can it nhat {MIN_DOCUMENTS} tai lieu de sinh test set, hien co {len(df)}."
        )

    test_set: list[dict[str, Any]] = []
    for index, row in enumerate(_select_rows(df, QUESTION_COUNT)):
        question_type = QUESTION_TYPES[index % len(QUESTION_TYPES)]
        test_set.append(
            {
                "id": f"q{index + 1:02d}",
                "question_type": question_type,
                "question": QUESTION_TEMPLATES[question_type].format(title=str(row["title"])),
                "ground_truth": _ground_truth(question_type, row),
                "ground_truth_doc_ids": [str(row["paper_id"])],
            }
        )

    write_json(output_path, test_set)
    return test_set