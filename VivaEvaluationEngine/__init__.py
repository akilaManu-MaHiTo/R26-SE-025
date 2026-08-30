"""Makes VivaEvaluationEngine importable as a package from anywhere.

Every internal module uses absolute imports written as if this directory
were the sys.path root (``from services.x import y``, ``from config import
...``), so external callers historically had to append this directory to
sys.path themselves before importing anything from here (see git history of
Gradex_AI_Server/app/viva_service.py). Registering it here instead means
that side effect happens exactly once, as part of importing this package,
regardless of who imports it or what their own CWD is.
"""
import sys
from pathlib import Path

_ENGINE_ROOT = Path(__file__).resolve().parent
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))
