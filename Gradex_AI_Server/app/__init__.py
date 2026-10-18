"""Gradex application package with access to the analytics subpackages."""

import sys
from pathlib import Path


sys.modules.setdefault("app", sys.modules[__name__])

_analytics_app = (
    Path(__file__).resolve().parents[2]
    / "AdaptiveExamAnalyticsEngine"
    / "app"
)
if _analytics_app.is_dir():
    _analytics_app_path = str(_analytics_app)
    if _analytics_app_path not in __path__:
        __path__.append(_analytics_app_path)
