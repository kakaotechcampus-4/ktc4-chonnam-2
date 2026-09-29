import io
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from daesingo.search.execution import RunDeadline
from daesingo.search.media import MediaInput, PreparedMedia
from daesingo.search.runs import ContractRef, RunId
from daesingo.search.scope import AnalysisScope
from daesingo.search.service import SearchService
from daesingo.search.sources import AnalysisSourceResolver, ResolvedAnalysisSource


class OpenableResolver:
    _delegate: AnalysisSourceResolver

    def __init__(self, delegate: AnalysisSourceResolver) -> None:
        self._delegate = delegate

    def resolve(self, scope: AnalysisScope) -> tuple[ResolvedAnalysisSource, ...]:
        return self._delegate.resolve(scope)

    def resolve_reference(self, input_ref: ContractRef) -> ResolvedAnalysisSource:
        return self._delegate.resolve_reference(input_ref)

    @contextmanager
    def open_source(self, ref: ContractRef) -> Generator[MediaInput]:
        try:
            source = self._delegate.resolve_reference(ref)
            duration = source.duration_sec
        except (LookupError, NotImplementedError):
            duration = 0.0
        stream = io.BytesIO(b"fixture")
        try:
            yield MediaInput(stream, "video/mp4", 7, declared_duration_sec=duration)
        finally:
            stream.close()


class FixtureMediaPreparer:
    _duration_sec: float

    def __init__(self, duration_sec: float) -> None:
        self._duration_sec = duration_sec

    def prepare_coarse(
        self,
        media_input: MediaInput,
        deadline: RunDeadline,
    ) -> AbstractContextManager[PreparedMedia]:
        _ = deadline
        duration = media_input.declared_duration_sec or self._duration_sec
        return _prepared_media(duration)

    def prepare_fine(
        self,
        media_input: MediaInput,
        start_sec: float,
        end_sec: float,
        deadline: RunDeadline,
    ) -> AbstractContextManager[PreparedMedia]:
        _ = media_input, deadline
        return _prepared_fine_media(start_sec, end_sec)


@contextmanager
def _prepared_media(duration_sec: float) -> Generator[PreparedMedia]:
    yield PreparedMedia(
        path=Path("fixture-prepared.mp4"),
        content_type="video/mp4",
        byte_size=7,
        duration_sec=duration_sec,
        origin_start_sec=0.0,
        origin_end_sec=duration_sec,
    )


@contextmanager
def _prepared_fine_media(start_sec: float, end_sec: float) -> Generator[PreparedMedia]:
    yield PreparedMedia(
        path=Path("fixture-fine.mp4"),
        content_type="video/mp4",
        byte_size=7,
        duration_sec=end_sec - start_sec,
        origin_start_sec=start_sec,
        origin_end_sec=end_sec,
    )


def frozen_clock() -> float:
    """시간이 흐르지 않는 monotonic — deadline이 테스트 도중 만료되지 않는다."""
    return 0.0


def remember_coarse_run(
    service: SearchService, run_id: RunId, budget_ms: int = 30_000
) -> SearchService:
    """손으로 만든 후보의 Coarse run을 service가 실행한 것처럼 등록한다.

    실제로는 search_candidates()가 등록한다. Fine 단위 테스트가 Coarse를 매번
    돌리지 않도록 그 결과만 재현한다.
    """
    service._run_budget_ms[run_id] = budget_ms  # pyright: ignore[reportPrivateUsage]
    return service
