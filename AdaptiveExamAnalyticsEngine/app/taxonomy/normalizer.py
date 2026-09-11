"""Single source of truth for topic taxonomy normalization.

Loads config/topic_taxonomy.json (and fallback datasets/bloom_dataset/taxonomy_v2.json)
and provides case-insensitive alias -> canonical_id mapping.

Usage:
  from app.taxonomy.normalizer import normalize_topic, load_taxonomy, get_canonical_topic

  normalize_topic("Database Management Systems") -> "intro_dbms"
  normalize_topic("SQL Queries and Triggers in Database Management Systems") -> "sql"
  normalize_topic("Database Connectivity and SQL Injection Prevention using JDBC") -> "jdbc"
"""
from __future__ import annotations

import json
import pathlib
from functools import lru_cache

CONFIG_TAXONOMY = pathlib.Path(__file__).resolve().parents[2] / "config" / "topic_taxonomy.json"
FALLBACK_TAXONOMY = pathlib.Path(__file__).resolve().parents[2] / "datasets" / "bloom_dataset" / "taxonomy_v2.json"


def _taxonomy_path() -> pathlib.Path:
    if CONFIG_TAXONOMY.exists():
        return CONFIG_TAXONOMY
    return FALLBACK_TAXONOMY


@lru_cache(maxsize=1)
def load_taxonomy() -> dict[str, dict]:
    path = _taxonomy_path()
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _alias_map() -> dict[str, str]:
    """casefold alias -> canonical_id, including canonical_topic itself."""
    taxonomy = load_taxonomy()
    alias_map: dict[str, str] = {}
    for cid, entry in taxonomy.items():
        # canonical_topic itself is an alias (case-insensitive)
        canon = entry.get("canonical_topic", "")
        if canon:
            alias_map[canon.casefold().strip()] = cid
        for alias in entry.get("aliases", []):
            key = alias.casefold().strip()
            if key:
                alias_map[key] = cid
        # also map canonical_id lower
        alias_map[cid.casefold()] = cid
    return alias_map


def normalize_topic(raw: str | None) -> str | None:
    """Return canonical_id for raw topic string, or None if unmapped.

    Case-insensitive and whitespace-trimmed. Handles your noisy variants:
      - "Database Connectivity with JDBC" -> "jdbc"
      - "Database Connectivity and SQL Injection Prevention using JDBC" -> "jdbc"
      - "SQL Queries and Triggers in Database Management Systems" -> "sql"
    """
    if not raw:
        return None
    key = raw.casefold().strip()
    # direct alias match
    am = _alias_map()
    if key in am:
        return am[key]
    # fallback: substring match for long noisy strings (e.g., exam OCR merges)
    # try to find alias as substring of raw or vice versa
    for alias_key, cid in am.items():
        if alias_key in key or key in alias_key:
            # require alias length > 5 to avoid false positives like "sql" in "mysql"
            if len(alias_key) > 5:
                return cid
    return None


def get_canonical_topic(canonical_id: str) -> str | None:
    taxonomy = load_taxonomy()
    entry = taxonomy.get(canonical_id)
    return entry.get("canonical_topic") if entry else None


def validate_topic_coverage() -> dict:
    """Return {canonical_id: {canonical_topic, alias_count, subtopic_count}} for diagnostics."""
    taxonomy = load_taxonomy()
    return {
        cid: {
            "canonical_topic": entry.get("canonical_topic"),
            "alias_count": len(entry.get("aliases", [])),
            "subtopic_count": len(entry.get("subtopics", [])),
        }
        for cid, entry in taxonomy.items()
    }


def unmapped_topics(raw_topics: list[str]) -> list[str]:
    return [t for t in raw_topics if normalize_topic(t) is None]


def reload_cache() -> None:
    load_taxonomy.cache_clear()
    _alias_map.cache_clear()
