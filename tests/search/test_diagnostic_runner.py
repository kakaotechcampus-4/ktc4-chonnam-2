from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

from pydantic import BaseModel

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.diagnostic import DiagnosticDependencies, run_case
from daesingo.search.diagnostic_models import DiagnosticCase, DiagnosticProfile
from daesingo.search.media import MediaInput, PreparedMedia
from daesingo.search.provider import ProviderResult, StructuredInvocation
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.scope import VisualEventType
from daesingo.search.smoke_errors import ProviderPayloadError
from daesingo.search.usage import ProviderUsage


@dataclass(slots=True)
class FakeInvoker:
    remaining: list[str | ProviderPayloadError]
    calls: list[StructuredInvocation] = field(default_factory=list)

    def invoke_structured[T: BaseModel](
        self, request: StructuredInvocation[T]
    ) -> ProviderResult[T]:
        self.calls.append(request)
        item = self.remaining.pop(0)
        if isinstance(item, ProviderPayloadError):
            raise item
        return ProviderResult(
            request.response_model.model_validate_json(item),
            ProviderUsage(10, 20, 0, 30),
            12,
        )


@dataclass(frozen=True, slots=True)
class FakeMedia:
    path: Path

    @contextmanager
    def prepare_coarse(
        self, media_input: MediaInput, deadline
    ) -> Generator[PreparedMedia]:
        yield PreparedMedia(self.path, "video/mp4", 1, 6, 0, 6)

    @contextmanager
    def prepare_fine(
        self, media_input: MediaInput, start: float, end: float, deadline
    ) -> Generator[PreparedMedia]:
        yield PreparedMedia(self.path, "video/mp4", 1, end - start, start, end)


def _negative() -> FineResponse:
    return FineResponse.model_validate(
        {
            "verification": "NOT_OBSERVED",
            "visual_event_type": None,
            "target": {
                "association_status": "NOT_FOUND",
                "described_as": None,
                "match_with_hint": None,
                "association_confidence": None,
                "track_ref": None,
            },
            "primitives": [],
            "temporal_facts": [],
            "uncertainties": [],
        }
    )


def test_payload_failure_isolated_and_following_candidate_processed(
    tmp_path: Path,
) -> None:
    # Given: two candidate windows; the first Fine response cannot be parsed.
    path = tmp_path / "source.mp4"
    path.write_bytes(b"video")
    coarse = CoarseResponse.model_validate(
        {
            "candidates": [
                {
                    "event_type": "SIGNAL",
                    "span": {"start_sec": start, "end_sec": start + 1},
                    "at_sec": start + 0.5,
                    "observed": ["movement"],
                    "score": score,
                }
                for start, score in ((1, 0.9), (3, 0.8))
            ]
        }
    )
    invoker = FakeInvoker(
        [
            coarse.model_dump_json(),
            ProviderPayloadError("private response must not leak"),
            _negative().model_dump_json(),
        ]
    )
    case = DiagnosticCase(
        case_id="clip",
        source=path,
        duration_sec=6,
        event_types=(VisualEventType.SIGNAL,),
    )
    deps = DiagnosticDependencies(
        invoker,
        FakeMedia(path),
        GeminiSearchConfig(max_retries=0),
        DiagnosticProfile.P3,
    )
    # When: one local case runs through both stages.
    result = run_case(case, deps)
    # Then: the failure is safe, the next candidate completes, and no public evidence is made.
    assert len(invoker.calls) == 3
    assert result.calls[1].issue_codes == ("PROVIDER_PAYLOAD",)
    assert result.calls[1].response is None
    assert result.calls[2].status == "SUCCEEDED"
    assert result.calls[2].usage.total_tokens == 30
    assert "private response" not in result.model_dump_json()
    assert "visual_evidence" not in result.model_dump_json()


def test_out_of_source_candidate_is_not_sent_to_fine(tmp_path: Path) -> None:
    path = tmp_path / "source.mp4"
    path.write_bytes(b"video")
    coarse = CoarseResponse.model_validate(
        {
            "candidates": [
                {
                    "event_type": "SIGNAL",
                    "span": {"start_sec": 5, "end_sec": 7},
                    "at_sec": 6,
                    "observed": [],
                    "score": 0.5,
                }
            ]
        }
    )
    invoker = FakeInvoker([coarse.model_dump_json()])
    case = DiagnosticCase(
        case_id="clip",
        source=path,
        duration_sec=6,
        event_types=(VisualEventType.SIGNAL,),
    )
    result = run_case(
        case,
        DiagnosticDependencies(
            invoker,
            FakeMedia(path),
            GeminiSearchConfig(max_retries=0),
            DiagnosticProfile.P3,
        ),
    )
    assert len(invoker.calls) == 1
    assert result.calls[1].issue_codes == ("CANDIDATE_OUT_OF_BOUNDS",)
    assert result.calls[1].invocation_started is False


def test_media_failure_preserves_coarse_and_processes_next_candidate(
    tmp_path: Path,
) -> None:
    from daesingo.search.media import FfmpegError

    @dataclass(slots=True)
    class FaultyMedia:
        path: Path
        calls: int = 0

        def prepare_coarse(self, media_input, deadline):
            return FakeMedia(self.path).prepare_coarse(media_input, deadline)

        @contextmanager
        def prepare_fine(self, media_input, start, end, deadline):
            self.calls += 1
            if self.calls == 1:
                raise FfmpegError("sensitive codec output")
            yield PreparedMedia(self.path, "video/mp4", 1, end - start, start, end)

    path = tmp_path / "source.mp4"
    path.write_bytes(b"video")
    coarse = CoarseResponse.model_validate(
        {
            "candidates": [
                {
                    "event_type": "SIGNAL",
                    "span": {"start_sec": start, "end_sec": start + 1},
                    "at_sec": start + 0.5,
                    "observed": [],
                    "score": score,
                }
                for start, score in ((1, 0.9), (3, 0.8))
            ]
        }
    )
    invoker = FakeInvoker([coarse.model_dump_json(), _negative().model_dump_json()])
    case = DiagnosticCase(
        case_id="clip",
        source=path,
        duration_sec=6,
        event_types=(VisualEventType.SIGNAL,),
    )
    result = run_case(
        case,
        DiagnosticDependencies(
            invoker,
            FaultyMedia(path),
            GeminiSearchConfig(max_retries=0),
            DiagnosticProfile.P3,
        ),
    )
    assert result.calls[0].usage.total_tokens == 30
    assert result.calls[1].issue_codes == ("MEDIA_PREPARATION",)
    assert result.calls[1].invocation_started is False
    assert result.calls[2].status == "SUCCEEDED"
    assert "sensitive codec" not in result.model_dump_json()
