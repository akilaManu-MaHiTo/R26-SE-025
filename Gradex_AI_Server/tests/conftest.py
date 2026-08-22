import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
V2_ROOT = PROJECT_ROOT / "V2_QuestionExamPredictionEngine"
for path in (PROJECT_ROOT, V2_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)