import io
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

from daesingo.search.execution import RunDeadline
from daesingo.search.media import MediaInput, PreparedMedia
from daesingo.search.runs import ContractRef
from daesingo.search.scope import AnalysisScope
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
        _ = ref
        stream = io.BytesIO(b"fixture")
        try:
            yield MediaInput(stream, "video/mp4", 7)
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
        _ = media_input, deadline
        return _prepared_media(self._duration_sec)


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


def make_deadline() -> RunDeadline:
    return RunDeadline(lambda: 0.0, budget_ms=30_000)
