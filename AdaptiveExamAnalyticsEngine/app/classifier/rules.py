import re
from dataclasses import dataclass, field

from app.analytics.taxonomy import TOPICS
from app.schemas.catalog import TopicAssignment

BLOOM_VERBS: dict[str, set[str]] = {}  # deprecated: Bloom is ONLY via ModernBERT; kept for import compat

TOPIC_KEYWORDS: dict[str, set[str]] = {
    "Introduction to DBMS and Conceptual Database Design": {
        "dbms", "database management system", "conceptual", "er model", "entity relationship", "architecture", "data model", "schema", "database design phases", "weak entities", "ternary relationships",
    },
    "Logical Database Design": {
        "logical", "relational schema", "relational model", "primary key", "foreign key", "mapping", "normalization first", "candidate key",
    },
    "Schema Refinement": {
        "schema refinement", "functional dependency", "attribute closure", "normalize", "3nf", "bcnf", "2nf", "1nf", "anomaly", "closure", "decomposition", "decompose",
    },
    "SQL": {
        "select", "insert", "update", "delete", "join", "where", "group by", "order by", "having", "sql", "subquery", "index", "aggregate",
    },
    "Database Programming": {
        "view", "views", "pl/sql", "stored procedure", "trigger", "cursor", "function", "package", "transaction", "commit", "rollback",
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
        "dbms", "database management system", "conceptual", "er model", "entity relationship", "architecture", "data model", "schema", "database design phases", "weak entities", "ternary relationships",
    },
    "Structured Query Language (SQL)": {
        "select", "insert", "update", "delete", "join", "where", "group by", "order by", "having", "sql", "subquery", "index", "aggregate",
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
    lower = text.casefold()
    entries = taxonomy if taxonomy is not None else {
        topic: {"canonical_topic": topic} for topic in _TOPIC_ORDER
    }
    matches: set[tuple[int, int, str, int]] = set()
    for cid, entry in entries.items():
        canon = entry.get("canonical_topic") if isinstance(entry, dict) else None
        if not isinstance(canon, str) or not canon.strip():
            continue
        canon = canon.strip()
        keywords = {canon, str(cid), *(entry.get("aliases") or []), *(entry.get("subtopics") or [])}
        legacy = TOPIC_KEYWORDS.get(canon) or TOPIC_KEYWORDS.get(canon.replace("&", "and"))
        if legacy:
            keywords.update(legacy)
        for keyword in keywords:
            if not isinstance(keyword, str) or not keyword.strip():
                continue
            keyword = keyword.strip().casefold()
            for match in re.finditer(r"(?<!\w)" + re.escape(keyword) + r"(?:s|es)?(?!\w)", lower):
                matches.add((match.start(), match.end(), canon, len(keyword.split())))
    hits: dict[str, int] = {}
    for start, end, topic, words in matches:
        # A specific phrase owns its span: "schema" must not tie with "schema refinement".
        if any(other != topic and a <= start and end <= b and (a < start or end < b)
               for a, b, other, _ in matches):
            continue
        hits[topic] = hits.get(topic, 0) + words * words
    return hits


def _question_type(text: str, bloom_level: str) -> str:
    lower = text.lower()
    if any(re.search(rf"\b{v}\b", lower) for v in ("select", "insert", "update", "delete")):
        return "coding"
    if bloom_level in ("Apply", "Analyze", "Evaluate", "Create"):
        return "problem_solving"
    return "short_answer"


def classify_by_rules(
    question_text: str, taxonomy: dict | None = None, *, bloom_level: str | None = None
) -> RuleClassification:
    hits = _topic_hits(question_text, taxonomy)
    bloom = _bloom_level(question_text) if bloom_level is None else bloom_level
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
