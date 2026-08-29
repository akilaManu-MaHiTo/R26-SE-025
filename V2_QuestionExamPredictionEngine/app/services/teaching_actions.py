"""Generate teaching action recommendations using LLM with caching."""
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from typing import Any
from app.config import settings

async def get_teaching_actions(
    db, course_code: str, session_name: str,
    canonical_topics: list[dict], question_perf: list[dict]
) -> list[dict[str, Any]]:
    topic_hash = hashlib.md5(
        json.dumps(canonical_topics, sort_keys=True, default=str).encode()
    ).hexdigest()[:12]
    cached = await db["teaching_actions_cache"].find_one({
        "course_code": course_code, "session_name": session_name, "topics_hash": topic_hash
    })
    if cached:
        return cached.get("actions", [])
    actions = await _generate_actions(canonical_topics, question_perf)
    await db["teaching_actions_cache"].update_one(
        {"course_code": course_code, "session_name": session_name},
        {"$set": {
            "course_code": course_code, "session_name": session_name,
            "topics_hash": topic_hash, "actions": actions,
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
    import httpx
    descs = [f"- {t['topic']}: {t['average_percentage']}% ({t['priority']})" for t in priority_topics]
    if lowest_question:
        descs.append(f"- Lowest question: {lowest_question['question_id']} at {lowest_question['average_percentage']}%")
    prompt = f"""Generate 3-5 specific teaching recommendations for each Critical/High priority topic.
Topics:
{chr(10).join(descs)}
Return JSON array: [{{"topic": str, "priority": str, "performance_percentage": float, "actions": [str], "generated_at": str}}]"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{settings.ollama_base_url}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False, "format": "json"})
        resp.raise_for_status()
        parsed = json.loads(resp.json().get("response", "[]"))
        if isinstance(parsed, list):
            now = datetime.now(timezone.utc).isoformat()
            for item in parsed:
                item.setdefault("generated_at", now)
            return parsed
        raise ValueError("non-array")

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
            "generated_at": now})
    if lowest_question:
        actions.append({"topic": f"Question {lowest_question['question_id']}", "priority": "High",
            "performance_percentage": lowest_question["average_percentage"],
            "actions": ["Review question wording", "Provide worked examples", "Break into sub-parts"],
            "generated_at": now})
    return actions
