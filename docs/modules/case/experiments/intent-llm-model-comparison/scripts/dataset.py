"""datasets/*.jsonl 로더. locked dataset 파일은 여기서만 읽는다 — 수정하지 않는다."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestCase:
    id: str
    scenario_tag: str
    prior_hints: dict | None
    input_sentence: str
    expected_notes: str


def load_dataset(path: str | Path) -> list[TestCase]:
    path = Path(path)
    cases: list[TestCase] = []
    seen_ids: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            case = TestCase(
                id=row["id"],
                scenario_tag=row["scenario_tag"],
                prior_hints=row.get("prior_hints"),
                input_sentence=row["input_sentence"],
                expected_notes=row["expected_notes"],
            )
            if case.id in seen_ids:
                raise ValueError(f"{path}:{lineno} 중복 id: {case.id}")
            seen_ids.add(case.id)
            cases.append(case)
    return cases
