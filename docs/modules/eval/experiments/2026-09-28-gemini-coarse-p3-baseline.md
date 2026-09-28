# 2026-09-28 · Gemini Coarse `coarse-p3` 베이스라인 (B tier)

작성: 김대원 · 브랜치 `exp/eval-gemini-coarse-baseline`

`search:gemini-coarse-p3`를 공식 B tier 평가셋 전체에 처음 돌린 결과다. `eval/README.md`의 규칙대로 **최초 실제 실행이 baseline**이며, 이후 challenger는 같은 manifest·GT·metric 버전으로 이 값과 비교한다.

## 한눈에

| 지표 | 값 | 95% CI |
| --- | --- | --- |
| Recall@1 | **0.10** (1/10) | 0.02–0.40 |
| Recall@3 | **0.50** (5/10) | 0.24–0.76 |
| Recall@10 | 0.50 | 0.24–0.76 |
| Localization Recall@3 (유형 무시) | 0.70 (7/10) | 0.40–0.89 |
| 위치를 맞춘 사건의 유형 정확도 | 0.71 (5/7) | 0.36–0.92 |
| onset 오차 (적중분) | 평균 1.7s · 중앙 2.0s (허용 2.0s) | |
| FP / negative clip | **2.80** (113클립 중 110클립에 후보) | |
| 비용 | $0.645 ≈ **₩903** 전체 · $0.318 ≈ ₩445 / 원본 1시간 | |
| 지연 (클립당) | p50 6.0s · p90 8.7s · max 17.2s | |
| 실패 클립 | 0 / 123 | |

**한 줄:** 사건 위치는 10건 중 7건을 3위 안에서 찾지만, 1위에 오는 것은 1건뿐이다. 순위와 유형(특히 중앙선 침범 → 실선 차로변경 혼동)이 약하고, 위반 없는 클립에도 거의 전부 후보를 낸다.

## [CASE]

| 항목 | 값 |
| --- | --- |
| manifest | `b_youtube` · `m3` · clip rule `c1` · split 전부 `DEV` |
| 정답지 | `gt_candidate.json` · `g3` (123/123 검수, negative 확정, 2026-09-16) |
| 구성 | 실제 YouTube 블랙박스 원본 3개를 ≤60초 클립으로 자름 — 123클립 · 7,303초(약 2시간 2분) |
| 원본별 | `YT_0001` 55클립 · `YT_0002` 1클립 · `YT_0003` 67클립 |
| positive | 10클립 · 사건 11건 — `SOLID_LINE_LANE_CHANGE` 7 · `SIGNAL` 2 · `CENTER_LINE_CROSSING` 2 · `MOTORCYCLE_HELMET_NON_USE` 0 |
| 채점 대상 | 10건 (1건 `BOUNDARY_EXCLUDED` — 클립 경계에 걸침) |
| negative | 113클립 |

**해석 주의:** 채점 사건이 10건이라 recall 1건 = 10%p다. 헬멧 미착용은 이 셋으로 측정되지 않는다.

## [INPUT]

- user hint 없음 (`SearchHint(vehicle=None, free_text=None)`)
- 대상 유형: 4종 전부
- scope: 클립 전 구간 · `budget.max_latency_sec=3600` · `max_cost_krw=100000`(미집행)

## [PIPELINE]

| 항목 | 값 |
| --- | --- |
| impl | `search:gemini-coarse-p3` (`eval/runners/impls/search_gemini.py`, `IMPL_VERSION` v1) |
| 호출 경계 | `daesingo.search.search_candidates(scope)` 공개 경계만 |
| model | `gemini-3.8-flash` (Elice ML API 프록시 경유) |
| prompt | `coarse-p3` |
| config | `gemini-search-v2` · coarse fps 1.0 · media resolution `low` · reasoning `low` |
| Fine | 실행 안 함 (candidate stage) |
| 서비스 | 클립마다 새로 생성 — 서비스 실행 상한 60초가 클립별로 적용된다 (아래 「실행 전 수정」) |

| 실행 메타 | 값 |
| --- | --- |
| run_id | `gemini_coarse_p3_baseline_20260928` |
| prediction | `eval/predictions/gemini_coarse_p3_baseline_20260928.json` (sha256 `b2e5d205…9ea7`) |
| result | `eval/results/gemini_coarse_p3_baseline_20260928.g3.s5-c3.json` |
| 채점 | scorer `s5` · cost scorer `c3` · normalizer `n3` · onset 허용 2.0s |
| 실행 시각 | 2026-09-28 13:3x 시작 → 14:04 종료 (호출 지연 합계 781s) |
| prompt fingerprint | `ac53a32b…1704c3c` |
| SDK | `google-genai` 2.24.0 |

**`code_commit` 값이 틀렸다.** 두 파일의 `meta.code_commit`은 `97b0ead`인데, 이 값은 실행이 **끝날 때** `git rev-parse HEAD`로 읽는다. 실행 중 같은 작업 폴더에서 다른 세션이 브랜치를 `docs/wireframe-result-first-flow`로 바꿨다. 실제로 돈 코드는 **`18c5d65`**다. 근거는 두 가지다. prediction `facts`에 `n_not_succeeded_clips` 필드가 있는데 `18c5d65`에서 생긴 필드다. 그리고 옛 코드는 첫 클립에서 `TypeError`로 죽는다. prediction은 immutable이라 고치지 않고 여기에 적는다.

## [RESULT]

### 사건별 (top-3, 허용 2.0s)

| 사건 | 유형 | onset | 결과 | 가장 가까운 후보 |
| --- | --- | ---: | --- | --- |
| `YT_0003_C10` | 실선 차로변경 | 8s | **적중@1** | r1 차로변경 · 오차 1.0s |
| `YT_0001_C08` | 신호위반 | 16s | 적중@3 | r3 신호 · 오차 2.0s (r1은 같은 시점을 **차로변경**으로 냄) |
| `YT_0001_C33` | 신호위반 | 51s | 적중@3 | r2 신호 · 오차 1.5s |
| `YT_0001_C39` | 실선 차로변경 | 53s | 적중@3 | r2 · 오차 2.0s (r1은 5s 앞) |
| `YT_0003_C05` #2 | 실선 차로변경 | 21s | 적중@3 | r2 · 오차 2.0s |
| `YT_0002_C00` | 중앙선 침범 | 12s | 위치만 맞음 | r1 **차로변경** · 오차 0.5s |
| `YT_0003_C28` | 중앙선 침범 | 9s | 위치만 맞음 | r1 **차로변경** · 오차 1.5s |
| `YT_0003_C44` | 실선 차로변경 | 29s | 놓침 | r1 · 오차 3.5s (허용 밖) |
| `YT_0003_C05` #1 | 실선 차로변경 | 11s | 놓침 | r1 · 오차 7.5s |
| `YT_0001_C09` | 실선 차로변경 | 10s | 놓침 | r3 · 오차 7.0s |
| `YT_0001_C47` | 실선 차로변경 | 1s | 제외 | `BOUNDARY_EXCLUDED` |

### 유형별 Recall@3

| 유형 | n | Recall@3 |
| --- | ---: | ---: |
| 실선 차로변경 | 6 | 0.50 |
| 신호위반 | 2 | 1.00 |
| 중앙선 침범 | 2 | **0.00** |
| 헬멧 미착용 | 0 | 측정 안 됨 |

### 오탐 (negative 113클립)

- 후보 316개. 113클립 중 110클립이 후보를 1개 이상 냈다. 후보 0개인 클립은 전체 123 중 3개뿐이다.
- 유형별: 차로변경 182 · 신호 90 · **헬멧 미착용 42** · 중앙선 2. 1위 후보 기준으로는 차로변경 73 · 신호 25 · 헬멧 12다.
- 정답지에 헬멧 사건이 0건인데 헬멧 후보가 전체 45개 나왔다. 요약문 대부분이 「헬멧 착용 여부 확인 필요」다. 이륜차가 보이기만 하면 후보를 올린다.
- 오탐 점수 사분위 0.40 / 0.48 / 0.65. 적중 후보(0.35–0.88)와 겹쳐서 점수 문턱으로 거르기 어렵다.
- 모델이 낸 후보 수는 클립당 0–8개(중앙 3개)다.

## [FAILURE]

분류 이름은 `docs/modules/search/decisions/failure-taxonomy.md`를 따른다.

| stage | kind | 건수 | 사건 | 관찰 |
| --- | --- | ---: | --- | --- |
| COARSE | `PRIMITIVE_FAILURE` | 2 | `YT_0002_C00` · `YT_0003_C28` | 중앙선 침범을 둘 다 **실선 차로변경**으로 냈다. 위치는 1위로 맞았다. 황색 중앙선과 백색 실선을 구분하지 못한다 |
| COARSE | `SEARCH_FAILURE` | 3 | `YT_0001_C09` · `YT_0003_C05`#1 · `YT_0003_C44` | 같은 클립에 차로변경 후보가 있지만 onset에서 3.5–7.5s 벗어났다. C44는 허용 2.0s를 1.5s 넘긴 근접 실패다 |
| COARSE | 순위 (`RANKING_FAIL` 후보) | 4 | C08 · C33 · C39 · C05#2 | 맞는 후보가 2–3위다. 1위 적중이 1/10뿐인 원인이다. taxonomy에서 이 항목을 `SEARCH_FAILURE`의 하위로 둘지는 미결이다 |
| COARSE | 오탐 | — | negative 110/113클립 | 위 「오탐」 참조 |

## 비용 산정

프록시 고지 단가는 원화다: 입력 ₩1,141 · 캐시 입력 ₩114 · 출력 ₩5,709 (1M 토큰당). 설정은 USD만 받으므로 **1 USD = 1,400 KRW**로 환산해 넣었다 — 입력 0.815 · 출력 4.078 USD/1M. 캐시 입력 단가는 설정에 자리가 없어 반영하지 않았다(캐시 적중분은 과대 계상될 수 있다). 토큰 수는 prediction `facts`에 남아 있어 원화로 다시 계산할 수 있다.

## 실행 전 수정 (커밋 `18c5d65`)

1. **러너가 첫 클립에서 `TypeError`로 죽었다.** search 리팩터링으로 `ResolvedAnalysisSource`가 경로를 갖지 않게 됐는데 러너는 옛 생성자를 썼다. 기존 테스트는 `_build_service`를 monkeypatch해서 못 잡았다 → 실제 `_build_service`를 부르는 테스트를 추가했다.
2. **123클립이 60초 시계 하나를 공유했다.** `build_gemini_search_service`가 서비스 생성 시점부터 60초를 센다(#149, 수정 PR #180 미머지). 한 서비스로 돌리면 앞 1~2클립 뒤 전부 조용히 `FAILED`(후보 0개)가 되어 baseline이 오염된다 → 클립마다 서비스를 만든다.
3. `SUCCEEDED`가 아닌 클립을 `facts.not_succeeded_clips`에 남기고, 후보의 `summary`·`uncertainties`를 prediction에 옮긴다.

PR #180이 머지되면 서비스 상한이 scope의 `max_latency_sec`로 바뀐다. 그 뒤 실행과 비교할 때 이 조건 차이를 적는다.

## 재현

```bash
uv sync --extra test --extra eval-gemini
uv run python -m eval.run --impl search:gemini-coarse-p3 --manifest b_youtube --stage candidate --run-id gemini_coarse_p3_baseline_20260928
uv run python -m eval.score --prediction gemini_coarse_p3_baseline_20260928
```

## [LEARNING]

- **다음에 바꿀 한 가지:** Coarse 프롬프트에 **중앙선(황색)과 차선(백색) 실선을 구분하는 기준**을 넣는다. 중앙선 침범 2건이 위치는 1위로 맞았는데 유형 때문에 놓쳤다. 이 한 가지로 Recall@3이 0.5 → 0.7까지 오를 수 있다.
- 오탐 2.8/클립은 Fine 단계가 걸러야 하는 양이다. Fine 비용을 추정할 때 「negative 클립에도 거의 항상 후보 2–3개」를 전제로 둔다.
- 헬멧 후보 45개는 정답지로 채점할 수 없다. 헬멧 positive가 있는 클립을 셋에 추가하기 전까지 이 유형은 오탐만 보인다.
- 사건이 10건뿐이라 CI가 넓다(Recall@3 0.24–0.76). challenger와의 차이가 1–2건이면 우연과 구분되지 않는다.
- 같은 작업 폴더에서 여러 세션이 브랜치를 바꾸면 `code_commit`이 틀린다. 평가는 전용 worktree(`대신고-eval`)에서 돌린다.
