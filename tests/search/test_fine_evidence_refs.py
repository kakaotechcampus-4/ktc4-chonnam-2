"""Fine은 모델에게 frame ref를 묻지 않는다 (이슈 #135).

`FrameRef`는 `recording`의 `resolve_frame(locator)`만 발급한다
(`contract-source-asset-media-stream.md` §5.3). Fine 입력은 영상 clip 한 덩어리라
모델에게 주소 지정 가능한 frame inventory를 준 적이 없고, 따라서 모델이 답할 수 있는
frame ref는 존재하지 않는다. 실제로 Gemini는 이 칸에 `"00:03"` 같은 타임스탬프를
넣어 돌려줬다.

타임스탬프를 `fr_...`로 변환하는 길은 막혀 있다 — `contract-visual-evidence.md` §4
"위치는 ID에 인코딩하지 않는다", `contract-source-asset-media-stream.md` §5.3 규칙 6,
`module-architecture.md` "Consumer가 여러 값을 이어 붙여 ref를 합성하는 것도 금지다".

그래서 wire schema에서 이 칸을 빼 **애초에 묻지 않는다**. 공개 `VisualEvidence`의
`evidence_refs`는 필드로 남되 빈 tuple이다 — 발급받은 ref가 생기면 그때 채운다.
"""

import io
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import ValidationError

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.execution import RunDeadline
from daesingo.search.fine import verify_fine
from daesingo.search.ledger import SearchLedger
from daesingo.search.media import MediaInput, PreparedMedia
from daesingo.search.provider import CoarseRequest, FineRequest, ProviderResult
from daesingo.search.runs import (
    CandidateEvent,
    CandidateId,
    CandidateSpan,
    ContractRef,
    RunId,
)
from daesingo.search.schemas import (
    CoarseResponse,
    FinePrimitive,
    FineResponse,
    FineTarget,
    FineTemporalFact,
    FineUncertainty,
)
from daesingo.search.scope import VisualEventType
from daesingo.search.sources import ResolvedAnalysisSource
from daesingo.search.usage import ProviderUsage


def _populated_response() -> FineResponse:
    """관찰을 모두 채운 응답 — evidence_refs만 없다."""
    return FineResponse(
        verification="OBSERVED",
        visual_event_type=VisualEventType.SIGNAL,
        target=FineTarget(
            association_status="MATCHED",
            described_as="흰색 SUV",
            match_with_hint=True,
            association_confidence=0.8,
            track_ref=None,
        ),
        primitives=(
            FinePrimitive(kind="red_signal", state="PRESENT", confidence=0.9),
        ),
        temporal_facts=(
            FineTemporalFact(at_offset_ms=3_200, fact="TARGET_ENTERS_INTERSECTION"),
        ),
        uncertainties=(FineUncertainty(kind="OCCLUSION", detail="앞차에 가림"),),
    )


@dataclass(slots=True)
class _Provider:
    response: FineResponse = field(default_factory=_populated_response)

    def search_coarse(self, request: CoarseRequest) -> ProviderResult[CoarseResponse]:
        _ = request
        raise NotImplementedError

    def verify_fine(self, request: FineRequest) -> ProviderResult[FineResponse]:
        _ = request
        return ProviderResult(self.response, ProviderUsage(10, 2, 0, 12), 15)


@dataclass(slots=True)
class _Resolver:
    source: ResolvedAnalysisSource

    def resolve_reference(self, input_ref: ContractRef) -> ResolvedAnalysisSource:
        _ = input_ref
        return self.source

    @contextmanager
    def open_source(self, ref: ContractRef) -> Generator[MediaInput]:
        _ = ref
        stream = io.BytesIO(b"original")
        try:
            yield MediaInput(stream, "video/mp4", 8)
        finally:
            stream.close()


@dataclass(slots=True)
class _Preparer:
    prepared: PreparedMedia

    @contextmanager
    def prepare_fine(
        self,
        media_input: MediaInput,
        start_sec: float,
        end_sec: float,
        deadline: RunDeadline,
    ) -> Generator[PreparedMedia]:
        _ = media_input, start_sec, end_sec, deadline
        yield self.prepared


def _candidate() -> CandidateEvent:
    return CandidateEvent(
        candidate_id=CandidateId("candidate-fine"),
        run_id=RunId("run-coarse"),
        span=CandidateSpan(
            timeline_id="timeline-fine",
            timeline_revision=2,
            start_ms=2_000,
            end_ms=6_000,
            representative_ms=4_000,
        ),
        rank=1,
        ranking_score=0.9,
        event_type_hint=VisualEventType.SIGNAL,
        summary="signal",
        uncertainties=(),
        thumbnail_ref=None,
    )


@pytest.mark.parametrize(
    "model",
    [FineTarget, FinePrimitive, FineTemporalFact, FineUncertainty],
)
def test_fine_wire_schema_does_not_ask_the_model_for_frame_refs(
    model: type,
) -> None:
    # Then — 물어볼 칸이 없으면 모델이 타임스탬프를 채워 넣을 자리도 없다.
    assert "evidence_refs" not in model.model_fields


def test_fine_wire_schema_rejects_model_supplied_frame_refs() -> None:
    # Given — 이슈 #135에서 Gemini가 실제로 돌려준 모양
    payload = {
        "verification": "UNCERTAIN",
        "visual_event_type": None,
        "target": {
            "association_status": "AMBIGUOUS",
            "described_as": None,
            "match_with_hint": None,
            "association_confidence": None,
            "track_ref": None,
        },
        "primitives": [],
        "temporal_facts": [
            {
                "at_offset_ms": 3_000,
                "fact": "TARGET_CROSSES_LINE",
                "evidence_refs": ["00:03", "00:04"],
            }
        ],
        "uncertainties": [],
    }

    # Then — 변환하지 않고 거절한다. search는 ref를 합성할 권한이 없다.
    with pytest.raises(ValidationError):
        FineResponse.model_validate(payload)


def test_fine_emits_empty_evidence_refs_without_crashing(tmp_path: Path) -> None:
    # Given
    source_ref = ContractRef(kind="analysis_source", ref="source-fine")
    source = ResolvedAnalysisSource(source_ref, 10.0, "timeline-fine", 2)
    prepared_path = tmp_path / "prepared.mp4"
    prepared_path.write_bytes(b"prepared")

    # When
    result = verify_fine(
        source_ref,
        _candidate(),
        None,
        VisualEventType.SIGNAL,
        _Resolver(source),
        _Provider(),
        GeminiSearchConfig(fine_padding_sec=1.5),
        SearchLedger(),
        _Preparer(PreparedMedia(prepared_path, "video/mp4", 8, 7.0, 0.5, 7.5)),
        RunDeadline(lambda: 0.0, budget_ms=30_000),
    )

    # Then — 관찰은 보존되고, 근거 ref 칸만 비어 있다.
    evidence = result.visual_evidence
    assert evidence.temporal_facts[0].fact == "TARGET_ENTERS_INTERSECTION"
    assert evidence.temporal_facts[0].at_offset_ms == 3_200
    assert evidence.target.evidence_refs == ()
    assert evidence.primitives[0].evidence_refs == ()
    assert evidence.temporal_facts[0].evidence_refs == ()
    assert evidence.uncertainties[0].evidence_refs == ()
