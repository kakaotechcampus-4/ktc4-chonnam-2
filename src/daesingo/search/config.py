import json
import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Final
from urllib.parse import urlsplit

from daesingo.common import load_env_file

from .errors import GeminiBaseUrlRejectionReason, UnsafeGeminiBaseUrlError

_APPROVED_GEMINI_BASE_URL_HOSTS: Final = frozenset(
    {"mlapi.run", "generativelanguage.googleapis.com"}
)


@dataclass(frozen=True, slots=True)
class GeminiSearchConfig:
    model: str = "gemini-3.8-flash"
    media_resolution: str = "low"  # Coarse. 넓게 싸게 훑는다
    fine_media_resolution: str = (
        "high"  # Fine. 실선/점선·신호색 판별이 화질에 직접 걸린다
    )
    coarse_fps: float = 1.0
    fine_fps: float = 2.0
    max_materialized_source_bytes: int = 512 * 1024 * 1024  # 512 MiB
    max_inline_media_bytes: int = 12 * 1024 * 1024  # 12 MiB
    max_inline_request_bytes: int = 18 * 1024 * 1024  # 18 MiB
    max_retries: int = 3
    retry_base_sec: float = 5.0
    fine_padding_sec: float = 4.0
    # 추론 강도 (none/low/medium/high). 시연 단가 우선이라 low 기본. 필요 시 상향.
    reasoning_effort: str = "low"
    # 단가: 프록시가 고지한 USD/백만 토큰. 테스트에서 명시 주입; 운영은 Task 11/13 담당.
    input_usd_per_million: float = 0.0
    output_usd_per_million: float = 0.0
    # 예산 한도 및 Fine 호출 전 예비비
    max_cost_usd: float = 0.0
    fine_reserve_usd: float = 0.0
    # 모든 Gemini 호출은 이 프록시(Bearer 인증)를 거친다. 운영자가 로컬에서
    # DAESINGO_GEMINI_BASE_URL 로 덮어쓸 수 있다.
    base_url: str = "https://mlapi.run/a90d8545-f100-4276-bf86-eb774596b91d/v1"
    version: str = "gemini-search-v2"

    def __post_init__(self) -> None:
        try:
            parsed = urlsplit(self.base_url)
            port = parsed.port
        except ValueError:
            raise UnsafeGeminiBaseUrlError(
                GeminiBaseUrlRejectionReason.MALFORMED
            ) from None

        if parsed.scheme != "https":
            raise UnsafeGeminiBaseUrlError(GeminiBaseUrlRejectionReason.HTTPS_REQUIRED)
        if parsed.username is not None or parsed.password is not None:
            raise UnsafeGeminiBaseUrlError(GeminiBaseUrlRejectionReason.USERINFO)
        if parsed.hostname not in _APPROVED_GEMINI_BASE_URL_HOSTS:
            raise UnsafeGeminiBaseUrlError(GeminiBaseUrlRejectionReason.UNAPPROVED_HOST)
        if port not in (None, 443):
            raise UnsafeGeminiBaseUrlError(
                GeminiBaseUrlRejectionReason.NON_DEFAULT_PORT
            )
        if parsed.query or "?" in self.base_url:
            raise UnsafeGeminiBaseUrlError(GeminiBaseUrlRejectionReason.QUERY)
        if parsed.fragment or "#" in self.base_url:
            raise UnsafeGeminiBaseUrlError(GeminiBaseUrlRejectionReason.FRAGMENT)
        if self.max_materialized_source_bytes < 0:
            raise ValueError("max_materialized_source_bytes must be non-negative")
        if self.max_inline_media_bytes < 0:
            raise ValueError("max_inline_media_bytes must be non-negative")
        if self.max_inline_request_bytes < 0:
            raise ValueError("max_inline_request_bytes must be non-negative")
        if (
            not math.isfinite(self.input_usd_per_million)
            or self.input_usd_per_million < 0
        ):
            raise ValueError("input_usd_per_million must be finite and non-negative")
        if (
            not math.isfinite(self.output_usd_per_million)
            or self.output_usd_per_million < 0
        ):
            raise ValueError("output_usd_per_million must be finite and non-negative")
        if not math.isfinite(self.max_cost_usd) or self.max_cost_usd < 0:
            raise ValueError("max_cost_usd must be finite and non-negative")
        if not math.isfinite(self.fine_reserve_usd) or self.fine_reserve_usd < 0:
            raise ValueError("fine_reserve_usd must be finite and non-negative")

    @classmethod
    def from_dotenv(cls, env: Mapping[str, str] | None = None) -> "GeminiSearchConfig":
        if env is None:
            env = load_env_file()
        defaults = cls()
        return cls(
            model=env.get("DAESINGO_GEMINI_MODEL", defaults.model),
            media_resolution=env.get(
                "DAESINGO_GEMINI_MEDIA_RESOLUTION", defaults.media_resolution
            ),
            base_url=env.get("DAESINGO_GEMINI_BASE_URL", defaults.base_url),
            input_usd_per_million=float(
                env.get(
                    "DAESINGO_GEMINI_INPUT_USD_PER_MILLION",
                    defaults.input_usd_per_million,
                )
            ),
            output_usd_per_million=float(
                env.get(
                    "DAESINGO_GEMINI_OUTPUT_USD_PER_MILLION",
                    defaults.output_usd_per_million,
                )
            ),
            max_cost_usd=float(
                env.get("DAESINGO_GEMINI_MAX_COST_USD", defaults.max_cost_usd)
            ),
            fine_reserve_usd=float(
                env.get("DAESINGO_GEMINI_FINE_RESERVE_USD", defaults.fine_reserve_usd)
            ),
        )

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":")
        ).encode()
        return sha256(encoded).hexdigest()
