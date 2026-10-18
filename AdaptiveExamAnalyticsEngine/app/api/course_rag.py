"""Lecturer-only access to the analytics engine's independent material index."""
from contextlib import contextmanager
import sqlite3
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, Path, UploadFile
from fastapi.responses import Response

from app.schemas.course_rag import SearchRequest, SearchResult, DocumentType, MaterialInventory
from app.services.course_rag import get_course_rag
from app.embeddings.embedder import EmbeddingUnavailable

router = APIRouter(prefix="/lecturers/materials", tags=["course materials"])
MAX_PDF_BYTES = 20 * 1024 * 1024
DocumentId = Path(pattern=r"^[a-f0-9]{24}$")


@contextmanager
def material_errors():
    try:
        yield
    except FileExistsError as exc:
        raise HTTPException(409, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except EmbeddingUnavailable as exc:
        raise HTTPException(503, "Embedding model unavailable. Existing materials are unchanged; check the analytics embedding dependencies.") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise HTTPException(503, "Material storage or indexing failed. Existing indexed material has been preserved; retry after checking the server.") from exc


def require_document(document_id):
    inventory = get_course_rag().list_documents()
    if inventory.status != "ok":
        raise HTTPException(503, inventory.warnings[0])
    item = next((item for item in inventory.items if item.document_id == document_id), None)
    if item is None:
        raise HTTPException(404, "Material not found")
    return item


def read_pdf(file):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(422, "Only PDF files are supported")
    content = file.file.read(MAX_PDF_BYTES + 1)
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF must be 20 MB or smaller")
    if not content.startswith(b"%PDF"):
        raise HTTPException(422, "The uploaded file is not a valid PDF")
    return content


@router.get("", response_model=MaterialInventory)
def list_materials():
    return get_course_rag().list_documents()


@router.post("", status_code=201)
def upload_material(file: UploadFile = File(...), course_code: str = Form(...),
                    document_type: DocumentType = Form(...), year: int | None = Form(None, ge=1900, le=2200)):
    content = read_pdf(file)
    with material_errors():
        report = get_course_rag().index_bytes(content, file.filename, course_code, document_type, year, overwrite=False)
        return {"item": require_document(report["document_id"]), "status": report["status"]}


@router.put("/{document_id}")
def replace_material(document_id: str = DocumentId, file: UploadFile = File(...)):
    item = require_document(document_id)
    content = read_pdf(file)
    with material_errors():
        report = get_course_rag().index_bytes(content, item.filename, item.course_code, item.document_type,
            item.year, require_existing=True)
        return {"item": require_document(document_id), "status": report["status"]}


@router.delete("/{document_id}")
def remove_material(document_id: str = DocumentId):
    with material_errors():
        if not get_course_rag().delete_document(document_id):
            raise HTTPException(404, "Material not found")
    return {"removed": document_id}


@router.get("/{document_id}/pdf")
def download_material(document_id: str = DocumentId):
    item = require_document(document_id)
    with material_errors():
        content = get_course_rag().document_pdf(document_id)
    if content is None:
        raise HTTPException(404, "Original PDF unavailable. Reimport this source PDF to attach it to the existing index.")
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(item.filename, safe='')}",
        "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
        "Content-Security-Policy": "sandbox",
    })


@router.post("/search", response_model=SearchResult)
def search_materials(payload: SearchRequest):
    # A sync route keeps PDF-model/SQLite work off the async event loop.
    return get_course_rag().search(payload)
