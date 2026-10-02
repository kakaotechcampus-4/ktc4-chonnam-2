"""7순위 — case Orchestration 지표 러너 (행동 순서 길이 1~N).

정정·관찰 상태 조합의 세션을 fixture 기반
`RealAdapter`로 하나씩 돌리고 세 지표를 채점한다. 유료 호출 없음 · 결정론적.

  ① 필요한 단계만 재실행 — 행동 직후 실제 호출된 단계 ⊆ 부분 재실행 정책 표의 허용 단계
  ② 잘못된 전이 0건 — 매 단계 뒤 불변식
  ③ 불필요한 재실행 — 같은 단계가 같은 입력(선택 context)으로 다시 호출된 횟수

제품 코드는 바꾸지 않는다. 관찰 상태 주입·호출 계측은 이 스크립트 안에서만 한다.
"""
from __future__ import annotations

import argparse
import itertools
import json
import time
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from daesingo import search as search_module
from daesingo.case import correction, jobs, real_e2e, service
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter
from daesingo.case.command import handle_command
from daesingo.case.domain import CaseAggregate, InvalidTransition
from daesingo.case.store import CaseStore
from daesingo.recording.service import RecordingService

ROOT = Path(__file__).resolve().parents[1]
MOCK_ROOT = ROOT / "data" / "mock"
SCENARIO_ID = "happy_001"

# ── 계측 ─────────────────────────────────────────────────────────────────

# (owner, 속성 이름, 단계 이름). 관찰 단계는 선택 context가 같으면 입력이 같다고 본다(③).
_STAGES = (
    (search_module, "search_candidates", "coarse_search"),
    (search_module, "verify_visual", "fine_verify"),
    (RecordingService, "build_incident_clip", "incident_clip"),
    (real_e2e.readout_api, "read_plate", "plate_ocr"),
    (real_e2e.readout_api, "read_overlay_time", "overlay_ocr"),
    (real_e2e, "assemble_evidence", "assemble"),
)


class Recorder:
    def __init__(self) -> None:
        self.case: CaseAggregate | None = None
        self.calls: list[tuple[str, tuple]] = []

    def key(self, stage: str) -> tuple:
        case = self.case
        selected = next((c.candidate_id for c in case.candidates if c.selected), None) if case else None
        if stage == "assemble":
            # 조립은 선택 context·정정마다 입력이 바뀐다(순수 계산) — selection_rev·case_rev를 입력에 넣는다.
            return (selected, case.selection_rev if case else None, case.case_rev if case else None)
        # 관찰은 같은 탐색 결과의 같은 후보면 입력이 같다(decisions/reselect-observation-reuse.md) —
        # 「탐색 결과 세대」는 지금까지의 1차 탐색 호출 수로 센다. 재선택(selection_rev)은 입력을 바꾸지 않는다.
        generation = sum(1 for s, _ in self.calls if s == "coarse_search")
        return (selected, generation)

    def mark(self) -> int:
        return len(self.calls)

    def since(self, mark: int) -> list[str]:
        return [stage for stage, _ in self.calls[mark:]]


@contextmanager
def patched(patches: list[tuple[Any, str, Any]]):
    originals = [(owner, name, getattr(owner, name)) for owner, name, _ in patches]
    try:
        for owner, name, value in patches:
            setattr(owner, name, value)
        yield
    finally:
        for owner, name, value in reversed(originals):
            setattr(owner, name, value)


def _counting(recorder: Recorder, stage: str, original: Callable) -> Callable:
    def spy(*args, **kwargs):
        recorder.calls.append((stage, recorder.key(stage)))
        return original(*args, **kwargs)
    return spy


# ── baseline 호환층 ─────────────────────────────────────────────────────
# baseline 커밋(#175·#202 이전)에는 지금 공개 함수 일부가 없다. 없으면 같은 결과를 내는 옛 경로를 쓴다.

def _auto_select(case: CaseAggregate) -> None:
    if hasattr(case, "select_top_ranked"):  # #194 이후
        case.select_top_ranked()
    elif case.candidates:  # 이전: 후보가 1개뿐인 fixture라 첫 후보 = rank1
        case.select_candidate(case.candidates[0].candidate_id)


# ── 관찰 상태 주입 (happy 바탕) ─────────────────────────────────────────

def _scope() -> search_module.AnalysisScope:
    return search_module.AnalysisScope.model_validate(
        MockFixtureAdapter(MOCK_ROOT, SCENARIO_ID).get_analysis_scopes()[0]
    )


def _not_observed(original_verify: Callable) -> Callable:
    def verify(*args, **kwargs):
        payload = original_verify(*args, **kwargs).model_dump(mode="json")
        payload["visual_evidence"]["verification"] = "NOT_OBSERVED"
        payload["visual_evidence"]["visual_event_type"] = None
        return search_module.VisualVerificationResult.model_validate(payload)
    return verify


def _uncertain(original_verify: Callable) -> Callable:
    """Fine `UNCERTAIN` — 상황 응답 전에는 `AWAIT_SITUATION_RESPONSE`로 조립하지 않는다(#165·#203)."""
    def verify(*args, **kwargs):
        payload = original_verify(*args, **kwargs).model_dump(mode="json")
        payload["visual_evidence"]["verification"] = "UNCERTAIN"
        payload["visual_evidence"]["visual_event_type"] = None
        return search_module.VisualVerificationResult.model_validate(payload)
    return verify


def _search_outcome(outcome: str) -> Callable[[Callable], Callable]:
    """후보 0개로 끝나는 1차 탐색 — `SUCCEEDED`면 결과 없음, `FAILED`면 탐색 실패(#197·#209)."""
    def make(original: Callable) -> Callable:
        def search_candidates(scope, **kwargs):
            payload = original(scope, **kwargs).model_dump(mode="json")
            payload["candidates"] = []
            payload["analysis_run"]["outcome"] = outcome
            return search_module.CandidateSearchResult.model_validate(payload)
        return search_candidates
    return make


def _plate_failed(_original: Callable) -> Callable:
    def read_plate(request, **kwargs):
        return SimpleNamespace(outcome="FAILED"), None
    return read_plate


def _plate_unread(original: Callable) -> Callable:
    """판독은 됐지만 번호를 못 읽음(#172 D-2 1·3) — `PlateReadout` status UNKNOWN, value null."""
    def read_plate(request, **kwargs):
        run, plate = original(request, **kwargs)
        data = plate.to_dict()
        data["observation"]["value"] = None
        data["observation"]["status"] = "UNKNOWN"
        data["abstained"] = False
        return run, SimpleNamespace(to_dict=lambda: json.loads(json.dumps(data)))
    return read_plate


SECOND_CANDIDATE_SUFFIX = "_r2"


def _with_second_candidate(original: Callable) -> Callable:
    """mock search fixture는 전부 후보 1개라 「다른 후보 선택」을 돌릴 수 없다 — rank1을 복사해 rank2를
    하나 더 만든다. span이 같아서 recording·Fine·판독 fixture가 그대로 풀리고, 달라지는 것은
    `candidate_id`뿐이다(선택 context가 바뀌는 것 자체를 보려는 축이라 이걸로 충분하다)."""
    def search_candidates(scope, **kwargs):
        payload = original(scope, **kwargs).model_dump(mode="json")
        if len(payload["candidates"]) == 1:
            second = json.loads(json.dumps(payload["candidates"][0]))
            second["candidate_id"] += SECOND_CANDIDATE_SUFFIX
            second["rank"] = 2
            payload["candidates"].append(second)
        return search_module.CandidateSearchResult.model_validate(payload)
    return search_candidates


def _fine_for_selected(recorder: "Recorder") -> Callable[[Callable], Callable]:
    """Fine fixture의 `VisualEvidence.candidate_id`는 rank1로 고정이다 — 합성 rank2가 선택됐을 때만
    그 후보로 바꾼다(evidence가 CandidateEvent와 대조한다). 관찰 내용은 그대로다."""
    def make(original: Callable) -> Callable:
        def verify(*args, **kwargs):
            result = original(*args, **kwargs)
            case = recorder.case
            selected = next((c.candidate_id for c in case.candidates if c.selected), None) if case else None
            if not (selected or "").endswith(SECOND_CANDIDATE_SUFFIX):
                return result
            payload = result.model_dump(mode="json")
            payload["visual_evidence"]["candidate_id"] = selected
            return search_module.VisualVerificationResult.model_validate(payload)
        return verify
    return make


_HAPPY_OBSERVATION_FACTS = json.loads(
    (ROOT / "tests" / "evidence" / "fixtures" / "adapter_inputs.json").read_text(encoding="utf-8")
)["scenarios"][f"scenario_{SCENARIO_ID}"]["requirement_observation_facts"]


def _with_observation_facts(original: Callable) -> Callable:
    """최종 신고영상 관찰(I4, `observation_facts`)은 producer가 없어 real 경로 FINAL이 늘 `UNKNOWN`이고
    `READY`에 못 간다(ADR-EVIDENCE-008 §6.2, case 몫 아님). READY 시점 행동과 I1을 재려고 evidence mock
    하니스가 쓰는 happy 값을 러너 안에서만 넣는다."""
    def evaluate_requirements(record, *, scope, **kwargs):
        if scope == "FINAL_PACKAGE" and kwargs.get("observation_facts") is None:
            kwargs["observation_facts"] = _HAPPY_OBSERVATION_FACTS
        return original(record, scope=scope, **kwargs)
    return evaluate_requirements


def _common(recorder: "Recorder") -> list[tuple[Any, str, Callable[[Callable], Callable]]]:
    """모든 관찰 상태에 공통으로 까는 주입 — 후보 2개 합성 · 최종 관찰 사실."""
    return [
        (search_module, "search_candidates", _with_second_candidate),
        (search_module, "verify_visual", _fine_for_selected(recorder)),
        (real_e2e, "evaluate_requirements", _with_observation_facts),
    ]

OBSERVATIONS: dict[str, list[tuple[Any, str, Callable[[Callable], Callable]]]] = {
    "ASSEMBLE": [],
    "NOT_ASSEMBLED": [(search_module, "verify_visual", _not_observed)],
    "PLATE_FAILED": [(real_e2e.readout_api, "read_plate", _plate_failed)],
    "PLATE_UNREAD": [(real_e2e.readout_api, "read_plate", _plate_unread)],
    "AWAIT_RESPONSE": [(search_module, "verify_visual", _uncertain)],
    "NO_CANDIDATES": [(search_module, "search_candidates", _search_outcome("SUCCEEDED"))],
    "SEARCH_FAILED": [(search_module, "search_candidates", _search_outcome("FAILED"))],
}

# ── 행동 ────────────────────────────────────────────────────────────────
# 값은 세션 안에서 반복될 때마다 바뀐다 — 러너가 스스로 무변경 입력을 만들지 않게(무변경은 NOOP 행동이 맡는다).
# 이전 값은 항상 지금 evidence에 보이는 값이다(web이 CaseView에서 보는 값과 같다).

_ASSEMBLE_ONLY = frozenset({"assemble"})
_EVERYTHING = frozenset(stage for _, _, stage in _STAGES)
_REPORT_TYPES = ("TRAFFIC_VIOLATION", "MOTORCYCLE_VIOLATION")


class Ctx:
    def __init__(self, case: CaseAggregate, real: RealAdapter) -> None:
        self.case, self.real, self.n = case, real, Counter()
        self.store = CaseStore()
        self.store.register(case, real)

    def record(self) -> dict[str, Any] | None:
        return self.real.get_evidence_record() if any(c.selected for c in self.case.candidates) else None

    def next(self, key: str) -> int:
        self.n[key] += 1
        return self.n[key]


def _cur_time(ctx: Ctx):
    return ((ctx.record() or {}).get("occurred_at") or {}).get("value")


def _cur_plate(ctx: Ctx):
    return ((ctx.record() or {}).get("vehicle_number") or {}).get("value")


def _cur_report_type(ctx: Ctx):
    return (((ctx.record() or {}).get("event") or {}).get("safety_report_type") or {}).get("value")


def _plate_edit(ctx: Ctx) -> None:
    correction.apply_correction(ctx.case, kind="PLATE_MANUAL_EDIT", target_field="vehicle_number",
                                previous_value=_cur_plate(ctx), new_value=f"12가{9000 + ctx.next('plate')}")


def _report_type(ctx: Ctx) -> None:
    prev = _cur_report_type(ctx) or _REPORT_TYPES[0]
    new = _REPORT_TYPES[1] if prev == _REPORT_TYPES[0] else _REPORT_TYPES[0]
    correction.apply_correction(ctx.case, kind="REPORT_TYPE_CHANGE", target_field="event.safety_report_type",
                                previous_value=prev, new_value=new)


def _event_time(ctx: Ctx) -> None:
    correction.apply_correction(ctx.case, kind="EVENT_TIME_MANUAL", target_field="occurred_at",
                                previous_value=_cur_time(ctx),
                                new_value=f"2026-08-24T18:{10 + ctx.next('time'):02d}:00+09:00")


def _noop(ctx: Ctx) -> None:
    value = _cur_time(ctx)
    correction.apply_correction(ctx.case, kind="EVENT_TIME_MANUAL", target_field="occurred_at",
                                previous_value=value, new_value=value)


def _time_hint(ctx: Ctx) -> None:
    correction.edit_time_hint(ctx.case, {"time": f"{ctx.next('hint')}0분쯤 전이었어요"})
    # 시스템 단계(사용자 행동으로 세지 않음): 재탐색 → rank1 자동 선택
    service.receive_search_candidates(ctx.case, ctx.real)
    _auto_select(ctx.case)


def _command(kind: str, payload: Callable[[CaseAggregate], dict[str, Any]]) -> Callable[[Ctx], None]:
    """web → case 진입점(`handle_command`, #216)으로 보낸다 — 성공 뒤 `READY` 재확인까지 같은 경로다.
    command 거부(`error`)는 domain 거부와 같이 `InvalidTransition`으로 센다."""
    def run(ctx: Ctx) -> None:
        response = handle_command(
            {"case_id": ctx.case.case_id, "expected_case_rev": ctx.case.case_rev, "kind": kind,
             "payload": payload(ctx.case)},
            store=ctx.store,
        )
        if response["error"] is not None:
            raise InvalidTransition(response["error"]["code"])
    return run


def _select(target: Callable[[CaseAggregate], str]) -> Callable[[Ctx], None]:
    return _command("SELECT_OTHER_CANDIDATE", lambda case: {"candidate_id": target(case)})


def _respond(value: str) -> Callable[[Ctx], None]:
    return _command("RECORD_SITUATION_RESPONSE", lambda case: {"value": value})


def _current(case: CaseAggregate) -> str:
    return next((c.candidate_id for c in case.candidates if c.selected), "none-selected")


def _other(case: CaseAggregate) -> str:
    return next((c.candidate_id for c in case.candidates if not c.selected), "no-other-candidate")


def _no_selection(case: CaseAggregate) -> bool:
    return not any(c.selected for c in case.candidates)


def _before_selection(case: CaseAggregate) -> bool:
    """값 정정은 `EVIDENCE_REVIEW`·`READY`에서만 받는다(상태 기계 설계 초안 v1 §4)."""
    return case.stage not in ("EVIDENCE_REVIEW", "READY")


def _always(case: CaseAggregate) -> bool:
    return True


# name → (실행, 허용 단계(①), 거부돼야 하는가(행동 직전 case로 판단), 기대 case_rev 증가)
# command가 같은 요청 안에서 `READY`로 올리면 기대 증가에 +1을 더한다(case-command 계약 §5).
# 4차 측정부터 command 대상 행동(다른 후보 · 상황 응답 · 최종 검토)은 `handle_command`로 보낸다.
# 정정(입력형)은 command 판본이 아직 없어 domain을 그대로 부른다.
ACTIONS: dict[str, tuple[Callable[[Ctx], None], frozenset[str], Callable[[CaseAggregate], bool], int | None]] = {
    "PLATE_MANUAL_EDIT": (_plate_edit, _ASSEMBLE_ONLY, _before_selection, 1),
    "REPORT_TYPE_CHANGE": (_report_type, _ASSEMBLE_ONLY, _before_selection, 1),
    "EVENT_TIME_MANUAL": (_event_time, _ASSEMBLE_ONLY, _before_selection, 1),
    "NOOP_SAME_VALUE": (_noop, frozenset(), _before_selection, 0),  # correction-record §8-7: 무변경 입력은 기록하지 않음
    "USER_REVIEWED": (_command("MARK_REVIEWED", lambda case: {}), _ASSEMBLE_ONLY,
                      lambda case: case.stage != "READY", 1),
    # 상태 기계 설계 초안 v1 §3: 시간 단서 정정은 CANDIDATE_REVIEW·EVIDENCE_REVIEW·READY에서만 —
    # 탐색 실패로 SEARCHING에 머문 case는 `RETRY_SEARCH`가 출구다.
    "TIME_HINT_EDIT": (_time_hint, _EVERYTHING,
                       lambda case: case.stage not in ("CANDIDATE_REVIEW", "EVIDENCE_REVIEW", "READY"), None),
    "RESELECT_MISSING": (_select(lambda case: "does-not-exist"), frozenset(), _always, 0),
    "RESELECT_CURRENT": (_select(_current), frozenset(), _always, 0),
    # 정책 표 2행: 2차 확인(필요시)+병렬 보강·증거 재조립, 1차 탐색은 절대 안 건드린다.
    "OTHER_CANDIDATE": (_select(_other), _EVERYTHING - {"coarse_search"},
                        lambda case: case.stage not in ("EVIDENCE_REVIEW", "READY") or len(case.candidates) < 2, 1),
    # 상황 응답은 관찰을 다시 돌리지 않고 조립만 다시 한다(#203 — 같은 selection context의 관찰 재사용).
    "SITUATION_CONFIRMED": (_respond("CONFIRMED"), _ASSEMBLE_ONLY, _no_selection, 1),
    "SITUATION_UNSURE": (_respond("USER_UNSURE"), _ASSEMBLE_ONLY, _no_selection, 1),
}
_RESPONSES = frozenset({"SITUATION_CONFIRMED", "SITUATION_UNSURE"})
NOT_YET = {
    "PLATE_REREAD · SPAN_ADJUST · TIMELINE_REBASE×2": "real 경로에 흐름 없음",
    "RUN_NOTICE_ACTION(재시도 발주)": "동기 경로에서는 JobRecord만 남고 실행이 없다 — worker 배선 뒤",
    "상황 응답 CORRECTED": "case-command v0이 받지 않는다(입력형 판본)",
}

# ── 불변식 (②) ──────────────────────────────────────────────────────────

_ALLOWED_EDGES = {
    ("SEARCHING", "CANDIDATE_REVIEW"), ("CANDIDATE_REVIEW", "EVIDENCE_REVIEW"),
    ("EVIDENCE_REVIEW", "READY"), ("READY", "EVIDENCE_REVIEW"),
    ("EVIDENCE_REVIEW", "SEARCHING"), ("READY", "SEARCHING"),
}


def _snapshot(case: CaseAggregate) -> tuple:
    return (case.stage, case.case_rev, case.selection_rev, tuple(c.selected for c in case.candidates),
            len(case.correction_records), case.user_reviewed)


def check_view(case: CaseAggregate, real: RealAdapter, view: dict[str, Any]) -> list[str]:
    bad = []
    selected = [c for c in case.candidates if c.selected]
    if view["stage"] == "READY" and view["package"] is None:
        bad.append("I1 READY인데 Package 없음")
    if view["stage"] == "EVIDENCE_REVIEW" and len(selected) != 1:
        bad.append(f"I2 EVIDENCE_REVIEW인데 선택 후보 {len(selected)}개")
    if view["evidence"] is not None:
        record = real.get_evidence_record() or {}
        ref = (record.get("basis") or {}).get("candidate_ref", {}).get("ref")
        if not selected or ref != selected[0].candidate_id or record.get("selection_rev") != case.selection_rev:
            bad.append("I3 evidence가 현재 선택 context가 아님")
    if view["stage"] == "READY" and any(n["blocking"] for n in view["notices"]):
        bad.append("I7 READY인데 blocking notice")
    # I8(user_reviewed ⇒ READY)은 철회 — CaseView 계약 B절 「stage=READY가 아니어도 true일 수 있다」.
    return bad


# ── 세션 ────────────────────────────────────────────────────────────────

def run_session(observation: str, actions: tuple[str, ...]) -> dict[str, Any]:
    recorder = Recorder()
    patches: list[tuple[Any, str, Any]] = []
    injected: dict[tuple[int, str], tuple[Any, str, Callable]] = {}
    for owner, name, make in _common(recorder) + OBSERVATIONS[observation]:
        base = injected.get((id(owner), name), (owner, name, getattr(owner, name)))[2]
        injected[(id(owner), name)] = (owner, name, make(base))
    for owner, name, stage in _STAGES:
        base = injected.pop((id(owner), name), (owner, name, getattr(owner, name)))[2]
        patches.append((owner, name, _counting(recorder, stage, base)))
    # 세지 않는 함수에 건 주입(최종 관찰 사실 등)도 깐다 — 위에서 단계로 감싼 것은 이미 빠졌다.
    patches += list(injected.values())

    result: dict[str, Any] = {"observation": observation, "actions": list(actions), "steps": [],
                              "violations": [], "error": None, "error_step": None}
    started = time.perf_counter()
    with patched(patches):
        case = CaseAggregate.intake(case_id=f"case_{observation}", hints={}, manifest_summary={})
        recorder.case = case
        real = RealAdapter(case_id=case.case_id, case=case, search_scope=_scope(), mock_root=MOCK_ROOT)
        ctx = Ctx(case, real)
        step = "0:setup"
        try:
            case.start_search()
            jobs.issue_coarse_search(case, scope_ref="scope_h001", input_fingerprint="sha1:h001-coarse-search")
            service.receive_search_candidates(case, real)
            _auto_select(case)
            view = service.build_view_from_adapter(case, real)
            result["violations"] += [f"{step}: {v}" for v in check_view(case, real, view)]

            for i, action in enumerate(actions, 1):
                step = f"{i}:{action}"
                run, allowed, reject_if, rev_delta = ACTIONS[action]
                must_reject = reject_if(case)
                before, stage_before = _snapshot(case), case.stage
                mark = recorder.mark()
                rejected = False
                try:
                    run(ctx)
                except InvalidTransition:
                    rejected = True
                view = service.build_view_from_adapter(case, real)
                called = recorder.since(mark)
                after = _snapshot(case)
                extra = sorted(set(called) - allowed)
                result["steps"].append({"action": action, "rerun_ok": not extra, "extra": extra,
                                        "called": dict(Counter(called)), "rejected": rejected,
                                        "stage_before": stage_before, "stage": case.stage})
                result["violations"] += [f"{step}: {v}" for v in check_view(case, real, view)]
                if stage_before != case.stage and (stage_before, case.stage) not in _ALLOWED_EDGES:
                    result["violations"].append(f"{step}: I4 허용 안 된 전이 {stage_before}→{case.stage}")
                if must_reject and not rejected:
                    result["violations"].append(f"{step}: I5 거부돼야 하는데 통과")
                if rejected and not must_reject:
                    result["violations"].append(f"{step}: I5 허용돼야 하는데 거부")
                if rejected and before != after:
                    result["violations"].append(f"{step}: I5 거부됐는데 상태가 바뀜")
                expected = 0 if rejected else rev_delta
                # command가 같은 요청 안에서 READY로 올리면 +1. READY에서 받은 상황 응답은 먼저 내렸다가
                # gate가 그대로면 다시 올리므로 이것도 +1이다(case-command 계약 §5).
                if expected is not None and case.stage == "READY" and (
                    stage_before != "READY" or action in _RESPONSES
                ):
                    expected += 1
                if expected is not None and after[1] - before[1] != expected:
                    result["violations"].append(f"{step}: I6 case_rev +{after[1] - before[1]} (기대 +{expected})")
        except Exception as exc:  # 크래시도 결과다 — 숨기지 않는다
            result["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            result["error_step"] = step
    obs_calls = [(s, k) for s, k in recorder.calls if s != "coarse_search"]
    result["duplicate_calls"] = sum(n - 1 for n in Counter(obs_calls).values() if n > 1)
    result["total_calls"] = len(recorder.calls)
    result["seconds"] = round(time.perf_counter() - started, 3)
    return result


def _sequences(max_length: int):
    for length in range(1, max_length + 1):
        yield from itertools.product(ACTIONS, repeat=length)


def _bucket(counter: Counter, title: str) -> None:
    print(f"\n{title}")
    for key, n in counter.most_common():
        print(f"  {n:5d}  {key}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--length", type=int, default=1, help="행동 순서 최대 길이")
    parser.add_argument("--raw-out", type=Path, default=None, help="세션별 raw JSONL (git에 올리지 않는 위치)")
    args = parser.parse_args()

    sessions = [run_session(o, seq) for o in OBSERVATIONS for seq in _sequences(args.length)]
    if args.raw_out:
        args.raw_out.parent.mkdir(parents=True, exist_ok=True)
        args.raw_out.write_text("\n".join(json.dumps(s, ensure_ascii=False) for s in sessions) + "\n",
                                encoding="utf-8")

    steps = [st for s in sessions for st in s["steps"]]
    total_s = sum(s["seconds"] for s in sessions)
    crashed = [s for s in sessions if s["error"]]
    print(f"세션 {len(sessions)}개 (관찰 {len(OBSERVATIONS)} × 순서 길이 1~{args.length}) · 판정한 행동 {len(steps)}"
          f" · 총 {total_s:.1f}s · 세션당 {total_s / len(sessions):.3f}s")
    print(f"① 필요한 단계만 재실행: 위반 {sum(not st['rerun_ok'] for st in steps)} / {len(steps)} 행동")
    print(f"② 불변식 위반: {sum(len(s['violations']) for s in sessions)}건 · 위반 있는 세션 "
          f"{sum(bool(s['violations']) for s in sessions)} / {len(sessions)}")
    print(f"③ 불필요한 재실행: {sum(s['duplicate_calls'] for s in sessions)} / "
          f"{sum(s['total_calls'] for s in sessions)} 호출")
    print(f"크래시: {len(crashed)} / {len(sessions)} 세션")

    def inv_key(v: str) -> str:
        where, what = v.split(": ", 1)
        return f"{what.split(' ')[0]} @ {where.split(':', 1)[1]}"

    _bucket(Counter(inv_key(v) for s in sessions for v in s["violations"]), "② 불변식 위반 — (불변식 @ 그 단계 행동)별")
    _bucket(Counter(f"{s['error_step'].split(':', 1)[1]} ← {s['error'][:60]} [{s['observation']}]" for s in crashed),
            "크래시 — (멈춘 행동 ← 원인 [관찰])별")
    _bucket(Counter(f"{st['action']} → {st['extra']}" for st in steps if not st["rerun_ok"]),
            "① 위반 — (행동 → 추가 호출된 단계)별")
    print("\n측정 안 한 칸:")
    for name, why in NOT_YET.items():
        print(f"  - {name}: {why}")


if __name__ == "__main__":
    main()
