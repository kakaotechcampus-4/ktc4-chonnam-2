# `search` — 사건 탐색

**Owner:** 서어진 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈2 · **문서 작업공간:** `docs/modules/search/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈2)

Coarse 후보 구간 생성·Fine/Classification visual verification·4종 event routing·`AnalysisRun` 실행 기록·실패 taxonomy 기록·외부 AI API 호출. 아키텍처 문서의 `search/providers/` 경계는 실제로 `provider.py` 한 파일이고, 외부 AI 호출은 여기서만 한다.

## 이 폴더가 알면 안 되는 것 (§4-모듈2 「알면 안 되는 것」)

신고 규정·Report Type / case stage / 확정 Evidence / 사용자 개인정보 / eval의 존재 / 신고용 mp4 생성 / 평가 전용 분기

## 공개 함수

다른 모듈은 `daesingo.search`가 노출하는 공개 함수만 호출한다.

| 함수 | 입력 | 출력 |
| --- | --- | --- |
| `search_candidates(scope, *, service=None, usage_sink=None, on_progress=None)` | `AnalysisScope` | `CandidateSearchResult(analysis_run, candidates)` |
| `verify_visual(input_ref, target_hint=None, *, service=None, event_type=SOLID_LINE_LANE_CHANGE, candidate=None, max_latency_sec=None, usage_sink=None)` | `ContractRef`, 선택 `SearchHint`. `service`를 넘기면 `candidate`가 필요하다(없으면 `MissingCandidateError`) | `VisualVerificationResult(analysis_run, visual_evidence)` |
| `verify_visual_with_stream_context(input_ref, candidate, analysis_source_streams, target_hint=None, *, service=None, event_type=SOLID_LINE_LANE_CHANGE, max_latency_sec=None, usage_sink=None)` | `ContractRef`, `CandidateEvent`, typed MediaStream facts, 선택 Fine 실행 상한(초) | `VisualVerificationExecution(result, selected_video_stream)` — 실제 영상 E2E(Case → Search → Recording)에서 쓰는 비정규 실행 문맥. Fine에 쓴 VIDEO stream 하나를 함께 돌려준다. `max_latency_sec`를 넘기면 Coarse와 다른 Worker에서도 실행된다(#226). 생략하면 같은 `SearchService`가 실행한 Coarse scope 상한을 이어받는다 |
| `build_intent_hint_extractor(api_key).extract(text, case_id=..., prior_hints=None, timeout_sec=60, usage_sink=None)` | 사용자 자연어 원문, 선택 이전 단서 | `IntentHintResult(status=OK·ABSTAINED·FAILED, 단서 4개, confidence, correction_target, failure_kind, usage)` — 자연어 단서 구조화(#210). 예외를 던지지 않는다(`usage_sink`의 `UsageError`만 그대로 올린다). 모델은 `DAESINGO_INTENT_MODEL` |

`service=`를 넘기지 않으면 `data/mock/search/`에 기록된 fixture 결과를 돌려준다. 실제 실행에서는 공개 `SearchService`와 `AnalysisSourceResolver`를 구성하고 `service=`로 주입한다. `usage_sink=`(Runtime `common/usage/port.py::UsageSink`)를 주면 provider HTTP 시도마다 HTTP 직전 `begin`, 관측 뒤 `finish`를 부르고, 발급된 `usage_id`를 성공 · 실패 Run의 `usage_refs`에 담는다(#303). `finalize`는 Worker가 한다. `begin`·`finish`의 `UsageError`는 감싸거나 재시도하지 않고 그대로 올린다. 없으면(eval · CLI) 기록하지 않고 내부 `SearchLedger`만 남긴다. 제품과 eval 모두 이 경로를 사용하며 `eval_mode`나 GT 접근 분기는 없다.

입력과 출력은 Final Data Contract를 파싱한 불변 Pydantic 객체다. JSON 경계에서는
`model_validate_json`, Consumer 전달 시에는 위 타입을 그대로 사용한다.

## 상태

Mock 통합용 fixture 경로와 실제 AI 구현이 함께 있다. `data/mock/search/scenario_*.json`에 기록된 실행은 `service=` 없이 부른 기본 경로가 반환한다.

실제 구현은 Elice ML API 프록시(OpenAI 호환)로 Gemini 계열 모델을 부른다. 설정 기본값은 `config.py::GeminiSearchConfig`에 있다.

- 모델: Coarse · Fine 모두 `gemini-4-argon` ([결정](../../../docs/modules/search/decisions/search-argon-model-2026-10-27.md)). 자연어 단서 추출(intent)은 Flash 모델을 쓴다.
- 전송 영상: 무음 재인코딩. Coarse는 270p · crf28로 전체 구간을 2배 느리게, Fine은 360p로 후보 ±4초를 4배 느리게 보낸다 ([구조 결정](../../../docs/modules/search/decisions/search-structure-2026-10-28.md), [270p 결정](../../../docs/modules/search/decisions/coarse-270p-e2e-2026-11-04.md)).
- 프롬프트(`prompt_resources/`): Coarse는 `coarse-p3` + `coarse-brief-v1`. Fine은 `fine-p3` + event type별 지침(`fine-p3-<type>`) + `fine-gore-v1`. 느리게 보낼 때는 `playback-slowdown-v1`을 덧붙인다. 조합 코드는 `prompts.py`에 있다.
- 그 밖에 프롬프트 fingerprint, 구조화 응답 schema, 429 전용 재시도, 업로드 cache, usage/cost ledger를 쓴다.
- Fine은 네 event type별 검증 지침을 고른다. 기존 `LANE_CHANGE` 입력은 공개 계약의 `SOLID_LINE_LANE_CHANGE`로 바꾼다.

독립 실행용 진입점은 다음과 같다. `coarse`는 `ELICE_ML_API_KEY`가 필요하다. 기존 이름 `GEMINI_API_KEY`도 읽는다(`config.api_key_from_env`). 결과 JSON의 문자열은 번호판 형식을 마스킹한다.

```bash
# 실제 Coarse 실행 (유료 API 호출)
uv run python -m daesingo.search coarse --source clip.mp4 --duration-sec 30

# Coarse → Fine을 이어 실행. --provider-fixture는 네트워크 없이 기록된 응답을 쓴다
uv run python -m daesingo.search smoke \
  --provider-fixture tests/search/fixtures/smoke_provider.json \
  --source clip.mp4 --duration-sec 30
```

`fine` 명령은 Coarse 후보가 있어야 해서 단독으로 실행되지 않는다(종료 코드 2). Fine만 보려면 `smoke`를 쓰거나 공개 함수 `verify_visual`에 `candidate`를 넘긴다. 실제 API로 `smoke`를 돌리려면 `--provider-fixture` 대신 `--live-manifest <JSON>`을 준다.

## 테스트

```bash
# search만
uv run pytest tests/search
uv run ruff check src/daesingo/search tests/search

# 레포 전체
uv run pytest
uv run ruff check
uv run ruff format --check
uv run basedpyright
uv run python data/mock/validate_mock_pack.py
```
