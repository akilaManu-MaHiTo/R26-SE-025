import json
import logging
import os
import re
import unicodedata
from typing import Any, Callable

import httpx


OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "512"))
OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "4096"))
OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "llama3:latest")
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


def grade_diagram_with_ollama(
    result: dict[str, Any],
    guideline: dict[str, Any],
    progress_callback: Callable[[dict], None] | None = None,
) -> dict[str, Any]:
    guideline_json = json.dumps(_relax_relationship_labels(guideline), ensure_ascii=True, default=str)
    max_marks = _guideline_max_marks(guideline)
    structure = _diagram_structure_data(result)
    structure_json = json.dumps(structure, ensure_ascii=True, default=str)
    logger.info(
        "Ollama grading started model=%s base_url=%s guideline_id=%s detection_count=%s",
        OLLAMA_MODEL,
        OLLAMA_BASE_URL,
        guideline.get("_id", "unknown"),
        len(result.get("detections", [])),
    )
    logger.info("Guideline JSON sent to Ollama: %s", guideline_json)
    logger.info("OLLAMA_INPUT_GUIDELINE %s", guideline_json)
    logger.info("OLLAMA_INPUT_STRUCTURE %s", structure_json)

    if progress_callback:
        progress_callback({
            "stage": "ollama_preparing",
            "message": "Preparing rubric and diagram structure for Grading...",
            "progress": 86,
        })

    prompt = f"""
You are an ER diagram grading agent running locally with Ollama. Grade the student's extracted diagram against the supplied marking guideline.

=== HARD RULES (apply without exception) ===
1. Use ONLY the diagram structure provided below. Never infer, assume, or hallucinate any element that is not explicitly present in the structure data.
2. Before scoring any criterion, check the structure data for each required element. If an element is absent from the data, the criterion requiring it receives ZERO marks — no exceptions, regardless of how close another element looks.
3. Award marks only when you can point to the exact entry in the structure data (entity name, attribute name, primary_key name, or relationship) that satisfies the requirement.

PRIMARY KEY RULE: Each entity's "primary_keys" list contains its primary key attributes. Primary keys also appear in the "attributes" list (they are attributes AND keys). A primary key criterion is fully satisfied when the attribute name appears in the entity's "primary_keys" list — no additional check is required. Do not deduct marks for underline notation or formatting; presence in "primary_keys" is sufficient. If the attribute name is absent from "primary_keys", the criterion gets ZERO marks.

ATTRIBUTE RULE: An attribute criterion (non-primary-key) is satisfied ONLY when the attribute name (allowing only OCR-level formatting differences: case, spaces, underscores, hyphens between the same tokens) appears in the entity's "attributes" list. A differently-named attribute — even one that sounds similar — is NOT a match. Do NOT accept a substitute.

IDENTIFIER MATCHING (OCR formatting only): For identifier-style attributes (those ending in _ID, _Id, ID, etc.), treat these as the same attribute only when they share the same prefix token: S_ID, S_Id, SID, S ID are all the same; C_ID and S_ID are different identifiers and must never be cross-matched. Entity names may contain OCR typos; match entity names to the rubric by closest meaning, but still require the attribute to be present under that entity.

RELATIONSHIP RULE: Relationships are free-form. Judge a relationship by whether it connects the required entities and whether its label expresses a plausible association (any sensible verb phrase). Accept reasonable synonyms, spelling variants, and inflections. Do not deduct marks for a different-but-sensible verb.

COMPLETENESS RULE: The Overall Completeness criterion checks only structural presence

=== PROCESS ===
Step 1 — for each criterion, list every required element and check whether it appears in the structure data.
Step 2 — award marks only for elements confirmed in Step 1.
Step 3 — if any criterion failed, set Overall Completeness to zero.

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
        "OLLAMA_REQUEST_BEGIN model=%s guideline_id=%s prompt_chars=%s",
        OLLAMA_MODEL,
        guideline.get("_id", "unknown"),
        len(prompt),
    )
    logger.info("OLLAMA_REQUEST_PROMPT\n%s\nOLLAMA_REQUEST_END", prompt)

    if progress_callback:
        progress_callback({
            "stage": "ollama_grading",
            "message": "Grading the diagram against the guideline...",
            "progress": 92,
        })

    request_models = [OLLAMA_MODEL]
    if OLLAMA_MODEL != OLLAMA_FALLBACK_MODEL:
        request_models.append(OLLAMA_FALLBACK_MODEL)

    response_payload = None
    last_error = None
    for model in request_models:
        logger.info("Sending grading prompt to Ollama model=%s guideline_id=%s", model, guideline.get("_id", "unknown"))
        try:
            response = httpx.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": model,
                "prompt": prompt,
                "stream": False,
                "format": {
                    "type": "object",
                    "properties": {
                        "agent_marks": {"type": "number"},
                            "max_marks": {"type": "number"},
                        "criterion_results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "number"},
                                    "marks": {"type": "number"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["id", "marks", "reason"],
                                "additionalProperties": False,
                            },
                        },
                        "feedback": {"type": "string"},
                    },
                    "required": ["agent_marks", "max_marks", "criterion_results", "feedback"],
                    "additionalProperties": False,
                },
                "think": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0,
                    "top_k": 20,
                    "num_ctx": OLLAMA_NUM_CTX,
                    "num_predict": OLLAMA_NUM_PREDICT,
                },
                },
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=OLLAMA_TIMEOUT_SECONDS,
                    write=10.0,
                    pool=10.0,
                ),
            )
            response.raise_for_status()
            response_payload = response.json()
            text = str(response_payload.get("response", ""))
            logger.info(
                "OLLAMA_RESPONSE_STATUS model=%s done=%s done_reason=%s response_chars=%s",
                model,
                response_payload.get("done"),
                response_payload.get("done_reason"),
                len(text),
            )
            logger.info("OLLAMA_RESPONSE_RAW model=%s %s", model, text)
            break
        except httpx.ReadTimeout as exc:
            last_error = exc
            if model == request_models[-1]:
                raise RuntimeError(
                    f"Ollama grading timed out for models: {', '.join(request_models)}"
                ) from exc
            logger.warning(
                "Ollama model timed out; retrying with fallback model=%s",
                OLLAMA_FALLBACK_MODEL,
            )
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f"Ollama grading request failed: {exc}") from exc
    if response_payload is None:
        raise RuntimeError(f"Ollama grading request failed: {last_error}")
    if not text.strip():
        raise RuntimeError("Qwen returned an empty grading response.")
    grading = _extract_json(text)
    logger.info("Ollama grading JSON received: %s", json.dumps(grading, ensure_ascii=True, default=str))

    try:
        grading["criterion_results"] = _validated_criterion_results(grading, guideline)
        grading["agent_marks"] = min(
            max_marks,
            sum(float(item["marks"]) for item in grading["criterion_results"]),
        )
        grading["max_marks"] = max_marks
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("Qwen returned invalid grading marks.") from exc

    if progress_callback:
        progress_callback({
            "stage": "ollama_completed",
            "message": "Grading complete.",
            "progress": 100,
        })
    logger.info(
        "Ollama grading completed guideline_id=%s agent_marks=%s max_marks=%s",
        guideline.get("_id", "unknown"),
        grading["agent_marks"],
        grading["max_marks"],
    )
    return grading