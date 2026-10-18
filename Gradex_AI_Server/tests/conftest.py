import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_ENGINE_ROOT = PROJECT_ROOT / "AdaptiveExamAnalyticsEngine"
for path in (PROJECT_ROOT, ANALYTICS_ENGINE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)
