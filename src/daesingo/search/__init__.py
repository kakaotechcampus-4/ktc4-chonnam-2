"""search 모듈 공개 API.

Consumer(case·eval)는 여기서 노출하는 함수만 호출한다 — 내부 구현(현재는 fixture stub)을
몰라도 연결할 수 있어야 한다.
"""

from .stub import search_candidates, verify_visual

__all__ = ["search_candidates", "verify_visual"]
