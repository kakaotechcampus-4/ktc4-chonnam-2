import json
import os
from dataclasses import asdict, dataclass
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class GeminiSearchConfig:
    model: str = "gemini-3-flash-preview"
    media_resolution: str = "low"
    coarse_fps: float = 1.0
    fine_fps: float = 2.0
    max_retries: int = 3
    retry_base_sec: float = 5.0
    fine_padding_sec: float = 4.0
    version: str = "gemini-search-v1"

    @classmethod
    def from_env(cls) -> "GeminiSearchConfig":
        defaults = cls()
        return cls(
            model=os.getenv("DAESINGO_GEMINI_MODEL", defaults.model),
            media_resolution=os.getenv(
                "DAESINGO_GEMINI_MEDIA_RESOLUTION", defaults.media_resolution
            ),
        )

    @property
    def fingerprint(self) -> str:
        encoded = json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":")
        ).encode()
        return sha256(encoded).hexdigest()
