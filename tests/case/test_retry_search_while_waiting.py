"""「다시 찾기」로 새 탐색을 기다리는 동안 — #426 case 결정.

1. 결과 없음(`CANDIDATE_REVIEW` · 후보 0개)에서 다시 찾으면 `SEARCHING`으로 돌아간다 — 탐색 결과 반영은
   `SEARCHING`에서만 받으므로, 머물면 새 결과가 반영되지 못했다. 진행 상태는 이전 결과(DONE · FAILED)가 아니라
   탐색 중(`coarse_search=RUNNING`)이다.
2. 탐색 job(`HINT_EXTRACT` · `COARSE_SEARCH`)을 기다리는 동안 notice에 `RETRY_SEARCH`를 싣지 않는다. 허용 = 화면의
   버튼이라(case-command 계약 §5) 같은 입력의 추가 발주가 서버에서도 막힌다.
3. 결과가 반영되면 버튼이 다시 실린다.
"""
from __future__ import annotations

from pathlib import Path

from daesingo.case import command, jobs, service
from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.domain import CaseAggregate
from daesingo.case.store import CaseStore
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
CASE_ID = "case_retry426"
NO_CANDIDATES = "search.no_candidates"
FAILED = "search.candidate_search_failed"


def _no_candidates_store() -> tuple[CaseStore, MockFixtureAdapter]:
    """`empty_001` — 탐색은 성공했지만 후보 0개(`CANDIDATE_REVIEW`)."""
    adapter = MockFixtureAdapter(MOCK_ROOT, "empty_001")
    case = CaseAggregate.intake(case_id=CASE_ID, hints={}, manifest_summary={})
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_e001", input_fingerprint="sha1:e001-coarse-search")
    service.receive_search_candidates(case, adapter)
    store = CaseStore()
    store.register(case, adapter)
    return store, adapter


def _retry(store: CaseStore) -> command.CommandResult:
    rev = store.get_case(CASE_ID).case_rev
    request = {
        "case_id": CASE_ID,
        "expected_case_rev": rev,
        "kind": "RUN_NOTICE_ACTION",
        "payload": {"notice_code": NO_CANDIDATES, "action": "RETRY_SEARCH"},
    }
    return command.execute_command(request, store=store)


def _step(view: dict, step: str) -> str:
    return next(s["state"] for s in view["progress"] if s["step"] == step)


def _actions(view: dict, code: str) -> list[str]:
    return next(n["actions"] for n in view["notices"] if n["code"] == code)


def _coarse_jobs(store: CaseStore) -> list[dict]:
    return [r for r in store.get_case(CASE_ID).job_records if r["kind"] == "COARSE_SEARCH"]


def test_no_candidates_offers_retry_before_any_retry():
    store, _ = _no_candidates_store()
    view = service.get_view(CASE_ID, store=store)
    assert _step(view, "coarse_search") == "DONE"
    assert "RETRY_SEARCH" in _actions(view, NO_CANDIDATES)


def test_retry_shows_search_running_not_previous_result():
    store, _ = _no_candidates_store()

    result = _retry(store)

    assert result.response["ok"] is True
    view = result.response["case_view"]
    assert view["stage"] == "SEARCHING"
    assert [j["kind"] for j in view["running_jobs"]] == ["COARSE_SEARCH"]
    assert _step(view, "coarse_search") == "RUNNING"
    assert _step(view, "candidate_review") == "PENDING"
    assert NO_CANDIDATES not in [n["code"] for n in view["notices"]]


def test_second_retry_while_waiting_is_rejected_and_issues_nothing():
    store, _ = _no_candidates_store()
    assert _retry(store).response["ok"] is True
    issued = len(_coarse_jobs(store))

    result = _retry(store)

    assert result.response["ok"] is False
    assert result.response["error"]["code"] == "case.command.unknown_target"
    assert len(_coarse_jobs(store)) == issued


def test_retry_button_returns_after_result_is_reflected():
    store, adapter = _no_candidates_store()
    assert _retry(store).response["ok"] is True

    case = store.load_for_update(CASE_ID)
    service.receive_search_candidates(case, adapter)
    store.save(case)

    view = service.get_view(CASE_ID, store=store)
    assert view["stage"] == "CANDIDATE_REVIEW"
    assert view["running_jobs"] == []
    assert _step(view, "coarse_search") == "DONE"
    assert "RETRY_SEARCH" in _actions(view, NO_CANDIDATES)


class _FailedSearchAdapter:
    def get_candidate_events(self):
        return []

    def get_candidate_search_outcome(self):
        return "FAILED"


def test_retry_after_failure_shows_running_not_failed():
    case = CaseAggregate.intake(case_id="case_sf426", hints={}, manifest_summary={})
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_sf", input_fingerprint="sha1:sf")
    service.receive_search_candidates(case, _FailedSearchAdapter())
    assert _step(build_case_view(case), "coarse_search") == "FAILED"

    jobs.issue_same_input(case, jobs.latest_job_record(case, "COARSE_SEARCH"))

    view = service.derive_notices(build_case_view(case))
    assert _step(view, "coarse_search") == "RUNNING"
    # 실패 notice는 진행 상태로 정해지므로 새 탐색을 기다리는 동안 붙지 않는다.
    assert FAILED not in [n["code"] for n in view["notices"]]


def test_any_retry_search_action_is_dropped_while_search_job_waits():
    # notice 공통 규칙 — 기다리는 탐색 job이 있으면 어떤 notice에도 `RETRY_SEARCH`를 싣지 않는다.
    view = {
        "stage": "CANDIDATE_REVIEW",
        "candidates": [],
        "progress": [{"step": "coarse_search", "state": "DONE"}],
        "running_jobs": [{"job_id": "j2", "kind": "COARSE_SEARCH", "label_key": "x", "status": "PENDING"}],
        "notices": [],
    }
    assert _actions(service.derive_notices(view), NO_CANDIDATES) == ["EDIT_HINT"]
