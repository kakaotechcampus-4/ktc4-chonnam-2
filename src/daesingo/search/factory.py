import time

from .config import GeminiSearchConfig
from .execution import RunDeadline
from .media import MediaPreparer
from .provider import GeminiProvider
from .service import SearchService
from .sources import AnalysisSourceResolver


def build_gemini_search_service(
    api_key: str,
    resolver: AnalysisSourceResolver,
    config: GeminiSearchConfig | None = None,
) -> SearchService:
    selected = config or GeminiSearchConfig.from_dotenv()
    return SearchService(
        resolver,
        GeminiProvider(api_key, selected),
        selected,
        MediaPreparer(selected),
        RunDeadline(time.monotonic, budget_ms=60_000),
    )
