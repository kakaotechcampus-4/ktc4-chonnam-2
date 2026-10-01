"""Compose p3 instructions with observation-only diagnostic output instructions."""

import json
from hashlib import sha256
from typing import Final

from .decision_trace import CHECKLISTS, review_windows
from .prompts import COARSE_PROMPT, PromptTemplate, fine_prompt_for, load_prompt
from .scope import VisualEventType


def _compose(base: PromptTemplate, suffix: str) -> PromptTemplate:
    delta = load_prompt(suffix)
    text = base.text.rstrip() + "\n\n" + delta.text
    return PromptTemplate(
        suffix,
        text,
        sha256(text.encode()).hexdigest(),
        base.placeholders | delta.placeholders,
    )


def diagnostic_coarse_prompt() -> PromptTemplate:
    return _compose(COARSE_PROMPT, "coarse-diagnostic-v1")


def diagnostic_fine_prompt(event_type: VisualEventType) -> PromptTemplate:
    return _compose(fine_prompt_for(event_type), "fine-diagnostic-v1")


_UNCERTAIN_DELTAS: Final = {
    VisualEventType.SOLID_LINE_LANE_CHANGE: "fine-uncertain-v1-solid-line-lane-change",
    VisualEventType.CENTER_LINE_CROSSING: "fine-uncertain-v1-center-line-crossing",
}


def uncertain_fine_prompt(event_type: VisualEventType) -> PromptTemplate:
    base = diagnostic_fine_prompt(event_type)
    suffix = _UNCERTAIN_DELTAS.get(event_type)
    if suffix is None:
        return base
    return _compose(_compose(base, "fine-uncertain-v1"), suffix)


def handoff_fine_prompt(event_type: VisualEventType) -> PromptTemplate:
    return _compose(diagnostic_fine_prompt(event_type), "fine-handoff-v1")


def window_instruction(duration_sec: float) -> str:
    return json.dumps(review_windows(duration_sec))


def checklist_instruction(event_type: VisualEventType) -> str:
    return json.dumps(CHECKLISTS[event_type])
