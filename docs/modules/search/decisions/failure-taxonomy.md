# search 실패 분류 (Failure Taxonomy)

> **상태: 「실행 실패 — `JobExecution.failure_kind`」 절은 Owner(서어진) 확정(2026-10-25, #297 RT-10(b)). 그 아래 품질 분류(stage · kind)는 아직 초안.**
> 2026-09-04 문서 정리에서 만들었다.
> 이 목록은 새로 정한 것이 아니다. 모듈 구조 설계 v3와 `modules/eval/experiment-guide.md` 템플릿에 흩어져 있던 이름을 **소유자 폴더 한 곳**으로 모은 것이다. v4는 「실패 taxonomy 기록」을 `search` 책임으로 두고 세부 이름은 Data Contract로 내렸다(`module-architecture.md` §4-모듈2 ②, §13-2).
> `eval`은 이 이름을 **복제하지 않고 가리킨다.** `experiment-guide.md` `[FAILURE]`, `initial-evaluation-plan.md` §6이 이 문서를 본다.

## 실행 실패 — `JobExecution.failure_kind` (확정)

Search 실행이 실패로 끝났을 때 Worker가 `JobExecution.failure_kind`에 쓰는 값이다(`contract-job-execution.md` §6). 아래 품질 분류(사건을 놓쳤나 · 틀렸나)와는 다른 축이다 — 이쪽은 「실행이 끝까지 돌았나」만 본다.

**Worker는 따로 매핑하지 않고 `daesingo.search`의 함수 결과를 그대로 쓴다.** 규칙 구현은 `search/failure_kind.py` 한 곳이다.

| 입력 | 함수 |
| --- | --- |
| `COARSE_SEARCH` · `FINE_VERIFY`가 돌려준 `AnalysisRun` | `failure_kind_for_run(run)` |
| `HINT_EXTRACT`가 돌려준 `IntentHintResult` | `failure_kind_for_intent(result)` |
| Search public capability가 던진 예외 | `failure_kind_for_error(error)` |

반환값 `None`은 「Search 실패가 아니다」 — 성공 · `PARTIAL` Run, intent `OK` · `ABSTAINED`, Runtime 소유인 `UsageError`다. `UsageError`는 Search 실패로 바꾸지 않고 Runtime terminal 오류 경계를 따른다(#303).

### 값 7개

| `failure_kind` | 뜻 | 다시 하면 나아질 수 있나 |
| --- | --- | --- |
| `SEARCH_PROVIDER_CONFIG` | 인증 · 권한 · 모델 경로 오류(HTTP 401 · 403 · 404), 허용되지 않은 base URL | 아니오 — 설정을 고쳐야 한다 |
| `SEARCH_PROVIDER_ERROR` | provider 호출 실패 — 429 재시도 소진, 5xx, 네트워크 · SDK timeout, 요청 거부(400) | 예 |
| `SEARCH_DEADLINE_EXCEEDED` | 실행 시간 상한(`AnalysisScope.budget.max_latency_sec` 등) 초과 | 예 |
| `SEARCH_RESPONSE_INVALID` | 응답은 받았지만 쓸 수 없다 — JSON · schema 위반, 잘림 · 필터, 시각이 클립 밖, Coarse 후보가 전부 영상 밖 | 예 |
| `SEARCH_MEDIA_PREPARATION_FAILED` | 영상 준비 실패 — ffmpeg · ffprobe, 크기 상한, 선언 길이와 실제 길이 불일치, 요청 크기 상한 | 대개 아니오 |
| `SEARCH_INPUT_INVALID` | 호출 입력이 계약과 맞지 않는다 — 후보 누락 · 불명, 후보와 출처 timeline 불일치, Fine 구간 없음, VIDEO stream을 하나로 정할 수 없음 | 아니오 — 발주 쪽 결함 |
| `SEARCH_UNCLASSIFIED` | 위 어디에도 들지 않는 Search 실패(fallback) | 모름 |

### Run → `failure_kind`

- `outcome=FAILED`인 Run만 실패다. `PARTIAL`(일부 후보만 빠짐)은 Job 실패로 올리지 않는다.
- **여러 issue면 첫 번째 issue를 쓴다.** Search는 Run을 실패로 만든 issue를 `issues[0]`에 둔다.
- `FAILED`인데 issue가 없거나 아래 표에 없는 code면 `SEARCH_UNCLASSIFIED`.

| `issues[].code` | `failure_kind` |
| --- | --- |
| `PROVIDER_CONFIG_ERROR` | `SEARCH_PROVIDER_CONFIG` |
| `PROVIDER_CALL_FAILED` | `SEARCH_PROVIDER_ERROR` |
| `PROVIDER_RESPONSE_INVALID` | `SEARCH_RESPONSE_INVALID` |
| `RUN_DEADLINE_EXCEEDED` | `SEARCH_DEADLINE_EXCEEDED` |
| `MEDIA_PREPARATION_FAILED` | `SEARCH_MEDIA_PREPARATION_FAILED` |
| `COARSE_SPAN_OUT_OF_SOURCE` | `SEARCH_RESPONSE_INVALID`(후보가 전부 빠져 `FAILED`일 때만. 일부면 `PARTIAL`) |

Coarse는 provider 호출 실패를 issue code로 남길 때 같은 분류(`provider_issue_code`)를 쓴다 — 인증 실패가 `PROVIDER_CALL_FAILED`에 섞이지 않는다.

### intent(`HINT_EXTRACT`) → `failure_kind`

| `IntentHintResult.failure_kind` | `failure_kind` |
| --- | --- |
| `CONFIG_ERROR` | `SEARCH_PROVIDER_CONFIG` |
| `PROVIDER_ERROR` | `SEARCH_PROVIDER_ERROR` |
| `DEADLINE_EXCEEDED` | `SEARCH_DEADLINE_EXCEEDED` |
| `RESPONSE_INVALID` | `SEARCH_RESPONSE_INVALID` |
| 없음 · 예상 밖 값 | `SEARCH_UNCLASSIFIED` |

intent `FAILED`를 Job 실패로 볼지, 빈 단서로 진행할지는 이 문서 범위 밖이다(case-command 계약 §11, #259).

### Fine(`FINE_VERIFY`)

현재 Fine은 `FAILED` Run을 돌려주지 않고 실패를 예외로 던진다. 예외는 `failure_kind_for_error`로 분류한다. 나중에 `FAILED` Run을 돌려주게 되면 위 Run 규칙을 그대로 쓴다.

### 값 추가

새 값은 이 표와 `SearchFailureKind`에 함께 등재한 뒤 쓴다. Worker가 임의의 `SEARCH_*` 값을 만들지 않는다.

---

## stage

`COARSE` · `FINE`

## kind (search)

| 이름 | 의미 | 챌린저 매핑(`challenger-policy.md`) |
| --- | --- | --- |
| `SEARCH_FAILURE` | 사건 자체를 후보에 올리지 못함 | SEARCH_FAILURE 행 |
| `PRIMITIVE_FAILURE` | 차선·신호·차량 등 기본 시각 정보 인식 실패 | PRIMITIVE_FAILURE 행 |
| `TEMPORAL_ORDER_FAILURE` | 신호 → 정지선 → 통과 같은 전후 순서 판단 실패 | TEMPORAL_ORDER_FAILURE 행 |
| `TARGET_ASSOCIATION` | 다른 차량/대상을 사건 주체로 연결 | TARGET_ASSOCIATION 행 |
| `FINE_FALSE_NEGATIVE` | Coarse는 찾았는데 Fine이 제거 | FINE_FALSE_NEGATIVE 행 |
| `COST` | 비용·지연 상한 초과로 중단 | COST 행 |
| `INFRA` | timeout / API / 파이프라인 오류 (공통) | 챌린저 대상 아님 |

## Owner가 확정할 때 함께 볼 후보 이름

`experiment-guide.md` §13이 다른 이름 체계를 제안했다. 확정 시 흡수·병합 여부를 정한다.

```text
RANKING_FAIL       후보에는 있지만 Top-K 밖          → SEARCH_FAILURE의 하위로 둘지 별도로 둘지
EVENT_CLASS_FAIL   사건 유형 판단 오류               → Fine/Classification 실패. FINE_FALSE_NEGATIVE와 구분할지
OVERCONFIDENT      불확실하지만 확정값 반환          → search에서는 VisualEvidence.uncertainty 미기록. readout에도 같은 항목 필요
UNKNOWN            아직 원인 불명
```

## 기록 규칙

- `AnalysisRun`에 stage + kind로 기록한다. 이름만 적고 자유 텍스트로 대신하지 않는다.
- 이 분류 통계가 특정 카테고리를 가리킬 때만 챌린저를 연다(`challenger-policy.md`).
- 번호판·화면시각 실패는 여기 넣지 않는다 → `modules/readout/decisions/failure-taxonomy.md`.
