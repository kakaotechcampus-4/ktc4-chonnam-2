import json
from pathlib import Path

import httpx
import openai
import pytest

from daesingo.search.config import GeminiSearchConfig
from daesingo.search.decision_trace import (
    CHECKLISTS,
    DiagnosticCoarseResponse,
    DiagnosticFineResponse,
    fine_trace_issues,
)
from daesingo.search.media import PreparedMedia
from daesingo.search.provider import GeminiProvider, StructuredInvocation
from daesingo.search.scope import VisualEventType


@pytest.mark.parametrize("event", list(VisualEventType))
def test_real_sdk_routes_and_parses_private_coarse_and_fine_models(
    event: VisualEventType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: actual SDK JSON parsing with a local HTTP transport, never a remote call.
    bodies = []
    replies = [
        {"candidates": [], "window_reviews": []},
        {
            "verification": "UNCERTAIN",
            "visual_event_type": None,
            "target": {
                "association_status": "AMBIGUOUS",
                "described_as": None,
                "match_with_hint": None,
                "association_confidence": None,
                "track_ref": None,
            },
            "primitives": [],
            "temporal_facts": [],
            "uncertainties": [],
            "decision_reason": "Insufficient visible evidence.",
            "decision_basis": [
                {
                    "criterion": key,
                    "observation": "Not visible",
                    "at_offset_ms": None,
                    "limitation": "Occlusion",
                }
                for key in CHECKLISTS[event]
            ],
        },
    ]

    def respond(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "local",
                "object": "chat.completion",
                "created": 1,
                "model": "fixture",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(replies.pop(0)),
                        },
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30,
                },
            },
        )

    original = openai.OpenAI
    client = httpx.Client(transport=httpx.MockTransport(respond))
    monkeypatch.setattr(
        openai, "OpenAI", lambda **kwargs: original(http_client=client, **kwargs)
    )
    provider = GeminiProvider("local-test-key", GeminiSearchConfig(max_retries=0))
    source = tmp_path / "prepared.mp4"
    source.write_bytes(b"media")
    media = PreparedMedia(source, "video/mp4", 5, 1, 0, 1)
    try:
        # When: the shared provider invokes each private response model.
        coarse = provider.invoke_structured(
            StructuredInvocation(media, "coarse", DiagnosticCoarseResponse, 5)
        )
        fine = provider.invoke_structured(
            StructuredInvocation(media, "fine", DiagnosticFineResponse, 5)
        )
    finally:
        client.close()
    # Then: the actual strict wire schemas and explanation fields survive SDK parsing.
    assert isinstance(coarse.response, DiagnosticCoarseResponse)
    assert isinstance(fine.response, DiagnosticFineResponse)
    assert fine_trace_issues(fine.response, event, 1000) == ()
    assert fine.usage.total_tokens == 30
    coarse_schema = bodies[0]["response_format"]["json_schema"]["schema"]
    fine_schema = bodies[1]["response_format"]["json_schema"]["schema"]
    assert "window_reviews" in coarse_schema["required"]
    assert {"decision_reason", "decision_basis"} <= set(fine_schema["required"])
