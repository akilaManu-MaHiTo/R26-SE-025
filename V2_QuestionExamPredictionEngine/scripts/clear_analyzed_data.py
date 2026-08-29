"""
Clear derived/analyzed data to start fresh. Keeps source collections.
Preserved: courses, rubricCollection, submissions, exam_drafts, users, exams, questions, rubrics
Derived (will be DELETED if --confirm): student_analytics, studentExamAnalysis, studentExamResults,
  analytics_snapshots, examAnalytics, analyzedExams, generatedQuestions, question_catalog,
  question_attempts, exam_recommendations, analysis_runs, teaching_actions_cache
Usage:
  python scripts/clear_analyzed_data.py              # dry-run counts
  python scripts/clear_analyzed_data.py --confirm    # actually delete
  python scripts/clear_analyzed_data.py --confirm --db grading
  python scripts/clear_analyzed_data.py --confirm --uri "mongodb://..."
"""
import argparse, os, sys
from pathlib import Path
try:
    import pymongo
except ImportError:
    print("pymongo not installed. pip install pymongo")
    sys.exit(1)

# Preserved vs derived
PRESERVED = {"courses","rubricCollection","submissions","exam_drafts","users","exams","questions","rubrics"}
DERIVED = [
    "student_analytics","studentExamAnalysis","studentExamResults",
    "analytics_snapshots","examAnalytics","analyzedExams",
    "generatedQuestions","question_catalog","question_attempts",
    "exam_recommendations","analysis_runs","teaching_actions_cache",
    # extra aliases seen in code
    "generated_questions",
]

def load_env():
    env = {}
    p = Path(__file__).resolve().parents[1] / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v=line.split("=",1); env[k.strip()]=v.strip()
    return env

def get_uri_and_db(args):
    env = load_env()
    if args.uri: return args.uri, args.db
    mode = env.get("MONGODB_MODE","local")
    db = args.db or env.get("MONGODB_DB","grading")
    if mode == "local":
        uri = env.get("MONGODB_LOCAL_URI","mongodb://127.0.0.1:27017")
    else:
        uri = env.get("MONGODB_URI","")
    if args.uri: uri=args.uri
    return uri, db

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="actually delete")
    ap.add_argument("--uri", default=None)
    ap.add_argument("--db", default=None)
    ap.add_argument("--yes-source", action="store_true", help="also wipe source (DANGEROUS)")
    args = ap.parse_args()
    uri, dbname = get_uri_and_db(args)
    if not uri:
        print("No URI. Set MONGODB_URI or use --uri")
        sys.exit(2)
    print(f"Connecting to {uri[:40]}... db={dbname} mode={'confirm' if args.confirm else 'dry-run'}")
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8000)
    try: client.admin.command("ping")
    except Exception as e: print(f"Cannot connect: {e}"); sys.exit(3)
    db = client[dbname]
    existing = set(db.list_collection_names())
    print(f"\nExisting collections: {sorted(existing)}")
    print(f"Preserved (never deleted): {sorted(PRESERVED & existing)}")
    to_clear = [c for c in DERIVED if c in existing]
    missing = [c for c in DERIVED if c not in existing]
    if missing: print(f"Missing (skip): {missing}")
    if not to_clear:
        print("\nNothing to clear. Already fresh.")
        return
    print("\nCounts (dry-run):")
    for c in to_clear:
        try: n = db[c].count_documents({})
        except Exception as e: n=f"err {e}"
        print(f"  {c}: {n}")
    if not args.confirm:
        print("\nDry-run done. Re-run with --confirm to DELETE above derived collections.")
        print("Example: python scripts/clear_analyzed_data.py --confirm")
        return
    print("\nDeleting...")
    for c in to_clear:
        before = db[c].count_documents({})
        db[c].delete_many({})
        after = db[c].count_documents({})
        print(f"  {c}: {before} -> {after} (deleted {before-after})")
    print("\nDone. Source collections untouched. Verify with:")
    print(f"  mongosh '{uri}' --eval 'db.getSiblingDB(\"{dbname}\").getCollectionNames()'")

if __name__ == "__main__": main()
