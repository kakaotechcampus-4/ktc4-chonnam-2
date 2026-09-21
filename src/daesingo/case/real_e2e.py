"""`scenario_happy_001` 대표 시나리오용 real E2E 파이프라인 — recording → search →
readout → evidence까지 전부 실제 공개 함수를 호출한다(W5/W6, 2026-09-22 월 20:00
회의 데드라인 대응).

기준은 "대표 시나리오 1개가 전체 흐름을 실제로 통과하는가"이지 모든 단계가 PASS
등급을 받는가가 아니다(요청 문서 "이번엔 안 해도 되는 것" — 모든 edge case·완성된
Worker 배선은 이번 범위 밖).

## 알려진 단순화 (정직하게 남김 — W7에서 메운다)

- **`time_source_candidates`**: recording의 `RecordingFixture` pydantic 모델에 이
  필드 자체가 없다(1차 구현 범위 밖) — 공개 함수로 노출된 적이 없으므로 recording의
  raw fixture JSON에서 그대로 읽는다. 이 한 곳만 mock이고 나머지는 전부 real 함수
  호출이다.
- **`situation_response`/`observation_facts`**: case에 이 값을 만드는 로직이 아직
  없어(intake UI 미구현) `None`으로 둔다. 그 결과 `FINAL_PACKAGE` 판정이 PASS/WARN에
  못 미쳐 `build_report_package()`가 `PackageNotReady`를 던질 수 있다 — 이건 실패가
  아니라 "정보가 부족해 아직 패키지를 못 만든다"는 실제 도메인 상태이고, `CaseView`의
  partial 표현이 원래 이런 상태를 위해 있다(`module-architecture.md` §5-12).
- **`gps_observation`**: recording이 GPS 관찰을 내놓는 공개 함수를 아직 노출하지 않아
  `None`으로 둔다. case의 자연어 위치 단서(`hints.location`)는 real 경로에 전달하지만,
  좌표(`location.coord`)는 GPS producer가 연결되기 전까지 비어 있을 수 있다.
- **시나리오 고정**: `scenario_happy_001` 하나로 고정돼 있다. 다른 시나리오로 넓히려면
  recording fixture 선택과 asset_facts 매핑을 다시 설계해야 한다(W7).

## Fine 결과 소비 (이슈 #137)

Fine은 `OBSERVED` 말고도 정상적인 결과를 낸다. `verification=NOT_OBSERVED`는 "영상은 봤고
실행도 성공했는데 이 후보를 지지하는 근거가 없다"는 뜻이고(`contract-visual-evidence.md`
§4-1), `EvidenceRecord`로 승격시키면 안 되는 유효한 negative 결과다. 그래서 이 파이프라인은
Fine 결과를 받자마자 `evidence.classify_visual_evidence()`로 분류하고, 조립 대상이 아니면
IncidentClip·readout·TimeResolution·evidence를 **시작하지 않고** 정상 종료한다 —
`EvidenceBundle`의 조립 산출물이 전부 `None`인 것이 그 상태다. `build_evidence_for_real_video_candidate()`도
같은 분류를 거친다(PR #131→#142 후속 정합화, 2026-09-22).

`NOT_OBSERVED`를 `UNCERTAIN` fallback으로 합치지 않는다. `UNCERTAIN + USER_UNSURE`는
사용자가 "잘 모르겠지만 진행"을 택한 generic 신고 경로이고, `NOT_OBSERVED`는 Fine이 후보를
기각한 것이라 둘을 합치면 관찰되지 않은 위반으로 신고문을 만들게 된다.

다음 후보를 자동으로 Fine하거나 가장 높은 후보를 자동 채택하는 정책은 여기 없다 —
`core-user-flow.md`가 정본화된 뒤 Product/Case/Evidence/Web이 함께 정할 후속 변경이다.

## 의존 중(합의됐지만 미병합) — 2026-09-21

- **`search.verify_visual_with_stream_context` / `AnalysisSourceStream` /
  `VideoStreamSelectionError`**: 서어진(search)이 월요일 Real E2E stream 선택
  경계용으로 만들었다고 알려온 API이지만, 이 글을 쓰는 시점엔 어느 브랜치·PR에도
  push되지 않았다(전체 브랜치 grep으로 확인). 아래 코드는 그 API가 그 시그니처로
  들어온다는 전제로 미리 짜둔 것이다 — search 쪽이 실제로 push되기 전까지는
  `ImportError`/`AttributeError`로 실패한다(조용히 다른 것으로 대체하지 않음).
- **`recording.resolve_span(..., media_stream_ref=...)` / `register_local_source()` /
  `create_relative_timeline()`**: 정철원(recording)이 이 시그니처로 준비됐다고
  알려왔다. 실제로는 `origin/feature/recording-real-e2e` 브랜치에 있고(PR 미생성,
  develop 미병합) develop의 `RecordingService.resolve_span()`은 여전히
  2-param(`timeline_ref`, `requested_range`)이다 — 그래서 아래 두 번째
  `resolve_span()` 호출은 이 브랜치가 develop에 없는 동안은
  `TypeError: unexpected keyword argument 'media_stream_ref'`로 실패한다.
- **`AnalysisProfile` / `LocalAnalysisMaterializer`**: 정철원 확인(2026-09-21) —
  `daesingo.recording.materialization`에 있고 `origin/feature/recording-real-e2e`
  (커밋 `3f5fb385`)에만 있다. develop에는 없어서 `build_real_video_evidence_bundle()`은
  이 브랜치가 develop에 없는 동안 `ImportError`로 실패한다.

## `build_real_video_evidence_bundle()` — 월요일 real 영상 경로, 알려진 단순화

- **`profile_ref`**: 정철원 확인(2026-09-21, 이슈 #95 D2와는 별개 — D2는 이미 책임
  경계가 종결돼 월요일 실행이 기다릴 필요 없음) — 480p H.264, preset=veryfast,
  crf=23, audio off. 이 설정은 `profile_ref` 문자열에 인코딩되지 않고 실행 조립 시
  `LocalAnalysisMaterializer`에 명시적으로 등록한다. **최종 canonical profile
  이름·값 공간은 미확정** — `_MONDAY_ANALYSIS_PROFILE`은 이번 실행 안에서의
  동일성/재사용 판단용 opaque 설정일 뿐 계약 기본값이 아니다.
- **`AnalysisScope`의 `budget`/`target_event_types`**: case Producer 소유(recording
  소유 아님). 공용 Mock Pack의 happy 기준(`target_event_types=["SOLID_LINE_LANE_CHANGE"]`,
  `budget={max_cost_krw:1000, max_latency_sec:180}`)을 월요일 GT 없는 배관 E2E에
  재사용한다(정철원 확인, 2026-09-21) — `SOLID_LINE_LANE_CHANGE`는 실제 영상의
  정답을 단정하는 값이 아니라 search에 요청하는 탐지 대상이다. Elice 실제 호출
  한도로 다른 값이 필요하면 서어진 확인이 남는다 — 계약 기본값으로 새로 확정된 게
  아니다.
- **candidate 선택은 `candidates[0]`으로 고정한다.** GT 없는 배관 확인이 목적이라
  "어느 candidate가 맞는지"는 이번 범위 밖이다 — `happy_001`이 후보 1개라 우연히
  안전했던 것과 같은 자리다. 후보가 여럿이면 이 단순화가 그대로 드러난다.
- **readout provider는 여전히 `FixtureOcrProvider`다.** 실제 영상엔 맞지 않는
  provider이지만, 이건 readout Owner가 확인해야 할 별도 gap이라 이 파일이 대신
  풀지 않는다.
- **`RecordingService.close()`는 이 함수가 부르지 않는다.** search가
  `open_analysis_source()`로 바이트를 다 읽기 전에 닫으면 실행 중인 AnalysisSource가
  해제된다(정철원 확인, 2026-09-21) — 반환값에 `rec_service`를 포함해 호출자가 언제
  닫을지 스스로 결정하게 한다.
- **아직 실행해서 확인한 적이 없다.** 실제 영상 파일이 이 저장소에 없고(정철원이
  공유 안 하기로 한 대로), `register_local_source`가 실제 `ffmpeg`/`ffprobe`
  프로세스를 부르므로 이 함수는 로컬에서 실행·테스트되지 않았다 — 아래 새 helper
  (`_unique_video_media_stream_ref`/`_match_analysis_source_streams`)만 순수 값으로
  단위 테스트됐다.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from daesingo import search as search_module
from daesingo.case.domain import CaseAggregate
from daesingo.case.scope import build_analysis_scope
from daesingo.evidence import (
    NOT_ASSEMBLED,
    VisualEvidenceDisposition,
    assemble_evidence,
    build_report_package,
    calculate_evidence_needs,
    classify_visual_evidence,
    evaluate_requirements,
    resolve_time,
)
from daesingo.evidence.errors import PackageNotReady
from daesingo.readout import api as readout_api
from daesingo.readout import providers as readout_providers
from daesingo.readout.contracts import InputRef
from daesingo.recording import AssetSpan, RecordingService, SpanResolution, load_recording_fixture

SCENARIO_ID = "scenario_happy_001"

# 공용 Mock Pack happy 기준(정철원 확인, 2026-09-21) — 계약 기본값으로 확정된 게
# 아니라 월요일 GT 없는 배관 E2E용 재사용 값이다.
_MONDAY_TARGET_EVENT_TYPES = ["SOLID_LINE_LANE_CHANGE"]
_MONDAY_BUDGET = {"max_cost_krw": 1000, "max_latency_sec": 180}

# `AnalysisProfile`/`LocalAnalysisMaterializer`는 모듈 최상단에서 import하지 않는다
# — develop에 아직 없어서(모듈 docstring "의존 중" 참고) 최상단 import로 두면
# `daesingo.case` 패키지 전체(이 파일을 참조하는 `adapters.py`/`service.py`까지)의
# import 자체가 깨진다. `build_real_video_evidence_bundle()` 안에서 지연 import한다
# — 그 함수를 실제로 부르기 전까지는 이 의존성이 나머지 case 코드를 막지 않는다.


class StreamSelectionError(Exception):
    """`SpanResolution.spans[]`에서 쓸 `AssetSpan`을 정확히 하나로 좁힐 수 없을 때.

    여러 VIDEO stream(front/rear 등)이 같은 시간대를 가리킬 수 있다는 게
    `contract-recording-timeline-asset-span.md` §9 불변식 7이 명시적으로 허용하는
    상황이다 — 그 상태에서 `spans[0]`을 조용히 쓰면 어떤 카메라가 선택됐는지가
    사실상 우연이 된다. 그래서 애매하면 조용히 넘어가지 않고 여기서 표면화한다.
    """


def _select_asset_span(
    resolution: SpanResolution, media_stream_ref: str | None
) -> AssetSpan:
    """`media_stream_ref`와 일치하는 span을 명시적으로 고른다.

    `media_stream_ref`가 없으면 span이 정확히 하나일 때만 그대로 쓴다(지금까지의
    단일 스트림 경로와 동일) — span이 여러 개면 어떤 stream인지 명시해야 한다.
    """
    candidates = resolution.spans
    if media_stream_ref is not None:
        candidates = [span for span in candidates if span.media_stream_ref == media_stream_ref]
    if len(candidates) != 1:
        raise StreamSelectionError(
            f"media_stream_ref={media_stream_ref!r}로 span을 하나로 좁힐 수 없습니다 "
            f"(일치하는 span {len(candidates)}개, 전체 {len(resolution.spans)}개). "
            "여러 stream이 같은 시간대를 가리키면 media_stream_ref를 명시해야 합니다."
        )
    return candidates[0]


def _unique_video_media_stream_ref(media_streams: Any) -> str:
    """등록된 `MediaStream` 중 `media_type == "VIDEO"`가 정확히 하나인지 검증하고 그
    ref를 반환한다.

    정철원(recording) 확인(2026-09-21) — 이건 "여러 VIDEO 후보 중 하나를 임의로
    고르는 것"이 아니라 **유일성 검증**이다. 월요일 대표 파일(`20260620_141956_EVT_1.avi`)은
    ffprobe 결과 VIDEO 1개/AUDIO 1개뿐이라(subtitle/data는 recording이 등록에서
    제외) 이 검증이 항상 통과해야 정상이다. VIDEO가 0개거나 여러 개면 recording이
    임의로 고르지 않듯 case도 임의로 고르지 않고 여기서 실패시킨다 — 일반적인 복수
    카메라 선택 정책은 W7 후속이다.
    """
    video_refs = [s.media_stream_ref for s in media_streams if s.media_type == "VIDEO"]
    if len(video_refs) != 1:
        raise StreamSelectionError(
            f"media_streams에서 media_type=VIDEO가 정확히 하나가 아닙니다"
            f"(VIDEO {len(video_refs)}개). 복수 카메라 선택 정책은 W7 후속이라 case가"
            " 여기서 임의로 고르지 않는다."
        )
    return video_refs[0]


def _match_analysis_source_streams(
    media_stream_refs: Any, media_streams: Any
) -> tuple[Any, ...]:
    """`AnalysisSource.media_stream_refs[]`의 각 ref를 등록된 `media_streams`(fixture의
    `RecordingFixture.media_streams` 또는 `register_local_source()`가 돌려준
    `RegisteredSource.media_streams`)에서 찾아 `search.AnalysisSourceStream`으로
    변환한다.

    누락(매칭 0개)되거나 중복 매칭(2개 이상)되면 fixture 값으로 보정하지 않고 여기서
    실패시킨다(정철원 확인, 2026-09-21) — search가 stream을 임의로 고르지 않는 것과
    같은 원칙이다.
    """
    streams: list[Any] = []
    for ref in media_stream_refs:
        matches = [s for s in media_streams if s.media_stream_ref == ref]
        if len(matches) != 1:
            raise StreamSelectionError(
                f"AnalysisSource.media_stream_refs의 {ref!r}가 등록된 media_streams에서"
                f" 정확히 하나로 매칭되지 않습니다(매칭 {len(matches)}개)."
            )
        streams.append(
            search_module.AnalysisSourceStream(
                media_stream_ref=ref, media_type=matches[0].media_type
            )
        )
    return tuple(streams)


def _resolve_via_search_stream_context(
    *,
    analysis_source: Any,
    media_streams: Any,
    candidate: search_module.CandidateEvent,
    target_hint: Any,
) -> tuple[Any, str]:
    """`AnalysisSource.media_stream_refs`를 등록된 `media_streams`와 매칭해 search의
    실행 문맥 API를 부르고, `(VisualVerificationResult, 선택된 media_stream_ref)`를
    돌려준다. fixture 경로(`build_happy_001_evidence_bundle`)와 실제 영상 경로
    (`build_real_video_evidence_bundle`)가 공유한다.
    """
    analysis_source_streams = _match_analysis_source_streams(
        analysis_source.media_stream_refs, media_streams
    )
    execution = search_module.verify_visual_with_stream_context(
        input_ref=search_module.ContractRef(
            kind="analysis_source", ref=analysis_source.analysis_source_ref
        ),
        candidate=candidate,
        analysis_source_streams=analysis_source_streams,
        target_hint=target_hint,
    )
    return execution.result, execution.selected_video_stream.media_stream_ref


@dataclass
class EvidenceBundle:
    """Fine 결과를 소비한 결과. `NOT_OBSERVED`면 조립 산출물 쪽이 전부 `None`이다.

    `visual_evidence`/`fine_run`/`disposition`은 어느 결말에서도 채워진다 — Fine이
    후보를 기각했다는 것도 평가·진단에 쓰이는 관찰 결과라서(`adr-visual-evidence.md`)
    조립을 하지 않는다고 지워버리면 안 된다. `fine_run`에 `usage_refs`/`usage_summary`가
    들어 있어 비용 기록도 같이 남는다.
    """

    evidence_record: dict[str, Any] | None
    evidence_needs: dict[str, Any] | None
    requirement_report_evidence: dict[str, Any] | None
    requirement_report_package: dict[str, Any] | None
    report_package: dict[str, Any] | None
    package_error: str | None
    visual_evidence: dict[str, Any]
    fine_run: dict[str, Any]
    disposition: VisualEvidenceDisposition

    @property
    def assembled(self) -> bool:
        return self.evidence_record is not None


def build_happy_001_evidence_bundle(
    *,
    case_id: str,
    candidate: search_module.CandidateEvent,
    scope: search_module.AnalysisScope,
    mock_root: Path,
    selection_rev: int = 1,
    correction_records: list[dict[str, Any]] | None = None,
    location_hint: str | None = None,
) -> EvidenceBundle:
    """recording → `search.verify_visual_with_stream_context` → readout → evidence까지
    실제 함수로 이어서 실행한다. 모듈 docstring의 "알려진 단순화" 두 곳만 raw
    fixture/`None`이고 나머지는 전부 각 모듈의 공개 함수 호출 결과다.

    `correction_records`는 case의 사용자 정정을 evidence 계산에 전달한다(이슈 #73).
    """
    fixture = load_recording_fixture(SCENARIO_ID)
    rec_service = RecordingService.from_fixture(fixture, case_id=case_id)

    # candidate.span을 recording.resolve_span() 입력으로 변환한다 — ms→sec는
    # recording 경계에서 명시적으로 한다(`contract-analysis-scope.md` §12 B08).
    timeline_ref = {
        "timeline_id": candidate.span.timeline_id,
        "revision": candidate.span.timeline_revision,
    }
    requested_range = {
        "start_sec": candidate.span.start_ms / 1000,
        "end_sec": candidate.span.end_ms / 1000,
    }
    resolution = rec_service.resolve_span(timeline_ref, requested_range)

    # AnalysisSource는 source_asset_ref+timeline_range+profile로 찾아지고(recording의
    # find_analysis_sources가 `media_stream_ref in media_stream_refs[]`로 매칭),
    # 어떤 span을 넘기든 같은 그룹의 AnalysisSource가 나온다 — 실제로 어떤 VIDEO
    # stream을 분석에 쓸지는 이 다음 search가 고른다.
    analysis_source = rec_service.prepare_analysis_source(
        resolution.spans[0].model_dump(mode="json"),
        fixture.analysis_sources[0].profile_ref,
    )

    # search와 합의한 stream 선택 경계(2026-09-21, 정철원·서어진) — search가 실제로
    # 분석에 쓴 VIDEO stream ref 하나를 `CandidateEvent`/`VisualVerificationResult`의
    # canonical 계약은 바꾸지 않고 별도 실행 문맥으로 돌려준다. media_type은 월요일
    # 범위에서 `fixture.media_streams`로 읽는다(실제 영상에서는
    # `RegisteredSource.media_streams` — 모듈 docstring 참고).
    visual_result, media_stream_ref = _resolve_via_search_stream_context(
        analysis_source=analysis_source,
        media_streams=fixture.media_streams,
        candidate=candidate,
        target_hint=scope.hint,
    )
    visual_evidence = visual_result.visual_evidence.model_dump(mode="json")
    fine_run = visual_result.analysis_run.model_dump(mode="json")

    # Fine 결과를 downstream(두 번째 resolve_span·IncidentClip 포함)으로 밀어넣기 전에
    # 먼저 분류한다(이슈 #137). `NOT_OBSERVED`는 실행 실패가 아니라 "이 후보는 아니다"라는
    # 유효한 관찰 결과이므로, IncidentClip·readout·TimeResolution·evidence 조립을
    # 시작하지 않고 여기서 정상 종료한다. 다음 후보를 자동으로 고르는 정책은 이번 범위가
    # 아니다 — `core-user-flow.md`가 정본화된 뒤 별도로 결정한다.
    disposition = classify_visual_evidence(visual_evidence)
    if disposition.decision == NOT_ASSEMBLED:
        return EvidenceBundle(
            evidence_record=None,
            evidence_needs=None,
            requirement_report_evidence=None,
            requirement_report_package=None,
            report_package=None,
            package_error=None,
            visual_evidence=visual_evidence,
            fine_run=fine_run,
            disposition=disposition,
        )

    # 두 번째 resolve_span() (정철원 정정, 2026-09-21) — recording이 이제
    # media_stream_ref를 직접 받아 검증·좁히므로, search가 고른 stream으로 다시
    # 명시적으로 부른다. 실제 로컬 영상(`register_local_source`로 등록된 source)에서는
    # media_stream_ref 없이는 이 호출 자체가 실패하므로, 첫 호출과 동일 인자를 그냥
    # 재사용하지 않는다. `_select_asset_span`은 fixture 경로(media_stream_ref를 줘도
    # recording이 spans[]를 자동으로 좁혀주지 않는 경로)에 대한 방어적 재확인으로 남긴다
    # — 실제 로컬 영상 경로는 recording이 이미 단일 span으로 narrowing해서 돌려주므로
    # 여기서는 no-op 확인이 된다.
    fine_resolution = rec_service.resolve_span(
        timeline_ref, requested_range, media_stream_ref=media_stream_ref
    )
    selected_span = _select_asset_span(fine_resolution, media_stream_ref)
    narrowed_resolution = fine_resolution.model_copy(update={"spans": [selected_span]})
    incident_clip = rec_service.build_incident_clip(
        narrowed_resolution.model_dump(mode="json")
    )

    read_request = readout_api.ReadRequest(
        case_id=case_id,
        candidate_id=candidate.candidate_id,
        input_ref=InputRef(
            incident_clip_ref=incident_clip.incident_clip_ref,
            source_profile="readout-native",
            provenance="SOURCE_DERIVED_INCIDENT_CLIP",
        ),
    )
    _plate_run, plate_readout = readout_api.read_plate(
        read_request, provider=readout_providers.FixtureOcrProvider()
    )
    _overlay_run, overlay_readout = readout_api.read_overlay_time(
        read_request, provider=readout_providers.FixtureOcrProvider()
    )

    # 알려진 단순화 1 (모듈 docstring 참고) — recording이 아직 공개 함수로 노출 안 함.
    raw_recording = json.loads(
        (mock_root / "recording" / f"{SCENARIO_ID}.json").read_text(encoding="utf-8")
    )
    time_source_candidates = raw_recording.get("time_source_candidates", [])

    time_resolution = resolve_time(
        time_source_candidates=time_source_candidates,
        overlay_time_readout=overlay_readout.to_dict() if overlay_readout else None,
        candidate_event=candidate.model_dump(mode="json"),
        correction_records=correction_records or [],
        case_id=case_id,
        selection_rev=selection_rev,
        resolution_id=f"tr_{case_id}_001",
    )

    evidence_record = assemble_evidence(
        case_id=case_id,
        selection_rev=selection_rev,
        candidate_event=candidate.model_dump(mode="json"),
        visual_evidence=visual_evidence,
        time_resolution=time_resolution,
        plate_readout=plate_readout.to_dict() if plate_readout else None,
        incident_clip=incident_clip.model_dump(mode="json"),
        record_id=f"er_{case_id}_001",
        location_hint=location_hint,
        # 알려진 단순화 2 및 GPS 단순화 (모듈 docstring 참고).
        situation_response=None,
        gps_observation=None,
        correction_records=correction_records or [],
    )

    evidence_needs = calculate_evidence_needs(
        evidence_record,
        plate_readout.to_dict() if plate_readout else None,
        emit_empty=True,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    requirement_report_evidence = evaluate_requirements(
        evidence_record,
        scope="EVIDENCE",
        report_id=f"rr_{case_id}_evidence",
        evaluated_at=now,
        time_resolution=time_resolution,
    )

    asset_refs = [facts.asset_ref for facts in fixture.asset_facts]
    asset_facts_real = [
        rec_service.lookup_asset_facts(ref).model_dump(mode="json") for ref in asset_refs
    ]
    requirement_report_package = evaluate_requirements(
        evidence_record,
        scope="FINAL_PACKAGE",
        report_id=f"rr_{case_id}_package",
        evaluated_at=now,
        time_resolution=time_resolution,
        asset_facts=asset_facts_real,
        # 알려진 단순화 2와 같은 이유로 None (모듈 docstring 참고).
        observation_facts=None,
    )

    report_package: dict[str, Any] | None = None
    package_error: str | None = None
    try:
        report_package = build_report_package(
            evidence_record,
            requirement_report_package,
            package_id=f"pkg_{case_id}_001",
            created_at=now,
            asset_facts=asset_facts_real,
        )
    except PackageNotReady as exc:
        package_error = str(exc)

    return EvidenceBundle(
        evidence_record=evidence_record,
        evidence_needs=evidence_needs,
        requirement_report_evidence=requirement_report_evidence,
        requirement_report_package=requirement_report_package,
        report_package=report_package,
        package_error=package_error,
        visual_evidence=visual_evidence,
        fine_run=fine_run,
        disposition=disposition,
    )


def build_real_video_evidence_bundle(
    *,
    case_id: str,
    local_video_path: str | Path,
    case: CaseAggregate,
    scope_id: str,
    selection_rev: int = 1,
    correction_records: list[dict[str, Any]] | None = None,
    location_hint: str | None = None,
) -> tuple[EvidenceBundle, RecordingService]:
    """월요일 real 영상(`register_local_source`) 경로 — 모듈 docstring
    "build_real_video_evidence_bundle() 알려진 단순화" 절의 전제를 그대로 따른다.
    실행되어 검증된 적은 없다(같은 절 참고).

    `case`는 `scope.build_analysis_scope()`가 `hint.vehicle`/`hint.free_text`를
    파생할 `case.hints`를 읽기 위해서만 쓰인다 — 이 함수가 `case`의 상태를 바꾸지
    않는다.

    반환하는 `RecordingService`는 호출자가 이 함수의 결과(특히 evidence 조립까지
    끝난 뒤, search의 `open_analysis_source()` 소비도 끝난 뒤)에 `close()`해야 한다.
    """
    # 지연 import — 모듈 최상단 주석 참고(develop에 아직 없어서 여기서만 부른다).
    from daesingo.recording import AnalysisProfile, LocalAnalysisMaterializer

    # 월요일 대표 파일(20260620_141956_EVT_1.avi) 기준 profile 설정 — 480p H.264,
    # preset=veryfast, crf=23, audio off(정철원 확인, 2026-09-21). canonical profile
    # 값 공간이 아니라 이번 실행 전용 opaque 설정이다(모듈 docstring 참고).
    profile_ref = f"prof_{uuid4().hex}"
    materializer = LocalAnalysisMaterializer(
        {profile_ref: AnalysisProfile(height=480, preset="veryfast", crf=23)}
    )
    rec_service = RecordingService(analysis_materializer=materializer)

    registered = rec_service.register_local_source(local_video_path)
    timeline = rec_service.create_relative_timeline(registered.source_asset.source_asset_ref)

    # 부트스트랩 stream 선택 — 정철원 확인(2026-09-21): 유일성 검증이지 임의 선택이
    # 아니다(모듈 docstring 참고).
    bootstrap_ref = _unique_video_media_stream_ref(registered.media_streams)

    duration_ms = int((registered.source_asset.duration_sec or 0) * 1000)
    if duration_ms <= 0:
        raise StreamSelectionError(
            "등록된 SourceAsset의 duration_sec을 확인할 수 없어 AnalysisScope 범위를"
            " 만들 수 없습니다."
        )
    scope_dict = build_analysis_scope(
        case,
        scope_id=scope_id,
        time_ranges=[
            {
                "kind": "TIMELINE_RELATIVE",
                "timeline_ref": {
                    "timeline_id": timeline.timeline_id,
                    "revision": timeline.revision,
                },
                "start_ms": 0,
                "end_ms": duration_ms,
            }
        ],
        target_event_types=_MONDAY_TARGET_EVENT_TYPES,
        max_cost_krw=_MONDAY_BUDGET["max_cost_krw"],
        max_latency_sec=_MONDAY_BUDGET["max_latency_sec"],
    )
    scope = search_module.AnalysisScope.model_validate(scope_dict)
    candidates = search_module.search_candidates(scope).candidates
    if not candidates:
        raise StreamSelectionError(
            "월요일 대표 영상에서 candidate가 하나도 나오지 않았습니다 — GT 없는"
            " 배관 확인이 목적이라 이 경우를 자동으로 처리하지 않는다."
        )
    # 알려진 단순화(모듈 docstring 참고) — candidate가 여럿이면 어느 것이 맞는지는
    # 이번 범위 밖이라 첫 번째를 그대로 쓴다.
    candidate = candidates[0]

    timeline_ref = {
        "timeline_id": candidate.span.timeline_id,
        "revision": candidate.span.timeline_revision,
    }
    requested_range = {
        "start_sec": candidate.span.start_ms / 1000,
        "end_sec": candidate.span.end_ms / 1000,
    }
    bootstrap_resolution = rec_service.resolve_span(
        timeline_ref, requested_range, media_stream_ref=bootstrap_ref
    )
    bootstrap_span = _select_asset_span(bootstrap_resolution, bootstrap_ref)
    analysis_source = rec_service.prepare_analysis_source(
        bootstrap_span.model_dump(mode="json"),
        profile_ref,
        timeline_ref=timeline_ref,
    )

    visual_result, media_stream_ref = _resolve_via_search_stream_context(
        analysis_source=analysis_source,
        media_streams=registered.media_streams,
        candidate=candidate,
        target_hint=scope.hint,
    )
    # 정철원 확인(2026-09-21) — 월요일 대표 파일은 VIDEO가 하나뿐이라 search가
    # 부트스트랩과 다른 stream을 고를 수 없다. 다르면 조용히 넘어가지 않고 실패시켜
    # 배선 버그를 표면화한다.
    if media_stream_ref != bootstrap_ref:
        raise StreamSelectionError(
            f"search 실행 문맥이 돌려준 media_stream_ref({media_stream_ref!r})가"
            f" 부트스트랩 ref({bootstrap_ref!r})와 다릅니다 — 월요일 대표 파일은"
            " VIDEO가 하나뿐이라 항상 같아야 합니다."
        )

    fine_resolution = rec_service.resolve_span(
        timeline_ref, requested_range, media_stream_ref=media_stream_ref
    )
    selected_span = _select_asset_span(fine_resolution, media_stream_ref)
    narrowed_resolution = fine_resolution.model_copy(update={"spans": [selected_span]})
    incident_clip = rec_service.build_incident_clip(
        narrowed_resolution.model_dump(mode="json")
    )

    read_request = readout_api.ReadRequest(
        case_id=case_id,
        candidate_id=candidate.candidate_id,
        input_ref=InputRef(
            incident_clip_ref=incident_clip.incident_clip_ref,
            source_profile="readout-native",
            provenance="SOURCE_DERIVED_INCIDENT_CLIP",
        ),
    )
    # 알려진 단순화(모듈 docstring 참고) — 실제 영상엔 맞지 않는 provider지만
    # readout Owner가 풀 gap이라 여기서 대신 만들지 않는다.
    _plate_run, plate_readout = readout_api.read_plate(
        read_request, provider=readout_providers.FixtureOcrProvider()
    )
    _overlay_run, overlay_readout = readout_api.read_overlay_time(
        read_request, provider=readout_providers.FixtureOcrProvider()
    )

    # 알려진 단순화 1과 같은 이유(모듈 docstring) — recording이 time_source_candidates를
    # 아직 공개 함수로 노출하지 않고, 실제 영상엔 읽을 raw fixture JSON 자체가 없다.
    time_source_candidates: list[dict[str, Any]] = []

    time_resolution = resolve_time(
        time_source_candidates=time_source_candidates,
        overlay_time_readout=overlay_readout.to_dict() if overlay_readout else None,
        candidate_event=candidate.model_dump(mode="json"),
        correction_records=correction_records or [],
        case_id=case_id,
        selection_rev=selection_rev,
        resolution_id=f"tr_{case_id}_001",
    )

    evidence_record = assemble_evidence(
        case_id=case_id,
        selection_rev=selection_rev,
        candidate_event=candidate.model_dump(mode="json"),
        visual_evidence=visual_result.visual_evidence.model_dump(mode="json"),
        time_resolution=time_resolution,
        plate_readout=plate_readout.to_dict() if plate_readout else None,
        incident_clip=incident_clip.model_dump(mode="json"),
        record_id=f"er_{case_id}_001",
        location_hint=location_hint,
        situation_response=None,
        gps_observation=None,
        correction_records=correction_records or [],
    )

    evidence_needs = calculate_evidence_needs(
        evidence_record,
        plate_readout.to_dict() if plate_readout else None,
        emit_empty=True,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    requirement_report_evidence = evaluate_requirements(
        evidence_record,
        scope="EVIDENCE",
        report_id=f"rr_{case_id}_evidence",
        evaluated_at=now,
        time_resolution=time_resolution,
    )

    # 알려진 단순화(모듈 docstring) — fixture 경로의 fixture.asset_facts 목록에
    # 대응하는 것이 없어, 이 실행에서 실제로 만든 자산 3개(원본·AnalysisSource·
    # IncidentClip)만 조회한다. 신고요건 판정에 필요한 전체 자산 집합과 다를 수 있다.
    asset_facts_real = [
        rec_service.lookup_asset_facts(
            {"kind": "source_asset", "ref": registered.source_asset.source_asset_ref}
        ).model_dump(mode="json"),
        rec_service.lookup_asset_facts(
            {"kind": "analysis_source", "ref": analysis_source.analysis_source_ref}
        ).model_dump(mode="json"),
        rec_service.lookup_asset_facts(
            {"kind": "incident_clip", "ref": incident_clip.incident_clip_ref}
        ).model_dump(mode="json"),
    ]
    requirement_report_package = evaluate_requirements(
        evidence_record,
        scope="FINAL_PACKAGE",
        report_id=f"rr_{case_id}_package",
        evaluated_at=now,
        time_resolution=time_resolution,
        asset_facts=asset_facts_real,
        observation_facts=None,
    )

    report_package: dict[str, Any] | None = None
    package_error: str | None = None
    try:
        report_package = build_report_package(
            evidence_record,
            requirement_report_package,
            package_id=f"pkg_{case_id}_001",
            created_at=now,
            asset_facts=asset_facts_real,
        )
    except PackageNotReady as exc:
        package_error = str(exc)

    bundle = EvidenceBundle(
        evidence_record=evidence_record,
        evidence_needs=evidence_needs,
        requirement_report_evidence=requirement_report_evidence,
        requirement_report_package=requirement_report_package,
        report_package=report_package,
        package_error=package_error,
    )
    return bundle, rec_service
