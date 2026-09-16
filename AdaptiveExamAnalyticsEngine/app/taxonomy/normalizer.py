"""Single source of truth for topic taxonomy normalization.

Loads config/topic_taxonomy.json (and fallback datasets/bloom_dataset/taxonomy_v2.json)
and provides case-insensitive alias -> canonical_id mapping.

Per-course variant (Task 2):
 - DB-first per course_code, file only seeds IT2040, empty for new courses
 - TTLCache keyed by course_code (128, 60s)
 - slugify_topic + async per-course helpers + sync compat wrappers
"""

from __future__ import annotations

import json
import pathlib
import re

from cachetools import TTLCache

CONFIG_TAXONOMY = pathlib.Path(__file__).resolve().parents[2] / "config" / "topic_taxonomy.json"
FALLBACK_TAXONOMY = pathlib.Path(__file__).resolve().parents[2] / "datasets" / "bloom_dataset" / "taxonomy_v2.json"

# TTLCache keyed by course_code upper, DB-first, 60s ttl
_cache: TTLCache = TTLCache(maxsize=128, ttl=60)


def _taxonomy_path() -> pathlib.Path:
    if CONFIG_TAXONOMY.exists():
        return CONFIG_TAXONOMY
    return FALLBACK_TAXONOMY


def _load_file_taxonomy() -> dict[str, dict]:
    path = _taxonomy_path()
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def slugify_topic(canonical_topic: str | None) -> str:
    """Slugify canonical_topic: lower, re.sub r'[^a-z0-9]+' '_' , strip '_' [:64] or 'topic'."""
    if not canonical_topic or not isinstance(canonical_topic, str):
        return "topic"
    s = canonical_topic.lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")[:64].strip("_")
    return s if s else "topic"


async def load_taxonomy(db=None, course_code: str | None = None) -> dict[str, dict]:
    """Async per-course DB-first loader.

    - Cache keyed by course_code upper.
    - DB-first via repository.get_course_taxonomy.
    - File only seeds IT2040 via seed_it2040_if_empty + fallback file.
    - Returns {} for non-IT2040 missing.
    - Backward compat: if course_code is None, defaults to IT2040; if db is None,
      offline fallback to file for IT2040, {} otherwise.
    """
    # Normalize course_code; default to IT2040 for backward compat
    if course_code is None:
        # support legacy call load_taxonomy() with no args -> IT2040 file
        course_code = "IT2040"
    if not isinstance(course_code, str) or not course_code.strip():
        course_code = "IT2040"
    code = course_code.strip().upper()

    # Cache hit
    if code in _cache:
        return _cache[code]

    # DB-first if db provided
    if db is not None:
        try:
            from app.db import repository

            doc = await repository.get_course_taxonomy(db, code)
            if doc and isinstance(doc.get("topics"), dict) and doc["topics"]:
                topics = doc["topics"]
                _cache[code] = topics
                return topics

            # Not found or empty
            if code == "IT2040":
                # Try seed
                try:
                    seeded = await repository.seed_it2040_if_empty(db)
                    # Re-fetch after seed
                    doc2 = await repository.get_course_taxonomy(db, code)
                    if doc2 and isinstance(doc2.get("topics"), dict) and doc2["topics"]:
                        _cache[code] = doc2["topics"]
                        return doc2["topics"]
                    if seeded and isinstance(seeded, dict) and isinstance(seeded.get("topics"), dict) and seeded["topics"]:
                        _cache[code] = seeded["topics"]
                        return seeded["topics"]
                except Exception:
                    pass
                # Fallback file for IT2040
                file_data = _load_file_taxonomy()
                if file_data:
                    _cache[code] = file_data
                    return file_data
                return {}
            else:
                return {}
        except Exception:
            # On repo error, fallback file for IT2040 else empty
            if code == "IT2040":
                file_data = _load_file_taxonomy()
                if file_data:
                    _cache[code] = file_data
                    return file_data
            return {}
    else:
        # Offline / no DB
        if code == "IT2040":
            file_data = _load_file_taxonomy()
            if file_data:
                _cache[code] = file_data
                return file_data
            return {}
        else:
            return {}


def load_taxonomy_sync(course_code: str | None = None) -> dict[str, dict]:
    """Sync compat wrapper for offline tests.

    - If course_code None defaults to IT2040.
    - Checks TTLCache first.
    - For IT2040 loads file; for other courses returns {}.
    """
    if course_code is None:
        course_code = "IT2040"
    if not isinstance(course_code, str) or not course_code.strip():
        course_code = "IT2040"
    code = course_code.strip().upper()
    if code in _cache:
        return _cache[code]
    if code != "IT2040":
        return {}
    file_data = _load_file_taxonomy()
    if file_data:
        _cache[code] = file_data
    return file_data if file_data else {}


async def _alias_map_for_course(db, course_code: str) -> dict[str, str]:
    """casefold alias -> canonical_id for given course, including canonical_topic itself."""
    if course_code is None:
        course_code = "IT2040"
    taxonomy = await load_taxonomy(db, course_code)
    alias_map: dict[str, str] = {}
    for cid, entry in taxonomy.items():
        canon = entry.get("canonical_topic", "") if isinstance(entry, dict) else ""
        if canon and isinstance(canon, str):
            alias_map[canon.casefold().strip()] = cid
        for alias in entry.get("aliases", []) if isinstance(entry, dict) else []:
            if isinstance(alias, str):
                key = alias.casefold().strip()
                if key:
                    alias_map[key] = cid
        if isinstance(cid, str):
            alias_map[cid.casefold()] = cid
    return alias_map


def _alias_map_sync(course_code: str | None = None) -> dict[str, str]:
    """Sync alias map from file/cache for backward compat."""
    taxonomy = load_taxonomy_sync(course_code)
    alias_map: dict[str, str] = {}
    for cid, entry in taxonomy.items():
        canon = entry.get("canonical_topic", "") if isinstance(entry, dict) else ""
        if canon and isinstance(canon, str):
            alias_map[canon.casefold().strip()] = cid
        for alias in entry.get("aliases", []) if isinstance(entry, dict) else []:
            if isinstance(alias, str):
                key = alias.casefold().strip()
                if key:
                    alias_map[key] = cid
        if isinstance(cid, str):
            alias_map[cid.casefold()] = cid
    return alias_map


# Keep original sync _alias_map name for any leftover imports (backward compat)
def _alias_map() -> dict[str, str]:  # type: ignore[override]
    return _alias_map_sync("IT2040")


async def _normalize_topic_async(raw: str | None, db=None, course_code: str | None = None) -> str | None:
    """Internal async per-course implementation."""
    if not raw or not isinstance(raw, str):
        return None
    key = raw.casefold().strip()
    if not key:
        return None
    if course_code is None:
        course_code = "IT2040"
    am = await _alias_map_for_course(db, course_code)
    if key in am:
        return am[key]
    for alias_key, cid in am.items():
        if alias_key in key or key in alias_key:
            if len(alias_key) > 5:
                return cid
    return None


def normalize_topic(raw: str | None, db=None, course_code: str | None = None):
    """Hybrid sync/async: sync when db is None (legacy), async coroutine when db provided.

    Legacy: normalize_topic("SQL") -> "sql" (sync, IT2040 file)
    Per-course: await normalize_topic("Scheduling", db, "CS3010") -> "sched"
    """
    if db is None:
        # Sync fast path for legacy callers (weakness.py, etc.) – avoids coroutine
        return _normalize_topic_sync(raw, course_code)
    # Per-course DB path – return coroutine for await
    return _normalize_topic_async(raw, db, course_code)


def _normalize_topic_sync(raw: str | None, course_code: str | None = None) -> str | None:
    """Sync variant for old callers and unmapped_topics."""
    if not raw or not isinstance(raw, str):
        return None
    key = raw.casefold().strip()
    if not key:
        return None
    am = _alias_map_sync(course_code)
    if key in am:
        return am[key]
    for alias_key, cid in am.items():
        if alias_key in key or key in alias_key:
            if len(alias_key) > 5:
                return cid
    return None


def get_canonical_topic(canonical_id: str, course_code: str | None = None) -> str | None:
    """Sync get canonical_topic; course_code optional (defaults IT2040 via sync cache)."""
    taxonomy = load_taxonomy_sync(course_code)
    entry = taxonomy.get(canonical_id)
    return entry.get("canonical_topic") if isinstance(entry, dict) else None


async def get_canonical_topic_async(canonical_id: str, db, course_code: str) -> str | None:
    taxonomy = await load_taxonomy(db, course_code)
    entry = taxonomy.get(canonical_id)
    return entry.get("canonical_topic") if isinstance(entry, dict) else None


def validate_topic_coverage(course_code: str | None = None) -> dict:
    """Return {canonical_id: {canonical_topic, alias_count, subtopic_count}} for diagnostics."""
    taxonomy = load_taxonomy_sync(course_code)
    return {
        cid: {
            "canonical_topic": entry.get("canonical_topic") if isinstance(entry, dict) else None,
            "alias_count": len(entry.get("aliases", [])) if isinstance(entry, dict) else 0,
            "subtopic_count": len(entry.get("subtopics", [])) if isinstance(entry, dict) else 0,
        }
        for cid, entry in taxonomy.items()
    }


def unmapped_topics(raw_topics: list[str], course_code: str | None = None) -> list[str]:
    """Sync unmapped topics using sync alias map (defaults IT2040)."""
    return [t for t in raw_topics if _normalize_topic_sync(t, course_code) is None]


async def invalidate_taxonomy_cache(course_code: str | None = None) -> None:
    """Invalidate TTLCache entry for course_code or all if None/empty."""
    if course_code is None:
        _cache.clear()
        return
    if not isinstance(course_code, str):
        _cache.clear()
        return
    code = course_code.strip().upper()
    if not code:
        _cache.clear()
        return
    # pop specific
    try:
        _cache.pop(code, None)
    except Exception:
        pass
    # also pop any case variants? cache is upper only, so done


def reload_cache() -> None:
    """Backward compat: clear TTLCache (and any lru caches if present)."""
    _cache.clear()
    # also clear legacy lru if they exist (during transition)
    try:
        load_taxonomy.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        _alias_map.cache_clear()  # type: ignore[attr-defined]
    except Exception:
        pass
