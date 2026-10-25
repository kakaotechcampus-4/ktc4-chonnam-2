"""provider가 부르는 `chat.completions.with_raw_response.parse()`의 대역.

대역 클래스는 `parse(**kwargs)`만 구현하고 이 mixin을 상속한다. HTTP 본문의 usage는
대역 completion의 `usage`(없으면 빈 본문)로 흉내 낸다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class _RawResponse:
    completion: object

    @property
    def http_response(self) -> _RawResponse:
        return self

    def json(self) -> dict[str, object]:
        usage = getattr(self.completion, "usage", None)
        if usage is None:
            return {}
        return {
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
            }
        }

    def parse(self) -> object:
        return self.completion


@dataclass(frozen=True, slots=True)
class RawParse:
    _parse: Callable[..., object]

    def parse(self, **kwargs: object) -> _RawResponse:
        return _RawResponse(self._parse(**kwargs))


class RawResponseFake:
    @property
    def with_raw_response(self) -> RawParse:
        return RawParse(self.parse)  # pyright: ignore[reportAttributeAccessIssue]
