"""Explicit, repeatable import of local PDFs into the analytics-owned course index."""
import argparse
import json
from pathlib import Path
import re
import sys

ENGINE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ENGINE_ROOT))

from app.services.course_rag import CourseRag


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--course", default="IT2040")
    parser.add_argument("--root", type=Path, help="Folder containing lectures/, tutorial/, and Final exam/")
    parser.add_argument("--index", type=Path, help="Analytics SQLite index path")
    parser.add_argument("--keyword-only", action="store_true", help="Skip embedding model; explicitly use keyword retrieval")
    parser.add_argument("--rebuild", action="store_true", help="Re-extract unchanged PDFs and rebuild vectors")
    args = parser.parse_args(argv)
    if args.course.upper() != "IT2040" and args.root is None:
        parser.error("Other courses require an explicit --root; the bundled corpus belongs to IT2040")
    root = args.root or ENGINE_ROOT / "datasets" / "bloom_dataset"
    rag = CourseRag(args.index, semantic=False if args.keyword_only else None)
    reports, failures = [], []
    for folder, kind in [("lectures", "lecture"), ("tutorial", "tutorial"), ("Final exam", "exam")]:
        paths = sorted((root / folder).glob("*.pdf"))
        if not paths:
            failures.append({"folder": str(root / folder), "error": "No PDFs found"})
        for path in paths:
            year_match = re.search(r"\b(?:19|20)\d{2}\b", path.stem.replace("_", " "))
            year = int(year_match[0]) if year_match else None
            try:
                report = rag.index_pdf(path, args.course, kind, year, rebuild=args.rebuild)
                reports.append({"kind": kind, **report})
                print(json.dumps(reports[-1]), flush=True)
            except Exception as exc:
                failures.append({"filename": path.name, "error": str(exc)})
                print(json.dumps(failures[-1]), flush=True)
    summary = {"course_code": args.course.upper(), "index": str(rag.index_path),
               "documents": len(reports), "indexed": sum(r["status"] == "indexed" for r in reports),
               "unchanged": sum(r["status"] == "unchanged" for r in reports),
               "pages": sum(r.get("pages", 0) for r in reports),
               "chunks": sum(r.get("chunks", 0) for r in reports), "failures": failures,
               "extraction": "Text only; no OCR or diagram interpretation."}
    print(json.dumps(summary, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
