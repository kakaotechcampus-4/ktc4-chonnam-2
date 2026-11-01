"""Worker file configuration and module validation for the composition root."""

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TextIO

from pydantic import SecretStr

from daesingo.common.bootstrap import ModuleFactory, Startup, bootstrap_service
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.intent import intent_config_from_dotenv
from daesingo.recording.factory import RECORDING_KEYS, RecordingSettings


@dataclass(frozen=True, slots=True)
class SearchSettings:
    api_key: SecretStr = field(repr=False)
    config: GeminiSearchConfig = field(repr=False)


def _search_config(values: Mapping[str, str]) -> SearchSettings:
    # Current Search credential name; rename/alias stays with Search (#153).
    key = values.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("missing Search credential")
    return SearchSettings(SecretStr(key), GeminiSearchConfig.from_dotenv(values))


_SEARCH = ModuleFactory("search", (
    "GEMINI_API_KEY", "DAESINGO_GEMINI_MODEL", "DAESINGO_GEMINI_MEDIA_RESOLUTION",
    "DAESINGO_GEMINI_BASE_URL", "DAESINGO_GEMINI_INPUT_USD_PER_MILLION",
    "DAESINGO_GEMINI_OUTPUT_USD_PER_MILLION", "DAESINGO_GEMINI_MAX_COST_USD",
), _search_config)

_INTENT = ModuleFactory("intent", ("DAESINGO_INTENT_MODEL",), intent_config_from_dotenv)
_RECORDING = ModuleFactory("recording", RECORDING_KEYS, RecordingSettings.from_mapping)


def bootstrap(*, revision: str, stream: TextIO | None = None,
              module_factories: Sequence[ModuleFactory] = ()) -> Startup:
    """Search always validates; additional module factories cannot disable it.

    Pricing/FX values are not required. No provider call or service is started.
    """
    path = os.environ.get("DAESINGO_ENV_FILE", str(Path.cwd() / ".env"))
    return bootstrap_service("worker", env_file=path, revision=revision,
                             stream=stream, module_factories=(_SEARCH, _INTENT, _RECORDING, *module_factories))
