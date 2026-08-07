import re
from dataclasses import dataclass, field

from app.analytics.taxonomy import TOPICS
from app.schemas.catalog import TopicAssignment

BLOOM_VERBS: dict[str, set[str]] = {
    "Remember": {"list", "define", "state", "name", "identify", "recall", "label", "match"},
    "Understand": {"explain", "describe", "summarize", "discuss", "distinguish", "classify", "relate"},
    "Apply": {"apply", "use", "calculate", "compute", "solve", "implement", "write", "execute", "find"},
    "Analyze": {"analyze", "compare", "contrast", "differentiate", "examine", "trace", "break down", "determine"},
    "Evaluate": {"evaluate", "justify", "assess", "recommend", "judge", "critique", "prioritize"},
    "Create": {"design", "create", "construct", "develop", "plan", "propose", "formulate", "compose"},
}

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
    lower = text.lower()
    for level in ("Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"):
        if any(re.search(rf"\b{v}\b", lower) for v in BLOOM_VERBS[level]):
            return level
    return "Understand"


def _topic_hits(text: str) -> dict[str, int]:
    lower = text.lower()
    hits: dict[str, int] = {}
    for topic in _TOPIC_ORDER:
        count = 0
        for kw in TOPIC_KEYWORDS[topic]:
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


def classify_by_rules(question_text: str) -> RuleClassification:
    hits = _topic_hits(question_text)
    bloom = _bloom_level(question_text)
    confidence = "high"
    if not hits:
        assignments = [TopicAssignment(topic=_TOPIC_ORDER[0], weight=1.0)]
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