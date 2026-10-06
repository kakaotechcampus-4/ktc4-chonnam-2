"""case_id → `CaseAggregate` 최소 in-memory 저장소.

`common.InMemoryJobExecutionStore`와 같은 패턴이다 — 정식 DB 영속화·동시성 제어는
이번 범위 밖이다(W5/W6 요청 문서 "이번엔 안 해도 되는 것"). 프로세스가 재시작되면
사라진다. 나중에 실제 저장소로 교체할 때도 `register`/`get_case`/`get_adapter`
시그니처만 유지하면 `service.get_view()`는 그대로 동작한다.

`ModuleAdapter`를 case와 함께 등록해서 들고 있는 이유 — 어떤 case가 Mock 시나리오
기반인지 Real 데이터 기반인지는 등록 시점에 정해지고 그 case의 생애주기 동안 안
바뀐다(스모크 테스트·`real_e2e.py`가 지금까지 해온 방식과 동일). 매 조회마다 호출자가
어댑터를 다시 구성해서 넘기게 하면 `get_view(case_id)`가 사실상 한 개 인자로 안 끝난다.
"""

from __future__ import annotations

import copy
from typing import Any, Literal, Protocol

from daesingo.case.adapters import ModuleAdapter
from daesingo.case.domain import CaseAggregate
from daesingo.case.store_state import CaseRow, from_row, to_row

CASE_ID_MAX = 128  # `cases.case_id` VARCHAR(128) ascii_bin


class CaseNotFound(KeyError):
    """등록되지 않은 case_id — `KeyError`라서 기존 `except KeyError`(command의 unknown_target)가 그대로 잡는다."""


class CaseAlreadyExists(ValueError):
    pass


class AppendOnlyViolation(RuntimeError):
    """저장된 레코드의 앞부분이 바뀌거나 지워졌다 — 정상 경로에서는 나지 않는 프로그래밍 오류."""


class InvalidCaseId(ValueError):
    pass


def validate_case_id(case_id: str) -> None:
    if not case_id or len(case_id) > CASE_ID_MAX or not case_id.isascii():
        raise InvalidCaseId(f"case_id는 1~{CASE_ID_MAX}자 ASCII여야 한다: {case_id!r}")


class CaseRepository(Protocol):
    """case 저장소. `conn`은 호출자의 SQLAlchemy `Connection`이고 transaction도 호출자 것이다 —
    저장소는 commit · rollback하지 않는다(#245 D-2). in-memory 구현은 `conn`을 무시한다."""

    def insert(self, conn: Any, case: CaseAggregate) -> None: ...
    def load(self, conn: Any, case_id: str, *, lock: Literal["share", "update"] = "share") -> CaseAggregate: ...
    def save(self, conn: Any, case: CaseAggregate) -> None: ...


def check_append_only(stored_ids: list[str], current_ids: list[str], what: str) -> None:
    if current_ids[: len(stored_ids)] != stored_ids:
        raise AppendOnlyViolation(f"{what}의 저장된 앞부분이 바뀌었다")


class InMemoryCaseRepository:
    """테스트 · 로컬용. load는 늘 새 객체를 준다 — 같은 객체를 주면 save를 빠뜨려도 테스트가 통과해
    MySQL에서만 상태가 사라진다(`decisions/case-store-mysql.md` §5)."""

    def __init__(self) -> None:
        self._rows: dict[str, CaseRow] = {}

    def insert(self, conn: Any, case: CaseAggregate) -> None:
        validate_case_id(case.case_id)
        if case.case_id in self._rows:
            raise CaseAlreadyExists(f"case_id는 재등록할 수 없다: {case.case_id!r}")
        self._rows[case.case_id] = to_row(case)

    def load(self, conn: Any, case_id: str, *, lock: Literal["share", "update"] = "share") -> CaseAggregate:
        try:
            row = self._rows[case_id]
        except KeyError:
            raise CaseNotFound(f"등록되지 않은 case_id: {case_id!r}") from None
        return from_row(copy.deepcopy(row))

    def save(self, conn: Any, case: CaseAggregate) -> None:
        stored = self._rows.get(case.case_id)
        if stored is None:
            raise CaseNotFound(f"등록되지 않은 case_id: {case.case_id!r}")
        new = to_row(case)
        check_append_only([r["job_id"] for r in stored.job_records], [r["job_id"] for r in new.job_records], "job_records")
        check_append_only(
            [r["correction_id"] for r in stored.correction_records],
            [r["correction_id"] for r in new.correction_records],
            "correction_records",
        )
        for scope_id, scope in stored.analysis_scopes.items():
            if new.analysis_scopes.get(scope_id) != scope:
                raise AppendOnlyViolation(f"analysis_scopes {scope_id!r}가 바뀌거나 지워졌다")
        self._rows[case.case_id] = new


class CaseStore:
    def __init__(self) -> None:
        self._cases: dict[str, CaseAggregate] = {}
        self._adapters: dict[str, ModuleAdapter | None] = {}

    def register(self, case: CaseAggregate, adapter: ModuleAdapter | None = None) -> None:
        """`adapter=None`은 빈 case(`service.create_case()`)다 — 선택 전에는 adapter를 조회하지 않는다."""
        if case.case_id in self._cases:
            raise ValueError(f"case_id는 재등록할 수 없다: {case.case_id!r}")
        self._cases[case.case_id] = case
        self._adapters[case.case_id] = adapter

    def get_case(self, case_id: str) -> CaseAggregate:
        try:
            return self._cases[case_id]
        except KeyError:
            raise KeyError(f"등록되지 않은 case_id: {case_id!r}") from None

    def get_adapter(self, case_id: str) -> ModuleAdapter | None:
        try:
            return self._adapters[case_id]
        except KeyError:
            raise KeyError(f"등록되지 않은 case_id: {case_id!r}") from None
