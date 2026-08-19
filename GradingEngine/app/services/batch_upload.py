"""
Stage browser-uploaded batches under uploads/batches/<batch_id>/.
Expected layout: one subfolder per student_id containing images and/or PDFs.
"""
from __future__ import annotations

import io
import os
import shutil
import zipfile
from pathlib import Path

from fastapi import UploadFile


def get_batches_root() -> Path:
    base = Path(__file__).resolve().parent.parent.parent / "uploads" / "batches"
    base.mkdir(parents=True, exist_ok=True)
    return base


def safe_relative_path(name: str) -> str | None:
    name = (name or "").replace("\\", "/").strip("/")
    if not name:
        return None
    parts = name.split("/")
    if ".." in parts:
        return None
    return name


def _ensure_under_root(root: Path, dest: Path) -> bool:
    try:
        dest.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def extract_zip_to_batch(zip_bytes: bytes, batch_id: str) -> Path:
    root = get_batches_root() / batch_id
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.infolist():
            if member.is_dir():
                continue
            rel = safe_relative_path(member.filename)
            if not rel:
                continue
            dest = (root / rel).resolve()
            if not _ensure_under_root(root, dest):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, "r") as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)

    return root


async def write_multipart_files_to_batch(files: list[UploadFile], batch_id: str) -> Path:
    root = get_batches_root() / batch_id
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    wrote = 0
    for uf in files:
        rel = safe_relative_path(uf.filename or "")
        if not rel:
            continue
        dest = (root / rel).resolve()
        if not _ensure_under_root(root, dest):
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = await uf.read()
        if not body:
            continue
        dest.write_bytes(body)
        wrote += 1

    if wrote == 0:
        shutil.rmtree(root, ignore_errors=True)
        raise ValueError("No valid files were written (check paths / webkitRelativePath).")

    return root


def resolve_batch_directory(batch_id: str) -> Path:
    root = get_batches_root()
    candidate = (root / batch_id.strip()).resolve()
    if not _ensure_under_root(root.resolve(), candidate):
        raise ValueError("Invalid batch_id")
    if not candidate.is_dir():
        raise FileNotFoundError("Batch directory not found")
    return candidate


def resolve_effective_batch_root(batch_dir: Path) -> Path:
    """
    Unwrap a single top-level folder when it only contains student subfolders.

    Example: ``<batch_id>/batch1/IT22145976/...`` → use ``.../batch1`` so
    ``run_batch_grading`` sees ``IT22145976`` as immediate children.

    Does **not** unwrap when the single folder holds loose files (e.g. one
    student folder ``IT123`` with ``page.jpg`` inside — those are files, not
    only nested dirs).

    Metadata files/dirs (names starting with ``_`` or ``.``) are ignored so
    that ``_id_scan.json`` does not block unwrapping.
    """
    current = batch_dir.resolve()
    if not current.is_dir():
        return current

    def _is_meta(name: str) -> bool:
        return (not name) or name.startswith(".") or name.startswith("_")

    while True:
        try:
            children = [p for p in current.iterdir() if not _is_meta(p.name)]
        except OSError:
            break
        dirs = [p for p in children if p.is_dir()]
        files = [p for p in children if p.is_file()]
        if len(files) != 0 or len(dirs) != 1:
            break
        sole = dirs[0]
        try:
            inner = [p for p in sole.iterdir() if not _is_meta(p.name)]
        except OSError:
            break
        inner_dirs = [p for p in inner if p.is_dir()]
        inner_files = [p for p in inner if p.is_file()]
        if len(inner_dirs) >= 1 and len(inner_files) == 0:
            current = sole
            continue
        break

    return current


def count_student_folders(batch_dir: Path) -> int:
    if not batch_dir.is_dir():
        return 0
    n = 0
    for name in os.listdir(batch_dir):
        if (batch_dir / name).is_dir():
            n += 1
    return n
