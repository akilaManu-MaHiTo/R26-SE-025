"""Lecturer management of the exam identities used by grading."""
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pymongo.errors import DuplicateKeyError, PyMongoError

from Gradex_AI_Server.app.auth import require_lecturer
from Gradex_AI_Server.app.mongodb import get_exam_keys_collection

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/exam-keys", dependencies=[Depends(require_lecturer)])
RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ExamKeyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subjectCode: RequiredText
    subjectName: RequiredText
    examYear: int = Field(ge=1900, le=9999, strict=True)
    examSemester: Literal[1, 2]
    examMonth: Literal[
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ]
    session: Literal["Final", "Mid Term"]
    examStructure: list[RequiredText] = Field(min_length=1, max_length=100)


@router.get("")
def list_exam_keys():
    try:
        return list(get_exam_keys_collection().find({}, {"_id": 0}).sort([
            ("examYear", -1), ("subjectCode", 1), ("examKey", 1),
        ]))
    except (PyMongoError, RuntimeError) as exc:
        logger.exception("Failed to list exam keys")
        raise HTTPException(503, "Could not load exam keys. Please retry.") from exc


@router.post("", status_code=201)
def create_exam_key(payload: ExamKeyPayload):
    record = payload.model_dump()
    session = payload.session.replace(" ", "").upper()
    record["examKey"] = f"EXAM-{payload.subjectCode}-{payload.examYear}-S{payload.examSemester}-{payload.examMonth[:3]}-{session}"
    try:
        collection = get_exam_keys_collection()
        collection.create_index("examKey", unique=True)
        collection.create_index([
            ("subjectCode", 1), ("examYear", 1), ("examMonth", 1),
            ("examSemester", 1), ("session", 1),
        ], unique=True)
        collection.insert_one(record.copy())
    except DuplicateKeyError as exc:
        raise HTTPException(409, "An exam key or these exam details already exist. Check the saved keys for duplicates.") from exc
    except (PyMongoError, RuntimeError) as exc:
        logger.exception("Failed to create exam key")
        raise HTTPException(503, "Could not save the exam key. Please retry.") from exc
    return record
