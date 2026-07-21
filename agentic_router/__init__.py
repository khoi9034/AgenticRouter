"""AgenticRouter: a rule-based DevSpace model router."""

from .normalizer import normalize_task
from .router import route

__all__ = ["normalize_task", "route"]
