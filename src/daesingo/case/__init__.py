"""`case` — Workflow / Orchestration. 유일한 지휘자.

Owner: 유소연 (`docs/management/ownership.md`). 경계: `docs/architecture/module-architecture.md` §4-모듈5.
이 패키지가 알면 안 되는 것(업로드 규정 수치 / OCR threshold / LLM 지시문 내용 / evidence 정책 /
codec·ffmpeg / Worker lifecycle 구현)은 여기 코드에도 그대로 적용된다 — 금지 문자열 목록은
`scripts/check_boundaries.py`가 소유하며, 그 목록 자체를 여기 docstring에 복제하지 않는다
(복제하면 이 파일 자체가 검사에 걸린다).
"""

from daesingo.case.service import get_view
from daesingo.case.store import CaseStore

__all__ = ["CaseStore", "get_view"]
