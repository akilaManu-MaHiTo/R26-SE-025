"""Question Bank builder for IT2040 - Phase 1.

Builds datasets/bloom_dataset/question_bank.json from:
- Final exam/*.pdf (4 exams)
- tutorial/*.pdf (6 tutorials)
- lectures/*.pdf (8 lectures)

Usage:
  python -m app.ingestion.question_bank
  python -m app.ingestion.question_bank --rebuild

Schema per record:
  question_id, source_type, source_id, canonical_topic, subtopic,
  bloom_level, difficulty, marks, question_type, text, year, semester
"""
from __future__ import annotations

import json
import re
import pathlib
from typing import Any

try:
    import pymupdf  # type: ignore
except ImportError:
    pymupdf = None  # type: ignore

BASE = pathlib.Path(__file__).resolve().parents[2] / "datasets" / "bloom_dataset"
TAXONOMY_PATH = BASE / "taxonomy_v2.json"
OUTPUT_PATH = BASE / "question_bank.json"

# Canonical mapping from manual lecture alignment
LECTURE_TOPIC_MAP = {
    "IT2040_Lecture01_2024.pdf": "intro_dbms",
    "IT2040_Lecture02_2024.pdf": "logical_database_design",
    "IT2040_Lecture03_2024.pdf": "schema_refinement",
    "IT2040_Lecture04_2024.pdf": "sql",
    "IT2040_Lecture05_2024.pdf": "database_programming",
    "IT2040_Lecture06_2024.pdf": "jdbc",
    "IT2040_Lecture07_2024.pdf": "indexes_storage",
    "IT2040_Lecture08_2024.pdf": "database_security",
}

# Tutorial number -> canonical topic (learning outcomes order)
TUTORIAL_TOPIC_MAP = {
    "01": "intro_dbms",
    "03": "schema_refinement",
    "04": "sql",
    "05": "sql",
    "06": "database_programming",
    "07": "database_security",
}

# Heuristic keywords to guess canonical topic when not lecture
KEYWORD_TO_CANONICAL = {
    "er diagram": "intro_dbms",
    "eer": "intro_dbms",
    "conceptual": "intro_dbms",
    "relational model": "logical_database_design",
    "primary key": "logical_database_design",
    "foreign key": "logical_database_design",
    "funtional depend": "schema_refinement",
    "functional depend": "schema_refinement",
    "normal form": "schema_refinement",
    "3nf": "schema_refinement",
    "bcnf": "schema_refinement",
    "closure": "schema_refinement",
    "candidate key": "schema_refinement",
    "select": "sql",
    "group by": "sql",
    "subquer": "sql",
    "join": "sql",
    "having": "sql",
    "aggregate": "sql",
    "write sql": "sql",
    "sql quer": "sql",
    "view": "database_programming",
    "trigger": "database_programming",
    "stored procedure": "database_programming",
    "function": "database_programming",
    "t-sql": "database_programming",
    "jdbc": "jdbc",
    "preparedstatement": "jdbc",
    "callablestatement": "jdbc",
    "statement": "jdbc",
    "sql injection": "jdbc",
    "driver": "jdbc",
    "resultset": "jdbc",
    "index": "indexes_storage",
    "storage": "indexes_storage",
    "b-tree": "indexes_storage",
    "transaction": "transaction_concurrency",
    "concurrency": "transaction_concurrency",
    "acid": "transaction_concurrency",
    "deadlock": "transaction_concurrency",
    "recovery": "recovery",
    "log": "recovery",
    "wal": "recovery",
    "backup": "database_utilities",
    "bcp": "database_utilities",
    "bulk insert": "database_utilities",
    "ssis": "database_utilities",
    "security": "database_security",
    "grant": "database_security",
    "revoke": "database_security",
    "login": "database_security",
    "role": "database_security",
}


def load_taxonomy() -> dict[str, Any]:
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        return json.load(f)


def extract_text(pdf_path: pathlib.Path) -> str:
    if pymupdf is None:
        raise RuntimeError("pymupdf not installed. pip install pymupdf")
    doc = pymupdf.open(pdf_path)
    return "\n".join(page.get_text() or "" for page in doc)


def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def guess_canonical(text: str) -> str | None:
    # Prefer taxonomy alias match first, fallback to keyword heuristics
    try:
        from app.taxonomy.normalizer import normalize_topic

        # Try to map raw heading/keyword phrase directly
        # e.g., "SQL Queries and Triggers in Database Management Systems"
        cid = normalize_topic(text)
        if cid:
            return cid
        # also try slicing first 120 chars as likely topic label
        cid = normalize_topic(text[:120])
        if cid:
            return cid
    except Exception:
        pass
    low = text.lower()
    best: str | None = None
    best_score = 0
    for kw, canon in KEYWORD_TO_CANONICAL.items():
        if kw in low:
            score = len(kw)
            if score > best_score:
                best_score = score
                best = canon
    return best


def parse_exam_marks(text: str) -> list[dict[str, Any]]:
    """Extract questions from exam text using 'Question N' + marks pattern."""
    # Find blocks starting with Question N
    # Marks patterns: (16 marks), (15 marks), (25 marks), (40 Marks)
    pattern = re.compile(
        r"Question\s*(\d+)\s*(?:\(?(\d+)\s*marks\)?)?(.*?)(?=Question\s*\d+|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    results = []
    for m in pattern.finditer(text):
        q_no = m.group(1)
        marks_raw = m.group(2)
        body = normalize_ws(m.group(3))[:2000]
        # fallback: search marks inside body if not in header
        if not marks_raw:
            in_body = re.search(r"\(?\s*(\d+)\s*marks\s*\)?", body, re.IGNORECASE)
            marks_raw = in_body.group(1) if in_body else None
        marks = int(marks_raw) if marks_raw and marks_raw.isdigit() else 0
        # If still 0, try last occurrence
        if marks == 0:
            all_marks = re.findall(r"\(\s*(\d+)\s*marks\s*\)", m.group(3), re.IGNORECASE)
            if all_marks:
                marks = sum(int(x) for x in all_marks)
        results.append({"q_no": q_no, "marks": marks, "body": body})
    return results


def parse_tutorial_questions(text: str) -> list[dict[str, Any]]:
    """Split tutorial text by numbered questions '1. ', '2.' etc.

    Merges lettered subparts (a. b. c. i. ii. iii. a) b) ) into parent numbered question.
    So Q6 with a/b/c subparts stays as one record, not three.
    """
    # Remove header
    text = re.sub(r"BSc.*?Tutorial\s*\d+", " ", text, flags=re.IGNORECASE | re.DOTALL)
    # Remove page footers like "B.Sc (Hons)..." that leak between questions
    text = re.sub(r"B\.Sc\s*\(Hons\).*?Information Technology\s*\d+", " ", text, flags=re.IGNORECASE | re.DOTALL)
    # Split on numbered headers: start-of-line or newline + digits + dot + space
    # Avoid splitting on lettered subparts: ensure preceding char is newline/start and not a letter
    splitter = re.compile(r"(?:^|\n)\s*(\d+)\.\s+")
    parts = splitter.split(text)
    questions = []
    for i in range(1, len(parts), 2):
        num = parts[i]
        raw_body = parts[i + 1] if i + 1 < len(parts) else ""
        body = normalize_ws(raw_body)
        if len(body) < 20:
            continue
        # Ensure subparts like 'a. ', 'b. ', 'i. ', 'ii. ', 'a) ', '1) ' at line start stay inside body
        # (splitter already ignores them because it requires \d+\. at line start, but normalize leading letter splits would false)
        # Trim very long questions to 3000 chars to preserve all subparts a/b/c
        questions.append({"q_no": num, "body": body[:3000]})
    # Merge orphan letter-only fragments (e.g., "a. Find..." was not split, but if it was, merge back)
    merged: list[dict[str, Any]] = []
    for q in questions:
        # If body looks like a lone subpart (starts with a. / b. / i. / ii. and is short) merge to previous
        if merged and re.match(r"^[a-z]\.\s+|^i{1,3}\.\s+|^[a-z]\)\s+", q["body"], re.IGNORECASE) and len(q["body"]) < 600:
            merged[-1]["body"] = normalize_ws(merged[-1]["body"] + " " + q["body"])[:3000]
        else:
            merged.append(q)
    return merged


def bloom_from_keywords(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ["convert", "map", "find", "calculate", "write sql", "write a", "create a", "create function", "create trigger"]):
        return "Apply"
    if any(k in low for k in ["explain", "describe", "what is", "briefly explain", "justify", "accept or refute"]):
        return "Understand"
    if any(k in low for k in ["analyze", "is r in", "give reasons", "compare"]):
        return "Analyze"
    return "Apply"


def difficulty_from_marks(marks: int) -> str:
    if marks == 0:
        return "Medium"
    if marks <= 5:
        return "Easy"
    if marks <= 15:
        return "Medium"
    return "Hard"


def question_type_from_text(text: str) -> str:
    low = text.lower()
    if "write sql" in low or "sql quer" in low or "display" in low or "find the" in low:
        return "write_query"
    if "er diagram" in low or "eer diagram" in low or "draw" in low:
        return "design"
    if "explain" in low or "what is" in low or "briefly" in low:
        return "short_answer"
    if "convert" in low or "mapping" in low:
        return "design"
    if "create" in low and ("function" in low or "trigger" in low or "procedure" in low):
        return "write_program"
    return "short_answer"


def build_question_bank() -> list[dict[str, Any]]:
    taxonomy = load_taxonomy()
    # id -> canonical
    canon_names = {k: v["canonical_topic"] for k, v in taxonomy.items()}
    records: list[dict[str, Any]] = []

    # --- Lectures: prefer clean curriculum (90 subtopics) if available, fallback to PDF ---
    curriculum_path = BASE / "curriculum_clean.json"
    if curriculum_path.exists():
        curriculum = json.loads(curriculum_path.read_text(encoding="utf-8"))
        for idx, entry in enumerate(curriculum):
            topic = entry.get("topic", "")
            subtopic = entry.get("subtopic", "")
            lo = entry.get("learning_objective", "")
            # map topic -> canonical_id via normalizer
            try:
                from app.taxonomy.normalizer import normalize_topic

                cid = normalize_topic(topic)
            except Exception:
                cid = None
            # fallback to direct canonical name match
            if not cid:
                for k, v in canon_names.items():
                    if v == topic:
                        cid = k
                        break
            if not cid:
                cid = "intro_dbms"
            lecture_tag = entry.get("lecture", f"lec{(idx // 10) + 1:02d}")
            # bloom heuristic from learning objective verb
            bloom = bloom_from_keywords(lo)
            records.append(
                {
                    "question_id": f"IT2040_2024_{lecture_tag.upper()}_{subtopic[:30].replace(' ', '_')[:30]}_{idx:03d}",
                    "source_type": "lecture",
                    "source_id": lecture_tag,
                    "canonical_topic": canon_names.get(cid, topic),
                    "canonical_id": cid,
                    "subtopic": subtopic,
                    "bloom_level": bloom,
                    "difficulty": "Easy",
                    "marks": 0,
                    "question_type": "concept_check",
                    "text": lo,
                    "year": 2024,
                    "semester": 1,
                    "original_topic_label": topic,
                }
            )
    else:
        lectures_dir = BASE / "lectures"
        for pdf in sorted(lectures_dir.glob("*.pdf")):
            key = pdf.name
            canon_id = LECTURE_TOPIC_MAP.get(key)
            if not canon_id:
                continue
            txt = extract_text(pdf)
            obj_match = re.search(r"LECTURE CONTENT(.*?)(?:\n\n|\Z)", txt, re.DOTALL | re.IGNORECASE)
            snippet = normalize_ws(obj_match.group(1) if obj_match else txt[:800])[:800]
            lec_match = re.search(r"Lecture0*(\d+)", key, re.IGNORECASE)
            lec_no = lec_match.group(1).zfill(2) if lec_match else "00"
            year_match = re.search(r"_(\d{4})\.pdf$", key)
            year = int(year_match.group(1)) if year_match else 2024
            records.append(
                {
                    "question_id": f"IT2040_{year}_Lecture_{lec_no}",
                    "source_type": "lecture",
                    "source_id": pdf.stem,
                    "canonical_topic": canon_names[canon_id],
                    "canonical_id": canon_id,
                    "subtopic": snippet[:200],
                    "bloom_level": "Understand",
                    "difficulty": "Easy",
                    "marks": 0,
                    "question_type": "concept_check",
                    "text": snippet,
                    "year": year,
                    "semester": 1,
                    "original_topic_label": canon_names[canon_id],
                }
            )

    # --- Exams: prefer clean JSON (16 structured) if available ---
    exams_clean_path = BASE / "exams_clean.json"
    if exams_clean_path.exists():
        exams_clean = json.loads(exams_clean_path.read_text(encoding="utf-8"))
        for entry in exams_clean:
            q_no = entry.get("question_no", "01").zfill(2)
            year = int(entry.get("year", 2023))
            body = entry.get("text", "")
            cid = entry.get("canonical_id") or guess_canonical(body) or "sql"
            canon_id = cid if cid in canon_names else "sql"
            records.append(
                {
                    "question_id": entry.get("question_id") or f"IT2040_{year}_Final_Q{q_no}",
                    "source_type": "exam",
                    "source_id": entry.get("source_id") or f"IT2040@Final Examination {year}",
                    "canonical_topic": canon_names[canon_id],
                    "canonical_id": canon_id,
                    "subtopic": body[:300],
                    "bloom_level": entry.get("bloom_level") or bloom_from_keywords(body),
                    "difficulty": difficulty_from_marks(int(entry.get("marks", 0))),
                    "marks": int(entry.get("marks", 0)),
                    "question_type": entry.get("question_type") or question_type_from_text(body),
                    "text": body,
                    "year": year,
                    "semester": 1,
                    "original_topic_label": entry.get("topic_raw") or body[:80],
                }
            )
    else:
        exams_dir = BASE / "Final exam"
        for pdf in sorted(exams_dir.glob("*.pdf")):
            txt = extract_text(pdf)
            ym = re.search(r"(\d{4})\s*Final", pdf.name)
            if not ym:
                ym = re.search(r"[^\d](20\d{2})[^\d]", pdf.name)
            year = int(ym.group(1)) if ym else 2023
            parsed = parse_exam_marks(txt)
            if not parsed:
                parsed = [{"q_no": "01", "marks": 100, "body": normalize_ws(txt)[:2000]}]
            for q in parsed:
                q_no = q["q_no"].zfill(2)
                body = q["body"]
                guess = guess_canonical(body) or "sql"
                canon_id = guess if guess in canon_names else "sql"
                records.append(
                    {
                        "question_id": f"IT2040_{year}_Final_Q{q_no}",
                        "source_type": "exam",
                        "source_id": f"IT2040@Final Examination {year}",
                        "canonical_topic": canon_names[canon_id],
                        "canonical_id": canon_id,
                        "subtopic": body[:300],
                        "bloom_level": bloom_from_keywords(body),
                        "difficulty": difficulty_from_marks(q["marks"]),
                        "marks": q["marks"],
                        "question_type": question_type_from_text(body),
                        "text": body,
                        "year": year,
                        "semester": 1,
                        "original_topic_label": body[:80],
                    }
                )

    # --- Tutorials: prefer clean JSON (55 structured) if available ---
    tutorials_clean_path = BASE / "tutorials_clean.json"
    if tutorials_clean_path.exists():
        tutorials_clean = json.loads(tutorials_clean_path.read_text(encoding="utf-8"))
        for entry in tutorials_clean:
            body = entry.get("text", "")
            q_no = entry.get("question_no", "01").zfill(2)
            tut_no = entry.get("tutorial_no", "00").zfill(2)
            year = int(entry.get("year", 2024))
            cid = entry.get("canonical_id") or guess_canonical(body) or "intro_dbms"
            canon_id = cid if cid in canon_names else "intro_dbms"
            records.append(
                {
                    "question_id": entry.get("question_id") or f"IT2040_{year}_Tutorial{tut_no}_Q{q_no}",
                    "source_type": "tutorial",
                    "source_id": entry.get("source_id") or f"IT2040 Tutorial {int(tut_no)}",
                    "canonical_topic": canon_names[canon_id],
                    "canonical_id": canon_id,
                    "subtopic": body[:300],
                    "bloom_level": entry.get("bloom_level") or bloom_from_keywords(body),
                    "difficulty": difficulty_from_marks(0),
                    "marks": 0,
                    "question_type": entry.get("question_type") or question_type_from_text(body),
                    "text": body,
                    "year": year,
                    "semester": 1,
                    "original_topic_label": body[:80],
                }
            )
    else:
        tut_dir = BASE / "tutorial"
        for pdf in sorted(tut_dir.glob("*.pdf")):
            txt = extract_text(pdf)
            ym = re.search(r"Semester\s*\d,\s*(20\d{2})", txt)
            if not ym:
                ym = re.search(r"Semester\s*1,\s*(20\d{2})", txt)
            year = int(ym.group(1)) if ym else 2024
            m = re.search(r"Tutorial\s*0*(\d+)", pdf.stem, re.IGNORECASE)
            tut_no = m.group(1) if m else "0"
            qs = parse_tutorial_questions(txt)
            if not qs:
                continue
            for q in qs:
                body = q["body"]
                tut_canon = TUTORIAL_TOPIC_MAP.get(tut_no.zfill(2))
                guess = guess_canonical(body)
                if tut_canon:
                    if guess == tut_canon:
                        canon_id = guess
                    elif guess in ("intro_dbms",) and tut_canon in ("sql", "database_programming", "schema_refinement", "database_security"):
                        canon_id = tut_canon
                    elif guess:
                        canon_id = guess if guess in canon_names else tut_canon
                    else:
                        canon_id = tut_canon
                else:
                    canon_id = guess if guess and guess in canon_names else "intro_dbms"
                    records.append(
                        {
                            "question_id": f"IT2040_{year}_Tutorial{tut_no.zfill(2)}_Q{q['q_no'].zfill(2)}",
                            "source_type": "tutorial",
                            "source_id": f"IT2040 Tutorial {tut_no}",
                            "canonical_topic": canon_names[canon_id],
                            "canonical_id": canon_id,
                            "subtopic": body[:300],
                            "bloom_level": bloom_from_keywords(body),
                            "difficulty": difficulty_from_marks(0),
                            "marks": 0,
                            "question_type": question_type_from_text(body),
                            "text": body,
                            "year": year,
                            "semester": 1,
                            "original_topic_label": body[:80],
                        }
                    )

    return records


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Build question_bank.json")
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()

    if OUTPUT_PATH.exists() and not args.rebuild:
        print(f"Exists: {OUTPUT_PATH} (use --rebuild to overwrite)")
        return

    records = build_question_bank()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(records)} records to {OUTPUT_PATH}")

    # summary
    from collections import Counter

    c_type = Counter(r["source_type"] for r in records)
    c_topic = Counter(r["canonical_topic"] for r in records)
    print("By source_type:", dict(c_type))
    print("By canonical_topic:", dict(c_topic))
    # warn unmapped
    unmapped = [r for r in records if not r["canonical_topic"]]
    if unmapped:
        print(f"WARN: {len(unmapped)} unmapped")


if __name__ == "__main__":
    main()
