"""Explicit approved ceilings, never inferred from an old demo or usage ledger."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from daesingo.common.storage._filesystem import ordinary, version
from daesingo.common.usage.port import UsageError

Positive = Annotated[int, Field(strict=True, gt=0, le=10**15)]


class PublicDenied(UsageError):
    """Fixed codes cross HTTP/Worker boundaries without inputs or SQL text."""
    def __init__(self, code="UNCONFIGURED"):
        self.code = code
        super().__init__()

    @property
    def status(self):
        return {"NOT_FOUND": 404, "ORIGIN": 403, "UPLOAD_DISABLED": 403,
                "LIMIT": 429, "CONCURRENT": 429, "BUDGET": 429,
                "LOCAL_LIMIT": 429, "LOCAL_CONCURRENT": 429,
                "INPUT": 422, "BUSY": 409}.get(self.code, 503)


class Bound(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    operation: Annotated[str, Field(min_length=1, max_length=64)]
    provider_label: Annotated[str, Field(min_length=1, max_length=191)]
    reserve_micros: Positive
    evidence_ref: Annotated[str, Field(min_length=1, max_length=256)]


class LocalWorkLimits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    case_jobs: Positive
    ip_daily_jobs: Positive
    global_concurrent: Positive


class SupportedCall(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
    operation: Literal["HINT_EXTRACT", "SEARCH_COARSE", "SEARCH_FINE"]
    provider_label: Annotated[str, Field(pattern=r"^elice:[^\s:]+$", max_length=191)]


class PublicPolicy(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, hide_input_in_errors=True)
    approval_ref: Annotated[str, Field(min_length=1, max_length=256)]
    release_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    origin: str
    session_key: SecretStr
    manifest_file: str
    manifest_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    samples_root: str
    max_input_bytes: Positive
    session_ttl_sec: Annotated[int, Field(strict=True, gt=0, le=604800)]
    case_ttl_sec: Annotated[int, Field(strict=True, gt=0, le=604800)]
    source_ttl_sec: Annotated[int, Field(strict=True, gt=0, le=86400)]
    session_daily: Positive
    ip_daily: Positive
    case_repeats: Positive
    session_concurrent: Positive
    global_concurrent: Positive
    funding_mode: Literal["krw", "elice_supported"] = "krw"
    case_budget_micros: Positive | None = None
    daily_budget_micros: Positive | None = None
    total_budget_micros: Positive | None = None
    bounds: Annotated[tuple[Bound, ...], Field(max_length=64)] = ()
    support_ref: Annotated[str, Field(min_length=1, max_length=256)] | None = None
    supported_calls: Annotated[tuple[SupportedCall, ...], Field(max_length=64)] = ()
    local_work: LocalWorkLimits | None = None

    @field_validator("bounds", "supported_calls", mode="before")
    @classmethod
    def immutable_bounds(cls, value):
        if not isinstance(value, (list, tuple)):
            raise ValueError("bound list required")
        return tuple(value)

    @field_validator("bounds", "supported_calls")
    @classmethod
    def unique_bounds(cls, value):
        identities = {(b.operation, b.provider_label) for b in value}
        if len(identities) != len(value):
            raise ValueError("duplicate invocation bound")
        return value

    @model_validator(mode="after")
    def funding_contract(self) -> Self:
        budgets = (self.case_budget_micros, self.daily_budget_micros, self.total_budget_micros)
        if self.funding_mode == "krw":
            if any(value is None for value in budgets) or not self.bounds or self.support_ref is not None or self.supported_calls:
                raise ValueError("KRW ceilings and invocation bounds required")
        elif (any(value is not None for value in budgets) or self.bounds or not self.supported_calls
              or self.support_ref is None or not self.support_ref.strip()):
            raise ValueError("supported scope required; monetary ceilings do not apply")
        return self

    @field_validator("session_key", mode="before")
    @classmethod
    def strong_key(cls, value):
        if not isinstance(value, str) or len(value.encode()) < 32:
            raise ValueError("session key required")
        return SecretStr(value)

    @field_validator("origin")
    @classmethod
    def https_origin(cls, value):
        url = urlsplit(value)
        if (url.scheme != "https" or not url.hostname or url.username or url.password
                or url.path not in ("", "/") or url.query or url.fragment):
            raise ValueError("HTTPS origin required")
        return value.rstrip("/")

    @field_validator("manifest_file", "samples_root")
    @classmethod
    def absolute(cls, value):
        if not Path(value).is_absolute() or ".." in Path(value).parts:
            raise ValueError("absolute protected path required")
        return value

    @field_validator("approval_ref")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("approval reference required")
        return value

    def fingerprint(self):
        data = self.model_dump(mode="json")
        if self.funding_mode == "krw":
            # Preserve the already-installed KRW policy identity across upgrade.
            for key in ("funding_mode", "support_ref", "supported_calls"):
                del data[key]
        data["session_key"] = self.session_key.get_secret_value()
        return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).digest()

    def bound(self, operation, provider):
        matches = [b for b in self.bounds if (b.operation, b.provider_label) == (operation, provider)]
        if len(matches) != 1:
            raise PublicDenied("UNPRICED")
        return matches[0].reserve_micros

    def require_supported(self, operation, provider):
        if not any((b.operation, b.provider_label) == (operation, provider) for b in self.supported_calls):
            raise PublicDenied("UNSUPPORTED")

    def krw_limits(self) -> tuple[int, int, int]:
        case, daily, total = self.case_budget_micros, self.daily_budget_micros, self.total_budget_micros
        if self.funding_mode != "krw" or case is None or daily is None or total is None:
            raise PublicDenied()
        return case, daily, total


def load_policy(path, *, revision):
    """Missing, invalid or release-mismatched protected inputs close admission."""
    try:
        if path is None:
            return None
        path = Path(path)
        before = path.lstat()
        if (not ordinary(before) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                or before.st_size > 262144 or not path.is_absolute()):
            return None
        if sys.platform != "win32" and (before.st_uid not in (0, os.geteuid()) or before.st_mode & 0o077):
            return None
        def unique(pairs):
            result = {}
            for k, v in pairs:
                if k in result:
                    raise ValueError("duplicate policy key")
                result[k] = v
            return result
        with path.open("rb") as reader:
            raw = reader.read(262145)
        if len(raw) > 262144:
            return None
        result = PublicPolicy.model_validate(json.loads(raw, object_pairs_hook=unique))
        after = path.lstat()
        if (version(after) != version(before) or after.st_mode != before.st_mode
                or after.st_uid != before.st_uid or after.st_nlink != before.st_nlink
                or result.release_revision != revision):
            return None
        return result
    except Exception:
        return None
