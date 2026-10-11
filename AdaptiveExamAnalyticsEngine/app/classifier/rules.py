import re
from dataclasses import dataclass, field

from app.analytics.taxonomy import TOPICS
from app.schemas.catalog import TopicAssignment

BLOOM_VERBS: dict[str, set[str]] = {}  # deprecated: Bloom is ONLY via ModernBERT; kept for import compat

TOPIC_KEYWORDS: dict[str, set[str]] = {
    "Introduction to DBMS and Conceptual Database Design": {
        "dbms", "database management system", "conceptual", "er model", "entity relationship", "architecture", "data model", "schema",
    },
    "Logical Database Design": {
        "logical", "relational schema", "relational model", "primary key", "foreign key", "mapping", "normalization first", "candidate key",
    },
    "Schema Refinement": {
        "schema refinement", "functional dependency", "attribute closure", "normalize", "3nf", "bcnf", "2nf", "1nf", "anomaly", "closure", "decompos",
    },
    "SQL": {
        "select", "insert", "update", "delete", "join", "where", "group by", "order by", "having", "sql", "subquery", "view", "index", "aggregate",
    },
    "Database Programming": {
        "pl/sql", "stored procedure", "trigger", "cursor", "function", "package", "transaction", "commit", "rollback",
    },
    "Java Database Connectivity (JDBC)": {
        "jdbc", "preparedstatement", "resultset", "connection", "drivermanager", "java", "getconnection", "statement",
    },
    "Database Utilities": {
        "backup", "recovery", "import", "export", "load", "utility", "dump", "restore", "log",
    },
    "Database Security": {
        "security", "privilege", "grant", "revoke", "encryption", "authentication", "authorization", "access control", "sql injection",
    },
    # Aliases / missing TOPICS entries — keep _topic_hits tolerant but also provide explicit keywords
    "Introduction to DBMS & Conceptual Database Design": {
        "dbms", "database management system", "conceptual", "er model", "entity relationship", "architecture", "data model", "schema",
    },
    "Structured Query Language (SQL)": {
        "select", "insert", "update", "delete", "join", "where", "group by", "order by", "having", "sql", "subquery", "view", "index", "aggregate",
    },
    "Database Indexes and Storage Structures": {
        "index", "b+ tree", "b tree", "hash", "extendible", "linear hashing", "clustered", "non-clustered", "storage", "page", "block", "external sort", "merge sort",
    },
    "Database Transaction Management and Concurrency Control": {
        "transaction", "concurrency", "schedule", "serializable", "conflict serializable", "view serializable", "2pl", "lock", "mvcc", "snapshot isolation", "write skew", "acid",
    },
    "Database Recovery and Log Management": {
        "recovery", "aries", "wal", "write-ahead", "log", "redo", "undo", "checkpoint", "compensat", "dirty page", "transaction table", "physiological",
    },
}

_TOPIC_ORDER = TOPICS


@dataclass
class RuleClassification:
    topic_assignments: list[TopicAssignment] = field(default_factory=list)
    bloom_level: str = "Understand"
    question_type: str = "short_answer"
    key_concepts: list[str] = field(default_factory=list)
    confidence: str = "medium"


def _bloom_level(text: str) -> str:
    """Bloom level ONLY via ModernBERT models/bloom_modernbert — no verb/Qwen fallback."""
    from app.classifier.bloom_classifier import is_bloom_model_available, predict_bloom
    from app.config import settings

    if not is_bloom_model_available():
        raise RuntimeError(
            f"Bloom ModernBERT not available at {settings.bloom_model_dir} — "
            "ensure models/bloom_modernbert/bloom.safetensors + tokenizer exist"
        )
    bloom = predict_bloom(text)
    return bloom["level"]


def _topic_hits(text: str, taxonomy: dict | None = None) -> dict[str, int]:
    # Per-course path: build keywords from taxonomy canonical_topic+aliases when provided
    if taxonomy is not None and isinstance(taxonomy, dict) and len(taxonomy) > 0:
        lower = text.casefold()
        hits: dict[str, int] = {}
        for cid, entry in taxonomy.items():
            if not isinstance(entry, dict):
                continue
            canon = entry.get("canonical_topic")
            if not canon or not isinstance(canon, str) or not canon.strip():
                continue
            canon = canon.strip()
            kws: set[str] = set()
            kws.add(canon.casefold().strip())
            if isinstance(cid, str) and cid.strip():
                kws.add(cid.casefold().strip())
            for alias in entry.get("aliases", []) or []:
                if isinstance(alias, str) and alias.strip():
                    kws.add(alias.casefold().strip())
            # Augment with legacy TOPIC_KEYWORDS for IT2040 backward compat
            # Ensures SELECT/JOIN still map to Structured Query Language (SQL) even when taxonomy only has canonical+alias
            legacy = TOPIC_KEYWORDS.get(canon)
            if legacy is None:
                norm = canon.replace("&", "and")
                legacy = TOPIC_KEYWORDS.get(norm)
            if legacy is None and "SQL" in canon:
                legacy = TOPIC_KEYWORDS.get("SQL")
            if legacy is None and isinstance(cid, str):
                # try cid-based legacy lookup (e.g., cid "sql" -> key "SQL")
                for lk in TOPIC_KEYWORDS:
                    if lk.casefold() == cid.casefold():
                        legacy = TOPIC_KEYWORDS.get(lk)
                        break
            if legacy:
                for kw in legacy:
                    if isinstance(kw, str) and kw.strip():
                        kws.add(kw.casefold().strip())
            count = 0
            for kw in kws:
                if not kw:
                    continue
                count += len(re.findall(re.escape(kw), lower))
            if count > 0:
                hits[canon] = count
        # If taxonomy provided but no hits, fallback to legacy IT2040 keywords for cases where taxonomy
        # legitimately doesn't cover e.g., empty alias but legacy keywords would (keeps existing tests green)
        if not hits:
            # fallback legacy evaluation (same as below) but return mapped to taxonomy canon where possible
            # Try legacy fallback using TOPIC_KEYWORDS directly — if that yields hits, map them to taxonomy canon
            lower2 = text.lower()
            for topic in _TOPIC_ORDER:
                kws2 = TOPIC_KEYWORDS.get(topic)
                if kws2 is None:
                    norm = topic.replace("&", "and")
                    kws2 = TOPIC_KEYWORDS.get(norm)
                if kws2 is None and "SQL" in topic:
                    kws2 = TOPIC_KEYWORDS.get("SQL")
                if not kws2:
                    continue
                count = 0
                for kw in kws2:
                    count += len(re.findall(re.escape(kw), lower2))
                if count > 0:
                    # map legacy topic to taxonomy canon if taxonomy has that canonical
                    target_canon = topic
                    # Find taxonomy entry with matching canonical or alias that corresponds to legacy topic
                    for _cid, _entry in taxonomy.items():
                        if not isinstance(_entry, dict):
                            continue
                        _canon = _entry.get("canonical_topic", "")
                        if _canon == topic or _canon.replace("&", "and") == topic.replace("&", "and"):
                            target_canon = _canon
                            break
                        # also check if legacy topic contains SQL and taxonomy has SQL canonical
                        if "SQL" in topic and "SQL" in str(_canon):
                            target_canon = _canon
                            break
                    hits[target_canon] = hits.get(target_canon, 0) + count
            if hits:
                return hits
        return hits
    # Fallback to existing IT2040 TOPIC_KEYWORDS
    lower = text.lower()
    hits: dict[str, int] = {}
    for topic in _TOPIC_ORDER:
        # TOPICS and TOPIC_KEYWORDS use slightly different strings (e.g. "&" vs "and",
        # "Structured Query Language (SQL)" vs "SQL"). Be tolerant of missing keys.
        kws = TOPIC_KEYWORDS.get(topic)
        if kws is None:
            # normalize "&" -> "and" and try again
            norm = topic.replace("&", "and")
            kws = TOPIC_KEYWORDS.get(norm)
        if kws is None and "SQL" in topic:
            kws = TOPIC_KEYWORDS.get("SQL")
        if not kws:
            continue
        count = 0
        for kw in kws:
            count += len(re.findall(re.escape(kw), lower))
        if count > 0:
            hits[topic] = count
    return hits


def _question_type(text: str, bloom_level: str) -> str:
    lower = text.lower()
    if any(re.search(rf"\b{v}\b", lower) for v in ("select", "insert", "update", "delete")):
        return "coding"
    if bloom_level in ("Apply", "Analyze", "Evaluate", "Create"):
        return "problem_solving"
    return "short_answer"


def classify_by_rules(question_text: str, taxonomy: dict | None = None) -> RuleClassification:
    hits = _topic_hits(question_text, taxonomy)
    bloom = _bloom_level(question_text)
    confidence = "high"
    if not hits:
        # No keyword match -> unclassified, reviewable (never silently use TOPICS[0])
        assignments = [TopicAssignment(topic="Unclassified", weight=1.0)]
        confidence = "low"
    else:
        # Check for ambiguous tie
        sorted_hits = sorted(hits.items(), key=lambda kv: kv[1], reverse=True)
        if len(sorted_hits) > 1 and sorted_hits[0][1] == sorted_hits[1][1]:
            assignments = [TopicAssignment(topic="Unclassified", weight=1.0)]
            confidence = "low"
        else:
            total = sum(hits.values())
            assignments = [
                TopicAssignment(topic=topic, weight=hits[topic] / total)
                for topic in sorted(hits, key=lambda t: hits[t], reverse=True)
            ]
            if len(hits) > 1 or max(hits.values()) <= 1:
                confidence = "medium"
    return RuleClassification(
        topic_assignments=assignments,
        bloom_level=bloom,
        question_type=_question_type(question_text, bloom),
        key_concepts=[],
        confidence=confidence,
    )