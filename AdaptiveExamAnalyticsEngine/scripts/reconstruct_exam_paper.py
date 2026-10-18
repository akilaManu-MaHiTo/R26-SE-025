"""Read-only reconstruction; console output omits student data by default."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bson.json_util import CANONICAL_JSON_OPTIONS, dumps
from pymongo.errors import PyMongoError

from app.api.deps import _get_client, get_db
from app.config import settings
from app.db.repository import load_exam_paper_sources
from app.services.exam_paper import reconstruct_exam_paper, reconstruction_summary


async def reconstruct(exam_key):
    try:
        sources = await asyncio.wait_for(load_exam_paper_sources(get_db(), exam_key), timeout=30)
        return reconstruct_exam_paper(exam_key, sources)
    finally:
        _get_client().close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exam_key", help="Exact examkeys.examKey; never inferred from a filename")
    parser.add_argument("--include-student-data", action="store_true",
                        help="Export student IDs, saved answer excerpts and grading results. Default: counts/statuses only.")
    parser.add_argument("--output", type=Path, help="Write a NEW local JSON file; never overwrite an existing file")
    args = parser.parse_args()
    try:
        paper = asyncio.run(reconstruct(args.exam_key))
        if args.include_student_data:
            # Extended JSON preserves ObjectIds, timestamps and nonfinite source marks.
            output = dumps(paper, json_options=CANONICAL_JSON_OPTIONS, indent=2)
        else:
            output = json.dumps({"database": settings.mongodb_db, **reconstruction_summary(paper)}, indent=2)
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(output + "\n")
        else:
            print(output)
        return 0 if paper["validation"]["status"] == "valid" else 2
    except (PyMongoError, OSError, TimeoutError) as exc:
        # Connection exceptions may embed credentials/hosts. Never print their text.
        print(f"Reconstruction failed ({type(exc).__name__}); check connectivity, settings or output path.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
