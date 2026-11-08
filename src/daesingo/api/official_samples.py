"""Server-owned official input verification, not public admission/authorization.

The caller supplies the approved manifest pin, protected root and byte budget.
No HTTP route or environment switch activates this component. Session ownership,
durable paid-call admission and retention must be bound before public use.
"""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path
import re
import stat
from types import MappingProxyType
from typing import Annotated, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from daesingo.common.storage._filesystem import ordinary, pin_root, tool_directory, version
from daesingo.recording.probe import FfprobeMediaProbe, LocalSource, MediaProbe


MAX_DURATION_MS = 600000
MAX_MANIFEST_BYTES = 262144
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_DEVICE = re.compile(r"(?:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)", re.IGNORECASE)
PositiveInt = Annotated[int, Field(strict=True, gt=0)]


class SampleRejected(ValueError):
    """Only fixed categories escape; no names, content or probe exception text."""
    def __init__(self, code: str):
        self.code = code
        super().__init__("official sample " + code.lower())


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)


class _File(_Strict):
    name: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    byte_size: PositiveInt
    duration_ms: Annotated[int, Field(strict=True, gt=0, le=MAX_DURATION_MS)]

    @field_validator("name")
    @classmethod
    def safe_name(cls, name):
        # Flat server-owned files only: no URL, drive, ADS, traversal or Win32 alias.
        if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", name)
                or not name.lower().endswith(".mp4") or _DEVICE.match(name)):
            raise ValueError("invalid official filename")
        return name


class _Sample(_Strict):
    sample_id: Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]
    label: Annotated[str, Field(min_length=1, max_length=120)]
    example_hint: Annotated[str, Field(max_length=1000)]
    authorization_ref: Annotated[str, Field(min_length=1, max_length=256)]
    files: Annotated[tuple[_File, ...], Field(min_length=1, max_length=64)]

    @field_validator("files", mode="before")
    @classmethod
    def file_list(cls, value):
        if not isinstance(value, list):
            raise ValueError("file list required")
        return tuple(value)

    @field_validator("authorization_ref", "label")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("nonblank approval and label required")
        return value


class _Manifest(_Strict):
    format: Literal["official-samples/v1"] = Field(alias="schema")
    samples: Annotated[list[_Sample], Field(min_length=1, max_length=64)]


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate manifest key")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("invalid JSON constant")


@dataclass(frozen=True)
class VerifiedSample:
    sample_id: str
    duration_ms: int
    byte_size: int
    sources: tuple[LocalSource, ...] = field(repr=False)


def source_duration_ms(source: LocalSource) -> int:
    durations = [source.duration_sec]
    video = [s.duration_sec for s in source.streams if s.media_type == "VIDEO"]
    if not video:
        raise SampleRejected("INTEGRITY_MISMATCH")
    durations.extend(video)
    if any(type(v) not in (float, int) or not Decimal(str(v)).is_finite()
           or Decimal(str(v)) <= 0 for v in durations):
        raise SampleRejected("INTEGRITY_MISMATCH")
    return int((max(Decimal(str(v)) for v in durations) * 1000).to_integral_value(rounding=ROUND_CEILING))


@dataclass(frozen=True)
class OfficialSamples:
    _root: Path = field(repr=False)
    _samples: Mapping[str, _Sample] = field(repr=False)
    _max_total_bytes: int = field(repr=False)

    @classmethod
    def from_manifest(cls, data: bytes, *, expected_sha256: str, root: Path,
                      max_total_bytes: int) -> "OfficialSamples":
        try:
            if (not isinstance(data, bytes) or len(data) > MAX_MANIFEST_BYTES
                    or not isinstance(expected_sha256, str) or not _DIGEST.fullmatch(expected_sha256)
                    or hashlib.sha256(data).hexdigest() != expected_sha256
                    or type(max_total_bytes) is not int or max_total_bytes <= 0):
                raise ValueError("invalid manifest binding")
            path = Path(root)
            if not path.is_absolute() or ".." in path.parts:
                raise ValueError("absolute protected root required")
            parsed = _Manifest.model_validate(json.loads(data.decode("utf-8"),
                object_pairs_hook=_unique, parse_constant=_invalid_constant))
            samples = {}
            for sample in parsed.samples:
                if (sample.sample_id in samples
                        or len({f.name.casefold() for f in sample.files}) != len(sample.files)
                        or sum(f.duration_ms for f in sample.files) > MAX_DURATION_MS
                        or sum(f.byte_size for f in sample.files) > max_total_bytes):
                    raise ValueError("invalid official sample bounds")
                samples[sample.sample_id] = sample
            # Check existing ancestors without resolving through a symlink/junction.
            with pin_root(path):
                pass
            return cls(path, MappingProxyType(samples), max_total_bytes)
        except (OSError, ValueError, TypeError, RecursionError, ValidationError):
            raise SampleRejected("INVALID_MANIFEST") from None

    def list_samples(self) -> list[dict]:
        """Detached public presentation only; no root/name/hash/approval location."""
        return [{"sample_id": s.sample_id, "label": s.label, "example_hint": s.example_hint,
                 "duration_ms": sum(f.duration_ms for f in s.files),
                 "byte_size": sum(f.byte_size for f in s.files), "file_count": len(s.files)}
                for s in self._samples.values()]

    def contains(self, sample_id):
        return isinstance(sample_id, str) and sample_id in self._samples

    def verify(self, sample_id: str, *, probe: MediaProbe | None = None) -> VerifiedSample:
        """Recheck actual bytes and duration before registration/conversion/AI.

        Reuses Recording's bounded file hash and ffprobe, not a parallel parser.
        Protected official files must remain read-only to API and Worker. This
        result is not a reusable authorization token or a reservation of costs.
        """
        if not isinstance(sample_id, str) or sample_id not in self._samples:
            raise SampleRejected("NOT_APPROVED")
        sample = self._samples[sample_id]
        # Container selection is server-owned, not inferred from a filename.
        # A playlist renamed .mp4 must not open unapproved local media.
        probe = FfprobeMediaProbe(input_format="mov") if probe is None else probe
        sources = []
        actual_duration = 0
        actual_bytes = 0
        try:
            with pin_root(self._root) as root:
                tool_root = tool_directory(root)
                for spec in sample.files:
                    with root.child(spec.name) as opened:
                        before = opened.stat()
                        if (not ordinary(before) or not stat.S_ISREG(before.st_mode)
                                or before.st_nlink != 1 or before.st_size != spec.byte_size):
                            raise SampleRejected("INTEGRITY_MISMATCH")
                        source = probe.probe(tool_root / spec.name)
                        if (not isinstance(source, LocalSource)
                                or version(opened.stat()) != version(before)
                                or version(root.lstat(spec.name)) != version(before)
                                or source.byte_size != spec.byte_size or source.sha256 != spec.sha256
                                or source.mtime_ns != before.st_mtime_ns
                                or not source.path.samefile(tool_root / spec.name)):
                            raise SampleRejected("INTEGRITY_MISMATCH")
                        duration_ms = source_duration_ms(source)
                        if duration_ms != spec.duration_ms:
                            raise SampleRejected("INTEGRITY_MISMATCH")
                        actual_duration += duration_ms
                        actual_bytes += source.byte_size
                        if actual_duration > MAX_DURATION_MS or actual_bytes > self._max_total_bytes:
                            raise SampleRejected("INPUT_LIMIT")
                        sources.append(source)
            return VerifiedSample(sample_id, actual_duration, actual_bytes, tuple(sources))
        except SampleRejected:
            raise
        except Exception:
            raise SampleRejected("UNAVAILABLE") from None
