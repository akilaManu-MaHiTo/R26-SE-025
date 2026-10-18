"""Deprecated shim — real implementation moved to archive/migrate_sample_v2.py."""
import importlib.util
import pathlib
import sys

_archive = pathlib.Path(__file__).resolve().parent / "archive" / "migrate_sample_v2.py"
spec = importlib.util.spec_from_file_location("archive.migrate_sample_v2", _archive)
mod = importlib.util.module_from_spec(spec)  # type: ignore
sys.modules[__name__] = mod
spec.loader.exec_module(mod)  # type: ignore
