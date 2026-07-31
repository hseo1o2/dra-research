"""Ensure open_deep_research.src is on sys.path before any test collects."""
import sys
from pathlib import Path

_ODR_SRC = str(Path(__file__).parent / "open_deep_research" / "src")
if _ODR_SRC not in sys.path:
    sys.path.insert(0, _ODR_SRC)
