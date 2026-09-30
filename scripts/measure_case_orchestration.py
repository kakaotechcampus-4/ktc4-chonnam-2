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
from daesingo.case.domain import CaseAggregate, InvalidTransition
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
        selection = (selected, case.selection_rev if case else None)
        # assemble은 정정마다 입력이 바뀐다(순수 계산) — case_rev를 입력에 넣는다.
        return selection + ((case.case_rev,) if stage == "assemble" and case else ())

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


def _common(recorder: "Recorder") -> list[tuple[Any, str, Callable[[Callable], Callable]]]:
    """모든 관찰 상태에 공통으로 까는 주입 — 후보 2개 합성."""
    return [
        (search_module, "search_candidates", _with_second_candidate),
        (search_module, "verify_visual", _fine_for_selected(recorder)),
    ]

OBSERVATIONS: dict[str, list[tuple[Any, str, Callable[[Callable], Callable]]]] = {
    "ASSEMBLE": [],
    "NOT_ASSEMBLED": [(search_module, "verify_visual", _not_observed)],
    "PLATE_FAILED": [(real_e2e.readout_api, "read_plate", _plate_failed)],
    "PLATE_UNREAD": [(real_e2e.readout_api, "read_plate", _plate_unread)],
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


def _reselect(target: Callable[[CaseAggregate], str]) -> Callable[[Ctx], None]:
    def run(ctx: Ctx) -> None:
        correction.reselect_candidate(ctx.case, target(ctx.case))
    return run


def _current(case: CaseAggregate) -> str:
    return next((c.candidate_id for c in case.candidates if c.selected), "none-selected")


def _other(case: CaseAggregate) -> str:
    return next((c.candidate_id for c in case.candidates if not c.selected), "no-other-candidate")


# name → (실행, 허용 단계(①), 거부돼야 하는가, 기대 case_rev 증가)
ACTIONS: dict[str, tuple[Callable[[Ctx], None], frozenset[str], bool, int | None]] = {
    "PLATE_MANUAL_EDIT": (_plate_edit, _ASSEMBLE_ONLY, False, 1),
    "REPORT_TYPE_CHANGE": (_report_type, _ASSEMBLE_ONLY, False, 1),
    "EVENT_TIME_MANUAL": (_event_time, _ASSEMBLE_ONLY, False, 1),
    "NOOP_SAME_VALUE": (_noop, frozenset(), False, 0),  # correction-record §8-7: 무변경 입력은 기록하지 않음
    "USER_REVIEWED": (lambda ctx: ctx.case.mark_reviewed(), _ASSEMBLE_ONLY, False, 1),
    "TIME_HINT_EDIT": (_time_hint, _EVERYTHING, False, None),
    "RESELECT_MISSING": (_reselect(lambda case: "does-not-exist"), frozenset(), True, 0),
    "RESELECT_CURRENT": (_reselect(_current), frozenset(), True, 0),
    # 정책 표 2행: 2차 확인(필요시)+병렬 보강·증거 재조립, 1차 탐색은 절대 안 건드린다.
    "OTHER_CANDIDATE": (_reselect(_other), _EVERYTHING - {"coarse_search"}, False, 1),
}
NOT_YET = {
    "PLATE_REREAD · SPAN_ADJUST · TIMELINE_REBASE×2": "real 경로에 흐름 없음",
    "situation_response": "#177 미머지",
    "READY 시점 행동 · 불변식 1(READY ⇒ Package)": "상황 응답(#177) + observation_facts 주입 필요",
    "UNCERTAIN(응답 대기)": "#203 미머지 — develop에선 ContractInputError",
    "후보 0개 · 탐색 실패": "#209 미머지 — 선택 전 CaseView 크래시",
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
    injected: dict[tuple[int, str], Callable] = {}
    for owner, name, make in _common(recorder) + OBSERVATIONS[observation]:
        base = injected.get((id(owner), name), getattr(owner, name))
        injected[(id(owner), name)] = make(base)
    for owner, name, stage in _STAGES:
        base = injected.get((id(owner), name), getattr(owner, name))
        patches.append((owner, name, _counting(recorder, stage, base)))

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
                run, allowed, must_reject, rev_delta = ACTIONS[action]
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
                                        "called": dict(Counter(called))})
                result["violations"] += [f"{step}: {v}" for v in check_view(case, real, view)]
                if stage_before != case.stage and (stage_before, case.stage) not in _ALLOWED_EDGES:
                    result["violations"].append(f"{step}: I4 허용 안 된 전이 {stage_before}→{case.stage}")
                if must_reject and not rejected:
                    result["violations"].append(f"{step}: I5 거부돼야 하는데 통과")
                if must_reject and before != after:
                    result["violations"].append(f"{step}: I5 거부됐는데 상태가 바뀜")
                if rev_delta is not None and after[1] - before[1] != rev_delta:
                    result["violations"].append(f"{step}: I6 case_rev +{after[1] - before[1]} (기대 +{rev_delta})")
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
