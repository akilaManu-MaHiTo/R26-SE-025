"""Unit tests for student-ID extraction and roster validation (no OCR/Excel I/O)."""
from __future__ import annotations

from app.services.roster_service import (
    effective_paper_id,
    extract_student_id_from_text,
    looks_like_student_id,
    normalize_student_id,
    validate_roster_against_papers,
)


def test_normalize_student_id():
    assert normalize_student_id(" it-2214 5976 ") == "IT22145976"


def test_looks_like_student_id():
    assert looks_like_student_id("IT22239195")
    assert looks_like_student_id("it-2223 9195")
    assert not looks_like_student_id("batch3")
    assert not looks_like_student_id("paper_1")


def test_effective_prefers_folder_over_wrong_ocr():
    paper = {
        "paper_key": "IT22239195",
        "ocr_student_id": "FT22239195",
        "manual_student_id": None,
    }
    assert effective_paper_id(paper) == "IT22239195"


def test_effective_manual_wins():
    paper = {
        "paper_key": "IT22239195",
        "ocr_student_id": "FT22239195",
        "manual_student_id": "IT99999999",
    }
    assert effective_paper_id(paper) == "IT99999999"


def test_effective_falls_back_to_ocr_when_folder_not_id():
    paper = {
        "paper_key": "paper_1",
        "ocr_student_id": "IT111",
        "manual_student_id": None,
    }
    # IT111 is short; looks_like requires 5+ digits after letters — use longer OCR id
    paper["ocr_student_id"] = "IT22145976"
    assert effective_paper_id(paper) == "IT22145976"


def test_extract_labeled_id():
    text = "Name: A. Perera\nStudent ID: IT22145976\nQuestion 1\nAnswer..."
    assert extract_student_id_from_text(text) == "IT22145976"


def test_extract_bare_id_in_header():
    text = "IT22145976\nTwo phase locking..."
    assert extract_student_id_from_text(text) == "IT22145976"


def test_validate_matched_missing_extra_duplicate_unreadable():
    roster = {
        "students": [
            {"student_id": "IT111", "name": "A"},
            {"student_id": "IT222", "name": "B"},
            {"student_id": "IT333", "name": "C"},
        ],
        "duplicate_roster_ids": [],
    }
    # Folder names are not IDs here, so OCR values drive matching.
    scan = {
        "papers": [
            {"paper_key": "p1", "ocr_student_id": "IT111", "manual_student_id": None},
            {"paper_key": "p2", "ocr_student_id": "IT222", "manual_student_id": None},
            {"paper_key": "p2b", "ocr_student_id": "IT222", "manual_student_id": None},
            {"paper_key": "p9", "ocr_student_id": "IT999", "manual_student_id": None},
            {"paper_key": "px", "ocr_student_id": None, "manual_student_id": None, "error": "no id"},
        ]
    }
    report = validate_roster_against_papers(roster, scan)
    statuses = {r["status"] for r in report["rows"]}
    assert "matched" in statuses
    assert "missing_paper" in statuses  # IT333
    assert "duplicate_paper" in statuses  # IT222
    assert "extra_paper" in statuses  # IT999
    assert "unreadable_id" in statuses
    assert report["can_grade"] is False
    assert "p1" in report["matched_paper_keys"]


def test_validate_uses_folder_names_against_roster():
    roster = {
        "students": [
            {"student_id": "IT22197835", "name": "A"},
            {"student_id": "IT22239195", "name": "B"},
        ],
        "duplicate_roster_ids": [],
    }
    scan = {
        "papers": [
            {
                "paper_key": "IT22197835",
                "ocr_student_id": None,
                "manual_student_id": None,
                "id_source": "folder",
            },
            {
                "paper_key": "IT22239195",
                "ocr_student_id": "FT22239195",  # wrong OCR ignored
                "manual_student_id": None,
                "id_source": "folder",
            },
        ]
    }
    report = validate_roster_against_papers(roster, scan)
    assert report["can_grade"] is True
    assert set(report["matched_paper_keys"]) == {"IT22197835", "IT22239195"}
    assert report["summary"]["matched"] == 2
    assert report["summary"]["extra_paper"] == 0
    assert report["summary"]["missing_paper"] == 0


if __name__ == "__main__":
    test_normalize_student_id()
    test_looks_like_student_id()
    test_effective_prefers_folder_over_wrong_ocr()
    test_effective_manual_wins()
    test_effective_falls_back_to_ocr_when_folder_not_id()
    test_extract_labeled_id()
    test_extract_bare_id_in_header()
    test_validate_matched_missing_extra_duplicate_unreadable()
    test_validate_uses_folder_names_against_roster()
    print("roster_service tests OK")
