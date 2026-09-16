"""Mock Fixture 기반 upstream adapter — recording/search/readout/evidence가 아직 코드가
없는 상태에서 case를 독립적으로 실행·테스트하기 위한 stand-in이다.

`data/mock/<module>/scenario_<id>.json`을 Canonical Contract 모양 그대로 읽어서 돌려준다.
여기서 하는 일은 오직 "파일을 읽어서 그대로 넘기는 것"뿐 — evidence의 판정 로직이나
readout의 OCR 판단을 이 어댑터가 재구현하지 않는다(그건 각 모듈 Owner의 책임).

나중에 실제 모듈이 구현되면, 이 클래스와 같은 메서드 시그니처를 갖는 실제 HTTP/함수
호출 어댑터로 교체하면 된다 — case의 domain/view 코드는 이 인터페이스에만 의존한다.

## Mock→Real 교체 (W5)

`ModuleAdapter`가 그 "인터페이스"를 `typing.Protocol`로 formalize한 것이다.
`MockFixtureAdapter`와 `RealAdapter` 둘 다 구조적으로 이 프로토콜을 만족한다(명시적
상속 없이도 각 메서드 시그니처가 같으면 타입체커가 호환으로 본다). `case/service.py`는
구체 클래스가 아니라 `ModuleAdapter`에만 의존하므로, 실행 시점에 어느 어댑터 인스턴스를
주입하느냐만 바꾸면 orchestration 코드는 손대지 않는다.

`RealAdapter`는 아직 골격뿐이다 — 각 메서드는 대응하는 모듈(search/evidence/common)의
실제 구현이 아직 없어 `NotImplementedError`를 낸다. 각 모듈 Owner가 실제 조회 경로(HTTP
또는 함수 호출)를 완성하면, 그 메서드 하나만 채우면 된다 — 나머지 메서드는 계속
`NotImplementedError`로 남겨서 "이 모듈은 아직 Mock, 저 모듈은 Real"인 혼재 상태를
그대로 표현할 수 있다(W5 원칙 "Mock retained for not-yet-ready modules").
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ModuleAdapter(Protocol):
    """`case`가 upstream 모듈 산출물을 읽을 때 의존하는 유일한 인터페이스.

    `MockFixtureAdapter`(현재)와 `RealAdapter`(골격, 앞으로 모듈별로 채워짐) 둘 다
    이 프로토콜을 만족한다. `case/service.py`의 함수들은 이 타입에만 의존한다 —
    Mock↔Real 교체는 여기 정의된 메서드 시그니처를 벗어나지 않는 한 `service.py`나
    `domain.py`/`jobs.py`/`view.py`를 고치지 않고도 가능하다.
    """

    def get_candidate_events(self) -> list[dict[str, Any]]: ...

    def get_analysis_scopes(self) -> list[dict[str, Any]]: ...

    def get_evidence_record(self) -> dict[str, Any] | None: ...

    def get_evidence_records(self) -> list[dict[str, Any]]: ...

    def get_requirement_report(self, scope: str) -> dict[str, Any] | None: ...

    def get_requirement_reports(self, scope: str) -> list[dict[str, Any]]: ...

    def get_evidence_needs(self) -> list[dict[str, Any]]: ...

    def get_report_package(self) -> dict[str, Any] | None: ...

    def get_job_executions(self) -> list[dict[str, Any]]: ...


class MockFixtureAdapter:
    def __init__(self, mock_root: Path, scenario_id: str) -> None:
        self.mock_root = Path(mock_root)
        self.scenario_id = scenario_id
        self._cache: dict[str, dict[str, Any]] = {}

    def _load(self, module: str) -> dict[str, Any]:
        if module not in self._cache:
            path = self.mock_root / module / f"scenario_{self.scenario_id}.json"
            with open(path, encoding="utf-8") as fh:
                self._cache[module] = json.load(fh)
        return self._cache[module]

    # ── search ──────────────────────────────────────────────────────────
    def get_candidate_events(self) -> list[dict[str, Any]]:
        """`AnalysisRun.operation == CANDIDATE_SEARCH`가 만든 `CandidateEvent`만 반환한다
        (`VISUAL_VERIFY`/Fine run은 후보를 만들지 않는다 — module-architecture.md §4-모듈2)."""
        search = self._load("search")
        candidates: list[dict[str, Any]] = []
        for entry in search.get("analysis_run_candidate_events", []):
            if entry["analysis_run"]["operation"] == "CANDIDATE_SEARCH":
                candidates.extend(entry.get("candidates", []))
        return candidates

    def get_analysis_scopes(self) -> list[dict[str, Any]]:
        """search fixture에 실려있는 `AnalysisScope`(case가 Producer로 만들어 보낸 것)를
        그대로 읽는다 — `scope.build_analysis_scope()`의 정답지로 쓴다."""
        return self._load("search").get("analysis_scopes", [])

    # ── evidence ────────────────────────────────────────────────────────
    def get_evidence_record(self) -> dict[str, Any] | None:
        records = self._load("evidence").get("evidence_records", [])
        return records[0] if records else None

    def get_evidence_records(self) -> list[dict[str, Any]]:
        """`get_evidence_record()`는 최초 1건만 돌려준다 — supersede 체인(재판독 등으로
        `EvidenceRecord`가 v1→v2로 갱신되는 시나리오, `scenario_plate_reread_001`)을
        순서대로 재현하려면 전체 목록이 필요해서 추가했다."""
        return self._load("evidence").get("evidence_records", [])

    def get_requirement_report(self, scope: str) -> dict[str, Any] | None:
        reports = self._load("evidence").get("requirement_reports", [])
        return next((r for r in reports if r["scope"] == scope), None)

    def get_requirement_reports(self, scope: str) -> list[dict[str, Any]]:
        """`get_requirement_report()`와 같은 이유로 추가 — 같은 scope에 여러 건(supersede
        전/후)이 있는 시나리오를 순서대로 재현하려고 전체 목록을 돌려준다."""
        reports = self._load("evidence").get("requirement_reports", [])
        return [r for r in reports if r["scope"] == scope]

    def get_evidence_needs(self) -> list[dict[str, Any]]:
        """`EvidenceRecord`와 마찬가지로 supersede 체인 순서대로(v1 basis→v2 basis) 전체
        목록을 돌려준다 — 각 `EvidenceNeeds.basis_record_ref`가 어느 `EvidenceRecord`
        revision을 기준으로 계산됐는지는 evidence의 책임이고, 이 어댑터는 그대로 옮기기만
        한다(`scenario_plate_reread_001`: v1 basis에 `PLATE_REREAD` 1건, v2 basis는 `items=[]`)."""
        return self._load("evidence").get("evidence_needs", [])

    def get_report_package(self) -> dict[str, Any] | None:
        packages = self._load("evidence").get("report_packages", [])
        return packages[0] if packages else None

    # ── common/runtime ──────────────────────────────────────────────────
    def get_job_executions(self) -> list[dict[str, Any]]:
        """`JobExecution`(job-execution/v1.1) 전체 목록 — case는 이 계약의 Producer가
        아니지만(common/runtime 소유), `progress[].state` projection(§13)의 입력으로
        읽어야 한다. `scenario_infra_failure_001`처럼 같은 `job_id`에 여러 attempt
        (STALE→FAILED)가 있을 수 있어 전체 목록을 그대로 돌려준다 — "어느 attempt가
        최신인가"를 고르는 건 이 어댑터가 아니라 호출자(case) 책임이다."""
        return self._load("common").get("job_executions", [])


class RealAdapter:
    """`ModuleAdapter` 골격 — 실제 모듈 호출로 채워질 자리.

    아직 어떤 모듈도 case가 호출할 수 있는 실제 엔드포인트/함수를 내놓지 않았으므로,
    지금은 전부 `NotImplementedError`다. **모듈별로 하나씩 채운다** — 예를 들어
    recording/search가 먼저 준비되면 `get_candidate_events()`/`get_analysis_scopes()`만
    실제 호출로 바꾸고, 나머지(`get_evidence_record()` 등)는 evidence가 준비될 때까지
    `NotImplementedError`로 남겨둔다. 이 상태에서도 `case/service.py`는 그대로
    동작해야 한다 — 실패는 "아직 Real로 안 바뀐 자리를 호출했다"는 명확한 신호여야
    하고, 조용히 빈 값을 돌려주면 안 된다(Mock의 정직한 실패 원칙과 동일).

    생성자 인자는 자리표시자다 — 실제 호출 방식(HTTP client, 같은 프로세스 내 함수
    호출 등)이 모듈별로 정해지면 그에 맞게 바뀐다.
    """

    def __init__(self, *, case_id: str, **clients: Any) -> None:
        self.case_id = case_id
        self._clients = clients

    def _not_ready(self, method: str, module: str) -> None:
        raise NotImplementedError(
            f"RealAdapter.{method}()는 아직 미구현 — {module} 모듈의 실제 구현이 준비되면 "
            f"이 메서드만 채운다(case/adapters.py). 그 전까지는 이 case_id에 대해 "
            f"{module}을 Mock으로 유지해야 한다."
        )

    # ── search ──────────────────────────────────────────────────────────
    def get_candidate_events(self) -> list[dict[str, Any]]:
        self._not_ready("get_candidate_events", "search")

    def get_analysis_scopes(self) -> list[dict[str, Any]]:
        self._not_ready("get_analysis_scopes", "search")

    # ── evidence ────────────────────────────────────────────────────────
    def get_evidence_record(self) -> dict[str, Any] | None:
        self._not_ready("get_evidence_record", "evidence")

    def get_evidence_records(self) -> list[dict[str, Any]]:
        self._not_ready("get_evidence_records", "evidence")

    def get_requirement_report(self, scope: str) -> dict[str, Any] | None:
        self._not_ready("get_requirement_report", "evidence")

    def get_requirement_reports(self, scope: str) -> list[dict[str, Any]]:
        self._not_ready("get_requirement_reports", "evidence")

    def get_evidence_needs(self) -> list[dict[str, Any]]:
        self._not_ready("get_evidence_needs", "evidence")

    def get_report_package(self) -> dict[str, Any] | None:
        self._not_ready("get_report_package", "evidence")

    # ── common/runtime ──────────────────────────────────────────────────
    def get_job_executions(self) -> list[dict[str, Any]]:
        self._not_ready("get_job_executions", "common/runtime")
