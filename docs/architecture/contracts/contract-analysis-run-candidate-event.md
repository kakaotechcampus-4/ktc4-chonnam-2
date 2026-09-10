# Final Data Contract — AnalysisRun + CandidateEvent v1

**Status:** `Final — Accepted`

> **B09 종결 (2026-09-07).** `CandidateEvent.span`에 `timeline_revision`을 추가했다(§4-1). Decider 정철원(`recording`), 필드 승인 서어진(`search`), 표시 유소연(`case`), evidence provenance 동일 형태 김준영. serialization 변경이므로 이 계약 §9 규칙대로 `contract_version`을 `v1.1`로 올렸다. 근거·기각안 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.8.

> **`usage_refs[]` 지위 표기 (2026-09-08 결정, 서어진 · 확인 김대원·김준영).** `AnalysisRun.usage_refs[]`는 **조회 편의용 파생값**이며 authoritative가 아니다. Run↔Usage 연결과 비용 집계의 기준은 `UsageRecord.run_ref`다(§3·§3-4·§6-1·§7·§8). `ReadoutRun.usage_refs`와 같은 지위다. 의미 변경이 아닌 표기 정합이라 **버전은 `v1.1` 유지**. 근거 `adr/adr-data-contract-call-closure-2026-09-08.md` §4.2.

**Accepted:** `2026-09-04` (짝 ADR의 결정일 9/4) · `2026-09-07` (v1.1)

**Related ADR:** `adr/adr-analysis-run-candidate-event.md` · `adr/adr-data-contract-call-closure-2026-09-07.md` §4.8

**Architecture Contract:** v4 §5-1 ⑤

**Contract:** `AnalysisRun + CandidateEvent`

**Contract Version:** `analysis-run-candidate-event/v1.1`

**Producer / Owner:** 서어진 (`search`)

**Consumers:** 유소연 (`case`), 김대원 (`eval`)

**기준 Architecture:** `module_architecture.md v4`

**결정 근거:** [ADR: `AnalysisRun + CandidateEvent` Data Contract 확정](https://app.notion.com/p/ADR-AnalysisRun-CandidateEvent-Data-Contract-3d17ae78fc6a801fb248faca5fb72d8b?pvs=21)

**검토 이력:** [`AnalysisRun + CandidateEvent`](https://app.notion.com/p/AnalysisRun-CandidateEvent-3cf7ae78fc6a80c58dd6ed813b4d9898?pvs=21)

<aside>
✅

이 페이지가 `AnalysisRun + CandidateEvent`의 **Source of Truth**다. Draft는 대안과 검토 이력을, ADR은 결정 이유를 보존한다. 구현·Mock·Eval serialization은 이 Final Contract를 따른다.

</aside>

---

# 1. 계약 목적

`search`의 public capability 실행을 `AnalysisRun`이라는 **불변 logical run**으로 기록하고, Candidate Search에서 발견한 사건 가능 시간 구간을 `CandidateEvent[]`로 `case`와 `eval`에 전달한다.

- `AnalysisRun`은 provider call이나 chunk가 아니라 **public capability invocation 1회**를 의미한다.
- `CandidateEvent`는 실제 파일이나 신고 영상을 소유하지 않고 **Recording Timeline 기준 span**을 표현한다.
- Candidate ordering의 authoritative 값은 `rank`다.
- Candidate는 법적 위반, 신고 유형, 최종 Evidence를 확정하지 않는다.
- 상세 usage ledger의 authoritative source는 `UsageRecord`이며, Eval 재평가를 위해 `AnalysisRun.usage_summary`를 **immutable snapshot**으로 함께 보존한다.

---

# 2. 최종 Serialization

아래 최상위 `{analysis_run, candidates}` 구조는 전달 예시이며 별도의 신규 Domain Contract를 뜻하지 않는다.

```json
{
  "analysis_run": {
    "run_id": "run_01J...",
    "operation": "CANDIDATE_SEARCH",
    "input_ref": {
      "kind": "ANALYSIS_SCOPE",
      "ref": "scope_11"
    },
    "implementation": {
      "impl_id": "gemini-candidate-search@c7",
      "model_ref": "gemini-3.7-flash",
      "prompt_version": "coarse-c7",
      "config_version": "search-v2"
    },
    "outcome": "SUCCEEDED",
    "started_at": "2026-09-02T16:00:02+09:00",
    "completed_at": "2026-09-02T16:01:06+09:00",
    "issues": [],
    "usage_refs": [
      "usage_101",
      "usage_102"
    ],
    "usage_summary": {
      "processed_duration_ms": 300000,
      "token_usage": {
        "input_tokens": 14200,
        "output_tokens": 1200,
        "total_tokens": 15400
      },
      "latency_ms": 64000,
      "total_cost": {
        "amount": "0.42",
        "currency": "USD"
      }
    },
    "contract_version": "analysis-run-candidate-event/v1.1"
  },
  "candidates": [
    {
      "candidate_id": "candidate_001",
      "run_id": "run_01J...",
      "span": {
        "timeline_id": "timeline_01",
        "timeline_revision": 1,
        "start_ms": 420000,
        "end_ms": 438000,
        "representative_ms": 429000
      },
      "rank": 1,
      "ranking_score": 0.81,
      "event_type_hint": "SOLID_LINE_LANE_CHANGE",
      "summary": "흰 SUV가 차선을 넘어 인접 차로로 이동하는 장면",
      "uncertainties": [
        "선 종류 일부 불명확"
      ],
      "thumbnail_ref": null
    }
  ]
}
```

---

# 3. `AnalysisRun` 필드 정의

| 필드 | 타입 | 필수 | 의미 / 보장 |
| --- | --- | --- | --- |
| `run_id` | ID | 필수 | public capability logical invocation의 고유 ID. 재실행마다 새 ID를 생성하며 Job ID와 동일 개념이 아니다. |
| `operation` | enum | 필수 | `CANDIDATE_SEARCH | VISUAL_VERIFY`. 내부 `COARSE/FINE` stage를 의미하지 않는다. |
| `input_ref` | object | 필수 | 실행 입력 Contract reference. `CANDIDATE_SEARCH`에서는 `kind=ANALYSIS_SCOPE`를 사용한다. |
| `implementation` | object | 필수 | 실행 구현 identity와 재현용 version metadata. |
| `outcome` | enum | 필수 | `SUCCEEDED | PARTIAL | FAILED`. terminal domain outcome만 표현한다. |
| `started_at` | datetime | 필수 | logical run 시작 시각. timezone offset을 포함한 ISO 8601. |
| `completed_at` | datetime | 필수 | logical run 완료 시각. `completed_at >= started_at`. |
| `issues` | Issue[] | 필수 | 부분/전체 실패 정보. 정상 성공이면 빈 배열 가능. |
| `usage_refs` | ID[] | 필수 | 해당 Run의 상세 `UsageRecord` reference. 외부 usage가 없으면 빈 배열 가능. **조회 편의용 파생값(역방향 참조)이며 authoritative가 아니다** — 어느 Run에 속한 사용량인지의 기준은 `UsageRecord.run_ref`(`{kind:"analysis_run", ref:<run_id>}`)이고 두 값이 어긋나면 `UsageRecord.run_ref`가 기준이다(`contract-usage-record.md` §8-12). 양방향 정합을 이 계약의 불변조건으로 강제하지 않는다. `ReadoutRun.usage_refs`와 같은 지위(2026-09-08, 서어진). |
| `usage_summary` | UsageSummary | 필수 | Run 완료 시점의 Eval용 immutable usage snapshot. |
| `contract_version` | string | 필수 | 현재 `analysis-run-candidate-event/v1.1`. v1과의 차이는 `CandidateEvent.span.timeline_revision` 추가 하나다. |

## 3-1. `input_ref`

```json
{
  "kind": "ANALYSIS_SCOPE",
  "ref": "scope_11"
}
```

- `kind`: 참조 대상 Contract 종류.
- `ref`: 실제 대상 ID.
- `CANDIDATE_SEARCH`는 `AnalysisScope`를 참조한다.
- 다른 operation의 허용 input 종류는 해당 output Contract의 접합 규칙을 따른다.

## 3-2. `implementation`

| 필드 | 타입 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `impl_id` | string | 필수 | implementation identity. 같은 모델이어도 prompt/config가 다르면 다른 구현일 수 있다. |
| `model_ref` | string/null | 조건부 | 주요 모델 식별. 모델을 사용하지 않는 구현이면 null 가능. |
| `prompt_version` | string/null | 조건부 | prompt 기반 구현이면 기록. prompt 본문은 포함하지 않는다. |
| `config_version` | string/null | 조건부 | 실행 config version. FPS/chunk 등의 전체 설정값을 공용 Contract에 직접 노출하지 않는다. |

## 3-3. `Issue`

```json
{
  "kind": "INFRA",
  "code": "SUBRANGE_PROVIDER_TIMEOUT",
  "scope_ref": "timeline_01:2400000-2700000",
  "detail": null
}
```

| 필드 | 타입 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `kind` | enum | 필수 | Search failure taxonomy의 상위 종류. 값 집합은 Search failure taxonomy를 따른다. |
| `code` | string | 필수 | stable machine-readable failure code. |
| `scope_ref` | ref/null | 선택 | 영향받은 입력 범위. Partial coverage를 Case/Eval이 식별할 수 있어야 한다. |
| `detail` | string/null | 선택 | 마스킹 가능한 최소 진단 정보. stack trace나 raw provider payload를 넣지 않는다. |

## 3-4. `UsageSummary`

`usage_summary`는 `UsageRecord`를 대체하지 않는다. **상세 ledger는 UsageRecord가 authoritative**, 이 객체는 Prediction과 함께 보존되는 Eval용 snapshot이다.

```json
{
  "processed_duration_ms": 300000,
  "token_usage": {
    "input_tokens": 14200,
    "output_tokens": 1200,
    "total_tokens": 15400
  },
  "latency_ms": 64000,
  "total_cost": {
    "amount": "0.42",
    "currency": "USD"
  }
}
```

| 필드 | 타입 | 필수 | 규칙 |
| --- | --- | --- | --- |
| `processed_duration_ms` | integer/null | 필수 키 | 실제로 처리한 source duration. 측정 불가/비적용이면 null. |
| `token_usage` | object/null | 필수 키 | `input_tokens`, `output_tokens`, `total_tokens`를 보존. provider가 token을 제공하지 않으면 null. |
| `latency_ms` | integer/null | 필수 키 | logical run latency snapshot. 측정 불가하면 null. |
| `total_cost` | Money/null | 필수 키 | `amount`는 decimal string, `currency`는 통화 코드. 계산 불가하면 null. |

**Snapshot 규칙**

- Run 완료 이후 `usage_summary`를 과거 가격 변경 때문에 다시 계산해 덮어쓰지 않는다.
- `usage_summary`는 해당 Run에 속한 usage의 실행 시점 aggregate와 정합해야 한다. 「해당 Run에 속한 usage」의 기준은 원장 행의 `UsageRecord.run_ref`가 이 Run을 가리키는 것이며 `usage_refs[]`가 아니다(2026-09-08). `usage_refs[]`가 잘못됐다는 이유만으로 `usage_summary`의 집계 기준이 바뀌지 않는다.
- 과거 비용을 현재 가격으로 다시 계산해야 하면 `usage_summary`를 고치지 않고 `UsageRecord.pricing_context`로 별도 평가 결과를 만든다.
- PARTIAL/FAILED에서도 확보 가능한 latency/cost/processed duration은 snapshot에 남길 수 있다.

---

# 4. `CandidateEvent` 필드 정의

| 필드 | 타입 | 필수 | 의미 / 보장 |
| --- | --- | --- | --- |
| `candidate_id` | ID | 필수 | Candidate 안정 reference. 확정 Evidence ID가 아니다. |
| `run_id` | ID | 필수 | 자신을 생성한 `AnalysisRun.run_id`. |
| `span` | object | 필수 | Recording Timeline 기준 canonical 위치. 생성 당시 `timeline_revision`을 함께 보존한다(v1.1). |
| `rank` | integer | 필수 | 해당 Run 내 최종 후보 순위. 1부터 시작하며 ordering/Recall@K의 authoritative 값. |
| `ranking_score` | number/null | 선택 | 동일 implementation 내부 ranking diagnostic. calibrated confidence가 아니다. |
| `event_type_hint` | VisualEvent enum/null | 선택 | 예상 visual event family. 법적 신고 유형이나 Fine 확정값이 아니다. |
| `summary` | string/null | 선택 | Candidate Review를 위한 짧은 시각 관찰 요약. 법적 판단 문구 금지. |
| `uncertainties` | string[] | 선택 | Coarse 단계에서 남은 불확실성. 없으면 빈 배열 가능. |
| `thumbnail_ref` | FrameRef/null | 선택 | 후보 검토용 Source-derived 대표 frame reference. exact syntax는 `recording` Contract를 따른다. |

## 4-1. `span`

```json
{
  "timeline_id": "timeline_01",
  "timeline_revision": 1,
  "start_ms": 420000,
  "end_ms": 438000,
  "representative_ms": 429000
}
```

- `timeline_id`: Recording Timeline reference.
- `timeline_revision` (v1.1, 필수): 이 span의 좌표가 기준으로 삼은 `RecordingTimeline.revision`(`>= 1`). **생성 당시 값이며 rebase 후에도 바꾸지 않는다.** Candidate provenance = `timeline_id + timeline_revision`. 현재 화면 표시 시각은 `case`가 현재 revision으로 projection하고, provenance revision과 현재 revision이 다르면 `case`가 비교해 `CaseView`에 「과거 timeline revision 기준」임을 표시한다 — **`search`는 revision 값만 노출하고 stale 판정·표시를 하지 않는다.** 근거 `adr/adr-data-contract-call-closure-2026-09-07.md` §4.8 (B09).
- `start_ms`: timeline 시작 기준 상대 offset. `>= 0`.
- `end_ms`: timeline 시작 기준 상대 offset. `> start_ms`.
- `representative_ms`: Candidate 대표 지점. `start_ms <= representative_ms <= end_ms`.
- 이 span은 실제 SourceAsset/file boundary가 아니며 최종 신고 `occurred_at`도 아니다.
- **명확화(2026-09-10, 이슈 #22 B-2·`CONTRACT_CONFLICTS.md` 불명확 항목 7 종결, 서어진 — 원문 `docs/modules/search/decisions/candidate-span-semantics-2026-09-10.md`).** `span`은 **coarse 후보 창(candidate window)이며 사건 길이(duration)와 같지 않다.** 이 span을 만드는 `AnalysisRun.operation=CANDIDATE_SEARCH`(coarse)의 산출물은 정밀 사건 구간이 아니라 대략적 후보 시간 창이고, 창 폭이 넓은 것(수십~백여 초) 자체는 정상이다. 사건의 정밀 시각은 이 계약이 아니라 별도 레이어가 담당한다 — Fine 단계(`VISUAL_VERIFY`)의 `temporal_facts[].at_offset_ms`, 그리고 최종적으로 `occurred_at`(overlay/`TimeResolution`). `representative_ms`는 이 넓은 창 안에서 실제 사건 순간(예: crossing moment)을 가리키도록 설계된 대표 시점이며 — `representative_ms = span.start_ms + fine.at_offset_ms`가 fixture 전반에서 성립한다 — coarse localization 정확도를 재는 authoritative 지점이다.

---

# 5. Outcome 의미

| 값 | 의미 | Candidate | Issue |
| --- | --- | --- | --- |
| `SUCCEEDED` | 요청 범위의 Search가 정상 완료됨 | 0개 이상 가능 | 실행 실패를 의미하는 issue 없음 |
| `PARTIAL` | 일부 범위/호출 실패가 있으나 usable result가 존재할 수 있음 | 0개 이상 가능 | 최소 1개 필수 |
| `FAILED` | logical run이 실패함 | usable Candidate 반환 금지 | 최소 1개 권장 |

`SUCCEEDED + candidates=[]`는 오류가 아니다. 이는 정상 탐색을 완료했지만 보존할 Candidate를 찾지 못했다는 뜻이다.

`QUEUED`, `RUNNING`, `STALE`은 이 Contract가 아니라 common/runtime의 `JobExecution` 책임이다.

---

# 6. Invariants

## 6-1. `AnalysisRun`

1. 하나의 public capability logical invocation은 하나의 `AnalysisRun`으로 표현한다.
2. `run_id`는 다른 실행에서 재사용하지 않는다.
3. 완료된 Run은 수정하지 않는다. 동일 입력 재실행도 새 `run_id`를 생성한다.
4. `completed_at >= started_at`.
5. `CANDIDATE_SEARCH`의 정상 결과는 Candidate 0개를 허용한다.
6. `FAILED`는 usable Candidate를 반환하지 않는다.
7. `PARTIAL`은 `issues.length >= 1`이어야 한다.
8. `SUCCEEDED`는 실행 실패를 의미하는 issue를 포함하지 않는다.
9. `AnalysisRun`은 `QUEUED/RUNNING/STALE`을 표현하지 않는다.
10. 모든 Run은 `implementation`과 `contract_version`을 가진다.
11. `usage_refs[]`는 해당 Run의 상세 UsageRecord를 추적할 수 있어야 한다. 단, 이 배열은 조회 편의용 파생값이며 Run 소속의 authoritative source는 `UsageRecord.run_ref`다 — 어긋나면 원장이 기준이다(2026-09-08).
12. `usage_summary`는 Run 완료 시점의 immutable snapshot이다.
13. 법적 위반, 신고 유형, Evidence confirmation 값은 `AnalysisRun`에 존재하지 않는다.
14. raw provider response는 공용 Contract에 저장하지 않는다.

## 6-2. `CandidateEvent`

1. `candidate_id`는 시스템 내에서 안정적으로 unique해야 한다.
2. `CandidateEvent.run_id == AnalysisRun.run_id`여야 한다.
3. `span.start_ms >= 0`.
4. `span.start_ms < span.end_ms`.
5. `span.start_ms <= representative_ms <= span.end_ms`.
6. 한 Run 안에서 `rank`는 중복되지 않으며 1부터 시작하는 positive integer다.
7. `ranking_score`가 없어도 `rank`는 반드시 존재한다.
8. `ranking_score`를 서로 다른 `impl_id` 사이의 calibrated confidence로 해석하지 않는다.
9. Candidate span은 SourceAsset/file boundary나 최종 `occurred_at`을 의미하지 않는다.
10. `event_type_hint`는 법적 신고 유형을 표현하지 않는다.
11. Candidate ordering을 바꿔야 하면 기존 Run/Candidate를 수정하지 않고 새 Search Run을 생성한다.
12. Candidate는 신고용 video/file reference를 소유하지 않는다.
13. (v1.1) `span.timeline_revision >= 1`이며 생성 당시 `RecordingTimeline.revision`이다. Timeline rebase가 일어나도 기존 Candidate의 `span`을 새 revision 기준으로 mutate하지 않는다.

---

# 7. Producer / Consumer 규칙

## Producer — `search`

반드시:

- public capability invocation마다 새 immutable `AnalysisRun`을 생성한다.
- Candidate를 `candidate_id + run_id`로 안정적으로 식별 가능하게 한다.
- Candidate canonical 위치를 Recording Timeline span으로 제공한다.
- ordering을 `rank`로 고정한다.
- `SUCCEEDED / PARTIAL / FAILED`를 구분한다.
- Partial failure에 필요한 최소 `scope_ref`를 제공한다.
- implementation version metadata를 기록한다.
- 상세 usage는 `UsageRecord`와 연결하고 Eval용 `usage_summary` snapshot을 함께 생성한다.
- raw provider payload, 법적 판단, 신고 유형, 최종 Evidence를 이 Contract에 넣지 않는다.

## Consumer — `case`

반드시:

- Candidate 선택 reference로 `candidate_id`를 사용한다.
- Candidate ordering은 `rank`로 처리한다.
- `ranking_score` threshold로 Evidence 의미를 재판정하지 않는다.
- Candidate absolute display time은 **현재** Timeline revision으로 projection한다. `span.timeline_revision`이 현재 `RecordingTimeline.revision`과 다르면 그 사실을 `CaseView`에 표시한다(표시 필드는 case 소유 — `contract-job-record-case-view.md` B절 §13). 과거 Candidate를 현재 anchor로 조용히 환산해 provenance를 지우지 않는다.
- `PARTIAL`이면 필요한 coverage notice를 구성할 수 있도록 `issues`를 확인한다.

## Consumer — `eval`

반드시:

- Recall@1/3/10은 `rank` 기준으로 계산한다.
- **coarse localization 매칭 규칙(2026-09-10 정정, 이슈 #22 B-2, 서어진 — 원문 `docs/modules/search/decisions/candidate-span-semantics-2026-09-10.md`).** `span`은 coarse 후보 창일 뿐 사건 구간이 아니므로(§4-1) **span IoU를 1차 매처로 쓰지 않는다.** localization은 `|representative_ms − gt_onset_ms|`(tolerance 매칭, point/onset error)로 계산한다. `start_ms <= gt_onset_ms <= end_ms`(span containment)는 보조 sanity 신호로만 쓴다. 이전 문구("span/timestamp error는 timeline-relative span 기준으로 계산한다")는 이 규칙으로 대체됐다 — timeline-relative라는 좌표계 자체는 여전히 맞지만, span 폭 전체와의 IoU로 오차를 재는 것은 coarse 창 설계와 맞지 않아 구조적으로 실패했다(예: `happy_001`은 오차 0인 매칭인데 IoU 최대 0.15).
- implementation 비교에는 `impl_id + model_ref + prompt_version + config_version + contract_version`을 사용한다.
- Efficiency 재평가에는 immutable `usage_summary`를 사용할 수 있다.
- **집계 키 분리(2026-09-10 정정, 이슈 #33 Required-7).** 이 Run 하나에 속한 상세 usage row를 감사(audit)할 때는 원장 `UsageRecord.run_ref`로 스캔한다 — `usage_refs[]`는 audit 진입점(편의)으로만 쓰고 집계 기준으로 쓰지 않는다(2026-09-08 결정 유지). 그러나 **`cost_per_source_video_hour` 같은 사건/source-video 단위 비용 지표의 정본 집계 키는 `run_ref`가 아니라 `UsageRecord.case_id`다**(`contract-usage-record.md` §9-2·§9-6) — `run_ref=null`인 row(예: Run이 생성되지 못한 채 종료된 STALE 호출, `run_ref_reason=RUN_NOT_PRODUCED`)도 실제로 그 사건에 청구된 비용이므로 `run_ref` 스캔만으로는 비용 분모에서 누락된다. 요약하면 **"이 Run에 속한 usage" 질의는 `run_ref`, "이 사건/영상에 든 전체 비용" 질의는 `case_id`**이며 서로 대체하지 않는다.

---

# 8. Contract 접합부

| 연관 Contract | 접합 | 책임 |
| --- | --- | --- |
| `AnalysisScope` | `AnalysisRun.input_ref` | Candidate Search 입력 범위/의도는 `case`가 생산 |
| `RecordingTimeline` | `CandidateEvent.span.timeline_id` | 실제 파일 경계 해석과 clip/frame materialization은 `recording` 책임 |
| `VisualEvidence` | Candidate 이후 verification | 구조화된 시각 관찰 및 Fine 결과는 별도 Contract 책임 |
| `UsageRecord` | `UsageRecord.run_ref`(authoritative) ← `AnalysisRun.usage_refs[]`(파생 역참조) | 상세 usage/pricing ledger와 Run 소속의 authoritative source는 원장 `run_ref` |
| `CaseView` | Candidate selection/display projection | absolute display time 및 사용자 선택 상태는 `case` 책임 |
| Eval Prediction | `usage_summary` 보존 | Prediction 파일 단독 Efficiency re-score 가능하도록 snapshot 유지 |

---

# 9. 변경 정책

- 이 페이지가 v1의 **유일한 schema/serialization Source of Truth**다.
- Draft의 예시와 이 페이지가 충돌하면 이 페이지를 따른다.
- ADR은 결정 이유를 설명하며 schema 자체의 Source of Truth는 아니다.
- backward-compatible 문구 명확화는 문서 수정으로 처리할 수 있다.
- 필드 의미 변경, 필수/선택 변경, enum의 호환 불가 변경, serialization 변경은 `contract_version` 증가가 필요하다.
- 호환 불가 변경 시 변경 ADR 또는 기존 ADR supersede를 함께 기록한다.

---

# 10. 최종 한 문장 정의

> `search`는 public capability invocation마다 불변 `AnalysisRun`을 생성하고 Recording Timeline 기준으로 순위화된 `CandidateEvent` span을 보장하며, 상세 usage는 `UsageRecord`로 연결하고 cost/token/latency는 immutable `usage_summary`로 함께 보존하여 `case`가 사용자 후보 선택에, `eval`이 Recall·span·비용 평가에 소비하도록 한다.
>
