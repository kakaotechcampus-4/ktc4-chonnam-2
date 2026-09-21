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

from daesingo.case.adapters import ModuleAdapter
from daesingo.case.domain import CaseAggregate


class CaseStore:
    def __init__(self) -> None:
        self._cases: dict[str, CaseAggregate] = {}
        self._adapters: dict[str, ModuleAdapter] = {}

    def register(self, case: CaseAggregate, adapter: ModuleAdapter) -> None:
        if case.case_id in self._cases:
            raise ValueError(f"case_id는 재등록할 수 없다: {case.case_id!r}")
        self._cases[case.case_id] = case
        self._adapters[case.case_id] = adapter

    def get_case(self, case_id: str) -> CaseAggregate:
        try:
            return self._cases[case_id]
        except KeyError:
            raise KeyError(f"등록되지 않은 case_id: {case_id!r}") from None

    def get_adapter(self, case_id: str) -> ModuleAdapter:
        try:
            return self._adapters[case_id]
        except KeyError:
            raise KeyError(f"등록되지 않은 case_id: {case_id!r}") from None
