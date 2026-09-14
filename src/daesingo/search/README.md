# `search` — 사건 탐색

**Owner:** 서어진 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈2 · **문서 작업공간:** `docs/modules/search/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈2)

Coarse 후보 구간 생성·Fine/Classification visual verification·4종 event routing·`AnalysisRun` 실행 기록·실패 taxonomy 기록·`providers/`(외부 AI API 호출은 여기서만)

## 이 폴더가 알면 안 되는 것 (§4-모듈2 「알면 안 되는 것」)

신고 규정·Report Type / case stage / 확정 Evidence / 사용자 개인정보 / eval의 존재 / 신고용 mp4 생성 / 평가 전용 분기

## 공개 함수

다른 모듈은 `daesingo.search`가 노출하는 공개 함수만 호출한다.

| 함수 | 입력 | 출력 |
| --- | --- | --- |
| `search_candidates(scope)` | `AnalysisScope` | `CandidateSearchResult(analysis_run, candidates)` |
| `verify_visual(input_ref, target_hint=None)` | `ContractRef`, 선택 `SearchHint` | `VisualVerificationResult(analysis_run, visual_evidence)` |

입력과 출력은 Final Data Contract를 파싱한 불변 Pydantic 객체다. JSON 경계에서는
`model_validate_json`, Consumer 전달 시에는 위 타입을 그대로 사용한다.

## 상태

1차 Mock E2E 통합용 fixture 스텁이 구현되어 있다. `data/mock/search/scenario_*.json`에 기록된
실행을 `scope_id` 또는 Fine `input_ref`로 찾아 반환하며, 실제 provider 호출·영상 처리·성능을
구현하지 않는다. 스텁과 이후 실제 구현은 위 공개 시그니처를 공유한다.

```bash
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run python data/mock/validate_mock_pack.py
```
