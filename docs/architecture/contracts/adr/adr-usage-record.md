# ADR — `UsageRecord` Data Contract

**Status:** Accepted
**Decider:** 김준영 (`common/runtime` Owner)
**Date:** 2026-09-05
**Contract:** `../contract-usage-record.md`
**상위 결정:** `adr-consistency-2026-09.md` C1-8

---

## 1. Context

v4 §5-1 ⑫에 `UsageRecord`가 등재돼 있고 `contract-analysis-run-candidate-event.md`가 이미 `usage_refs[]`로 참조하고 있었는데 **계약 문서가 없었다.** 참조되는 대상이 정의돼 있지 않으면 비용 목 데이터를 만들 수 없고, `eval`의 비용 지표가 전부 막힌다.

`common/runtime`은 PM 소유이므로 트랙 1로 작성했다.

## 2. Decision

**근거로 삼은 것** — v4 §4-모듈2 ⑥(정규화 사용량 + pricing context, raw payload 분리) · §4-모듈7 ⑤(비용 분모 이중 보존) · `AnalysisRun` 계약의 `usage_refs`/`UsageSummary` 규칙.

**`UsageSummary`와의 관계를 먼저 못박았다** — `AnalysisRun.usage_summary`는 Prediction과 함께 보존되는 **eval용 snapshot**이고, **상세 ledger의 authoritative source는 `UsageRecord`**다. 같은 숫자가 두 곳에 있는 것이 아니라 역할이 다르다.

PM이 새로 정한 것은 넷이고 계약 §9에 모아 두었다 — `execution_ref` · `case_id` 직접 보유 · `provider_label`/`operation` · `latency_ms`.

**`case_id`를 직접 둔 이유:** v4 §4-모듈7 ⑤의 `cost_per_source_video_hour`는 사건 단위 집계다. Run/Execution을 매번 join하게 만들면 `eval` 쪽 부담이 커진다. `eval` fixture 호출은 `case_id=null`.

**`latency_ms`를 둔 이유:** §4-모듈7 ⑤의 `latency_per_source_video_hour`가 이 값 없이 나오지 않는다. `JobExecution`의 시각 3개는 Job 단위라 **호출 단위** latency를 주지 못한다.

## 3. 충돌 확인 — `provider_label`

`Observation.source.kind`에 provider/model을 넣지 않는 규칙이 있다. `provider_label`은 그 규칙과 **충돌하지 않는다** — 그 규칙은 **관찰의 출처 표기**에 대한 것이고 비용 장부는 별개 값 공간이다. 비용 원장은 「어디에 돈을 냈는가」를 알아야 감사가 된다.

## 4. 기각한 안

**`JobExecution`에 금액을 직접 둔다** — 기각. 원천이 둘이 된다(`ownership.md` §6). `JobExecution`은 `usage_refs[]`만 갖는다.

**raw provider payload를 그대로 보존한다** — 기각. v4 §4-모듈2 ⑥이 정규화 사용량과 raw payload를 분리하도록 이미 정했고, 마스킹 로거 규칙에도 걸린다.

## 5. Consumer Review

계약을 소비자 리뷰 없이 닫았다. 소비자가 볼 범위를 §9 네 항목으로 좁혀 두었고 김대원(`eval`)에게 공지로 통보했다 — 「`cost_per_source_video_hour` / `cost_per_clip`이 둘 다 나오도록 `processed_duration_sec`과 `latency_ms`를 넣었다. §9만 보면 된다.」

2026-09-06 시점까지 이견 없음.

## 6. 미결

통화 고정 여부 · `purge_case`가 `UsageRecord`를 함께 지우는지. **보관 정책과 얽혀 있어 채우지 않았다.**
