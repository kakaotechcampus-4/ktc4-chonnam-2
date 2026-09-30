"""web → case 공용 command 진입점 — `docs/modules/case/contracts/contract-case-command.md`(Draft v0).

`get_view()`가 읽기 방향이라면 이 파일은 쓰기 방향이다. transport(HTTP 경로·인증·직렬화)는
여기 없다 — transport는 요청을 그대로 넘기고 응답을 그대로 돌려주기만 한다(#106). 상태 확인·
stale 검사·허용 조건·실패 코드는 전부 여기서 정한다.

## 여기 없는 것

- 도메인 규칙. 각 command는 이미 있는 domain·correction·jobs 함수를 부른다 — 여기는 요청 모양
  검사와 실패 코드 분류(§6)만 한다.
- Job 실행. `RUN_NOTICE_ACTION`은 `JobRecord`를 남길 뿐이고, 진행은 다음 CaseView의
  `running_jobs[]`·`progress[]`로 본다(§3).
- 신고요건·번호판·시각 값 판정(§7-3).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from daesingo.case import correction, jobs
from daesingo.case.domain import CaseAggregate, InvalidTransition
from daesingo.case.service import get_view
from daesingo.case.store import CaseStore

# 이 판본(v0)에서 받는 `CORRECTED` 제외 값 — `CORRECTED`는 `SITUATION_CHANGE`를 보낼 입력형
# 판본에서 함께 연다(§5).
_SITUATION_VALUES = frozenset({"CONFIRMED", "USER_UNSURE"})

# CaseView 계약 B절 §7 「`notices[].actions[]` → 발주 매핑」 중 발주형 4종 → `JobRecord.kind`.
_ACTION_JOB_KIND = {
    "GENERATE_REPORT_VIDEO": "REPORT_VIDEO_EXPORT",
    "RETRY_PLATE_READ": "PLATE_READ",
    "RETRY_SEARCH": "COARSE_SEARCH",
    "GENERATE_PLATE_IMAGE": "PLATE_IMAGE_EXPORT",
}

_PAYLOAD_KEYS = {
    "SELECT_OTHER_CANDIDATE": frozenset({"candidate_id"}),
    "RECORD_SITUATION_RESPONSE": frozenset({"value"}),
    "MARK_REVIEWED": frozenset(),
    "RUN_NOTICE_ACTION": frozenset({"notice_code", "action"}),
}


class _Rejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _check_payload(request: Any) -> None:
    if not isinstance(request, dict):
        raise _Rejected("invalid_payload")
    kind = request.get("kind")
    payload = request.get("payload")
    rev = request.get("expected_case_rev")
    if (
        not isinstance(request.get("case_id"), str)
        or not isinstance(rev, int)
        or isinstance(rev, bool)
        or kind not in _PAYLOAD_KEYS
        or not isinstance(payload, dict)
        or set(payload) != _PAYLOAD_KEYS[kind]
    ):
        raise _Rejected("invalid_payload")
    if any(not isinstance(v, str) for v in payload.values()):
        raise _Rejected("invalid_payload")
    if kind == "RECORD_SITUATION_RESPONSE" and payload["value"] not in _SITUATION_VALUES:
        raise _Rejected("invalid_payload")
    if kind == "RUN_NOTICE_ACTION" and payload["action"] not in _ACTION_JOB_KIND:
        raise _Rejected("invalid_payload")


def _select_other_candidate(case: CaseAggregate, payload: dict[str, Any], view: dict[str, Any]) -> None:
    candidate_id = payload["candidate_id"]
    if all(c.candidate_id != candidate_id for c in case.candidates):
        raise _Rejected("unknown_target")
    # 허용 stage(EVIDENCE_REVIEW·READY)·「이미 선택된 후보」 검사는 domain이 아무것도 바꾸기 전에 한다.
    try:
        case.check_reselect(candidate_id)
    except InvalidTransition:
        raise _Rejected("not_allowed") from None
    correction.reselect_candidate(case, candidate_id)


def _record_situation_response(case: CaseAggregate, payload: dict[str, Any], view: dict[str, Any]) -> None:
    if not any(c.selected for c in case.candidates):
        raise _Rejected("not_allowed")
    # `responded_at`은 web이 보내지 않는다 — 사용자 기기 시계를 기록값으로 쓰지 않는다(§5).
    case.record_situation_response(payload["value"], responded_at=_now())


def _mark_reviewed(case: CaseAggregate, payload: dict[str, Any], view: dict[str, Any]) -> None:
    # domain `mark_reviewed()`에는 stage 가드가 없다(§10) — READY만 받는다.
    if case.stage != "READY":
        raise _Rejected("not_allowed")
    case.mark_reviewed()


def _run_notice_action(case: CaseAggregate, payload: dict[str, Any], view: dict[str, Any]) -> None:
    # 허용 조건 = 「화면에 그 버튼이 떠 있었는가」(§5). web과 같은 근거(현재 CaseView notices)로만 받는다.
    notice = next((n for n in view["notices"] if n["code"] == payload["notice_code"]), None)
    if notice is None or payload["action"] not in notice.get("actions", []):
        raise _Rejected("unknown_target")
    kind = _ACTION_JOB_KIND[payload["action"]]
    # 같은 입력을 다시 보는 발주라 가장 최근 같은 kind JobRecord의 입력을 그대로 쓴다
    # (`jobs.issue_needed_jobs()`와 같은 원칙). case는 fingerprint를 새로 계산하지 않으므로, 이전
    # 발주가 없으면 만들 수 없다.
    prior = next((j for j in reversed(case.job_records) if j["kind"] == kind), None)
    if prior is None:
        raise _Rejected("not_allowed")
    # RETRY_* 는 FAILED가 cache hit 대상이 아니라 force_rerun 없이 새 job_id만으로 성립한다(B절 §7).
    jobs.issue_job(
        case, kind, scope_ref=prior["scope_ref"], input_fingerprint=prior["input_fingerprint"]
    )


_HANDLERS = {
    "SELECT_OTHER_CANDIDATE": _select_other_candidate,
    "RECORD_SITUATION_RESPONSE": _record_situation_response,
    "MARK_REVIEWED": _mark_reviewed,
    "RUN_NOTICE_ACTION": _run_notice_action,
}


def _response(error: str | None, case_view: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "ok": error is None,
        # `message_key` 값 목록은 web과 함께 정한다(§9 미결) — 지금은 §8 예시의 `command.<사유>` 모양.
        "error": None if error is None else {"code": f"case.command.{error}", "message_key": f"command.{error}"},
        "case_view": case_view,
    }


def handle_command(
    request: dict[str, Any],
    *,
    store: CaseStore,
    running_jobs: list[dict[str, Any]] | None = None,
    notices: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """command 하나를 받아 `{ok, error, case_view}`를 돌려준다(§4).

    검사 순서는 §6 그대로 `invalid_payload` → `unknown_target`(case) → `stale_revision` →
    `unknown_target`(대상) → `not_allowed`다. 실패하면 아무 상태도 바꾸지 않고 현재 CaseView를
    싣는다 — case_id가 없을 때만 `case_view=None`이다. `running_jobs`·`notices`는 `get_view()`에
    그대로 넘긴다(사용자가 본 화면과 같은 notices로 `RUN_NOTICE_ACTION`을 검사하기 위해).
    """
    view_kwargs = {"store": store, "running_jobs": running_jobs, "notices": notices}
    case_id = request.get("case_id") if isinstance(request, dict) else None

    def current_view() -> dict[str, Any] | None:
        try:
            return get_view(case_id, **view_kwargs)
        except KeyError:
            return None

    try:
        _check_payload(request)
    except _Rejected as rejected:
        return _response(rejected.reason, current_view() if isinstance(case_id, str) else None)

    try:
        case = store.get_case(case_id)
    except KeyError:
        return _response("unknown_target", None)

    view = get_view(case_id, **view_kwargs)
    if request["expected_case_rev"] != case.case_rev:
        return _response("stale_revision", view)

    try:
        _HANDLERS[request["kind"]](case, request["payload"], view)
    except _Rejected as rejected:
        return _response(rejected.reason, view)
    return _response(None, get_view(case_id, **view_kwargs))
