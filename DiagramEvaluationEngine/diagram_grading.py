import json
import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_FALLBACK_MODEL = os.getenv("GROQ_FALLBACK_MODEL", "openai/gpt-oss-120b")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT_SECONDS", "120"))
GROQ_MAX_TOKENS = int(os.getenv("GROQ_MAX_TOKENS", "8192"))
DEFAULT_DIAGRAM_MAX_MARKS = float(os.getenv("DIAGRAM_MAX_MARKS", "20"))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _normalized_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = text.replace("_", " ")
    text = re.sub(r"[^\w\s-]", " ", text, flags=re.UNICODE)
    text = re.sub(r"(?<!\w)-{2,}(?!\w)", " ", text)
    text = " ".join(text.split())
    return text


_ID_SUFFIX = re.compile(r"^(?P<prefix>[a-z]+?)(?:id|identifier|no|num|number|code)$")


def _compact(value: str) -> str:
    return re.sub(r"[\W_]+", "", value).casefold()


def _canonical_identifier(label: str, entity_names: list[str] | None = None) -> str:
    """Normalize identifier formatting only (e.g. "DID", "d_id", "D ID" -> "D_Id"). The
    prefix is kept as written so a rubric's "S_ID" still matches, even when
    OCR garbled the entity name (e.g. a misspelled entity)."""
    match = _ID_SUFFIX.match(_compact(label))
    if not match:
        return label
    return f"{match.group('prefix').capitalize()}_Id"


def _normalized_text_list(values: Any) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    return sorted(
        {_normalized_text(value) for value in values if _normalized_text(value)},
        key=str.casefold,
    )


def _normalize_diagram_structure(structure: Any) -> dict[str, Any]:
    structure = structure if isinstance(structure, dict) else {}
    raw_entities = structure.get("entities", {})
    raw_relationships = structure.get("relationships", [])

    entities = {}
    if isinstance(raw_entities, dict):
        for raw_name, raw_entity in sorted(raw_entities.items(), key=lambda item: str(item[0]).casefold()):
            name = _normalized_text(raw_name)
            if not name:
                continue
            entity = raw_entity if isinstance(raw_entity, dict) else {}
            entities[name] = {
                "attributes": _normalized_text_list(entity.get("attributes", [])),
            }
            primary_keys = _normalized_text_list(entity.get("primary_keys", []))
            if primary_keys:
                entities[name]["primary_keys"] = primary_keys

    entity_names = list(entities)
    for entity in entities.values():
        for key in ("attributes", "primary_keys"):
            if key in entity:
                entity[key] = sorted(
                    {_canonical_identifier(a, entity_names) for a in entity[key]},
                    key=str.casefold,
                )
        if "primary_keys" in entity:
            # Keep primary keys in both lists: they are attributes AND keys.
            # This ensures the LLM can verify attribute presence and underline notation separately.
            for pk in entity["primary_keys"]:
                if pk not in entity["attributes"]:
                    entity["attributes"] = sorted(entity["attributes"] + [pk], key=str.casefold)

    relationships = []
    if isinstance(raw_relationships, list):
        for raw_relationship in raw_relationships:
            if not isinstance(raw_relationship, dict):
                continue
            name = _normalized_text(raw_relationship.get("name"))
            if not name:
                continue
            relationship = {
                "name": name,
                "entities": _normalized_text_list(raw_relationship.get("entities", [])),
            }
            attributes = sorted(
                {_canonical_identifier(a, entity_names) for a in _normalized_text_list(raw_relationship.get("attributes", []))},
                key=str.casefold,
            )
            if attributes:
                relationship["attributes"] = attributes
            relationships.append(relationship)
    relationships.sort(key=lambda relationship: relationship["name"].casefold())

    return {"entities": entities, "relationships": relationships}


def _diagram_structure_data(result: dict[str, Any]) -> dict[str, Any]:
    return _normalize_diagram_structure(result.get("structure"))


def _guideline_max_marks(guideline: dict[str, Any]) -> float:
    total_marks = guideline.get("totalMarks")
    if isinstance(total_marks, (int, float)) and total_marks >= 0:
        return float(total_marks)
    criteria = guideline.get("guideLines", [])
    if isinstance(criteria, list):
        marks = [
            float(item["marks"])
            for item in criteria
            if isinstance(item, dict)
            and isinstance(item.get("marks"), (int, float))
            and item["marks"] >= 0
        ]
        if marks:
            return sum(marks)
    return DEFAULT_DIAGRAM_MAX_MARKS


def _validated_criterion_results(grading: dict[str, Any], guideline: dict[str, Any]) -> list[dict[str, Any]]:
    rubric = {
        item.get("id"): item
        for item in guideline.get("guideLines", [])
        if isinstance(item, dict)
        and isinstance(item.get("id"), (int, float))
        and isinstance(item.get("marks"), (int, float))
        and item["marks"] >= 0
    }
    returned = {}
    for item in grading.get("criterion_results", []):
        if not isinstance(item, dict) or not isinstance(item.get("id"), (int, float)):
            continue
        criterion_id = item["id"]
        if criterion_id not in rubric or criterion_id in returned:
            continue
        try:
            marks = max(0.0, float(item.get("marks", 0)))
        except (TypeError, ValueError):
            marks = 0.0
        marks = min(marks, float(rubric[criterion_id]["marks"]))
        returned[criterion_id] = {
            "id": criterion_id,
            "marks": marks,
            "reason": str(item.get("reason", "")),
        }

    validated = []
    for item in guideline.get("guideLines", []):
        if not isinstance(item, dict) or item.get("id") not in rubric:
            continue
        criterion_id = item["id"]
        validated.append(returned.get(criterion_id, {
            "id": criterion_id,
            "marks": 0.0,
            "reason": "Criterion was not supported by the extracted diagram structure.",
        }))
    return validated


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("Llama 3 returned a non-object response.")
    return parsed


def _relationship_label_names(node: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(node, dict):
        if str(node.get("type", "")).casefold() == "relationship" and isinstance(node.get("name"), str):
            names.add(node["name"].strip())
        for value in node.values():
            names |= _relationship_label_names(value)
    elif isinstance(node, list):
        for value in node:
            names |= _relationship_label_names(value)
    return {name for name in names if name}


def _relax_relationship_labels(guideline: dict[str, Any]) -> dict[str, Any]:
    """Relationship labels are free-form, so strip the rubric's literal label
    (whatever it is) before grading; only the connected entities are checked."""
    names = _relationship_label_names(guideline)
    if not names:
        return guideline
    pattern = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r")(?!\w)",
        re.IGNORECASE,
    )

    def relax(node: Any) -> Any:
        if isinstance(node, str):
            return pattern.sub("<any suitable relationship label>", node)
        if isinstance(node, list):
            return [relax(v) for v in node]
        if isinstance(node, dict):
            relaxed = {k: relax(v) for k, v in node.items()}
            if str(node.get("type", "")).casefold() == "relationship":
                relaxed.pop("name", None)
                relaxed["label"] = "any suitable relationship label is acceptable"
            return relaxed
        return node

    return relax(guideline)


def grade_diagram_with_groq(
    result: dict[str, Any],
    guideline: dict[str, Any],
    progress_callback: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    guideline_json = json.dumps(_relax_relationship_labels(guideline), ensure_ascii=True, default=str)
    max_marks = _guideline_max_marks(guideline)
    structure = _diagram_structure_data(result)
    structure_json = json.dumps(structure, ensure_ascii=True, default=str)
    logger.info(
        "Groq grading started model=%s base_url=%s guideline_id=%s detection_count=%s",
        GROQ_MODEL,
        GROQ_BASE_URL,
        guideline.get("_id", "unknown"),
        len(result.get("detections", [])),
    )
    logger.info("Guideline JSON sent to Groq: %s", guideline_json)
    logger.info("GROQ_INPUT_GUIDELINE %s", guideline_json)
    logger.info("GROQ_INPUT_STRUCTURE %s", structure_json)

    if progress_callback:
        progress_callback({
            "stage": "groq_preparing",
            "message": "Preparing rubric and diagram structure for Grading...",
            "progress": 86,
        })

    prompt = f"""
You are an ER diagram grading agent powered by Groq. Grade the student's extracted diagram against the supplied marking guideline.

=== HARD RULES (apply without exception) ===
1. Use ONLY the diagram structure provided below. Never infer, assume, or hallucinate any element that is not explicitly present in the structure data.
2. Before scoring any criterion, check the structure data for each required element. If an element is absent from the data, the criterion requiring it receives ZERO marks — no exceptions, regardless of how close another element looks.
3. Award marks only when you can point to the exact entry in the structure data (entity name, attribute name, primary_key name, or relationship) that satisfies the requirement.

PRIMARY KEY RULE: Each entity's "primary_keys" list contains its primary key attributes. Primary keys also appear in the "attributes" list (they are attributes AND keys). A primary key criterion is fully satisfied when the attribute name appears in the entity's "primary_keys" list — no additional check is required. Do not deduct marks for underline notation or formatting; presence in "primary_keys" is sufficient. If the attribute name is absent from "primary_keys", the criterion gets ZERO marks.

ATTRIBUTE RULE: An attribute criterion is satisfied when the entity's "attributes" list contains an attribute that means the same thing as the rubric attribute. Accept: case, spacing, underscore and hyphen differences; the entity name being abbreviated or dropped from the attribute name (rubric "Book_Title" matches "title" or "Book Title"; rubric "Student_ID" matches "S_Id", "SID", "student id"); and OCR typos. Do NOT accept an attribute with a genuinely different meaning (e.g. "Email" does not match "Phone"). Award partial marks proportionally when only some of the required attributes are present (e.g. 2 of 3 attributes = 2/3 of the marks).

IDENTIFIER MATCHING: An identifier attribute (ID, Id, _id, bid, S_Id, etc.) belongs to the entity it is listed under. Within a single entity, "S_Id" under Student IS Student_ID and "bid" under Book IS Book_ID, because the prefix is an abbreviation of that entity's name. Only reject an identifier if it is listed under the wrong entity or clearly refers to a different entity (e.g. "C_Id" under Student when no Customer is expected). Entity names may contain OCR typos or different casing; match them to the rubric by closest meaning.

NOTATION RULE: The structure data is already extracted from the image by shape detection, so it carries no shape information. Treat an entity as a rectangle, an attribute as an oval, a relationship as a diamond, and a primary key as underlined, if and only if it appears in the structure as an entity, attribute, relationship or "primary_keys" entry respectively. The Correct ER Notation criterion therefore receives full marks when entities, attributes, relationships and primary_keys are all present in the correct categories, and partial marks when some categories are missing.

RELATIONSHIP RULE: Relationships are free-form. Judge a relationship by whether it connects the required entities and whether its label expresses a plausible association (any sensible verb phrase). Accept reasonable synonyms, spelling variants, and inflections ("Borrow" = "Borrows"). A relationship listing both required entities in its "entities" field satisfies both the Borrows Relationship and the Relationship Connections criteria. Do not deduct marks for a different-but-sensible verb.

COMPLETENESS RULE: The Overall Completeness criterion checks only structural presence. Award full marks if all required entities, attributes, primary keys and relationships are present; award partial marks if only minor items are missing; zero only if most of the structure is missing. Do not zero it merely because a single other criterion lost marks.

=== PROCESS ===
Step 1 — for each criterion, list every required element and find its match (using the matching rules above) in the structure data.
Step 2 — award marks only for elements confirmed in Step 1; give partial marks where a criterion has several required items and only some are present.
Step 3 — the "reason" for each criterion must name the structure entry matched, or state exactly what is missing. The "feedback" must only mention items that are actually missing from the structure; if nothing is missing, say the diagram meets the guideline.

Return one criterion_results entry for every rubric criterion, including failed criteria with zero marks. Use the exact criterion IDs from the marking guideline, once each, and do not return any other IDs.
The total available marks for this guideline are {max_marks:g}. Return max_marks as exactly {max_marks:g}.
Return compact JSON only with this exact shape. Do not use markdown or add extra keys:
{{
  "agent_marks": <number>,
  "max_marks": <number>,
  "criterion_results": [{{"id": <number>, "marks": <number>, "reason": "<brief reason>"}}],
  "feedback": "<brief overall feedback>"
}}

MARKING GUIDELINE:
{guideline_json}

EXTRACTED DIAGRAM STRUCTURE:
{structure_json}
""".strip()

    logger.info(
        "GROQ_REQUEST_BEGIN model=%s guideline_id=%s prompt_chars=%s",
        GROQ_MODEL,
        guideline.get("_id", "unknown"),
        len(prompt),
    )
    logger.info("GROQ_REQUEST_PROMPT\n%s\nGROQ_REQUEST_END", prompt)

    if progress_callback:
        progress_callback({
            "stage": "groq_grading",
            "message": "Grading the diagram against the guideline...",
            "progress": 92,
        })

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set.")

    request_models = [GROQ_MODEL]
    if GROQ_MODEL != GROQ_FALLBACK_MODEL:
        request_models.append(GROQ_FALLBACK_MODEL)

    text = ""
    last_error: Exception | None = None
    for model in request_models:
        logger.info("Sending grading prompt to Groq model=%s guideline_id=%s", model, guideline.get("_id", "unknown"))
        try:
            response = httpx.post(
                f"{GROQ_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": GROQ_MAX_TOKENS,
                    "response_format": {"type": "json_object"},
                },
                timeout=httpx.Timeout(connect=10.0, read=GROQ_TIMEOUT_SECONDS, write=10.0, pool=10.0),
            )
            if response.is_error:
                raise httpx.HTTPError(f"{response.status_code}: {response.text[:500]}")
            payload = response.json()
            text = str(payload["choices"][0]["message"]["content"] or "")
            logger.info("GROQ_RESPONSE_RAW model=%s %s", model, text)
            break
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            last_error = exc
            if model == request_models[-1]:
                raise RuntimeError(f"Groq grading request failed: {exc}") from exc
            logger.warning("Groq model %s failed (%s); retrying with fallback model", model, exc)
    if not text.strip():
        raise RuntimeError(f"Groq returned an empty grading response. {last_error or ''}".strip())
    grading = _extract_json(text)
    logger.info("Groq grading JSON received: %s", json.dumps(grading, ensure_ascii=True, default=str))

    try:
        grading["criterion_results"] = _validated_criterion_results(grading, guideline)
        grading["agent_marks"] = min(
            max_marks,
            sum(float(item["marks"]) for item in grading["criterion_results"]),
        )
        grading["max_marks"] = max_marks
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Groq returned invalid grading marks.") from exc

    if progress_callback:
        progress_callback({
            "stage": "groq_completed",
            "message": "Grading complete.",
            "progress": 100,
        })
    logger.info(
        "Groq grading completed guideline_id=%s agent_marks=%s max_marks=%s",
        guideline.get("_id", "unknown"),
        grading["agent_marks"],
        grading["max_marks"],
    )
    return grading