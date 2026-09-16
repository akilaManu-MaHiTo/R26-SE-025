"""Generate teaching action recommendations using LLM with caching."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

async def get_teaching_actions(
    db, course_code: str, session_name: str,
    canonical_topics: list[dict], question_perf: list[dict],
    year: int | None = None, month: int | None = None, semester: int | None = None,
    evidence_fingerprint: str | None = None,
) -> list[dict[str, Any]]:
    # Full exam identity + evidence fingerprint; include question evidence and model version
    try:
        from app.config import settings as _settings
        model_version = getattr(_settings, "llm_model", "unknown")
        bloom_version = getattr(_settings, "bloom_model_dir", "unknown")
    except Exception:
        model_version = "unknown"
        bloom_version = "unknown"
    payload_for_hash = {
        "course_code": course_code,
        "session_name": session_name,
        "year": year, "month": month, "semester": semester,
        "canonical_topics": canonical_topics,
        "question_perf": question_perf,
        "model_version": model_version,
        "bloom_version": bloom_version,
        "evidence_fingerprint": evidence_fingerprint,
    }
    topic_hash = hashlib.md5(
        json.dumps(payload_for_hash, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    query = {
        "course_code": course_code, "session_name": session_name,
        "year": year, "month": month, "semester": semester,
        "topics_hash": topic_hash,
    }
    # Remove None keys for flexible matching but keep full identity where present
    query = {k: v for k, v in query.items() if v is not None}
    cached = await db["teaching_actions_cache"].find_one(query)
    if cached:
        # If previous result was template fallback due to outage, retry LLM instead of permanently caching template
        if cached.get("provenance") == "template":
            try:
                fresh = await _generate_actions(canonical_topics, question_perf)
                # _generate_actions already validates; check if fresh is AI-provenance
                if fresh and any(a.get("provenance") == "ai" for a in fresh):
                    await db["teaching_actions_cache"].update_one(
                        {"_id": cached["_id"]},
                        {"$set": {"actions": fresh, "provenance": "ai", "generated_at": datetime.now(timezone.utc)}},
                    )
                    return fresh
            except Exception:
                pass
        return cached.get("actions", [])
    actions = await _generate_actions(canonical_topics, question_perf)
    provenance = "ai" if any(a.get("provenance") == "ai" for a in actions) else "template"
    # If no priority topics, actions will be empty — intentional (no invented topics)
    await db["teaching_actions_cache"].update_one(
        query,
        {"$set": {
            "course_code": course_code, "session_name": session_name,
            "year": year, "month": month, "semester": semester,
            "topics_hash": topic_hash, "actions": actions,
            "provenance": provenance,
            "model_version": model_version,
            "generated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return actions

async def _generate_actions(canonical_topics, question_perf):
    priority_topics = [t for t in canonical_topics if t.get("priority") in ("Critical", "High")]
    lowest_q = min(question_perf, key=lambda x: x["average_percentage"]) if question_perf else None
    try:
        return await _llm_generate(priority_topics, lowest_q)
    except Exception:
        return _template_fallback(priority_topics, lowest_q)

async def _llm_generate(priority_topics, lowest_question):
    from app.llm.ollama import OllamaUnavailable, generate

    # Empty priority input -> intentional no-action (do not invent topics)
    if not priority_topics and not lowest_question:
        return []
    descs = [f"- {t['topic']}: {t['average_percentage']}% ({t['priority']})" for t in priority_topics]
    if lowest_question:
        descs.append(f"- Lowest question: {lowest_question['question_id']} at {lowest_question['average_percentage']}%")
    prompt = f"""Generate 3-5 specific teaching recommendations for each Critical/High priority topic.
Topics:
{chr(10).join(descs)}
Return JSON array: [{{"topic": str, "priority": str, "performance_percentage": float, "actions": [str], "generated_at": str}}]
IMPORTANT: Use only the provided topic names and percentages. Do not invent new topics or change percentages."""
    try:
        parsed = await generate(prompt, temperature=0.2, timeout=30.0)
    except OllamaUnavailable:
        raise
    # generate() already returns parsed JSON; teaching_actions expects a list
    if isinstance(parsed, list):
        now = datetime.now(timezone.utc).isoformat()
        for item in parsed:
            item.setdefault("generated_at", now)
            item["provenance"] = "ai"
        return _validate_llm_output(parsed, priority_topics, lowest_question)
    # Some models wrap the list in a dict — handle gracefully
    if isinstance(parsed, dict) and isinstance(parsed.get("actions"), list):
        now = datetime.now(timezone.utc).isoformat()
        for item in parsed["actions"]:
            item.setdefault("generated_at", now)
            item["provenance"] = "ai"
        return _validate_llm_output(parsed["actions"], priority_topics, lowest_question)
    raise ValueError("non-array")


def _validate_llm_output(parsed: list[dict], priority_topics: list[dict], lowest_question) -> list[dict]:
    """Strictly validate LLM output: topic IDs, priorities, percentages are backend-owned evidence.
    LLM may only propose action text. Reject/repair unknown topics and malformed output."""
    backend_map = {t["topic"]: t for t in priority_topics}
    # Also allow Question <id> entry
    allowed_question_topic = f"Question {lowest_question['question_id']}" if lowest_question else None
    allowed_q_pct = lowest_question["average_percentage"] if lowest_question else None
    validated = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "")).strip()
        if not topic:
            continue
        # Check if topic is backend-owned or Question entry
        if topic in backend_map:
            backend = backend_map[topic]
            # Repair priority/percentage to backend truth, keep LLM actions only
            actions = item.get("actions")
            if not isinstance(actions, list) or not actions:
                continue
            # sanitize actions: ensure strings
            clean_actions = [str(a).strip() for a in actions if str(a).strip()]
            if not clean_actions:
                continue
            validated.append({
                "topic": topic,
                "priority": backend["priority"],
                "performance_percentage": float(backend["average_percentage"]),
                "actions": clean_actions[:5],
                "generated_at": item.get("generated_at") or datetime.now(timezone.utc).isoformat(),
                "provenance": "ai",
            })
        elif allowed_question_topic and topic == allowed_question_topic:
            actions = item.get("actions")
            if not isinstance(actions, list) or not actions:
                continue
            clean_actions = [str(a).strip() for a in actions if str(a).strip()]
            if not clean_actions:
                continue
            validated.append({
                "topic": topic,
                "priority": "High",
                "performance_percentage": float(allowed_q_pct),
                "actions": clean_actions[:5],
                "generated_at": item.get("generated_at") or datetime.now(timezone.utc).isoformat(),
                "provenance": "ai",
            })
        else:
            # Unknown topic invented by LLM — reject
            continue
    # Never present generated advice as confirmed cause; keep wording as suggestions already
    return validated

def _template_fallback(priority_topics, lowest_question):
    now = datetime.now(timezone.utc).isoformat()
    templates = {
        "Critical": [
            "Schedule additional lab sessions focused on this topic",
            "Provide supplementary reading materials and practice exercises",
            "Review prerequisite concepts before advancing",
            "Assign targeted homework to reinforce understanding",
            "Offer optional tutorial sessions",
        ],
        "High": [
            "Include more examples in lectures",
            "Create practice worksheets with step-by-step solutions",
            "Pair students for peer learning",
            "Review common misconceptions",
        ],
    }
    actions = []
    for t in priority_topics:
        actions.append({"topic": t["topic"], "priority": t["priority"],
            "performance_percentage": t["average_percentage"],
            "actions": templates.get(t["priority"], templates["High"]),
            "generated_at": now, "provenance": "template"})
    if lowest_question:
        actions.append({"topic": f"Question {lowest_question['question_id']}", "priority": "High",
            "performance_percentage": lowest_question["average_percentage"],
            "actions": ["Review question wording", "Provide worked examples", "Break into sub-parts"],
            "generated_at": now, "provenance": "template"})
    return actions
