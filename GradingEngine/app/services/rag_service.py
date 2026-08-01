import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

_chroma_client = None
_collection = None

COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "lecture_notes")
EMBEDDING_MODEL = os.getenv("CHROMA_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
RAG_N_RESULTS = int(os.getenv("RAG_N_RESULTS", "3"))


def get_chroma_db_path() -> Path:
    override = os.getenv("CHROMA_DB_PATH", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent.parent / "chroma_db"


def get_collection():
    global _chroma_client, _collection
    if _collection is not None:
        return _collection

    db_path = get_chroma_db_path()
    db_path.mkdir(parents=True, exist_ok=True)

    _chroma_client = chromadb.PersistentClient(path=str(db_path))
    embedding_model = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    _collection = _chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_model,
    )
    return _collection


def _empty_rag_result(snippet: str, course: str = "") -> dict:
    return {
        "snippet": snippet,
        "rag_chunks": 0,
        "rag_context_used": False,
        "course_name": course or None,
    }


def retrieve_relevant_context(
    topic_query: str,
    n_results: int | None = None,
    course_name: str | None = None,
) -> dict:
    """
    Semantic search over lecture chunks.

    If ``course_name`` is set, only chunks tagged with that course are searched
    (all PDFs/PPTXs under that course). Does not fall back to other courses.

    Returns:
        snippet, rag_chunks, rag_context_used, course_name
    """
    query = (topic_query or "").strip()
    course = (course_name or "").strip()
    if not query:
        return _empty_rag_result(
            "No corresponding matching topic was found in the lecture materials.",
            course,
        )

    top_k = n_results or RAG_N_RESULTS

    try:
        collection = get_collection()
        query_kwargs: dict = {
            "query_texts": [query],
            "n_results": top_k,
        }
        if course:
            query_kwargs["where"] = {"course": course}

        results = collection.query(**query_kwargs)

        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or [[]]
        if documents and documents[0]:
            chunks = []
            for idx, doc in enumerate(documents[0]):
                if not isinstance(doc, str) or not doc.strip():
                    continue
                meta = {}
                if metadatas and metadatas[0] and idx < len(metadatas[0]):
                    meta = metadatas[0][idx] if isinstance(metadatas[0][idx], dict) else {}
                source = str(meta.get("source_file") or "").strip()
                page_number = meta.get("page_number")
                label_parts = []
                if source:
                    label_parts.append(source)
                if page_number is not None:
                    label_parts.append(f"p{page_number}")
                label = f"[{', '.join(label_parts)}] " if label_parts else ""
                chunks.append(f"{label}{doc.strip()}")

            if chunks:
                matched_course = course or (
                    (metadatas[0][0] or {}).get("course", "Unknown Course")
                    if metadatas and metadatas[0] and isinstance(metadatas[0][0], dict)
                    else "Unknown Course"
                )
                print(
                    f"RAG match from course={matched_course} "
                    f"({len(chunks)} chunk(s), filtered={bool(course)})"
                )
                return {
                    "snippet": "\n\n".join(chunks),
                    "rag_chunks": len(chunks),
                    "rag_context_used": True,
                    "course_name": matched_course,
                }

        if course:
            return _empty_rag_result(
                f"No lecture materials found for course '{course}' matching this topic.",
                course,
            )
        return _empty_rag_result(
            "No corresponding matching topic was found in the lecture materials.",
            course,
        )
    except Exception as err:
        # Chroma may error if the course filter matches zero records depending on version.
        err_text = str(err).lower()
        if course and ("no matching" in err_text or "does not exist" in err_text or "empty" in err_text):
            print(f"RAG: no indexed chunks for course={course} ({err})")
            return _empty_rag_result(
                f"No lecture materials found for course '{course}' matching this topic.",
                course,
            )
        print(f"RAG retrieval failure: {err}")
        return _empty_rag_result("Lecture context unavailable.", course)


def retrieve_relevant_snippet(
    topic_query: str,
    n_results: int | None = None,
    course_name: str | None = None,
) -> str:
    """Backward-compatible wrapper — prefer ``retrieve_relevant_context``."""
    return str(
        retrieve_relevant_context(
            topic_query, n_results=n_results, course_name=course_name
        ).get("snippet")
        or ""
    )


def build_grading_query(topic: str, questions: list[dict], answer: str) -> str:
    """
    Build a semantic RAG query. Prefer rubric question text over the student answer
    so retrieval stays lecture-focused (especially for single-question grading calls).
    """
    parts = [str(topic or "").strip()]
    for question in questions[:3]:
        if isinstance(question, dict):
            parts.append(
                str(question.get("question_text") or question.get("question") or "").strip()
            )
            criteria = question.get("criteria")
            if isinstance(criteria, list):
                for item in criteria[:2]:
                    if isinstance(item, dict):
                        parts.append(str(item.get("point") or item.get("criterion") or "").strip())
                    elif item:
                        parts.append(str(item).strip())
            elif isinstance(criteria, str):
                parts.append(criteria.strip()[:200])
    query = " ".join(part for part in parts if part)
    if query:
        return query
    return (answer or "").strip()[:500]


def list_indexed_lectures(course_name: str | None = None) -> list[dict]:
    """Aggregate Chroma chunks into one row per uploaded file."""
    try:
        collection = get_collection()
        if collection.count() == 0:
            return []

        stored = collection.get(include=["metadatas"])
        ids = stored.get("ids") or []
        metadatas = stored.get("metadatas") or []
        course_filter = (course_name or "").strip().lower()

        grouped: dict[tuple[str, str, str], dict] = {}
        for doc_id, meta in zip(ids, metadatas):
            if not isinstance(meta, dict):
                continue

            course = str(meta.get("course") or "").strip()
            filename = str(meta.get("source_file") or "").strip()
            doc_type = str(meta.get("type") or "PDF").strip()
            if not course or not filename:
                continue
            if course_filter and course.lower() != course_filter:
                continue

            key = (course, filename, doc_type)
            bucket = grouped.setdefault(
                key,
                {"course_name": course, "filename": filename, "type": doc_type, "indexed_items": 0},
            )
            bucket["indexed_items"] += 1

        items = list(grouped.values())
        items.sort(key=lambda row: (row["course_name"].lower(), row["filename"].lower()))
        return items
    except Exception as err:
        print(f"Failed to list lecture materials: {err}")
        raise


def delete_lecture_material(course_name: str, filename: str) -> int:
    """Remove all vector chunks for a given course + source file."""
    course = (course_name or "").strip()
    source_file = (filename or "").strip()
    if not course or not source_file:
        return 0

    collection = get_collection()
    stored = collection.get(include=["metadatas"])
    ids = stored.get("ids") or []
    metadatas = stored.get("metadatas") or []

    ids_to_delete = []
    for doc_id, meta in zip(ids, metadatas):
        if not isinstance(meta, dict):
            continue
        if (
            str(meta.get("course") or "").strip() == course
            and str(meta.get("source_file") or "").strip() == source_file
        ):
            ids_to_delete.append(doc_id)

    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
    return len(ids_to_delete)


def delete_all_lecture_materials_for_course(course_name: str) -> int:
    """Remove every indexed chunk tagged with this course."""
    course = (course_name or "").strip()
    if not course:
        return 0

    collection = get_collection()
    stored = collection.get(include=["metadatas"])
    ids = stored.get("ids") or []
    metadatas = stored.get("metadatas") or []

    ids_to_delete = []
    for doc_id, meta in zip(ids, metadatas):
        if not isinstance(meta, dict):
            continue
        if str(meta.get("course") or "").strip() == course:
            ids_to_delete.append(doc_id)

    if ids_to_delete:
        collection.delete(ids=ids_to_delete)
    return len(ids_to_delete)
