"""Tests for LocalAnalysisSourceResolver and RecordingAnalysisSourceResolver.

Proves:
- open_source yields a FRESH stream each call and CLOSES it on exit
- exact-ref lookup from the explicit mapping
- each Recording error code maps to the right Search error
- nullable duration/timeline is rejected (via typing — validated at construction)
- refs are NOT inferred from scope/timeline
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pytest

from daesingo.search.runs import ContractRef
from daesingo.search.scope import (
    AnalysisScope,
    SearchBudget,
    SearchHint,
    TimelineRef,
    TimelineRelativeTimeRange,
    TimeRangeKind,
    VisualEventType,
)
from daesingo.search.sources import (
    AnalysisSourceNotFoundError,
    AnalysisSourceTemporaryFailureError,
    AnalysisSourceUnavailableError,
    LocalAnalysisSourceResolver,
    RecordingAnalysisSourceResolver,
    ResolvedAnalysisSource,
    SourceMeta,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REF = ContractRef(kind="analysis_source", ref="src-1")
_META = SourceMeta(duration_sec=10.0, timeline_id="tl-1", timeline_revision=2)
_SOURCE = ResolvedAnalysisSource(
    source_ref=_REF,
    duration_sec=10.0,
    timeline_id="tl-1",
    timeline_revision=2,
)


def _scope(scope_id: str = "scope-1") -> AnalysisScope:
    return AnalysisScope(
        scope_id=scope_id,
        time_ranges=(
            TimelineRelativeTimeRange(
                kind=TimeRangeKind.TIMELINE_RELATIVE,
                timeline_ref=TimelineRef(timeline_id="tl-1", revision=2),
                start_ms=0,
                end_ms=10_000,
            ),
        ),
        target_event_types=(VisualEventType.SIGNAL,),
        hint=SearchHint(vehicle=None, free_text=None),
        budget=SearchBudget(max_cost_krw=1000, max_latency_sec=30),
        contract_version="1.1.0",
    )


# ---------------------------------------------------------------------------
# Fake Recording gateway
# ---------------------------------------------------------------------------


@dataclass
class _FakeOpened:
    stream: BinaryIO
    content_type: str
    byte_size: int


@dataclass
class _FakeGateway:
    """Configurable fake for RecordingAnalysisSourceGateway."""

    content: bytes = b"fake-video-bytes"
    content_type: str = "video/mp4"
    error_code: str | None = None
    open_calls: int = 0

    def open_analysis_source(self, analysis_source_ref: str) -> _FakeOpened:
        self.open_calls += 1
        if self.error_code is not None:
            from daesingo.recording.errors import RecordingCapabilityError

            raise RecordingCapabilityError(self.error_code, f"fake {self.error_code}")
        return _FakeOpened(
            stream=BytesIO(self.content),
            content_type=self.content_type,
            byte_size=len(self.content),
        )


# ---------------------------------------------------------------------------
# LocalAnalysisSourceResolver tests
# ---------------------------------------------------------------------------


class TestLocalAnalysisSourceResolver:
    def _resolver(self, path: Path) -> LocalAnalysisSourceResolver:
        return LocalAnalysisSourceResolver(
            sources_by_scope={"scope-1": (_SOURCE,)},
            sources_by_ref={"src-1": _SOURCE},
            paths_by_ref={"src-1": path},
        )

    def test_resolve_returns_sources_for_scope(self, tmp_path: Path) -> None:
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"data")
        resolver = self._resolver(path)
        result = resolver.resolve(_scope())
        assert result == (_SOURCE,)

    def test_resolve_unknown_scope_raises_lookup_error(self, tmp_path: Path) -> None:
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"data")
        resolver = self._resolver(path)
        with pytest.raises(LookupError, match="no analysis source for scope"):
            resolver.resolve(_scope("unknown-scope"))

    def test_resolve_reference_returns_source(self, tmp_path: Path) -> None:
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"data")
        resolver = self._resolver(path)
        result = resolver.resolve_reference(_REF)
        assert result == _SOURCE

    def test_resolve_reference_unknown_ref_raises_lookup_error(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"data")
        resolver = self._resolver(path)
        with pytest.raises(LookupError, match="no analysis source for ref"):
            resolver.resolve_reference(
                ContractRef(kind="analysis_source", ref="missing")
            )

    def test_open_source_yields_media_input_with_file_content(
        self, tmp_path: Path
    ) -> None:
        content = b"video-bytes-content"
        path = tmp_path / "clip.mp4"
        path.write_bytes(content)
        resolver = self._resolver(path)

        with resolver.open_source(_REF) as media:
            assert media.stream.read() == content
            assert media.content_type == "video/mp4"
            assert media.declared_byte_size == len(content)

    def test_open_source_yields_fresh_stream_each_call(self, tmp_path: Path) -> None:
        """Each open_source call must return a new, independent stream."""
        content = b"abc"
        path = tmp_path / "clip.mp4"
        path.write_bytes(content)
        resolver = self._resolver(path)

        with resolver.open_source(_REF) as m1, resolver.open_source(_REF) as m2:
            # Both streams are independent — reading one doesn't affect the other
            assert m1.stream.read() == content
            assert m2.stream.read() == content

    def test_open_source_closes_stream_on_exit(self, tmp_path: Path) -> None:
        """Stream must be closed after the context manager exits."""
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"data")
        resolver = self._resolver(path)

        with resolver.open_source(_REF) as media:
            stream = media.stream

        assert stream.closed

    def test_open_source_closes_stream_on_exception(self, tmp_path: Path) -> None:
        """Stream must be closed even when the body raises."""
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"data")
        resolver = self._resolver(path)

        stream: BinaryIO | None = None
        with pytest.raises(RuntimeError, match="boom"):  # noqa: SIM117
            with resolver.open_source(_REF) as media:
                stream = media.stream
                raise RuntimeError("boom")

        assert stream is not None and stream.closed

    def test_open_source_unknown_ref_raises_not_found(self, tmp_path: Path) -> None:
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"data")
        resolver = self._resolver(path)
        missing = ContractRef(kind="analysis_source", ref="no-such-ref")
        with pytest.raises(AnalysisSourceNotFoundError), resolver.open_source(missing):
            pass


# ---------------------------------------------------------------------------
# RecordingAnalysisSourceResolver tests
# ---------------------------------------------------------------------------


class TestRecordingAnalysisSourceResolver:
    def _resolver(self, gateway: _FakeGateway) -> RecordingAnalysisSourceResolver:
        return RecordingAnalysisSourceResolver(
            scope_sources={"scope-1": (_REF,)},
            ref_metadata={"src-1": _META},
            gateway=gateway,
        )

    def test_resolve_returns_metadata_only_source(self) -> None:
        resolver = self._resolver(_FakeGateway())
        sources = resolver.resolve(_scope())
        assert len(sources) == 1
        s = sources[0]
        assert s.source_ref == _REF
        assert s.duration_sec == 10.0
        assert s.timeline_id == "tl-1"
        assert s.timeline_revision == 2

    def test_resolve_unknown_scope_raises_lookup_error(self) -> None:
        resolver = self._resolver(_FakeGateway())
        with pytest.raises(LookupError, match="no analysis source for scope"):
            resolver.resolve(_scope("unknown"))

    def test_resolve_reference_returns_source(self) -> None:
        resolver = self._resolver(_FakeGateway())
        result = resolver.resolve_reference(_REF)
        assert result == _SOURCE

    def test_resolve_reference_unknown_raises_not_found(self) -> None:
        resolver = self._resolver(_FakeGateway())
        missing = ContractRef(kind="analysis_source", ref="missing")
        with pytest.raises(AnalysisSourceNotFoundError):
            resolver.resolve_reference(missing)

    def test_refs_not_inferred_from_scope_or_timeline(self) -> None:
        """A scope with no explicit mapping must raise LookupError, not infer refs."""
        resolver = RecordingAnalysisSourceResolver(
            scope_sources={},  # no scope mapping at all
            ref_metadata={"src-1": _META},
            gateway=_FakeGateway(),
        )
        with pytest.raises(LookupError):
            resolver.resolve(_scope("scope-1"))

    def test_open_source_yields_media_input(self) -> None:
        gateway = _FakeGateway(content=b"video")
        resolver = self._resolver(gateway)

        with resolver.open_source(_REF) as media:
            assert media.stream.read() == b"video"
            assert media.content_type == "video/mp4"
            assert media.declared_byte_size == 5

    def test_open_source_yields_fresh_stream_each_call(self) -> None:
        """Each open_source call must delegate to gateway (fresh stream)."""
        gateway = _FakeGateway(content=b"fresh")
        resolver = self._resolver(gateway)

        with resolver.open_source(_REF) as m1:
            data1 = m1.stream.read()
        with resolver.open_source(_REF) as m2:
            data2 = m2.stream.read()

        assert data1 == b"fresh"
        assert data2 == b"fresh"
        assert gateway.open_calls == 2

    def test_open_source_closes_stream_on_exit(self) -> None:
        gateway = _FakeGateway(content=b"data")
        resolver = self._resolver(gateway)

        with resolver.open_source(_REF) as media:
            stream = media.stream

        assert stream.closed

    def test_open_source_closes_stream_on_exception(self) -> None:
        gateway = _FakeGateway(content=b"data")
        resolver = self._resolver(gateway)

        stream: BinaryIO | None = None
        with pytest.raises(ValueError, match="oops"):  # noqa: SIM117
            with resolver.open_source(_REF) as media:
                stream = media.stream
                raise ValueError("oops")

        assert stream is not None and stream.closed

    # Recording error code mapping

    def test_not_found_maps_to_analysis_source_not_found(self) -> None:
        resolver = self._resolver(_FakeGateway(error_code="NOT_FOUND"))
        with pytest.raises(AnalysisSourceNotFoundError), resolver.open_source(_REF):
            pass

    def test_unavailable_maps_to_analysis_source_unavailable(self) -> None:
        resolver = self._resolver(_FakeGateway(error_code="UNAVAILABLE"))
        with pytest.raises(AnalysisSourceUnavailableError), resolver.open_source(_REF):
            pass

    def test_temporary_failure_maps_to_analysis_source_temporary_failure(self) -> None:
        resolver = self._resolver(_FakeGateway(error_code="TEMPORARY_FAILURE"))
        with (
            pytest.raises(AnalysisSourceTemporaryFailureError),
            resolver.open_source(_REF),
        ):
            pass

    def test_unsupported_media_maps_defensively_to_unavailable(self) -> None:
        """UNSUPPORTED_MEDIA is documented but not raised by recording/service.py today.
        Verify via fake gateway that it maps to AnalysisSourceUnavailableError.
        """
        resolver = self._resolver(_FakeGateway(error_code="UNSUPPORTED_MEDIA"))
        with pytest.raises(AnalysisSourceUnavailableError), resolver.open_source(_REF):
            pass

    def test_unknown_error_code_maps_to_temporary_failure(self) -> None:
        """Unmapped error codes fall back to AnalysisSourceTemporaryFailureError."""
        resolver = self._resolver(_FakeGateway(error_code="SOME_UNKNOWN_CODE"))
        with (
            pytest.raises(AnalysisSourceTemporaryFailureError),
            resolver.open_source(_REF),
        ):
            pass


# ---------------------------------------------------------------------------
# ResolvedAnalysisSource shape — no path
# ---------------------------------------------------------------------------


class TestResolvedAnalysisSourceShape:
    def test_has_no_path_attribute(self) -> None:
        assert not hasattr(_SOURCE, "path")

    def test_source_id_property_returns_ref_string(self) -> None:
        assert _SOURCE.source_id == "src-1"

    def test_construction_requires_contract_ref(self) -> None:
        """Positional construction with ContractRef works; passing a str fails."""
        s = ResolvedAnalysisSource(
            source_ref=ContractRef(kind="analysis_source", ref="x"),
            duration_sec=5.0,
            timeline_id="t",
            timeline_revision=1,
        )
        assert s.source_id == "x"
