from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.taxonomy.normalizer import invalidate_taxonomy_cache, slugify_topic

router = APIRouter(prefix="/api/courses", tags=["taxonomy"])


class TopicPayload(BaseModel):
    canonical_topic: str = Field(min_length=3, max_length=120)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    subtopics: list[str] = Field(default_factory=list, max_length=50)


def _validate_payload(payload: TopicPayload, existing_topics: dict, current_id: str | None):
    ct = payload.canonical_topic.strip()
    if not ct:
        raise HTTPException(status_code=400, detail="canonical_topic required")
    if len(ct) < 3 or len(ct) > 120:
        raise HTTPException(status_code=400, detail="canonical_topic must be 3-120 chars")
    # aliases trim dedup
    cleaned_aliases: list[str] = []
    seen: set[str] = set()
    for a in payload.aliases:
        if not isinstance(a, str):
            raise HTTPException(status_code=400, detail="alias must be string")
        aa = a.strip()
        if not aa:
            continue
        if len(aa) < 2 or len(aa) > 100:
            raise HTTPException(status_code=400, detail=f"alias '{aa}' must be 2-100 chars")
        k = aa.casefold()
        if k == ct.casefold():
            raise HTTPException(status_code=400, detail="alias cannot equal canonical_topic")
        if k in seen:
            continue
        seen.add(k)
        cleaned_aliases.append(aa)

    # cross-topic alias duplicate + canonical duplicate check
    all_aliases: dict[str, str] = {}
    for cid, entry in existing_topics.items():
        if current_id and cid == current_id:
            continue
        if not isinstance(entry, dict):
            continue
        canon = entry.get("canonical_topic", "")
        if isinstance(canon, str) and canon.strip():
            key = canon.strip().casefold()
            if key:
                all_aliases[key] = cid
        for al in entry.get("aliases", []) or []:
            if isinstance(al, str) and al.strip():
                k2 = al.strip().casefold()
                if k2:
                    all_aliases[k2] = cid
    for al in cleaned_aliases:
        if al.casefold() in all_aliases:
            raise HTTPException(status_code=409, detail=f"alias '{al}' already used in topic '{all_aliases[al.casefold()]}'")

    # subtopics
    cleaned_sub: list[str] = []
    seen2: set[str] = set()
    for s in payload.subtopics:
        if not isinstance(s, str):
            raise HTTPException(status_code=400, detail="subtopic must be string")
        ss = s.strip()
        if not ss:
            continue
        if len(ss) < 2 or len(ss) > 200:
            raise HTTPException(status_code=400, detail=f"subtopic '{ss}' must be 2-200 chars")
        k3 = ss.casefold()
        if k3 in seen2:
            continue
        seen2.add(k3)
        cleaned_sub.append(ss)
    if len(cleaned_sub) > 50:
        raise HTTPException(status_code=400, detail="subtopics max 50")
    if len(cleaned_aliases) > 20:
        raise HTTPException(status_code=400, detail="aliases max 20")
    return ct, cleaned_aliases, cleaned_sub


@router.get("/{course_code}/taxonomy")
async def get_taxonomy(course_code: str, db=Depends(get_db)):
    course_code = course_code.strip().upper()
    course = await db["courses"].find_one({"code": course_code})
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{course_code}' not found. Create course first.")
    from app.db.repository import get_course_taxonomy, seed_it2040_if_empty

    if course_code == "IT2040":
        try:
            await seed_it2040_if_empty(db)
        except Exception:
            pass
    doc = await get_course_taxonomy(db, course_code)
    if not doc:
        return {"course_code": course_code, "version": 0, "topics": {}, "updated_at": None}
    return {
        "course_code": doc["course_code"],
        "version": doc.get("version", 0),
        "topics": doc.get("topics", {}),
        "updated_at": doc.get("updated_at"),
    }


@router.put("/{course_code}/taxonomy/{canonical_id}")
async def upsert_topic(
    course_code: str,
    canonical_id: str,
    payload: TopicPayload,
    db=Depends(get_db),
    if_match: Optional[str] = Header(None, alias="If-Match"),
):
    course_code = course_code.strip().upper()
    course = await db["courses"].find_one({"code": course_code})
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{course_code}' not found.")
    from app.db.repository import get_course_taxonomy, upsert_course_taxonomy

    doc = await get_course_taxonomy(db, course_code)
    topics = dict(doc["topics"]) if doc and isinstance(doc.get("topics"), dict) else {}
    version = int(doc["version"]) if doc and "version" in doc else 0
    if if_match is not None and str(version) != str(if_match).strip():
        raise HTTPException(status_code=409, detail="Version conflict, refresh and retry")
    # slug handling
    target_id = canonical_id.strip().lower()
    if target_id in ("new", "__new"):
        target_id = slugify_topic(payload.canonical_topic)
    if not target_id or len(target_id) < 2 or len(target_id) > 64:
        raise HTTPException(status_code=400, detail="canonical_id 2-64 chars")
    # uniqueness canonical_topic per course case-insensitive
    for cid, entry in topics.items():
        if cid != target_id and isinstance(entry, dict):
            existing_canon = entry.get("canonical_topic", "")
            if isinstance(existing_canon, str) and existing_canon.strip().casefold() == payload.canonical_topic.strip().casefold():
                raise HTTPException(status_code=409, detail=f"Topic '{payload.canonical_topic.strip()}' already exists as '{cid}'")
    # uniqueness canonical_id already validated via above? also check case-insensitive id duplicate
    # if target_id casefold matches existing different id, treat as duplicate (though ids are slug lower)
    for cid in list(topics.keys()):
        if cid.casefold() == target_id.casefold() and cid != target_id:
            raise HTTPException(status_code=409, detail=f"canonical_id '{target_id}' already exists as '{cid}'")

    ct, cleaned_aliases, cleaned_sub = _validate_payload(payload, topics, target_id)
    topics[target_id] = {"canonical_topic": ct, "aliases": cleaned_aliases, "subtopics": cleaned_sub}
    new_doc = await upsert_course_taxonomy(db, course_code, topics, updated_by="lecturer")
    await invalidate_taxonomy_cache(course_code)
    return {"canonical_id": target_id, "version": new_doc["version"], "topic": topics[target_id]}


@router.delete("/{course_code}/taxonomy/{canonical_id}")
async def delete_topic(course_code: str, canonical_id: str, db=Depends(get_db)):
    course_code = course_code.strip().upper()
    course = await db["courses"].find_one({"code": course_code})
    if not course:
        raise HTTPException(status_code=404, detail=f"Course '{course_code}' not found.")
    from app.db.repository import find_taxonomy_usage_count, get_course_taxonomy, upsert_course_taxonomy

    doc = await get_course_taxonomy(db, course_code)
    if not doc or canonical_id not in (doc.get("topics") or {}):
        raise HTTPException(status_code=404, detail="topic not found")
    topics = dict(doc["topics"])
    topics.pop(canonical_id)
    warning = None
    cnt = await find_taxonomy_usage_count(db, course_code, canonical_id)
    if cnt and cnt > 0:
        warning = f"Used in {cnt} exam snapshots — will be Stale until Reanalyse"
    new_doc = await upsert_course_taxonomy(db, course_code, topics, updated_by="lecturer")
    await invalidate_taxonomy_cache(course_code)
    return {"deleted": True, "canonical_id": canonical_id, "version": new_doc["version"], "warning": warning}


@router.post("/{course_code}/taxonomy/seed")
async def seed_taxonomy(course_code: str, db=Depends(get_db)):
    course_code = course_code.strip().upper()
    from app.db.repository import get_course_taxonomy, seed_it2040_if_empty

    if course_code != "IT2040":
        raise HTTPException(status_code=400, detail="seed only for IT2040")
    doc = await seed_it2040_if_empty(db)
    if not doc:
        doc = await get_course_taxonomy(db, course_code)
        # also try direct find if get_course_taxonomy mocked to None but DB has doc
        if not doc:
            try:
                doc = await db["course_taxonomies"].find_one({"course_code": course_code}, {"_id": 0})
            except Exception:
                doc = None
    if doc:
        try:
            await invalidate_taxonomy_cache(course_code)
        except Exception:
            pass
    return doc
