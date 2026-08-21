"""Sanity checks for OCR question-marker splitting."""
from __future__ import annotations

from app.services.answer_splitter import (
    resolve_answer_for_question,
    split_transcript_by_questions,
)

RUBRIC = {
    "questions": [
        {"question_no": "01", "question_text": "Q1"},
        {"question_no": "02", "question_text": "Q2"},
        {"question_no": "03", "question_text": "Q3"},
    ]
}


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise SystemExit(f"FAIL: {msg}")


def test_ocr_letter_i_as_q1() -> None:
    text = "Q I\nTwo-phase locking grows then shrinks.\nQ2\nLocks are only released.\n"
    buckets = split_transcript_by_questions(text, RUBRIC["questions"])
    _assert("01" in buckets, f"expected Q01 bucket, got {sorted(buckets)}")
    _assert("02" in buckets, f"expected Q02 bucket, got {sorted(buckets)}")
    _assert("two-phase" in buckets["01"].lower(), buckets["01"])
    src = resolve_answer_for_question(text, RUBRIC["questions"][0], buckets, 1)[1]
    _assert(src == "split", f"Q01 source should be split, got {src}")


def test_ocr_qi_and_ql() -> None:
    for marker in ("QI", "Ql", "Q. I", "Question I"):
        text = f"{marker}\nAnswer one here.\nQ2\nAnswer two here.\n"
        buckets = split_transcript_by_questions(text, RUBRIC["questions"])
        _assert("01" in buckets, f"{marker!r} should map to 01, got {sorted(buckets)}")


def test_roman_ii_iii() -> None:
    text = "Q I\nFirst.\nQ II\nSecond.\nQ III\nThird.\n"
    buckets = split_transcript_by_questions(text, RUBRIC["questions"])
    _assert(set(buckets) == {"01", "02", "03"}, sorted(buckets))


def test_plain_digits_still_work() -> None:
    text = "Question 1\nAlpha.\nQ2\nBeta.\n"
    buckets = split_transcript_by_questions(text, RUBRIC["questions"][:2])
    _assert(set(buckets) == {"01", "02"}, sorted(buckets))


def test_q_in_is_not_q1() -> None:
    text = "Q in the following diagram the lock is held.\nOnly this paragraph.\n"
    buckets = split_transcript_by_questions(text, RUBRIC["questions"])
    _assert("01" not in buckets, f"false marker: {sorted(buckets)}")


def test_page_banners_stripped() -> None:
    text = (
        "--- Page 1: WhatsApp Image 2026-05-11 at 12.25.03 PM.jpeg ---\n"
        "Q1\nFirst answer.\n\n"
        "--- Page 2: page2.jpeg ---\n"
        "Q2\nSecond answer.\n"
    )
    from app.services.answer_splitter import clean_ocr_transcript

    cleaned = clean_ocr_transcript(text)
    _assert("WhatsApp" not in cleaned, cleaned)
    _assert("--- Page" not in cleaned, cleaned)
    buckets = split_transcript_by_questions(cleaned, RUBRIC["questions"][:2])
    _assert("01" in buckets and "02" in buckets, sorted(buckets))


if __name__ == "__main__":
    test_ocr_letter_i_as_q1()
    test_ocr_qi_and_ql()
    test_roman_ii_iii()
    test_plain_digits_still_work()
    test_q_in_is_not_q1()
    test_page_banners_stripped()
    print("answer splitter OCR marker tests passed")
