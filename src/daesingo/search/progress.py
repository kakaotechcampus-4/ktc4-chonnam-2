"""Coarse work boundaries, not an estimate of remaining time."""

from collections.abc import Callable
from typing import Literal

SearchPhase = Literal["PREPARING", "SEARCHING", "ORGANIZING"]
SearchProgress = Callable[[SearchPhase], None]
