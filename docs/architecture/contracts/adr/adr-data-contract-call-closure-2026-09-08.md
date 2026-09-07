# ADR — 데이터 계약 감사 접합부 종결 후속 (2026-09-08)

**Status:** Accepted — 아래 §4에 `ACCEPTED`로 표기한 결정에 한정. `CALL_REQUIRED`·`PROPOSED`·`PENDING`·`OUT_OF_SCOPE` 항목의 수락을 뜻하지 않는다
**Date:** 2026-09-08 (계약 반영일). Owner 결정 완료일은 §4 각 절에 있다
**Decider:** 각 결정 단위의 Decider는 §3 표에 있다. 이 문서의 작성·계약 반영은 PM(김준영)이 했고, PM은 어느 결정도 Owner를 대신해 만들지 않았다
**선행 문서:** `adr-data-contract-call-closure-2026-09-07.md`(2026-09-07 종결 회차의 결정 원장) → **이 문서가 2026-09-08 이후의 현재 결정 원장이다.** 선행 문서 본문은 고치지 않았고 §3·§9 상태표의 해당 행만 이 문서를 가리키도록 갱신했다(선행 문서 §11의 규칙)
**감사 원문:** `../../../management/contract-consistency-audit-2026-09-06.md` — 본문을 수정하지 않는다. 지적 ID(B01~B12 · W01~W07 · N01~N03)는 그 문서 §2를 따른다

> **이 문서를 읽는 법.** 선행 문서가 `CALL_REQUIRED`로 남긴 결정 회차 4건(CALL-12 · CALL-13 · CALL-14 · CALL-15)에 Owner 결정이 들어왔다. 회차 원문은 PM 내부 기록이며 저장소에 없다. **이 문서는 그 원문을 열지 않아도 계약을 수정·구현할 수 있도록 결정 내용·근거·기각안을 자기완결적으로 적은 공개 문서**이고, 이번 계약 반영의 유일한 근거다. CALL 번호는 결정 이력의 보조 식별자일 뿐이며 결정 내용은 모두 이 문서 본문에 있다. 계약 본문이 이 문서와 다르면 계약 본문이 규칙을 소유하고 이 문서는 근거·상태만 소유한다(`README.md`).
>
> 같은 날 recording 자산 계약 2건(`contract-source-asset-media-stream.md` · `contract-analysis-source-derived.md`)이 **Draft**로 추가됐다. Consumer Review는 시작되지 않았다. 이 문서는 그 두 계약을 수락하지 않으며 상태와 검수 결과만 기록한다(§4.5). 짝 ADR은 `adr-source-asset-media-stream.md` · `adr-analysis-source-derived.md`(둘 다 `Proposed`).

---

## 1. 배경과 해결 대상

2026-09-07 종결 회차는 감사 BLOCK 8건 중 5건을 `CLOSED_VERIFIED`로 닫고, B06(`SpanResolution` 실패 직렬화)·B08(`AnalysisScope` relative range 직렬화)은 `CALL_REQUIRED`, B07(Asset Facts 필드)은 `PENDING_IMPLEMENTATION`으로 남겼다. 함께 두 건의 표기·경계 항목(재판독 발주 `kind` · `AnalysisRun.usage_refs` 지위)을 별도 회차로 넘겼다. 이 문서는 그 네 회차의 **최종 결론**을 공개 결정으로 옮기고, 계약 반영·검증 상태·남은 Pending을 하나의 표로 다시 닫는다.

문서 권위 순서는 바뀌지 않는다: `product-spec.md` → `module-architecture.md`(v4) → `core-user-flow.md` → `ownership.md` → 공개 ADR(이 문서) → Final Contract.

## 2. 결정 단위의 상태 어휘

| 상태 | 뜻 |
| --- | --- |
| `ACCEPTED` | Owner가 결정하고 필요한 Producer/Consumer가 확인했다. 계약 반영 대상 |
| `ACCEPTED_PENDING_IMPLEMENTATION` | 결정은 끝났으나 그 결정을 담을 문서·필드가 아직 없다. 임의로 만들지 않는다 |
| `PROPOSED` | Draft 계약이 존재하지만 Consumer Review가 끝나지 않았다. 수락·수락일을 만들지 않는다 |
| `CALL_REQUIRED` | 기존 계약·ADR만으로 정할 수 없어 새 Owner 결정 회차가 필요하다. 계약에 `CALL_REQUIRED`로만 표기한다 |
| `PENDING_OWNER` | Owner 결정이 아직 없다 |
| `OUT_OF_SCOPE_FOLLOWUP` | 회차에서 「별건」으로 명시된 항목. 해당 감사 ID의 종결 근거에 섞지 않는다 |

회차 원문에서 앞부분의 중간 의견과 뒤의 최종 절이 다르면 **최종 절만** 결정으로 취급했다. 참여자의 「권고」·「~하겠다」는 구현 의향이며 계약 규칙으로 옮기지 않았다. Decider 소유 범위 밖의 문장은 결정으로 옮기지 않았다(§4.2 말미).

## 3. 결정 요약표

| 회차 | 결정 상태 | 공개 결정 요약 | Decider / 확인자 | 영향 계약 | 검증 조건 |
| --- | --- | --- | --- | --- | --- |
| CALL-12 | `ACCEPTED` | 재판독(`EvidenceNeeds.kind=PLATE_REREAD`) 발주는 **`JobRecord.kind=PLATE_READ` + `force_rerun=true`(무조건)**. 별도 kind를 만들지 않는다. 새 `job_id` → 새 execution → 새 `ReadoutRun` 1건 추가, 원판독 `ReadoutRun`은 갱신하지 않는다. abstain은 계속 `outcome=SUCCEEDED` | Decider 유소연(`case`) · 확인 신유민(`readout`) · 김준영(`evidence`) | `JobRecord` A절 §7·§13 · `EvidenceNeeds` §11 문구 | §7-V8 fixture: 동일 fingerprint 재발주가 `force_rerun=true`·새 job_id·새 run, 원 run 불변 |
| CALL-13 | `ACCEPTED` (표기 정합 · 버전 유지) | `AnalysisRun.usage_refs[]`는 **조회 편의용 파생값**. Run↔Usage 연결과 비용 집계의 authoritative source는 `UsageRecord.run_ref`. `usage_summary`는 원장 기준 실행 시점 immutable snapshot. eval은 search·readout에서 같은 규칙 | Decider 서어진(`search`) · 확인 김대원(`eval`) · 김준영(`common/runtime`) | `AnalysisRun+CandidateEvent` §3·§6-1·§7·§8 · `UsageRecord` §8·§10 | §7-V9 fixture: 파생값이 어긋난 row에서 원장 기준 집계가 유일 |
| CALL-14 | `ACCEPTED` (`source_ref` 규칙 1건 `CALL_REQUIRED`) | `MissingRange.reason`에 **`OUT_OF_TIMELINE_RANGE`** 추가(`TIMELINE_GAP`과 구분). `SpanResolution`에 **`failure: {kind, code} | null`** 키 항상 존재. `COMPLETE`/`PARTIAL`→`null`, `FAILED`→non-null. 위치 특정 가능 FAILED는 `missing_ranges`가 요청 범위 전체 설명 + `failure`; 위치 특정 불가 FAILED는 `missing_ranges=[]` + `failure`(완전성 불변조건의 명시적 예외). `kind` 값 집합은 recording 소유, 타 모듈 taxonomy와 비교 금지 | Decider 정철원(`recording`) · 확인 김준영(`evidence`) · 서어진(`search`) | recording 계약 헤더·§8.1·§9·§10·§23·§24 · `span-resolution/v1.1` | §7-V10 fixture: 범위초과 PARTIAL·위치특정 FAILED·위치불특정 FAILED·`failure` 상태별 필수성 |
| CALL-15 | `ACCEPTED` | `AnalysisScope.time_ranges[]` 원소에 **`kind: ABSOLUTE | TIMELINE_RELATIVE`**. relative는 `start_ms`·`end_ms`·`timeline_ref{timeline_id, revision}` 필수. 한 scope 안 혼합 금지, relative가 여럿이면 같은 `timeline_id+revision`. 하위 호환: `kind` 부재 + `start`/`end` 존재 = `ABSOLUTE`. `contract_version` **`1.1.0`** | Decider 유소연(`case`) · 확인 서어진(`search`) · 김대원(`eval`) · 정철원(`recording`) | `AnalysisScope` 헤더·§5·§6·§7·§8·§9·§10·§12 · 짝 ADR 고지 | §7-V11 fixture: relative 정상·legacy absolute·혼합 위반·`timeline_ref` 누락 위반·revision 불일치 위반 |
| 자산 계약 2건 | `PROPOSED` | Draft v0.2 두 건이 저장소에 추가됐다. B07 최소 자산 사실을 필드 수준에서 모두 담는다. Consumer Review 미시작 | Owner 정철원 · Consumer 서어진·신유민·유소연·김준영 | 신규 계약 2건 · 짝 ADR 2건(Proposed) | 계약 예시 JSON 파싱만(§7-V0). 의미 fixture는 Review 후 |
| CALL-16 | `CALL_REQUIRED` | `MissingRange.source_ref`의 타입과 `OUT_OF_TIMELINE_RANGE`·`TIMELINE_GAP`에서의 nullable/부재 규칙 | 정철원 · 확인 김준영·서어진 | recording §10 | 확정 후 V10 fixture에 `source_ref` 반영 |
| CALL-17 | `CALL_REQUIRED` | 자산 계층 `ContractRef.kind` 값 표기(대문자 `SOURCE_ASSET` vs 기존 소문자 `source_asset`)와 `AssetFacts.asset_kind`의 문자열 동일성 | 정철원 · 확인 김준영·서어진·유소연 | 자산 계약 2건 §2·§6 · `Observation` §12 예시 | — |
| CALL-18 | `CALL_REQUIRED` | `AssetSpan` identity 부재와 `PlateReadout.input_ref.span_ref`의 참조 대상 | 정철원 · 확인 신유민·유소연·김준영 | recording §6 · 파생 계약 §6 · plate/overlay §4 · `EvidenceNeeds` §8.3 | — |

## 4. 결정 상세

### 4.1 재판독 발주의 `JobRecord.kind`와 캐시 identity (Decider 유소연 · 확인 신유민 · 김준영 · 결정 완료 2026-09-07)

**해결할 문제.** `PlateReadout.abstained=true`인 판독도 `ReadoutRun.outcome=SUCCEEDED`다(eval의 Abstention Recall·Wrong Accept Rate 산식이 `abstained + SUCCEEDED` 조합에 의존). 그런데 `JobRecord` 캐시 재사용 조건은 「동일 `(case_id, kind, input_fingerprint)` + `force_rerun=false` + 기존 `SUCCEEDED`」이고, `PLATE_REREAD` Need는 사건 interval ref를 필수로 주므로 재판독 입력은 원판독과 같은 것이 기본값이다. 같은 `kind`로 재발주하면 cache hit가 나서 재판독이 실행되지 않는다.

**채택한 규칙.**

1. 재판독 발주는 **`JobRecord.kind=PLATE_READ`를 유지하고 `force_rerun=true`를 조건 없이 붙인다.** `PLATE_REREAD`라는 kind를 만들지 않는다(그 이름은 `EvidenceNeeds.kind` 값 공간이다). `EvidenceNeeds.kind=PLATE_REREAD`는 「왜 다시 도는가」, `JobRecord.kind=PLATE_READ`는 「무엇을 하는가」다.
2. `force_rerun=true`는 **무조건**이다. fingerprint 구성에 case/kind가 포함된다고 가정할 수 없고(A절 §7), 입력이 달라져 fingerprint가 달라질 것이라는 가정도 근거가 없다. 조건부로 두면 재판독이 조용히 누락된다.
3. `JobRecord.kind` ↔ `ReadoutRun.operation` 1:1 대응은 그대로 유지되고 `operation` 값 목록은 늘지 않는다.
4. **abstain은 계속 `outcome=SUCCEEDED`다.** cache hit 문제는 `outcome`을 바꿔서가 아니라 `force_rerun`으로 푼다.
5. 사용자 재판독(의미적 재요청)과 인프라 재시도(`STALE`)는 다른 층위다 — 재판독은 **새 `JobRecord`(새 `job_id`) + `force_rerun=true`**, 인프라 재시도는 **같은 `job_id` · 새 `execution_id` · `attempt` 증가**(`contract-job-execution.md` §9-2).
6. 1:1 불변조건과 충돌하지 않는다: 새 `job_id` → 새 execution → `produced`에 `readout_run` 정확히 1건. **원판독 `ReadoutRun`은 그대로 남고 재판독 `ReadoutRun`이 1건 추가된다. 기존 `ReadoutRun`을 갱신하지 않는다**(기존 규칙의 재기술).
7. 원판독/재판독 결과 중 「현재 값」을 고르는 책임은 `readout`에 없다. **B03에서 이미 `case`/`CaseView` projection 소관으로 확정된 사항**이며 이 결정으로 새로 열리는 숙제는 없다.

**Producer/Consumer 책임.** `evidence`는 `PLATE_REREAD` Need를 만든다. `case`는 그 Need를 `kind=PLATE_READ + force_rerun=true` 발주로 변환한다. `readout`은 `read_plate` 호출 1회 = `ReadoutRun` 1건을 만든다.

**기각한 대안.** 별도 kind(이름은 `PLATE_REREAD`가 아닌 것) — `JobRecord`만 보고 재판독임을 알 수 있지만 `kind`↔`operation` 1:1이 깨져 매핑 표와 그 소유자가 필요해진다. `operation`은 public capability와 1:1(`enum(2)`)이라 readout이 값을 늘리지 않으므로 대응 값 없는 `kind`는 A절 §7 「한쪽에만 값을 추가하지 않는다」를 어긴다. 조건부 `force_rerun` — 위 2번 근거로 기각.

**계약 영향.** `contract-job-record-case-view.md` A절 §7(재판독 발주 규칙 등재)·§13(미결 종결) · `contract-evidence-record-needs.md` §11 말미 문구(「`PLATE_READ` 계열 JobIntent」→ 발주 규칙 포인터). 버전 유지(`job-record/v1` — 값 목록·스키마 변경 없음, 규칙 명시만).

### 4.2 `AnalysisRun.usage_refs[]`의 지위 (Decider 서어진 · 확인 김대원 · 김준영 · 결정 완료 2026-09-08)

**해결할 문제.** B05는 `UsageRecord.run_ref`를 authoritative로, `ReadoutRun.usage_refs`를 「조회 편의용 파생값」으로 확정했다. 같은 성격의 `AnalysisRun.usage_refs[]`에는 지위 표기가 없어, eval이 search 산출물과 readout 산출물에서 서로 다른 규칙으로 usage를 모으게 된다 — 모듈마다 분기가 생기고 그 분기가 「어느 쪽을 믿었나」의 기록이 되어 비용 지표에 섞인다.

**채택한 규칙.**

1. `AnalysisRun.usage_refs[]`는 **조회 편의용 파생값(역방향 참조)**이며 authoritative하지 않다. 필드는 삭제하지 않고 조회·탐색·audit 진입 편의를 위해 유지한다.
2. Run↔Usage 연결과 비용·사용량 집계의 authoritative source는 **`UsageRecord.run_ref`** 하나다. `UsageRecord.run_ref = {kind:"analysis_run", ref:<run_id>}`인 원장 행이 「해당 `AnalysisRun`에 속한 usage」다. 두 값이 어긋나면 `UsageRecord.run_ref` 기준으로 집계한다.
3. `ReadoutRun.usage_refs`와 `AnalysisRun.usage_refs[]`는 같은 지위다. eval은 search·readout에서 동일한 규칙(원장 한 번 스캔)을 쓰고 모듈에 따라 다른 참조 방향을 신뢰하지 않는다.
4. `AnalysisRun.usage_summary`는 **Run 종료 시 원장(`run_ref`가 해당 Run을 가리키는 행)을 기준으로 집계한 immutable snapshot**이다. 실행 이후 가격표가 바뀌어도 다시 계산해 덮어쓰지 않는다. 과거 비용을 현재 가격으로 재계산해야 하면 `UsageRecord.pricing_context`로 별도 평가 결과를 만든다. `usage_summary`는 상세 원장을 대체하지 않고, `usage_refs[]`가 잘못됐다는 이유만으로 집계 기준이 바뀌지 않는다.
5. **버전을 올리지 않는다.** 필드 추가·의미 변경이 아니라 이미 정해진 원장 authority를 `AnalysisRun` 계약에도 같은 문장으로 표기하는 정합성 보완이다.

**Producer/Consumer 책임.** `search`는 `usage_refs[]`를 채우되 집계 기준으로 제시하지 않는다. `eval`은 재평가·Efficiency에 `usage_summary`를, 상세 audit·비용 분모 집계에 원장 스캔(`run_ref`)을 쓰고 `usage_refs[]`는 audit 진입점으로만 쓴다. `common/runtime`은 원장의 `run_ref`를 채울 책임을 유지한다(B05 D4).

**기각한 대안.** (b) 지위 미표기 현행 유지 — eval이 모듈별로 다른 규칙을 갖게 된다. (c) `AnalysisRun.usage_refs`를 authoritative로 선언 — `ReadoutRun`과 반대 방향이 되어 「어느 참조를 신뢰했는가에 따라 숫자가 달라지는」 상태(B05에서 김대원이 반대한 상태)가 된다.

**Decider 소유 범위 밖이라 옮기지 않은 문장.** 회차 결론에는 「`run_ref=null`은 Run 개념이 없거나 **아직 정식 연결 방식이 없는 호출**에서만 허용한다」는 문장이 있다. `UsageRecord.run_ref`의 `null` 의미는 `UsageRecord` Owner(김준영)가 B05 D4에서 「**Run 개념이 없는 직접 호출만**」으로 확정한 것이고(`contract-usage-record.md` §8-10 「Run에 속한 호출을 `run_ref=null`로 기록하지 않는다」), search Owner의 결정 범위가 아니다. 「아직 정식 연결 방식이 없는 호출」을 허용하면 §8-10과 충돌한다. **이 문장은 계약에 옮기지 않았고 B05 D4 의미를 유지한다.** 그런 호출이 실제로 존재한다면 `UsageRecord` Owner가 별도로 판단할 항목이다(§8.2).

**계약 영향.** `contract-analysis-run-candidate-event.md` 헤더 고지·§3 `usage_refs` 행·§3-4 Snapshot 규칙·§6-1-11·§7 eval 규칙·§8 접합부 표 · `contract-usage-record.md` §8 불변조건 12(신설)·§10 종결 문구. 두 계약 모두 버전 유지.

### 4.3 `SpanResolution` 실패 원인의 직렬화 (Decider 정철원 · 확인 김준영 · 서어진 · 회차 문서에 결정 완료일 미기재, 반영 2026-09-08)

**해결할 문제.** B06 종결로 「`spans + missing_ranges`가 `requested_range`를 빠짐없이 설명」「`FAILED`는 원인을 machine-readable하게 표면화」는 정해졌으나, ① 요청이 timeline 끝을 넘어간 구간에 쓸 `MissingRange.reason` 값이 없었고(기존 `TIMELINE_GAP`/`SOURCE_UNAVAILABLE`/`STREAM_UNAVAILABLE`) ② top-level failure reason의 필드명·모양·필수 조건이 없었다. fixture의 FAILED·범위초과 케이스가 이것을 기다렸다.

**채택한 규칙.**

1. **`MissingRange.reason`에 `OUT_OF_TIMELINE_RANGE`를 추가한다.** 최소 값 공간은 `TIMELINE_GAP` · `SOURCE_UNAVAILABLE` · `STREAM_UNAVAILABLE` · `OUT_OF_TIMELINE_RANGE`.
   - `TIMELINE_GAP` = `RecordingTimeline` 내부에서 존재해야 할 구간에 생긴 결손.
   - `OUT_OF_TIMELINE_RANGE` = 정상적인 요청 구간의 일부 또는 전체가 해당 Timeline의 경계 밖.
   - 둘은 recording이 관찰한 사실도, Consumer의 대응 의미도 다르므로 합치지 않는다.
2. **top-level 필드 `failure: {kind: string, code: string} | null`.** `failure != null`이면 `kind`·`code` 둘 다 필수. `kind`는 recording이 소유하는 상위 실패 분류, `code`는 stable machine-readable 실패 코드.
   - `ReadoutRun.failure`와 **구조만** 맞춘다. recording과 readout이 같은 taxonomy나 같은 코드 값을 공유한다는 뜻이 아니다. 값 집합은 recording 소유 문서 한 곳에서 관리하고 evidence/search 계약에 복제하지 않는다. Consumer는 서로 다른 모듈의 `kind/code`를 공통 enum처럼 직접 비교하지 않는다.
3. **상태별 필수성 — 키는 항상 존재한다.**

   ```
   status = COMPLETE → failure = null
   status = PARTIAL  → failure = null   (원인은 각 missing_ranges[].reason이 설명한다)
   status = FAILED   → failure != null
   ```

   `PARTIAL`은 usable span이 존재하므로 전체 실패를 뜻하는 top-level `failure`를 두지 않는다. `FAILED`에서는 `spans=[]`만 보고 Consumer가 원인을 추측하게 하지 않는다.
4. **`FAILED`에서 `missing_ranges`와 `failure`의 책임 분리.** `missing_ranges` = 요청 범위 중 어디를 해소하지 못했는가. `failure` = `SpanResolution` 전체가 왜 `FAILED`가 되었는가.
   - 위치를 특정할 수 있는 전체 실패: `spans=[]` · `missing_ranges`가 `requested_range` 전체를 설명 · `failure != null`.
   - 위치를 신뢰성 있게 특정할 수 없는 전체 실패(Timeline 자체를 읽거나 해석하지 못함): `spans=[]` · **`missing_ranges=[]`** · `failure != null`. 존재 여부를 확인할 수 없는 구간을 임의의 `MissingRange`로 만들지 않는다.
   - 따라서 완전성 불변조건(`spans ∪ missing_ranges == requested_range`)은 **구간 위치를 판정할 수 있는 `SpanResolution`에 적용**하고, 위치를 특정할 수 없는 top-level 실패에는 명시적 예외를 둔다. 이 경우에도 설명되지 않은 실패는 없다 — `failure`가 원인을 제공한다.
5. **입력 검증 실패와의 경계는 그대로다.** `start >= end` · 음수 범위 · 존재하지 않거나 잘못된 형식의 timeline reference는 `SpanResolution.FAILED`를 만들지 않는다(호출 입력 검증 실패). 유효한 Timeline reference를 받았지만 저장소·인덱스·해석 결과를 사용할 수 없어 resolution을 만들 수 없는 경우가 `status=FAILED + failure`다.
6. recording은 실패 사실과 원인만 제공한다. `failure.kind`나 `missing_ranges[].reason`이 신고 규칙상 `BLOCK`/`UNKNOWN` 중 무엇인지의 판정 매핑은 **evidence policy가 소유**하며 recording 계약에 고정하지 않는다. `evidence`는 `status → failure → missing_ranges` 순서로 소비할 계획이고, `search`는 `PARTIAL`의 `missing_ranges`와 `FAILED`의 `failure`를 구분해 소비할 계획이다(둘 다 Consumer 구현 의향이며 계약 규칙이 아니다).

**기각한 대안.** 범위 밖 구간에 `TIMELINE_GAP` 재사용 — 값이 늘지 않지만 「구멍」과 「경계 밖」이 섞여 evidence·search가 다르게 대응해야 하는 사실을 구분할 수 없다. `failure_reason: string` 단일 문자열 — 짧지만 `ReadoutRun.failure`·`AnalysisRun.issues[]`와 어긋나 세 계약을 같은 코드로 다룰 수 없다. `status != FAILED`일 때 키 부재 — 「없음」과 「누락」을 구분할 수 없어 키 항상 존재로 확정.

**PM bookkeeping(Owner 이견 시 조정).** `failure` 키 추가와 enum 값 추가는 스키마 변경이므로 선행 문서 §6의 규칙(스키마가 바뀐 계약만 minor를 올린다)에 따라 `contract_version`을 **`span-resolution/v1` → `span-resolution/v1.1`**로 올렸다. Owner는 버전을 언급하지 않았다. `span-resolution/v1` payload(`failure` 키 없음)를 v1.1 규칙으로 재해석하는 규칙은 정하지 않았다 — 구현 코드가 없어 마이그레이션 대상도 없다. 헤더의 `recording-timeline/v1` · `asset-span/v1` · `time-source-candidate/v1`은 바뀌지 않았다.

**결정되지 않아 반영하지 않은 것 → `CALL_REQUIRED`(CALL-16).** `MissingRange.source_ref`의 타입(평문 opaque string인가 `ContractRef`인가)과, `OUT_OF_TIMELINE_RANGE`·`TIMELINE_GAP`처럼 특정 Source가 원인이 아닌 reason에서 `source_ref`가 `null`인가 부재인가. 회차에서 다루지 않았고 PM이 정하지 않았다. fixture의 `OUT_OF_TIMELINE_RANGE` 항목은 `source_ref` 키를 넣지 않았고 검사기는 이 키를 읽지 않는다. `failure.kind` 값 집합을 담을 recording 소유 문서는 아직 없다(`ACCEPTED_PENDING_IMPLEMENTATION`, 정철원) — fixture는 값 집합을 검사하지 않고 모양(`kind`·`code` 비어 있지 않은 문자열)만 검사하며, 예시 값은 `EXAMPLE_*`로 표기해 실제 값을 만들지 않았다.

**계약 영향.** `contract-recording-timeline-asset-span.md` 헤더·§8.1(스키마에 `failure`·예시 `contract_version`)·§9(상태별 규칙·FAILED 예시 2건)·§10(reason 표·`source_ref` `CALL_REQUIRED`)·§23 SpanResolution 6·9·10·11·§24 통합 예시(`failure: null`).

### 4.4 `AnalysisScope` timeline-relative range의 직렬화 (Decider 유소연 · 확인 서어진 · 김대원 · 정철원 · 결정 완료 2026-09-07)

**해결할 문제.** B08 방향(relative-only `RecordingTimeline`은 정상 usable · 가짜 absolute datetime 생성 금지 · anchor 부재만으로 Search 차단 금지 → `AnalysisScope`가 relative range를 명시적으로 구분해 수용)은 닫혔지만 `AnalysisScope` §5는 locked 스키마라 모양이 없었다. relative-only 영상은 제품이 지원해야 하는 정상 입력인데 `AnalysisScope`를 만들 수 없는 상태였다.

**채택한 규칙.**

1. **원소 discriminator.** `time_ranges[]`의 각 원소에 `kind: ABSOLUTE | TIMELINE_RELATIVE`를 둔다. 별도 배열(`relative_ranges[]`)은 두지 않는다. 기존 「`time_ranges`는 최소 1개」 불변조건을 그대로 재사용하고 search·eval은 배열 하나만 순회한다. enum 이름은 **`TIMELINE_RELATIVE`**로 확정한다(회차 중 `RELATIVE` 표기는 동일 의미로 확인됐고 계약에는 `TIMELINE_RELATIVE`만 쓴다).
2. **relative 좌표 = `start_ms` / `end_ms` + range마다 `timeline_ref: {timeline_id, revision}`.** `CandidateEvent.span`과 같은 ms 좌표계라 search 입력과 출력의 단위가 같다 — 초/ms 변환 지점이 둘이면 1000배 오차가 조용히 들어간다(eval이 실측한 사고: 690000ms→0.69초로 IoU 매칭 전멸, recall 0). `timeline_ref.revision`은 **필수**다 — Timeline rebase 이후 좌표·정답지가 무효화됐는지 감지하는 유일한 수단이고 `CandidateEvent.span.timeline_revision`(B09)과 같은 provenance 형태다. `timeline_id`는 recording 공개 identity이므로 「search는 case 내부 참조·파일/asset ref를 받지 않는다」(§10-1)를 넘지 않는다.
3. **한 scope 안에서 absolute와 relative를 섞지 않는다.** scope는 하나의 시간 기준만 쓴다. `TIMELINE_RELATIVE` range가 여럿이면 모두 같은 `timeline_id`+`revision`을 참조한다.
4. **`contract_version` `1.0.0` → `1.1.0`.** 필드 추가이며 기존 absolute 입력은 수정 없이 유효하다(minor).
5. **하위 호환 규칙.** `kind` 필드가 없고 `start`/`end`가 존재하는 기존 형식은 `ABSOLUTE`로 해석한다. 이 규칙이 없으면 4번(「기존 입력 그대로 유효」)이 실제로 지켜지지 않는다. `TIMELINE_RELATIVE` range는 `kind`를 반드시 명시한다.
6. **§10-2 불변조건 재작성.** `kind=ABSOLUTE`: timezone 포함 ISO8601, `start <= end`(기존 문구). `kind=TIMELINE_RELATIVE`: `start_ms <= end_ms`이고 `timeline_ref`(`timeline_id`+`revision`)가 필수로 존재한다.
7. recording 불변조건 재확인(정철원): `USABLE_RELATIVE_ONLY`는 정상 usable · absolute anchor 부재만으로 Search 차단 금지 · 존재하지 않는 absolute datetime 생성 금지 · relative 좌표는 실제 `RecordingTimeline`의 `timeline_id + revision`을 참조 · rebase 이후에도 기존 Scope와 결과가 사용한 revision provenance 보존. recording의 `SpanResolution`은 초 단위를 유지하며 단위 변환은 recording 공개 경계에서 명시적으로, 동일 revision 기준으로 한다.

**Producer/Consumer 책임.** `case`가 `kind`를 정해 scope를 만든다. `search`는 두 kind를 모두 받고 legacy 형식을 `ABSOLUTE`로 해석한다(Consumer 지원 확인). `eval`은 아직 `AnalysisScope` fixture를 생산하지 않는다 — manifest는 clip·sequence 단위라 이번 결정으로 마이그레이션할 기존 fixture는 없고, 앞으로 만들 형식에 대한 확인이다.

**기각한 대안.** 별도 배열 `relative_ranges[]` — 기존 ISO8601 스키마를 손대지 않지만 「둘 중 하나는 비어 있지 않아야」라는 새 불변조건과 세 상태(둘 다 빔/하나만/둘 다 찼음) 검사가 생긴다. `start_sec` — `SpanResolution`과는 같지만 `CandidateEvent.span`과 다르다. 좌표계 혼합 허용 — search가 한 실행에서 두 좌표계를 처리해야 하고 eval 지표(평균 구간오차)가 서로 다른 단위의 구간을 한 분모에 넣게 된다. scope 상위에 `timeline_ref` 한 번 — range마다 두는 쪽이 원소 단위 검증과 독립 해석에 유리(정철원).

**PM 해석 주의(결정 아님).** ① `kind=ABSOLUTE`인 새 scope에 `kind`를 **명시할 것을 요구**하는지는 회차에서 다루지 않았다. 계약 예시는 명시하고, 부재 시 해석 규칙은 하위 호환용으로 적었다. ② relative range의 `start_ms >= 0`은 회차에서 다루지 않았다(`CandidateEvent.span`은 `>= 0`). 계약에 추가하지 않았다. 둘 다 Owner 이견 시 이 절을 고친다.

**범위 밖으로 명시된 것(`OUT_OF_SCOPE_FOLLOWUP`).** `timeline_id`+ms offset ↔ eval 정답지 `clip_id` 대응은 이번 결정으로 닫히지 않는다. 이번 결정은 그 대응을 만들 전제(timeline identity가 scope에 실려 옴)만 갖춘다. eval Owner의 별건 항목으로 유지한다.

**계약 영향.** `contract-analysis-scope.md` 헤더(Status 고지·버전 `1.1.0`)·§5 스키마·§6 필드표·§7 enum·하위 호환·§8 예시(relative 1건 추가)·§9(relative-only 경로 종결)·§10-2·§10-7·§12 B08 절 종결 · 짝 ADR `adr-analysis-scope.md`에 Status 아래 한 줄 고지(본문 불변).

### 4.5 recording 자산 계약 2건 — Draft 검수 (Owner 정철원 · 상태 `PROPOSED`)

두 계약은 B07의 `ACCEPTED_PENDING_IMPLEMENTATION`을 담을 문서로 추가됐다. **Consumer Review는 시작되지 않았다.** PM 검수 결과만 기록한다. 어느 항목도 승인이 아니다.

**형식.** H1·헤더 3항목(Status·Architecture Contract·Contract Version) 존재 · Status `Draft — Consumer Review 대기` · Producer/Consumer 명시 · JSON 예시 9블록(5+4) 파싱 PASS · 짝 ADR은 없었으므로 이번에 `Proposed`로 신설.

**B07 결정 대비.** 최소 자산 사실(`asset_ref` · kind/derived role · byte size · 판정 시점 존재·가용 · lineage · 조건부 duration+timeline_range)이 `AssetFacts` §6에 필드 수준으로 모두 있다. `FrameRef` 보장 6건이 §5.2에 동일하게 있다. 전달 경계(recording lookup → case 수집 → evidence 주입, evidence·web 직접 호출 금지)와 `thumb_ref=FrameRef`가 일치한다. `stream_selector`·thumbnail 전달 방식은 Pending으로 유지됐다(B07·W07 결정과 일치).

**검수에서 확인된 항목(Consumer Review·Owner 정리 대상, 계약에 반영하지 않음).**

| 구분 | 항목 |
| --- | --- |
| `CALL_REQUIRED` | `ContractRef.kind` 표기 — Draft는 `SOURCE_ASSET`/`MEDIA_STREAM`(대문자), Accepted `Observation` 예시는 `source_asset`/`media_stream`(소문자), 확정 run ref는 `analysis_run`(소문자) → CALL-17 |
| `CALL_REQUIRED` | `AssetSpan`에 identity가 없는데 Accepted `PlateReadout.input_ref.span_ref`와 `EvidenceNeeds` §8.3이 span ref를 전제 → CALL-18 |
| Owner 정리(단일 Owner) | `IncidentClip.source_provenance.asset_spans[]`가 「canonical AssetSpan 형태」라고 하면서 예시는 평탄화·ms 혼용(Accepted `AssetSpan`은 `timeline_range`/`source_range` 초 단위) · `requested_range`가 `SpanResolution`과 같은 이름·다른 단위 · `SourceAsset.byte_size` 필수 vs `AssetFacts.byte_size` nullable · `duration_sec`의 부재/null 혼용 · 헤더 `…/v0.2`와 본문 `"0.2.0"` 형식 · `RemoteCopy`·`IncidentClip` 필드표 없음 |
| Consumer 확인 필요 | `AssetFacts.timeline_range`에 `timeline_ref{timeline_id, revision}`가 없어 어느 revision 좌표인지 모름(B09·§4.4와의 정합) · span+시각으로 `FrameRef`를 **발급**받는 capability가 계약에 없음(search `thumbnail_ref`·readout `best_frame` 생산 경로) · `availability=UNKNOWN`과 `UNAVAILABLE`의 구분 기준 · `lookup_asset_facts` 모르는 ref 응답 · `read_frame`/`prepare_analysis_source` 실패 표현 · `profile_ref`(profile 태그 소유 3자 항목) |

**계약 영향.** 없음(Draft 본문을 PM이 고치지 않았다). 포인터 문서의 「작성 대기」 표기를 「Draft 존재 · Consumer Review 대기」로 갱신했다(§6).

### 4.6 새 결정 회차가 필요한 것 (`CALL_REQUIRED` · 내용은 Owner 결정 후 변경 ADR에)

| 회차 | 주제 | Decider | 확인 | 막는 것 |
| --- | --- | --- | --- | --- |
| CALL-16 | `MissingRange.source_ref` 타입 · reason별 nullable/부재 규칙 | 정철원 | 김준영 · 서어진 | `OUT_OF_TIMELINE_RANGE` fixture 완성 · evidence/search의 `missing_ranges` 소비 구현 |
| CALL-17 | 자산 계층 `ContractRef.kind` 값 표기 · `asset_kind` 문자열 동일성 | 정철원 | 김준영 · 서어진 · 유소연 | Consumer의 `asset_ref.kind` 문자열 비교 구현 · 자산 계약 2건 Accepted 전환 |
| CALL-18 | `AssetSpan` identity · `PlateReadout.input_ref.span_ref` 참조 대상 | 정철원 | 신유민 · 유소연 · 김준영 | readout 입력 조립(`needs_map`) · `IncidentClip` provenance 모양 · 자산 계약 2건 Accepted 전환 |

회차 문서는 PM 내부 기록이다. 답이 오면 이 문서를 고치지 않고 변경 ADR을 쓴 뒤 §3·§9 표의 해당 행만 갱신한다.

## 5. 임의로 만들지 않은 것

`MissingRange.source_ref` 규칙 · recording `failure.kind` 값 집합 · 자산 ref `kind` 표기 통일 · `AssetSpan` identity · Draft 계약 2건의 Pending(enum·nullability·`stream_selector`·thumbnail 전달·profile·retention·transform) · relative range `start_ms >= 0` · `kind=ABSOLUTE` 명시 의무 · `span-resolution/v1` payload 재해석 규칙 · `run_ref=null` 확장 · `clip_id` 대응 · `kind → BLOCK/UNKNOWN` 판정 매핑 · 수락일 · 구현 순서. 이들은 §4.6·§8의 항목으로 남긴다.

## 6. 공개 계약 영향과 버전 표기

**버전 표기 규칙(PM bookkeeping, Owner 이견 시 조정 — 선행 문서 §6과 동일).** 스키마(필드·타입·필수성·enum 값)가 바뀐 계약만 minor를 올린다. 불변조건·예시·포인터·Pending 문구만 바뀐 계약은 버전을 유지한다. major bump는 하지 않는다.

| 파일 | 바뀐 절 | 버전 | 하위 호환 |
| --- | --- | --- | --- |
| `contract-job-record-case-view.md` | 헤더 고지 · A§7 · A§13 | `job-record/v1` · `case-view/v1.2` 유지 | 규칙 명시만. 기존 payload 변화 없음 |
| `contract-evidence-record-needs.md` | §11 말미 문구 | 유지 | 문구 |
| `contract-analysis-run-candidate-event.md` | 헤더 고지 · §3 · §3-4 · §6-1 · §7 · §8 | `analysis-run-candidate-event/v1.1` 유지 | 표기 정합 |
| `contract-usage-record.md` | §8 불변조건 12 · §10 | `usage-record/v1.1` 유지 | 표기 정합 |
| `contract-recording-timeline-asset-span.md` | 헤더 · §8.1 · §9 · §10 · §23 · §24 | `span-resolution/v1 → v1.1` (다른 세 버전 유지) | `failure` 키 추가·enum 값 추가. v1 payload 재해석 규칙 없음(구현 없음) |
| `contract-analysis-scope.md` | 헤더 · §5 · §6 · §7 · §8 · §9 · §10 · §12 | `analysis-scope/1.0.0 → 1.1.0` | `kind` 부재 + `start`/`end` = `ABSOLUTE`. 기존 absolute 입력 수정 없이 유효 |
| 자산 계약 2건 | 변경 없음 | `…/v0.2` Draft 유지 | — |
| 짝 ADR | `adr-analysis-scope.md`(Status 아래 한 줄 고지) · `adr-recording-timeline-asset-span.md`(같은 고지) · `adr-source-asset-media-stream.md`·`adr-analysis-source-derived.md`(신설, Proposed) | — | — |
| 선행 ADR | `adr-data-contract-call-closure-2026-09-07.md` 헤더 고지 · §3·§8.1·§9 해당 행 상태만 갱신(본문 결정 불변) | — | — |
| 포인터 문서 | `../README.md`(contracts) · `../../../README.md`(docs) · `../../module-architecture.md` 개정 이력·§5-3 안내 · `../../../management/ownership.md` §7-④ 안내 · `../../mock-pack-v1-refs.md` · `../../../../scripts/README.md` | — | — |

## 7. 검증 조건과 결과

검사 코드는 `scripts/check_contract_fixtures.py`, 이번 회차 fixture는 `docs/architecture/contracts/fixtures/call-closure-2026-09-08/`에 있다(선행 회차 fixture는 `call-closure-2026-09-07/` 그대로). fixture는 이 문서에서 `ACCEPTED`인 모양만 쓴다. 결정되지 않은 값(`source_ref` 규칙 · recording `failure.kind` 값 · 자산 ref `kind` 표기)은 하드코딩하지 않았다.

| ID | 검증 조건 | 결과 (2026-09-08 실행) |
| --- | --- | --- |
| V0 | 수정한 계약 12건·Draft 2건의 모든 ```json 예시 + fixture 9건(선행 5 + 이번 4)이 파싱된다 | PASS — 23 검사 0 실패. 언어 표시 없는 펜스(recording §8.1·§9·§24)는 `{`로 시작할 때만 시도하고 실패를 세지 않는다 |
| V1~V5 | 선행 회차 의미 검사 그대로(B01·B02·B03·B05·B06 정상/PARTIAL·B09) | PASS — 선행 fixture 5건 변경 없음 |
| V6 | 수정·신설 문서 22건의 경로 표기(`../`·`adr/`·`docs/`·`scripts/`·계약/ADR 파일명)가 실제 파일을 가리킴 · 계약 본문에 옛 Pending 머리말 잔존 0 | PASS. 선행 회차의 「작성 대기 계약 참조」 NOTE 3건은 Draft가 존재하므로 사라졌다 |
| V8 | CALL-12: 재판독 fixture — 원판독(abstain·`SUCCEEDED`)과 동일 `(case_id, kind, input_fingerprint)` · `force_rerun=true` · 새 `job_id` · 새 execution(`attempt=1`) · 새 `ReadoutRun`(`operation=PLATE_READ`) · 원 run/결과 불변 · 인프라 재시도(같은 `job_id`, `attempt` 2, 새 execution)와 구분. 위반 fixture 3건(`force_rerun=false` 동일 tuple = cache hit · `kind=PLATE_REREAD` 미등재 · `job_id` 재사용)을 검사기가 검출. 계약 A절 §7 등재·§13 종결 표기 확인 | PASS — 5 검사 0 실패 |
| V9 | CALL-13: `usage_refs=[101,102]`인데 원장은 `{101,103}`이 이 Run 소속인 fixture. 원장 기준 소속·합계(0.30)가 기대값과 같고 파생 기준 합계(0.70)와 다르며 `usage_summary.total_cost`는 원장 기준과 정합. `run_ref=null`은 직접 호출 1건만. 두 계약 버전 유지(`v1.1`) 확인 | PASS — 2 검사 0 실패 |
| V10 | CALL-14(`span-resolution/v1.1`): 범위초과 `PARTIAL`(`OUT_OF_TIMELINE_RANGE`) · 위치특정 `FAILED` · 위치불특정 `FAILED`(`missing_ranges=[]`) · 전체 범위 밖 `FAILED` 정상 4건. 위반 6건(`PARTIAL`에 `failure` non-null · `FAILED`에 `failure=null` · `failure` 키 부재 · 위치특정 FAILED 미설명 구간 · enum 밖 reason · 빈 `code`) 검출. 계약 §8.1·§9(2건)·§24 예시 4건에 같은 검사 적용. `source_ref`는 읽지 않는다(`CALL_REQUIRED`) | PASS — 11 검사 0 실패 (+ V4 계약 예시 4건 PASS) |
| V11 | CALL-15(`analysis-scope/1.1.0`): relative 2-range · legacy absolute(`kind` 없음)→`ABSOLUTE` 해석 · 명시 `ABSOLUTE` · `start_ms == end_ms` 정상 4건. 위반 7건(혼합 · `timeline_ref` 누락 · `revision` 누락 · revision 불일치 · `start_ms > end_ms` · `kind` 없이 ms만 · relative-only timeline에 가짜 `ABSOLUTE`) 검출. 계약 §8 예시 2건(`ABSOLUTE`·`TIMELINE_RELATIVE`)이 `1.1.0`이고 규칙 위반 0 | PASS — 12 검사 0 실패 |
| V12 | 계약 16건 모두 짝 ADR 존재 · Draft 2건 헤더에 `Draft` · 신설 ADR 2건 Status가 `Proposed — Consumer Review pending` | PASS — 20 검사 0 실패 |
| V7 | `python scripts/check_boundaries.py` | PASS — exit 0. **NOTE 7건**(boundary: 모듈 코드 파일 0개). 선행 회차의 coverage NOTE 5건(`SourceAsset`·`MediaStream`·`RemoteCopy`·`IncidentClip`·`DerivedAsset` 전용 절 없음)과 adr-pair NOTE 2건은 Draft·짝 ADR이 생겨 사라졌다. 이 스크립트는 헤더·번호·enum 변형·짝 존재만 본다 |

### 실행 결과 (2026-09-08)

```text
python scripts/check_contract_fixtures.py
  == 문서 구조: PASS (58 검사, 0 실패)
  == JSON 파싱: PASS (23 검사, 0 실패)
  == 의미 fixture: PASS (54 검사, 0 실패)
python scripts/check_boundaries.py
  PASS — 경계·계약 정합성 위반 0건   NOTE 7 (boundary only)
```

**추가 구조 검사(일회성 스크립트, 저장소에 두지 않음).** 수정·신설 문서 25건(secret 검토 문서 포함)의 코드 펜스 균형 · 빈 `>` 인용 잔존 · ```json 파싱 — PASS. H1 개수: 신설 문서 전부 1개. **NOTE:** recording 계약·`AnalysisRun` 계약·`EvidenceRecord` 계약·recording 짝 ADR·`module-architecture.md`·`ownership.md`는 절 제목에 `# N.` 단일 `#`을 쓰는 기존 관례라 H1이 여러 개다 — 이번에 도입된 것이 아니고 고치지 않았다(역사적 본문·타 Owner 문서).

**검사 결과의 의미 분리.** 문서 구조·JSON·의미 fixture PASS는 계약 규칙을 코드로 옮겼을 때 서로 다른 구현이 나오지 않는다는 증거이며 제품 동작 증거가 아니다. **구현 통합 PASS — 확인 불가**(`src/daesingo/*`·`apps/web`·`eval/*`에 실행 코드 0개, `apps/prototype`은 계약을 소비하지 않는 UI 프로토타입). **실제 E2E PASS — 확인 불가**(`ownership.md` §7-④ 6기준 실행 기록 없음, Mock Pack fixture는 저장소에 없음). 검사기는 CI에 붙이지 않았다.

## 8. 범위 밖 · 후속 항목

### 8.1 새 결정 회차가 필요한 것

§4.6 표의 CALL-16 · CALL-17 · CALL-18.

### 8.2 결정은 끝났으나 담을 문서·필드가 없는 것 (`ACCEPTED_PENDING_IMPLEMENTATION`)

- recording `SpanResolution.failure.kind` 값 집합을 담을 recording 소유 문서 → 정철원
- `CaseView.candidates[]` stale-revision 표시 필드명 → 유소연(선행 문서 §8.2 유지)
- `TimeResolution` revision provenance 필드 → 김준영(유지)
- readout `failure-taxonomy.md`의 `OVERCONFIDENT` 분리 → 신유민(유지)
- `UsageRecord.run_ref=null`의 「아직 정식 연결 방식이 없는 호출」 존재 여부 판단 → 김준영(§4.2 말미). 현재 계약은 B05 D4 그대로

### 8.3 Consumer Review 대기 (`PROPOSED`)

- 자산 계약 2건 — search·readout·case·evidence 4 Consumer. Review 문서는 PM 내부 기록. 답변이 오면 Owner가 Draft를 고치고 PM이 짝 ADR에 Consumer Review 기록을 옮긴 뒤 상태를 바꾼다. CALL-17·CALL-18이 닫히기 전에는 Accepted로 전환하지 않는다.

### 8.4 별건으로 명시된 것 (`OUT_OF_SCOPE_FOLLOWUP`)

- `timeline_id`+ms offset ↔ eval 정답지 `clip_id` 대응 — eval(김대원) ↔ recording/case. §4.4
- `Abstention Recall`·Wrong Accept Rate 정답지(C tier) — eval(유지)
- `UsageRecord` §10 잔여(통화 · 가격표 · `purge_case`와 원장) — 각 Owner(유지)
- `ReadoutRun.outcome=PARTIAL` 판정 기준 — readout Technical Spec(유지)
- W04 잔여 `JobExecution` 소비자 확인 · domain `PARTIAL`↔runtime `status` 접합 — common/runtime ↔ case/search/eval(유지)
- Mock Pack 재작성 시 relative range·reread·failure fixture 반영 — case(유소연)
- `CorrectionRecord` Draft Consumer Review — case ↔ evidence(유지)
- profile 태그 체계 소유(recording·search·readout 3자) — 자산 계약 Consumer Review 답변에 따라 CALL 여부 재판정

## 9. 감사 폐쇄 매트릭스 (2026-09-08 현재)

최종 상태 어휘: `CLOSED_VERIFIED` · `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` · `PENDING_OWNER` · `CALL_REQUIRED` · `PENDING_IMPLEMENTATION` · `PENDING_CONSUMER_REVIEW` · `PENDING_VALIDATION` · `NOTE_ACCEPTED`. 결정이 끝났어도 계약 반영과 fixture 검증이 끝나지 않았으면 `CLOSED_VERIFIED`로 쓰지 않는다. 선행 문서에서 바뀌지 않은 행은 「(유지)」로 표시하고 근거는 선행 문서 §9다.

| 감사 ID | 원래 지적 | 공개 결정 근거 | 계약 반영 | 의미 검증 | 최종 상태 | 남은 Owner/작업 |
| --- | --- | --- | --- | --- | --- | --- |
| B01 | (유지) | 선행 §4.1 | 완료 | V1 PASS | `CLOSED_VERIFIED` | — |
| B02 | (유지) | 선행 §4.2 | 완료 | V2 PASS | `CLOSED_VERIFIED` | — |
| B03 | 결과 schema/JSON에 run 연결 없음 | 선행 §4.3 · **이 문서 §4.1(재판독 kind)** | 완료 | V3 PASS · **V8 PASS** | `CLOSED_VERIFIED` | 재판독 `kind` 별건도 종결 |
| B04 | (유지) | 후속 보정 ADR §2 | 완료 | V3 | `CLOSED_VERIFIED` | — |
| B05 | `UsageRecord.run_ref`가 `AnalysisRun` 전용 | 선행 §4.4 · **이 문서 §4.2(`AnalysisRun.usage_refs` 지위)** | 완료 | V3 PASS · **V9 PASS** | `CLOSED_VERIFIED` | `run_ref=null` 확장 문장은 채택 안 함(§8.2) |
| B06 | 미설명 10초 · 완전성·FAILED 원인 규칙 없음 | 선행 §4.5 · **이 문서 §4.3** | recording §8.1·§9·§10·§23·§24 · `span-resolution/v1.1` | V4 PASS · **V10 PASS** | **`CLOSED_VERIFIED` (단, `source_ref` 규칙 1건 `CALL_REQUIRED` — CALL-16)** | 정철원: CALL-16 · `failure.kind` 값 문서 |
| B07 | evidence에 필요한 자산 사실·표면 미작성 | 선행 §4.6 · **이 문서 §4.5** | Draft 계약 2건 존재(필드 수준 커버) | 불가(Review 전) | **`PENDING_CONSUMER_REVIEW`** (선행 `PENDING_IMPLEMENTATION`에서 진전) | 4 Consumer Review · CALL-17 · CALL-18 · 이후 evidence ASSET 판정 fixture |
| B08 | relative timeline ↔ ISO8601 scope | 선행 §4.7 · **이 문서 §4.4** | `AnalysisScope` 1.1.0 | **V11 PASS** | **`CLOSED_VERIFIED`** | `clip_id` 대응은 별건(§8.4) |
| B09 | (유지) | 선행 §4.8 | 완료 | V5 PASS | `CLOSED_VERIFIED` | 표시 필드명·TimeResolution 필드는 `PENDING_IMPLEMENTATION` 별도 추적 |
| B10 | (유지) | 후속 보정 ADR §2 | 완료 | 문구 | `CLOSED_VERIFIED` | fingerprint 알고리즘 미결 유지 |
| B11 | (유지) | 후속 보정 ADR §2 | — | — | `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` | 정철원 확인 없음 |
| B12 | (유지) | 후속 보정 ADR §2 · 선행 §4.10 | — | — | `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` | 수락일 **확인 불가** 유지 |
| W01~W03 · W05 · W06 | (유지) | 선행 §9 | 완료 | — | `CLOSED_VERIFIED` | — |
| W04 | (유지) | 선행 §4.4 | — | — | `PENDING_OWNER` | `JobExecution` 소비자 확인 · domain PARTIAL↔status |
| W07 | ref 접두어/위치 인코딩 · `thumb_ref` 자산 종류 | 선행 §4.9 · **이 문서 §4.5** | `FrameRef` 필드가 Draft에 존재 | V1 PASS | `CLOSED_VERIFIED` | `FrameRef` 필드 계약은 B07과 함께 `PENDING_CONSUMER_REVIEW` |
| N01 | (유지) | 선행 §7 · 이 문서 §7 | 검사기 범위 확장 | V7 재실행 | `NOTE_ACCEPTED` | E2E 아님 |
| N02 | (유지) | 선행 §4.10 | — | — | `PENDING_OWNER` | 신유민 · 김대원 · 유소연↔김준영 |
| N03 | (유지) | 이 문서 §7 말미 | — | — | `NOTE_ACCEPTED` | Trajectory 1회차 기록 비어 있음 |

**집계:** BLOCK 12건 중 `CLOSED_VERIFIED` 9(B01·B02·B03·B04·B05·B06·B08·B09·B10) · `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` 2(B11·B12) · `PENDING_CONSUMER_REVIEW` 1(B07). BLOCK 상태로 남은 항목은 0건이고 **종결되지 않은 BLOCK ID는 1건(B07)**이다. B06은 의미·직렬화가 닫혔으나 `source_ref` 규칙 1건이 `CALL_REQUIRED`다.

## 10. 종결 판정

**데이터 계약 감사 — `CONTRACT_AUDIT_PARTIAL`.** 종결 조건 6개 중 ①(Owner 결정) B07 자산 스키마의 Consumer Review와 CALL-16~18이 남아 부분 충족 · ②(공개 ADR) 충족 · ③(계약 반영) `ACCEPTED` 범위 충족 · ④(fixture 검증) V1~V5·V8~V11 충족 · ⑤(BLOCK 상태 0건) 충족 · ⑥(새 CALL이 필요한 계약 BLOCK 0건) **미충족** — B06 잔여 CALL-16, B07 선행 CALL-17·CALL-18이 열려 있다. 따라서 「데이터 계약 감사 종결」을 선언하지 않는다. 선행 문서의 `CALL_REQUIRED` 2건(B06·B08)은 닫혔고 B07이 `PENDING_IMPLEMENTATION`에서 `PENDING_CONSUMER_REVIEW`로 진전했다.

**모든 외부 감사 — 선언 불가.** `SECURITY_REVIEW_PENDING`(`pre-deploy-security-review.md` §1 표의 확인일·판정 칸이 모두 비어 있다) · `TRAJECTORY_REVIEW_PENDING`(`tool-trajectory-review.md` §4 두 회차 표가 비어 있다) · `IMPLEMENTATION_NOT_VERIFIED`(모듈 실행 코드 0개) · `E2E_NOT_VERIFIED`(통합 실행 기록 없음). 데이터 계약 감사가 닫히더라도 이들은 자동으로 닫히지 않는다.

## 11. 후속 변경 규칙

CALL-16~18 답이 오거나 자산 계약 Consumer Review가 끝나면 이 문서를 고치지 않고 **변경 ADR**을 쓴 뒤 §3·§9 표의 해당 행만 갱신한다(상태표는 원장이므로 갱신 대상). 자산 계약 2건이 Accepted가 되면 짝 ADR의 Status를 바꾸고 §4.5·§9 B07 행을 그 계약으로 닫는다. 과거 감사 보고·선행 ADR 본문은 수정하지 않는다.
