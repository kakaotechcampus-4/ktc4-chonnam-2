import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from hashlib import sha256

from daesingo.common import load_env_file


@dataclass(frozen=True, slots=True)
class GeminiSearchConfig:
    model: str = "gemini-3.8-flash"
    media_resolution: str = "low"           # Coarse. 넓게 싸게 훑는다
    fine_media_resolution: str = "high"     # Fine. 실선/점선·신호색 판별이 화질에 직접 걸린다
    coarse_fps: float = 1.0
    fine_fps: float = 2.0
    max_retries: int = 3
    retry_base_sec: float = 5.0
    fine_padding_sec: float = 4.0
    # 모든 Gemini 호출은 이 프록시(Bearer 인증)를 거친다. 운영자가 로컬에서
    # DAESINGO_GEMINI_BASE_URL 로 덮어쓸 수 있다.
    base_url: str = "https://mlapi.run/a90d8545-f100-4276-bf86-eb774596b91d/v1"
    version: str = "gemini-search-v2"

    @classmethod
    def from_dotenv(
        cls, env: Mapping[str, str] | None = None
    ) -> "GeminiSearchConfig":
        if env is None:
            env = load_env_file()
        defaults = cls()
        return cls(
            model=env.get("DAESINGO_GEMINI_MODEL", defaults.model),
            media_resolution=env.get(
                "DAESINGO_GEMINI_MEDIA_RESOLUTION", defaults.media_resolution
            ),
            base_url=env.get("DAESINGO_GEMINI_BASE_URL", defaults.base_url),
        )

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":")
        ).encode()
        return sha256(encoded).hexdigest()
