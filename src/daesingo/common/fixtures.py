"""공용 common/runtime Mock fixture loader."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .job_execution import JobExecution, RuntimeModel


_SCENARIO_ID = re.compile(r"scenario_[a-z0-9_]+")
_DEFAULT_FIXTURE_DIR = Path(__file__).resolve().parents[3] / "data" / "mock" / "common"


class CommonFixture(RuntimeModel):
    scenario_id: str = Field(min_length=1)
    module: Literal["common"]
    job_executions: list[JobExecution]

    @model_validator(mode="after")
    def executions_have_unique_identity_and_ordered_attempts(self) -> CommonFixture:
        execution_ids = {item.execution_id for item in self.job_executions}
        if len(execution_ids) != len(self.job_executions):
            raise ValueError("execution_id는 fixture 안에서 중복될 수 없습니다")
        attempts_by_job: dict[str, list[int]] = {}
        for execution in self.job_executions:
            attempts_by_job.setdefault(execution.job_id, []).append(execution.attempt)
        for attempts in attempts_by_job.values():
            if sorted(attempts) != list(range(1, len(attempts) + 1)):
                raise ValueError("attempt는 같은 job_id 안에서 1부터 연속 증가해야 합니다")
        return self


def load_common_fixture(
    scenario_id: str,
    *,
    fixture_dir: Path | None = None,
) -> CommonFixture:
    if _SCENARIO_ID.fullmatch(scenario_id) is None:
        raise ValueError("scenario_id 형식이 올바르지 않습니다")
    source_dir = fixture_dir if fixture_dir is not None else _DEFAULT_FIXTURE_DIR
    fixture_path = source_dir / f"{scenario_id}.json"
    return CommonFixture.model_validate_json(fixture_path.read_text(encoding="utf-8"))
