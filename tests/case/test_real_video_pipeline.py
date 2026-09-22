"""월요일 대표 real 영상(`register_local_source`) 경로 — `RealVideoAdapter`가
`case.get_view()`까지 실제로 이어지는지 확인한다.

search의 Coarse/Fine만 스텁으로 바꾼다(이슈 #132 — search 내부 coarse/fine
시간 정합성 검증이 이 영상에서 항상 실패해서, 실제 유료 호출로는 아직
`CaseView`까지 갈 수 없다. `docs/modules/case/experiments/
real-e2e-20260922-monday-baseline.md` 참고). recording(`register_local_source`
~`build_incident_clip`~`observe_time_sources`)과 readout(실제 PaddleOCR)은
전부 real 함수 호출이다 — case가 다운스트림에서 조용히 다른 걸로 대체하지
않는다는 것까지 이 테스트가 확인한다.

실제 영상 파일이 로컬에만 있고(정철원이 공유 안 하기로 함, git 미커밋) ffmpeg/
ffprobe·paddleocr도 필요해서, 없는 환경에서는 skip한다 — CI를 막지 않는다.

⚠️ **ffmpeg 빌드에 따라 결과가 갈린다(실행해보고 발견함).** conda-forge의
`ffmpeg` 4.3.1은 이 영상을 480p로 transcode할 때
`RecordingCapabilityError: ... media와 목표 frame coverage/시간이 어긋나 매치할
수 없습니다`로 매번 실패한다 — `pip install static-ffmpeg`가 받는 8.0.1
essentials 빌드는 같은 입력에서 매번 성공한다(재현 확인, 우연 아님). PATH에서
먼저 잡히는 `ffmpeg`가 어느 빌드인지에 따라 이 테스트가 갑자기 실패한 것처럼
보일 수 있다 — 그럴 땐 ffmpeg 자체가 아니라 recording의 로컬 materialization
쪽(`materialization.py`)이 이 특정 빌드의 출력을 못 받아들이는 게 원인이다.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from daesingo.case import jobs, real_e2e, service
from daesingo.case.adapters import RealVideoAdapter
from daesingo.case.domain import CaseAggregate

ROOT = Path(__file__).resolve().parents[2]
VIDEO_PATH = ROOT / "doc" / "20260620_141956_EVT_1.avi"

_FFMPEG_MISSING = shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None
try:
    import paddleocr as _paddleocr  # noqa: F401

    _PADDLEOCR_MISSING = False
except ImportError:
    _PADDLEOCR_MISSING = True

_SKIP_REASON = (
    f"video missing ({VIDEO_PATH})" if not VIDEO_PATH.exists()
    else "ffmpeg/ffprobe not on PATH" if _FFMPEG_MISSING
    else "paddleocr not installed" if _PADDLEOCR_MISSING
    else None
)
_NEEDS_REAL_VIDEO_ENV = pytest.mark.skipif(_SKIP_REASON is not None, reason=_SKIP_REASON or "")


def _visual_evidence_template() -> dict[str, Any]:
    data = json.loads(
        (ROOT / "data" / "mock" / "search" / "scenario_happy_001.json").read_text(encoding="utf-8")
    )
    return data["visual_evidences"][0]


class _DictModel(dict):
    def model_dump(self, mode: str = "json") -> dict:
        return dict(self)


@dataclass
class _FakeVisualResult:
    visual_evidence: _DictModel
    analysis_run: _DictModel


@dataclass
class _FakeExecution:
    result: Any
    selected_video_stream: Any


def _install_stubbed_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """search Coarse/Fine만 스텁으로 바꾼다(이슈 #132) — 나머지는 전부 real이다."""
    import daesingo.search as search_module
    from daesingo.search.runs import CandidateEvent, CandidateSpan

    def fake_search_candidates(scope, *, service=None):
        del service
        time_range = scope.time_ranges[0]
        duration_ms = time_range.end_ms - time_range.start_ms
        start_ms = time_range.start_ms + duration_ms // 3
        end_ms = time_range.start_ms + 2 * duration_ms // 3
        candidate = CandidateEvent(
            candidate_id="candidate_monday_test_001",
            run_id="run_monday_test_coarse",
            span=CandidateSpan(
                timeline_id=time_range.timeline_ref.timeline_id,
                timeline_revision=time_range.timeline_ref.revision,
                start_ms=start_ms,
                end_ms=end_ms,
                representative_ms=(start_ms + end_ms) // 2,
            ),
            rank=1,
            ranking_score=0.9,
            event_type_hint=None,
            summary="[STUB — 이슈 #132] search Coarse 대신",
            uncertainties=(),
            thumbnail_ref=None,
        )

        class _Result:
            candidates = (candidate,)

        return _Result()

    def fake_verify_visual_with_stream_context(
        *, input_ref, candidate, analysis_source_streams, target_hint, service=None
    ):
        del target_hint, service
        selected = search_module.select_single_video_stream(input_ref, analysis_source_streams)
        visual_evidence = dict(_visual_evidence_template())
        visual_evidence["candidate_id"] = candidate.candidate_id
        visual_evidence["input_ref"] = {"kind": input_ref.kind, "ref": input_ref.ref}
        analysis_run = {
            "run_id": "run_monday_test_fine",
            "operation": "VISUAL_VERIFY",
            "outcome": "SUCCEEDED",
            "usage_refs": [],
            "usage_summary": None,
        }
        return _FakeExecution(
            result=_FakeVisualResult(_DictModel(visual_evidence), _DictModel(analysis_run)),
            selected_video_stream=selected,
        )

    monkeypatch.setattr(search_module, "search_candidates", fake_search_candidates)
    monkeypatch.setattr(
        search_module, "verify_visual_with_stream_context", fake_verify_visual_with_stream_context
    )


@_NEEDS_REAL_VIDEO_ENV
def test_real_video_adapter_reaches_ready_caseview(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stubbed_search(monkeypatch)

    case = CaseAggregate.intake(case_id="case_monday_real_video_test", hints={}, manifest_summary={})
    real = RealVideoAdapter(
        case_id=case.case_id,
        case=case,
        local_video_path=VIDEO_PATH,
        scope_id="scope_monday_real_video_test",
    )
    try:
        case.start_search()
        jobs.issue_coarse_search(
            case, scope_ref="scope_monday_real_video_test", input_fingerprint="sha1:monday-coarse"
        )

        candidates = service.receive_search_candidates(case, real)
        assert len(candidates) == 1
        case.select_candidate(candidates[0].candidate_id)

        jobs.issue_plate_read(case, input_fingerprint="sha1:monday-plate")
        jobs.issue_overlay_time_read(case, input_fingerprint="sha1:monday-overlay")
        case.mark_ready()

        view = service.build_view_from_adapter(case, real)
    finally:
        real.close()

    assert view["stage"] == "READY"
    # 실제 dashcam overlay OCR이 실제로 읽은 값이다(스텁이 아님) — 파일명
    # (20260620_141956)과 초 단위까지 일치해야 한다.
    assert view["evidence"]["event_time_display"]["value"] == "2026-06-20T14:19:56+09:00"
    assert view["evidence"]["event_time_display"]["info_state"] == "INFO_SOURCE_VERIFIED"
    assert view["requirements_evidence"]["readiness"] == "UNKNOWN"


@_NEEDS_REAL_VIDEO_ENV
def test_real_video_context_can_be_reused_for_multiple_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    """`prepare_real_video_context()`가 만든 whole-video AnalysisSource를 여러
    candidate에 재사용해도 두 번째 `resolve_span()`(candidate별 incident clip)이
    독립적으로 도는지 확인한다 — coarse용 context와 fine용 span 선택이 서로
    간섭하지 않는다는 것."""
    _install_stubbed_search(monkeypatch)

    case = CaseAggregate.intake(case_id="case_monday_reuse_test", hints={}, manifest_summary={})
    context = real_e2e.prepare_real_video_context(
        local_video_path=VIDEO_PATH, case=case, scope_id="scope_monday_reuse_test"
    )
    try:
        candidates = real_e2e.get_real_video_candidates(context)
        assert len(candidates) == 1
        bundle = real_e2e.build_evidence_for_real_video_candidate(
            context, candidates[0], case_id=case.case_id
        )
        assert bundle.evidence_record["occurred_at"]["value"] == "2026-06-20T14:19:56+09:00"
    finally:
        context.rec_service.close()
