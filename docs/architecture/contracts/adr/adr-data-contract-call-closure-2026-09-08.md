# ADR — 데이터 계약 감사 접합부 종결 후속 (2026-09-08)

**Status:** Accepted — 아래 §4에 `ACCEPTED`로 표기한 결정에 한정. `PENDING`·`OUT_OF_SCOPE` 항목의 수락을 뜻하지 않는다
**Date:** 2026-09-08 (계약 반영일. **같은 날 2차 반영으로 §4.7~§4.10과 §3·§6~§11이 갱신됐다** — §11의 「이 문서를 고치지 않는다」 규칙에 대한 예외이며 그 근거는 §11 말미에 적었다). Owner 결정 완료일은 §4 각 절에 있다
**Decider:** 각 결정 단위의 Decider는 §3 표에 있다. 이 문서의 작성·계약 반영은 PM(김준영)이 했고, PM은 어느 결정도 Owner를 대신해 만들지 않았다
**선행 문서:** `adr-data-contract-call-closure-2026-09-07.md`(2026-09-07 종결 회차의 결정 원장) → **이 문서가 2026-09-08 이후의 현재 결정 원장이다.** 선행 문서 본문은 고치지 않았고 §3·§9 상태표의 해당 행만 이 문서를 가리키도록 갱신했다(선행 문서 §11의 규칙)
**감사 원문:** `../../../management/contract-consistency-audit-2026-09-06.md` — 본문을 수정하지 않는다. 지적 ID(B01~B12 · W01~W07 · N01~N03)는 그 문서 §2를 따른다

> **이 문서를 읽는 법.** 선행 문서가 `CALL_REQUIRED`로 남긴 결정 회차 4건(CALL-12 · CALL-13 · CALL-14 · CALL-15)에 Owner 결정이 들어왔다. 회차 원문은 PM 내부 기록이며 저장소에 없다. **이 문서는 그 원문을 열지 않아도 계약을 수정·구현할 수 있도록 결정 내용·근거·기각안을 자기완결적으로 적은 공개 문서**이고, 이번 계약 반영의 유일한 근거다. CALL 번호는 결정 이력의 보조 식별자일 뿐이며 결정 내용은 모두 이 문서 본문에 있다. 계약 본문이 이 문서와 다르면 계약 본문이 규칙을 소유하고 이 문서는 근거·상태만 소유한다(`README.md`).
>
> 같은 날 recording 자산 계약 2건(`contract-source-asset-media-stream.md` · `contract-analysis-source-derived.md`)이 **Draft**로 추가됐다(§4.5는 그 시점의 기록이다).
>
> **2차 반영 (같은 날, 이 문서 안).** §4.6이 `CALL_REQUIRED`로 남긴 결정 3건에 Owner 결정이 들어왔고(§4.7·§4.8·§4.9), 자산 계약 2건의 Consumer Review 4건이 종결됐다(§4.10). 두 계약은 `Final — Accepted`(`…/v1`), 짝 ADR 2건은 `Accepted`로 전환됐다. **§4.1~§4.6의 본문은 고치지 않았고** 상태표(§3·§9)와 검증·영향·판정 절(§6~§11)만 갱신했다.

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
| 자산 계약 2건 | `ACCEPTED` (2차 반영) | Consumer Review 4건 종결. 두 계약을 `…/v1` `Final — Accepted`로 전환. FrameRef 발급 capability 분리 · timeline revision 동반 필수 · null/부재/0 통일 · availability 부여 조건 · machine-readable failure · lineage 평탄화 · `profile_ref` non-null · `DeletionReport` · `derived_role` 2값. 상세는 §4.10과 두 짝 ADR §7 | Owner 정철원 · Consumer 서어진·신유민·유소연·김준영 | 계약 2건(`v0.2 → v1`) · 짝 ADR 2건(`Proposed → Accepted`) | §7-V14 fixture: `kind` 값 공간·`asset_kind` 대응표·`AVAILABLE⇒byte_size`·timeline 쌍·lineage 평탄화 · §7-V15: clip provenance |
| CALL-16 | `ACCEPTED` (2차 반영) | `MissingRange.source_ref`는 **`ContractRef {kind, ref} | null`**이고 **키 항상 존재**. `SOURCE_UNAVAILABLE`·`STREAM_UNAVAILABLE`은 필수 non-null(각각 `source_asset`·`media_stream`), `TIMELINE_GAP`·`OUT_OF_TIMELINE_RANGE`는 `null`. 판정 의미는 불변이고 `reason → outcome` 매핑은 evidence policy 소유 | Decider 정철원(`recording`) · 확인 김준영(`evidence`) · 서어진(`search`) | recording 헤더·§8.1·§9·§10.1·§10.2·§23(13·14) · `span-resolution/v1.1 → v1.2` | §7-V13 fixture: reason별 non-null/null · 키 부재 · 평문 · kind 불일치 · 대문자 kind |
| CALL-17 | `ACCEPTED` (2차 반영) | 자산 계층 `ContractRef.kind`를 **소문자 snake_case 8값**으로 통일하고 **값 공간 소유를 `contract-source-asset-media-stream.md` §2.1 한 곳**으로 확정. `asset_kind`는 대문자 enum 유지 + 명시적 1:1 대응표(문자열 동일성 요구 안 함). 보정 범위는 신규 자산 계약 2건뿐 | Decider 정철원 · 확인 김준영·서어진·유소연 | 자산 계약 2건 §2·§2.1·§6.2·모든 예시 | §7-V14 fixture |
| CALL-18 | `ACCEPTED` (2차 반영) | `AssetSpan`에 **identity를 추가하지 않는다**(immutable value mapping 유지, 합성 span ref 금지). readout `input_ref.span_ref` **삭제**(`plate/overlay v1.2`). 사건 구간 canonical ref는 `incident_clip`이고 clip 생성 전에는 `candidate_event` fallback. `IncidentClip.source_provenance`를 canonical `AssetSpan` 구조·초 단위·`sequence` 필수로 보정 | Decider 정철원 · 확인 신유민·유소연·김준영 | plate/overlay 헤더·§4·예시 · `EvidenceNeeds` §8.3·예시 · 파생 계약 §6 · recording 짝 ADR 고지 | §7-V15 fixture: clip provenance·readout 입력·evidence interval ref |

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

> **이 절은 Draft 추가 시점의 기록이다. 이후 경과(Consumer Review 종결과 Accepted 전환)는 §4.10이고, 이 절이 `CALL_REQUIRED`·`Consumer 확인 필요`로 넘긴 항목의 결론은 §4.7~§4.9다. 아래 본문은 고치지 않았다.**

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

### 4.6 새 결정 회차가 필요한 것 (당시 `CALL_REQUIRED` — **3건 모두 2026-09-08 종결**, 결론은 §4.7~§4.9)

| 회차 | 주제 | Decider | 확인 | 막는 것 |
| --- | --- | --- | --- | --- |
| CALL-16 | `MissingRange.source_ref` 타입 · reason별 nullable/부재 규칙 | 정철원 | 김준영 · 서어진 | `OUT_OF_TIMELINE_RANGE` fixture 완성 · evidence/search의 `missing_ranges` 소비 구현 |
| CALL-17 | 자산 계층 `ContractRef.kind` 값 표기 · `asset_kind` 문자열 동일성 | 정철원 | 김준영 · 서어진 · 유소연 | Consumer의 `asset_ref.kind` 문자열 비교 구현 · 자산 계약 2건 Accepted 전환 |
| CALL-18 | `AssetSpan` identity · `PlateReadout.input_ref.span_ref` 참조 대상 | 정철원 | 신유민 · 유소연 · 김준영 | readout 입력 조립(`needs_map`) · `IncidentClip` provenance 모양 · 자산 계약 2건 Accepted 전환 |

회차 문서는 PM 내부 기록이다. **세 건 모두 같은 날 Owner 결정이 들어와 종결됐다** — 결정 내용·근거·기각안은 §4.7(`MissingRange.source_ref`) · §4.8(자산 `kind` 표기) · §4.9(`AssetSpan` identity와 사건 구간 ref)에 자기완결적으로 적었다. 위 표의 「막는 것」 열은 당시 판단 기록이며 지금은 모두 해소됐다.

### 4.7 `MissingRange.source_ref`의 타입과 nullable 규칙 (Decider 정철원 · 확인 김준영 · 서어진 · 결정 완료 2026-09-08)

**해결할 문제.** §4.3에서 `MissingRange.reason`이 네 값(`TIMELINE_GAP` · `SOURCE_UNAVAILABLE` · `STREAM_UNAVAILABLE` · `OUT_OF_TIMELINE_RANGE`)으로 닫혔지만 `source_ref`의 모양이 남았다. 계약에는 예시 하나(`"source_ref":"sa_0002"`)만 있었고 필수성·nullable 규칙이 없었다. `SOURCE_UNAVAILABLE`/`STREAM_UNAVAILABLE`은 가리킬 Source/Stream이 있지만 **`OUT_OF_TIMELINE_RANGE`와 `TIMELINE_GAP`은 특정 Source가 원인이 아니라서 가리킬 대상이 없다.** 규칙이 없으면 `missing_ranges[]`를 소비하는 `evidence`·`search`가 `null`·부재·빈 문자열 중 무엇이 오는지 몰라 각자 다른 방어 코드를 쓴다.

**채택한 규칙.**

1. **타입은 `ContractRef {kind, ref} | null`이다.** 평문 opaque string이면 `SOURCE_UNAVAILABLE`과 `STREAM_UNAVAILABLE`의 참조 종류를 구분할 수 없고, 구분하려면 `sa_`/`ms_` 접두어를 파싱해야 한다 — v4 §5-3과 자산 계약 §2가 금지한다. `SpanResolution.failure`·`UsageRecord.run_ref`·`JobExecution.produced`와 같은 어휘를 쓴다.
2. **키는 항상 존재한다.** 「키 부재」와 「`null`」을 혼용하지 않는다. `failure`(§4.3)와 같은 규칙이므로 Consumer가 한 가지 방식으로 읽고, 의도적인 「참조 대상 없음」과 계약 위반에 의한 필드 누락을 구분할 수 있다.
3. `reason ∈ {SOURCE_UNAVAILABLE, STREAM_UNAVAILABLE}`이면 **필수 non-null**이고 `kind`가 각각 `source_asset`·`media_stream`이다. 원인 대상을 특정할 수 있는데 `null`인 payload는 계약 위반이다 — 그러면 evidence가 「원본 일부가 왜 없었는가」를 사용자에게 설명할 수 없다.
4. `reason ∈ {TIMELINE_GAP, OUT_OF_TIMELINE_RANGE}`이면 **`null`**이다. 임의의 참조 대상을 채우지 않는다.
5. `kind` 문자열은 §4.8이 확정한 소문자 snake_case를 그대로 쓴다. 이 회차에서 새로 정하지 않았다.
6. **판정 의미는 바뀌지 않는다.** `source_ref`는 원인 대상의 provenance와 사용자 설명을 위한 정보이며 `SpanResolution.status`를 바꾸지 않는다. evidence는 `status → failure → missing_ranges[].reason` 순서로 읽어 outcome을 정하고 `source_ref`는 `RequirementCheck.subject_refs`(`ContractRef[]`)에 provenance로만 담는다 — 그래서 평문이 아니라 `ContractRef`여야 한다.

**고려하고 기각한 대안.**

| 대안 | 기각 이유 |
| --- | --- |
| 평문 opaque string 유지 | 변경은 최소지만 Consumer가 접두어를 파싱해야 종류를 알 수 있다. 유지하려면 「reason → 참조 종류」 매핑을 계약에 명문화해 Consumer가 `ContractRef`를 **조립**하게 해야 하는데, 그건 recording이 이미 아는 사실을 Consumer가 재구성하는 것이다 |
| 키 부재 허용 | payload는 짧아지지만 「없음」과 「누락」을 구분할 수 없다 |
| `OUT_OF_TIMELINE_RANGE`에 timeline ref를 채워 넣기 | 「범위 밖」의 원인은 Source가 아니라 요청이다. 원인이 아닌 대상을 채우면 evidence가 잘못된 provenance를 보고한다 |

**임의로 만들지 않은 것.** `failure.kind` 값 집합(recording 소유 문서 작성 대기) · `OUT_OF_TIMELINE_RANGE`·`TIMELINE_GAP`·위치 불특정 `FAILED` 각각이 어느 outcome(`BLOCK`/`UNKNOWN`)으로 가는지의 매핑 — **evidence policy 소유이며 recording 계약에 고정하지 않는다.** Consumer 답변에 나온 판정 계획(「`OUT_OF_TIMELINE_RANGE`는 다른 판정 경로」·「위치 불특정 `FAILED`는 `UNKNOWN` 계열」)은 구현 의향이며 계약 규칙으로 옮기지 않았다.

**계약 영향.** `contract-recording-timeline-asset-span.md` 헤더(고지 1건 추가·`span-resolution/v1.1 → v1.2`) · §8.1 예시 · §9 `FAILED` 예시 · §10 예시와 신설 §10.1 필드표·§10.2 규칙 · §23 SpanResolution 13·14 · 짝 ADR 고지. `recording-timeline/v1`·`asset-span/v1`·`time-source-candidate/v1`은 그대로다. **하위 호환:** 필드 타입 변경이므로 v1.1 payload를 v1.2로 자동 재해석하는 규칙은 만들지 않았다 — 구현 코드가 없어 migration 대상 payload가 존재하지 않는다(§6).

### 4.8 자산 계층 `ContractRef.kind` 값 표기 (Decider 정철원 · 확인 김준영 · 서어진 · 유소연 · 결정 완료 2026-09-08)

**해결할 문제.** `ContractRef {kind, ref}`의 **모양**은 `contract-observation.md` §3이 정의하지만 `kind` 값의 전역 어휘를 소유하는 문서가 **없었다.** 그 결과 같은 대상을 두 표기로 쓰고 있었다 — 수락된 `Observation` §12 예시·`TimeResolution`·`RequirementReport`는 `source_asset`/`media_stream`(소문자), §4.1·§4.2에서 확정된 run ref는 `analysis_run`/`readout_run`(소문자), 그런데 새 자산 계약 2건의 Draft는 `SOURCE_ASSET`/`MEDIA_STREAM`/`FRAME`/`EXTERNAL_SOURCE`/`INCIDENT_CLIP`/`ANALYSIS_SOURCE`(대문자)였다. 네 Consumer 모두 `kind`를 **정확 문자열로 비교**할 계획이므로, 두 표기가 남으면 대소문자 무시 비교나 Consumer별 상수표가 생긴다. 둘 다 lineage를 조용히 끊는 경로다.

**채택한 규칙.**

1. **자산 계층 `kind`는 소문자 snake_case로 통일한다.** 값 8개: `external_source` · `source_asset` · `media_stream` · `frame` · `analysis_source` · `remote_copy` · `incident_clip` · `derived_asset`.
2. **값 공간의 소유 문서는 `contract-source-asset-media-stream.md` §2.1 한 곳이다.** 다른 계약은 복제 정의하지 않고 이 절을 가리킨다. 자산 계층이 아닌 ref는 각각의 소유 계약이 자기 값을 정한다.
3. Consumer는 정확한 문자열로 비교한다. **금지** — 대소문자 무시 비교 · 대문자/소문자 별칭 허용 · ref prefix를 통한 `kind` 추론 · Consumer별 `kind` 변환표 운영.
4. **`AssetFacts.asset_kind`는 대문자 enum을 유지한다.** `asset_ref.kind`는 참조 대상을 라우팅하는 값이고 `asset_kind`는 자산의 의미를 판정하는 enum이라 역할이 다르다. **문자열 동일성을 요구하지 않고** 명시적 1:1 대응표(`SOURCE_ASSET`↔`source_asset` · `ANALYSIS_SOURCE`↔`analysis_source` · `INCIDENT_CLIP`↔`incident_clip` · `DERIVED_ASSET`↔`derived_asset`)로 연결한다. 불변조건의 「일치」는 문자열 동일성이 아니라 이 표에 따른 **의미적 일치**다.
5. `asset_kind`의 직접 대상이 아닌 ref kind(`external_source`·`media_stream`·`frame`·`remote_copy`)에는 임의의 asset kind를 만들지 않는다. 이런 ref로 `lookup_asset_facts`를 호출하면 `INVALID_REF_KIND` 실패다.
6. **표기 보정 범위는 새 자산 계약 2건뿐이다.** 이미 소문자인 `Observation`·`TimeResolution`·`RequirementReport` 예시는 손대지 않는다. `AnalysisRun.input_ref.kind = ANALYSIS_SCOPE`도 바꾸지 않는다 — 자산 계층 ref가 아니고 이미 수락된 별도 계약 값이며, 이것을 근거로 모든 `ContractRef.kind`에 전역 대문자 규칙을 적용하지 않는다.

**고려하고 기각한 대안.**

| 대안 | 기각 이유 |
| --- | --- |
| 대문자로 통일(Draft 유지) | `asset_kind` enum과 문자열이 같아져 불변조건이 단순해지지만, 수락된 세 계약의 예시와 확정된 run ref 표기와 어긋나 **두 표기가 영구 공존**한다. 예시를 보정하겠다고 답한 Owner가 있었지만 run ref는 소문자로 남으므로 자산 ref와 표기가 영구히 갈린다 |
| 통일하지 않고 「ref 대상 계약이 자기 kind를 소유」만 명시 | 변경은 최소지만 Consumer 코드에 계약별 상수표가 생긴다. `evidence` 안에 어휘 사전이 생기고, `case`는 broker 역할인데도 「이 값은 A 계약이니 대문자, 저건 B 계약이니 소문자」를 들고 있어야 해서 「case는 domain 정책을 재해석하지 않는다」(v4 §3)와 어긋난다 |
| `asset_kind`와 `asset_ref.kind`의 **문자열 동일성**을 불변조건으로 요구 | `asset_kind`가 별도 enum으로 존재하는 이유를 없앤다. 두 필드를 비교·분기하는 Consumer가 없고(case는 통째로 전달, evidence는 각각 다른 목적으로 읽음) 대응표만 있으면 충분하다 |

**Producer/Consumer 책임.** recording은 두 계약의 `kind` 문자열과 §2.1 값 공간·§6.2 대응표를 소유한다. Consumer(`search`·`readout`·`case`·`evidence`)는 정확 문자열 비교만 하고 변환·보정·추론을 하지 않는다.

**계약 영향.** `contract-source-asset-media-stream.md` §2·§2.1·§2.2 신설 · §3.2·§6 예시 · §6.2 대응표 신설 · §8 금지사항 · `contract-analysis-source-derived.md` §2 말미·§2.1·모든 예시 · 두 짝 ADR §7. **하위 호환:** Draft(v0.x) 단계의 표기 변경이므로 호환성 대상 payload가 없다. 수락된 다른 계약의 예시는 바뀌지 않았다.

### 4.9 `AssetSpan` identity와 사건 구간 canonical reference (Decider 정철원 · 확인 신유민 · 유소연 · 김준영 · 결정 완료 2026-09-08)

**해결할 문제.** 수락된 `AssetSpan` 스키마(recording §6.2)는 `sequence`·`timeline_range`·`source_asset_ref`·`media_stream_ref`·`source_range` 다섯 필드뿐이고 **독립 식별자가 없다.** 그런데 수락된 `PlateReadout`/`OverlayTimeReadout` §4는 `input_ref`에 `span_ref`를 두고 예시·fixture가 `"span_001"`을 썼고, 수락된 `EvidenceNeeds` §8.3은 「`AssetSpan` / Source-derived incident interval ref」를 예로 들었다. **수락된 두 계약이 「span을 가리키는 ref가 있다」를 전제하고 recording 계약은 「span에는 ref가 없다」고 하는 상태**였다. 롤백된 Mock에서 실제로 `span_ref="sa_h001_01:690.0-708.0"`처럼 source ref와 시간 범위를 문자열에 인코딩한 값이 나왔다 — 존재하지 않는 identity를 Consumer가 합성한 것이다.

**채택한 규칙.**

1. **`AssetSpan`에 identity를 추가하지 않는다.** `span_id`·`asset_span_ref` 모두 만들지 않고 immutable value mapping으로 유지한다. 동일성 비교는 canonical 필드값 `(timeline_id, timeline revision, timeline_range, source_asset_ref, media_stream_ref, source_range)`으로 한다. **Consumer가 이 값을 문자열로 결합하거나 해시해 임의 span ref를 발급하는 것을 금지한다.**
2. **`PlateReadout.input_ref.span_ref`와 `OverlayTimeReadout.input_ref.span_ref`를 삭제한다.** `span_ref`라는 이름으로 `IncidentClip`이나 `SpanResolution`을 가리키는 **의미 재정의도 하지 않는다** — 이름과 대상이 어긋난 필드를 남기지 않는다. `plate-readout/v1.1 → v1.2` · `overlay-time-readout/v1.1 → v1.2`.
3. **clip 생성 이후 사건 구간의 canonical reference는 `{kind:"incident_clip", ref:...}`다.** 「어느 구간을 읽었나」는 `incident_clip_ref` 하나로 알 수 있다 — timeline·요청 범위·사용한 span 값이 모두 `IncidentClip.source_provenance`에 있다. readout 입력에서 `incident_clip_ref`는 필수다(overlay는 판독 실행 시 필수).
4. **`IncidentClip`은 저장·재참조할 수 있는 독립 자원이므로 opaque `incident_clip_ref`를 소유한다.** 같은 ref는 항상 같은 clip과 같은 provenance를 가리킨다 · rebase·재처리로 기존 ref의 의미를 바꾸지 않고 기존 clip을 mutate하지 않는다 · 재사용하면 기존 ref를 유지한다 · 새 profile·새 bytes·새 source provenance로 다시 materialize하면 새 ref를 발급한다 · 같은 사건 구간인지는 ID 문자열이 아니라 `source_provenance`의 canonical 값으로 비교한다 · ref에 timeline·sequence·offset 등 위치값을 인코딩하지 않는다. 따라서 `incident_clip_ref`를 `(timeline_id, revision, sequence)`로 만들 필요가 없고, 재처리 동일성은 immutable provenance와 case의 `input_fingerprint`가 보장한다.
5. **`IncidentClip.source_provenance`를 canonical 형태로 보정한다** — `timeline_ref {timeline_id, revision}`(필수) · `requested_range {start_sec, end_sec}` · `asset_spans[]`가 canonical `AssetSpan`과 **같은 필드·같은 중첩·같은 단위**(`sequence` 필수 · `timeline_range`/`source_range` 중첩 · **초**). Draft의 평탄화·ms 혼재 표기를 삭제한다. 합성 `source_span_ref`를 만들지 않는다.
6. **`EvidenceNeeds.context_refs`의 `evidence.interval`** — clip 생성 후 `incident_clip`, clip 생성 **전**에는 `candidate_event` ref를 fallback으로 허용한다. `CandidateEvent.span`이 `timeline_id` + `timeline_revision` + ms 범위를 가지므로(§9 B09) 기준 revision과 사건 범위를 복원할 수 있다. **candidate ref는 clip 생성 후에도 `incident_clip` ref를 대신하는 영구 별칭이 아니다** — case가 candidate ref를 받아 clip을 materialize한 뒤 readout에는 `incident_clip_ref`를 전달한다. 같은 규칙을 `EvidenceRecord.basis.evidence_interval_ref`에도 적용한다.
7. **readout은 `IncidentClip` 또는 그 clip에서 발급된 Source-derived `FrameRef`/crop을 근거로 사용한다.** `AssetSpan`만 직접 전달받아 판독하는 public 경로는 두지 않는다. frame 획득 경계는 `IncidentClip.source_provenance.asset_spans[]` → `resolve_frame(STREAM_POSITION)` → `FrameRef` → `read_frame`이며, `resolve_frame`은 `contract-source-asset-media-stream.md` §5.3이 소유한다(§4.10).

**고려하고 기각한 대안.**

| 대안 | 기각 이유 |
| --- | --- |
| **`AssetSpan`에 canonical identity 추가** | 고칠 문서 수는 가장 적다(recording 계약 한 곳). 한 Consumer가 그 실용적 이유로 선호했다. 그러나 이 선택은 `AssetSpan`을 immutable value mapping에서 **identity·저장·조회·재발급 정책을 가진 자원**으로 바꾼다 — 수정 파일은 적지만 recording의 영속 모델과 책임은 더 크게 변한다. 또한 결정적 발급 규칙이 없으면 재처리 동일성이 깨지고, 있으면 composite key 해시와 같아져 얻는 것이 적다. readout은 독립 span identity가 필요하지 않다고 확인했고(판독 근거는 항상 Incident Clip이라는 규칙이 이미 있다), evidence는 clip provenance로 원본 구간을 복원할 수 있다고 확인했고, 선호했던 Consumer 본인이 「recording·readout·evidence가 수정 범위를 감당할 수 있다면 막을 근거는 없다」고 확인했다 |
| **`span_ref`를 `SpanResolution` identity로 재정의**(`resolution_id` 신설) | resolution과 clip이 1:1이 아닐 수 있어 provenance가 한 단계 더 필요하다. 이름이 `span_ref`인데 대상이 `SpanResolution`이면 필드명도 `span_resolution_ref`로 바꿔야 해서 개정 규모가 채택안과 같아지고, 채택안은 readout만 고치는 데 비해 이 안은 recording·readout **양쪽**을 고친다 |
| **`span_ref` 이름 유지 + `IncidentClip`을 가리키게 의미만 변경** | 이름과 대상이 어긋난 필드를 남긴다. 이미 `incident_clip_ref`가 같은 `input_ref` 안에 있으므로 중복이다 |
| **Consumer가 canonical 값을 결합·해시해 span ref 발급** | 롤백된 Mock에서 실제로 나온 경로다. 존재하지 않는 identity를 만들어 Consumer가 파싱·조회하게 되고 위치를 ID에 인코딩한다(v4 §5-3 금지) |

**Producer/Consumer 책임.** recording은 clip 발급·불변성·provenance 완전성을 소유한다. case는 candidate ref로 clip을 materialize해 readout 입력을 조립하고, 사용자 구간 수정(`SPAN_ADJUST`) 시 `input_fingerprint`를 바꿔 캐시 재사용을 막는다. readout은 `incident_clip_ref`만 받고 span 값을 직접 조립하지 않는다. evidence는 clip provenance로 「결과가 어느 원본 구간에서 나왔는가」·「재처리해도 같은 구간인가」·「rebase 뒤에도 과거 결과를 가리키는가」를 증명한다.

**계약 영향.** `contract-plate-overlay-readout.md` 헤더(고지·`v1.2`)·`Accepted` 줄·§4 필드표·예시 2건 · `contract-evidence-record-needs.md` 헤더 고지·Upstream 목록·§8.3(참조 대상 절 신설)·예시 1건(`evidence-needs/v1` 유지 — `ContractRef` 모양·필수성은 불변, 허용 `kind`와 의미만 확정) · `contract-analysis-source-derived.md` §6 전체 · `contract-recording-timeline-asset-span.md`(스키마·버전 불변, 짝 ADR 고지로 「identity를 추가하지 않는다」 기록) · fixture `v3-readout-run-chain.json`(합성 `span_ref` 2건 제거) · 짝 ADR 3건 고지. **하위 호환:** readout 계약의 **필드 삭제**이므로 minor bump로 처리했다(PM bookkeeping) — 구현 코드가 없어 payload migration 대상이 없고, 삭제된 값은 애초에 Producer가 발급하지 않는 ID였다.

### 4.10 recording 자산 계약 2건 — Consumer Review 종결 (Owner 정철원 · Consumer 4인 · 종결 2026-09-08)

> §4.5는 이 두 계약이 **Draft로 추가된 시점**의 검수 기록이다. 그 절은 고치지 않았고, 이후 경과가 이 절이다.

**경과.** §4.5에서 `PROPOSED`로 남긴 두 Draft(`contract-source-asset-media-stream.md` · `contract-analysis-source-derived.md`)에 대해 계약 헤더가 지정한 4 Consumer(`search` 서어진 · `readout` 신유민 · `case` 유소연 · `evidence` 김준영)의 검토가 모두 들어왔다. Owner(정철원)가 필수 변경 요청을 전부 수용하고 §4.7~§4.9의 결정을 함께 반영했다. 두 계약을 `Final — Accepted`(`source-asset-media-stream/v1` · `analysis-source-derived/v1`)로, 짝 ADR 2건을 `Accepted`로 전환했다.

**Consumer별 역할과 제기된 핵심 우려, 계약에 반영한 변경, 반영하지 않은 요청과 이유, 조건부 승인 조건의 충족 근거는 두 짝 ADR의 §7이 자기완결적으로 소유한다** — `adr-source-asset-media-stream.md` §7 · `adr-analysis-source-derived.md` §7. 이 절은 결정 원장으로서 **종결 판정과 그 근거**만 기록한다.

**계약 의미가 확정된 항목(요약).**

| 영역 | 확정 |
| --- | --- |
| FrameRef 발급 | `resolve_frame(locator) -> FrameRef`와 `read_frame(frame_ref) -> image`를 분리. locator는 `TIMELINE_POSITION`(timeline_id+revision+at_sec) · `STREAM_POSITION`(media_stream_ref+source_offset_sec) 두 형태의 명시적 discriminator. canonical frame은 **원본 MediaStream 기준**으로 발급하고 proxy·`AnalysisSource` 기준으로 발급하지 않는다 |
| frame 정밀도 | `source_offset_sec`·`at_sec`은 decimal seconds이며 최소 ms 수준 또는 원본 stream time base보다 정밀한 값을 보존. 실제 선택된 frame의 offset을 `FrameRef`에 기록하고 요청 offset과 다를 수 있다 |
| timeline provenance | `AssetFacts`·`AnalysisSource`·`IncidentClip`·`DerivedAsset`에 `timeline_ref {timeline_id, revision}` 필수 동반. `timeline_ref == null ⇔ timeline_range == null`. 범위 단위는 **초** |
| null·부재·0 | `byte_size`·`duration_sec`은 **키 항상 존재 + nullable**. `AVAILABLE ⇒ byte_size non-null`, 그 외 측정 실패는 `null`이고 0으로 꾸미지 않는다 |
| availability | `AVAILABLE`/`UNAVAILABLE`/`UNKNOWN` 3값과 **부여 조건**을 세 객체가 공유. 한 stream의 실패가 asset 전체 상태를 바꾸지 않는다. 판정 매핑은 evidence policy 소유 |
| 실패 표현 | `resolve_frame`·`read_frame`·`lookup_asset_facts`·`open_analysis_source`·clip/export 실패를 정상 `null`·`UNAVAILABLE` 객체와 구분되는 machine-readable failure `{kind, code}`로 제공. `UNKNOWN_REF`(등록된 적 없음)·`INVALID_REF_KIND`(대상 아닌 kind)·`UNAVAILABLE`(있었지만 지금 못 씀) 혼용 금지 |
| lineage | 파생 자산 `AssetFacts.lineage[]`는 원본까지 **평탄화**되고 최소 하나의 `source_asset`/`external_source`를 포함. 객체의 `source_refs[]`는 직접 부모. **모르는 상태를 빈 배열로 표현 금지** |
| stream role·audio | `role=UNKNOWN`은 정상 상태이고 후보로 쓸 수 있다. 선택 우선순위는 계약이 정하지 않는다. `AUDIO` stream은 원본 자산 사실에 그대로 기록하고 분석 사본에서만 profile로 제외 |
| profile | `profile_ref` **필수 non-null**, canonical 값 공간 **소유는 recording**, Consumer는 opaque로 두고 동등성 비교만. 값 목록은 3자 합의 Pending |
| RemoteCopy | `find_remote_copy`는 조회 시점 `AVAILABLE`·만료 전 사본만 반환하고 나머지는 cache miss와 같은 `null`. 만료 판단은 recording. `remote_info` 최소 필드 `provider_object_ref`·`expires_at`. 토큰·URL·local path 저장 금지. evidence는 소비하지 않는다 |
| clip lifecycle | `build_incident_clip` option 소유는 recording, case는 이미 결정된 interval만 전달. `SPAN_ADJUST` 시 case가 fingerprint 변경, recording이 provenance가 다르면 새 clip 발급(기존 clip mutate 금지) |
| 삭제 | `DeletionReport {case_id, requested_at, completed_at, status, items[{asset_ref, result, failure_code}]}`. 외부 원본은 대상 아님, delete 미지원 사본은 `PENDING_EXPIRY`, 일부 실패는 `PARTIAL` |
| derived_role·transform | 등재 값 `REPORT_VIDEO`·`PLATE_IMAGE` 2건. `transform_ref`가 non-null이면 적용된 transform 종류를 machine-readable하게 조회할 수 있다. 필수성·부재 시 outcome은 evidence policy 소유 |
| 경계 잘림 | `timeline_range`(실제 materialize)와 `requested_range`(요청)는 다를 수 있고 Consumer는 두 필드 비교로 안다. 허용 폭은 evidence policy 소유 |
| 버전 | 헤더와 모든 payload가 `…/v1` 한 문자열. forward-compatibility(모르는 optional 필드 무시 · optional 추가는 minor · 필수 추가·타입 변경·nullable 축소·enum 제거는 breaking) 명문화 |

**종결 판정의 근거.**

1. 네 Consumer는 모두 판정과 함께 **승인 전제**를 명시했다(`case`는 형제 계약 하나에서 `APPROVE_WITH_CHANGES`, 나머지는 전제를 붙인 `CHANGES_REQUIRED`). Owner가 그 전제를 전부 수용해 반영했고, 각 전제가 계약 본문의 어느 절로 들어갔는지는 두 짝 ADR §7.5의 대조표가 기록한다. **글자 그대로의 `APPROVE`를 기다리지 않고 조건 충족으로 판정한 이유**는 여기 있다 — 각 Consumer가 스스로 「이것이 반영되면 승인으로 올린다」고 적은 조건이 계약 문장으로 존재하고, 그 문장이 해당 Consumer의 의도와 충돌하지 않는다.
2. **미반영으로 남긴 항목은 어느 Consumer도 승인 전제로 걸지 않았거나, 요청자 자신이 별도 합의로 분리한 것이다**(두 짝 ADR §7.4). 유일하게 판단이 필요했던 것은 `AnalysisSource` profile의 **값 목록**이다 — 요청한 Consumer가 「정확한 값과 의미는 recording·search·readout 3자가 합의하고 recording 계약이 canonical 값 공간을 소유해야 한다」고 적었으므로, 계약은 소유·필수성·opaque성을 확정하고 값 목록은 3자 합의 항목으로 남겼다. **PM/통합 판단:** `profile_ref`를 opaque로 확정했기 때문에 소비 코드가 동등성 비교만 하면 되고 값이 늘어도 breaking이 아니다 — 값 목록의 부재가 계약의 필드 모양·필수성·소유를 확정하는 데 필요하지 않고, Mock payload도 opaque 값 하나로 만들 수 있다. 가장 보수적이고 기존 계약과 호환되는 선택이다.
3. 계약 의미가 확정됐으나 실행 코드가 없어 확인할 수 없는 항목은 두 짝 ADR §7.6에 **비차단**으로 분리했다. 「계약 불확정」과 「구현 미검증」을 섞지 않았다.

**임의로 만들지 않은 것.** profile 값 목록 · `stream_selector` 직렬화와 기본 선택 정책 · thumbnail 이미지 전달 방식 · retention·즉시 delete·proxy 파라미터 · `derived_role` 추가 값 · `transform_ref` exact schema · `build_incident_clip` options schema · `media_type`/`role` enum 확장 · `media_stream_refs=[]` 허용 조건 · evidence policy가 소유하는 모든 판정 매핑(`availability` → outcome · `derived_role` 필수성 · 경계 잘림 허용 폭 · `MissingRange.reason` → outcome).

**계약 영향.** 두 계약 전면 개정(`v0.2 → v1`) · 짝 ADR 2건(`Proposed → Accepted`, §7 Consumer Review 기록 신설) · `contract-plate-overlay-readout.md`·`contract-evidence-record-needs.md`·`contract-recording-timeline-asset-span.md`(§4.7·§4.9 경유) · 짝 ADR 3건 고지 · fixture 4건 · 검사기. **하위 호환:** Draft(v0.x)에서 Final(v1)로의 전환이므로 호환성을 보장하지 않는다고 계약이 명시했고, 구현 코드가 없어 migration 대상 payload가 존재하지 않는다.

## 5. 임의로 만들지 않은 것

`MissingRange.source_ref` 규칙 · recording `failure.kind` 값 집합 · 자산 ref `kind` 표기 통일 · `AssetSpan` identity · Draft 계약 2건의 Pending(enum·nullability·`stream_selector`·thumbnail 전달·profile·retention·transform) · relative range `start_ms >= 0` · `kind=ABSOLUTE` 명시 의무 · `span-resolution/v1` payload 재해석 규칙 · `run_ref=null` 확장 · `clip_id` 대응 · `kind → BLOCK/UNKNOWN` 판정 매핑 · 수락일 · 구현 순서. 이들은 §4.6·§8의 항목으로 남긴다.

> **2차 반영에서 이 목록에서 빠진 것(Owner 결정으로 확정됐다):** `MissingRange.source_ref` 규칙(§4.7) · 자산 ref `kind` 표기 통일(§4.8) · `AssetSpan` identity(§4.9 — 「추가하지 않는다」로 확정) · Draft 계약 2건의 Pending 중 `profile_ref` 필수성·`derived_role` 2값·transform 조회 보장·`byte_size`/`duration_sec` nullability(§4.10). **여전히 임의로 만들지 않은 것:** recording `failure.kind` 값 집합 · profile 값 목록 · `stream_selector` 직렬화와 기본 선택 정책 · thumbnail 전달 방식 · retention·즉시 delete·proxy 파라미터 · `derived_role` 추가 값 · `transform_ref` exact schema · `build_incident_clip` options schema · `media_type`/`role` enum 확장 · `media_stream_refs=[]` 허용 조건 · **evidence policy가 소유하는 모든 판정 매핑**(`availability` → outcome · `MissingRange.reason` → outcome · `derived_role` 필수성 · 경계 잘림 허용 폭) · `clip_id` 대응 · `run_ref=null` 확장 · 구현 순서.

## 6. 공개 계약 영향과 버전 표기

**버전 표기 규칙(PM bookkeeping, Owner 이견 시 조정 — 선행 문서 §6과 동일).** 스키마(필드·타입·필수성·enum 값)가 바뀐 계약만 minor를 올린다. 불변조건·예시·포인터·Pending 문구만 바뀐 계약은 버전을 유지한다. major bump는 하지 않는다. **2차 반영에서 필드 삭제(`span_ref`)와 필드 타입 변경(`source_ref`)도 이 규칙에 따라 minor로 처리했다** — 실행 코드와 저장된 payload가 없어 breaking을 감지할 대상이 없고, Owner가 그 범위를 답변에서 지정했다.

| 파일 | 바뀐 절 | 버전 | 하위 호환 |
| --- | --- | --- | --- |
| `contract-job-record-case-view.md` | 헤더 고지 · A§7 · A§13 | `job-record/v1` · `case-view/v1.2` 유지 | 규칙 명시만. 기존 payload 변화 없음 |
| `contract-evidence-record-needs.md` | §11 말미 문구 | 유지 | 문구 |
| `contract-analysis-run-candidate-event.md` | 헤더 고지 · §3 · §3-4 · §6-1 · §7 · §8 | `analysis-run-candidate-event/v1.1` 유지 | 표기 정합 |
| `contract-usage-record.md` | §8 불변조건 12 · §10 | `usage-record/v1.1` 유지 | 표기 정합 |
| `contract-recording-timeline-asset-span.md` | 헤더 · §8.1 · §9 · §10 · §23 · §24 | `span-resolution/v1 → v1.1` (다른 세 버전 유지) | `failure` 키 추가·enum 값 추가. v1 payload 재해석 규칙 없음(구현 없음) |
| `contract-analysis-scope.md` | 헤더 · §5 · §6 · §7 · §8 · §9 · §10 · §12 | `analysis-scope/1.0.0 → 1.1.0` | `kind` 부재 + `start`/`end` = `ABSOLUTE`. 기존 absolute 입력 수정 없이 유효 |
| 자산 계약 2건 | 1차: 변경 없음 · **2차: 전면 개정**(§4.7~§4.10) | `…/v0.2` → **`source-asset-media-stream/v1`** · **`analysis-source-derived/v1`** | Draft(v0.x) → Final(v1). 계약이 호환성을 보장하지 않는다고 명시. 구현 코드가 없어 migration 대상 payload 없음 |
| `contract-plate-overlay-readout.md` | **2차:** 헤더 고지·`Accepted` 줄 · §4 필드표 · 예시 2건 | `plate-readout/v1.1 → v1.2` · `overlay-time-readout/v1.1 → v1.2` | `input_ref.span_ref` **삭제**. 삭제된 값은 Producer가 발급하지 않던 ID이고 구현 payload가 없어 migration 불필요 |
| `contract-evidence-record-needs.md` | **2차:** 헤더 고지 · Upstream 목록 · §8.3(참조 대상 절 신설) · 예시 1건 · §3 규칙 1줄 | `evidence-record/v1.2` · `evidence-needs/v1` **유지** | `ContractRef` 모양·필수성 불변. 허용 `kind`와 의미만 확정 |
| `contract-requirement-report-package.md` | **2차:** 헤더 포인터 갱신 1건(§4.6이 가리키는 자산 사실 필드 계약이 확정됐다는 고지) | `requirement-report/…` 유지 | 포인터·고지만. 판정 매핑은 이 계약·evidence policy가 그대로 소유 |
| `contract-job-record-case-view.md` | **2차:** B절 §6 주석 · §13 `FrameRef`/`thumb_ref` 포인터 종결 표기 | `job-record/v1` · `case-view/v1.2` 유지 | 포인터만 |
| 짝 ADR | 1차: `adr-analysis-scope.md`·`adr-recording-timeline-asset-span.md`(Status 아래 한 줄 고지) · `adr-source-asset-media-stream.md`·`adr-analysis-source-derived.md`(신설, Proposed) · **2차:** 자산 짝 ADR 2건 `Proposed → Accepted` + §7 Consumer Review 기록 신설 · `adr-recording-timeline-asset-span.md`·`adr-plate-overlay-readout.md`·`adr-evidence-record-needs.md`에 후속 변경 고지 1줄 | — | 수락된 ADR 본문은 고치지 않고 Status 아래 고지만 추가했다(`README.md`) |
| 선행 ADR | `adr-data-contract-call-closure-2026-09-07.md` 헤더 고지 · §3·§8.1·§9 해당 행 상태만 갱신(본문 결정 불변) | — | — |
| 포인터 문서 | 1차·2차 공통: `../README.md`(contracts) · `../../../README.md`(docs) · `../../module-architecture.md` 개정 이력·§5-3 안내 · `../../../management/ownership.md` §7-④ 안내 · `../../../../scripts/README.md` · **2차:** `../../mock-pack-v1-refs.md`(폐기 조건 충족 — Status를 폐기로 전환하고 본문은 역사 기록으로 남김) · `contract-job-record-case-view.md` §13의 `FrameRef`·`thumb_ref` 포인터 종결 표기 | — | — |

## 7. 검증 조건과 결과

검사 코드는 `scripts/check_contract_fixtures.py`, 이번 회차 fixture는 `docs/architecture/contracts/fixtures/call-closure-2026-09-08/`에 있다(선행 회차 fixture는 `call-closure-2026-09-07/` 그대로). fixture는 이 문서에서 `ACCEPTED`인 모양만 쓴다. **2차 반영에서 `source_ref` 규칙·자산 ref `kind` 표기·clip provenance가 확정되어 V13~V15 fixture 3건이 추가됐고 V10 fixture가 `span-resolution/v1.2`로 갱신됐다.** 여전히 결정되지 않은 값(recording `failure.kind` 값 집합 · profile 값 목록)은 하드코딩하지 않았다 — `failure.kind`/`code`는 `EXAMPLE_*` 자리표시자이고 검사기는 모양만 본다.

| ID | 검증 조건 | 결과 (2026-09-08 실행) |
| --- | --- | --- |
| V0 | 수정한 계약 12건·Draft 2건의 모든 ```json 예시 + fixture 9건(선행 5 + 이번 4)이 파싱된다 | PASS — 23 검사 0 실패. 언어 표시 없는 펜스(recording §8.1·§9·§24)는 `{`로 시작할 때만 시도하고 실패를 세지 않는다 |
| V1~V5 | 선행 회차 의미 검사 그대로(B01·B02·B03·B05·B06 정상/PARTIAL·B09) | PASS — 선행 fixture 5건 변경 없음 |
| V6 | 수정·신설 문서 22건의 경로 표기(`../`·`adr/`·`docs/`·`scripts/`·계약/ADR 파일명)가 실제 파일을 가리킴 · 계약 본문에 옛 Pending 머리말 잔존 0 | PASS. 선행 회차의 「작성 대기 계약 참조」 NOTE 3건은 Draft가 존재하므로 사라졌다 |
| V8 | CALL-12: 재판독 fixture — 원판독(abstain·`SUCCEEDED`)과 동일 `(case_id, kind, input_fingerprint)` · `force_rerun=true` · 새 `job_id` · 새 execution(`attempt=1`) · 새 `ReadoutRun`(`operation=PLATE_READ`) · 원 run/결과 불변 · 인프라 재시도(같은 `job_id`, `attempt` 2, 새 execution)와 구분. 위반 fixture 3건(`force_rerun=false` 동일 tuple = cache hit · `kind=PLATE_REREAD` 미등재 · `job_id` 재사용)을 검사기가 검출. 계약 A절 §7 등재·§13 종결 표기 확인 | PASS — 5 검사 0 실패 |
| V9 | CALL-13: `usage_refs=[101,102]`인데 원장은 `{101,103}`이 이 Run 소속인 fixture. 원장 기준 소속·합계(0.30)가 기대값과 같고 파생 기준 합계(0.70)와 다르며 `usage_summary.total_cost`는 원장 기준과 정합. `run_ref=null`은 직접 호출 1건만. 두 계약 버전 유지(`v1.1`) 확인 | PASS — 2 검사 0 실패 |
| V10 | CALL-14(`span-resolution/v1.2`로 갱신): 범위초과 `PARTIAL`(`OUT_OF_TIMELINE_RANGE`) · 위치특정 `FAILED` · 위치불특정 `FAILED`(`missing_ranges=[]`) · 전체 범위 밖 `FAILED` 정상 4건. 위반 6건(`PARTIAL`에 `failure` non-null · `FAILED`에 `failure=null` · `failure` 키 부재 · 위치특정 FAILED 미설명 구간 · enum 밖 reason · 빈 `code`) 검출. 계약 §8.1·§9(2건)·§24 예시 4건에 같은 검사 적용. **2차: 모든 `MissingRange`에 §4.7 규칙대로 `source_ref`를 채웠고 계약 본문에 `CALL_REQUIRED` 표기가 남아 있지 않은지도 검사한다** | PASS — 11 검사 0 실패 (+ V4 계약 예시 4건 PASS) |
| V11 | CALL-15(`analysis-scope/1.1.0`): relative 2-range · legacy absolute(`kind` 없음)→`ABSOLUTE` 해석 · 명시 `ABSOLUTE` · `start_ms == end_ms` 정상 4건. 위반 7건(혼합 · `timeline_ref` 누락 · `revision` 누락 · revision 불일치 · `start_ms > end_ms` · `kind` 없이 ms만 · relative-only timeline에 가짜 `ABSOLUTE`) 검출. 계약 §8 예시 2건(`ABSOLUTE`·`TIMELINE_RELATIVE`)이 `1.1.0`이고 규칙 위반 0 | PASS — 12 검사 0 실패 |
| V12 | 계약 16건 모두 짝 ADR 존재 · **2차: 자산 계약 2건 Status가 `Final — Accepted`이고 `**Accepted:** 2026-09-08`이 있으며 옛 Draft 문구가 남아 있지 않다 · 짝 ADR 2건 Status가 `Accepted`이고 `Consumer Review pending`이 남아 있지 않다**(1차의 `Draft`/`Proposed` 검사를 뒤집었다) | PASS — 20 검사 0 실패 |
| V13 | (2차) CALL-16 `MissingRange.source_ref`: `SOURCE_UNAVAILABLE`→`source_asset` · `STREAM_UNAVAILABLE`→`media_stream` · `TIMELINE_GAP`/`OUT_OF_TIMELINE_RANGE`→`null` · 한 resolution 안 혼재 · 위치불특정 `FAILED`(적용 대상 없음) 정상 6건. 위반 6건(키 부재 · 평문 string · non-null 필요한데 `null` · `null`이어야 하는데 채움 · `kind` 불일치 · 대문자 `kind`) 검출. 계약 본문에 평문 `source_ref` 잔존 0·`null` 예시 존재·§23 13·14 등재 확인 | PASS — 13 검사 0 실패 |
| V14 | (2차) CALL-17 + Consumer Review: 자산 `kind` 8값 공간 · `asset_kind` 4값 닫힌 목록과 1:1 대응표 · `AVAILABLE ⇒ byte_size non-null` · 측정 실패를 0으로 꾸미지 않음 · `checked_at` offset-aware · `timeline_ref`⇔`timeline_range` 쌍과 revision 필수 · 파생 자산 lineage 평탄화 · `SOURCE_ASSET`의 빈 lineage는 정상. 정상 6건 · 위반 13건(대문자 `kind` 2곳 · 대응표 불일치 · 대상 아닌 `asset_kind` · `AVAILABLE`에 `byte_size=null` · 0으로 꾸밈 · timeline 쌍 위반 · revision 누락 · lineage 미평탄화 2건 · offset 없는 `checked_at` · 키 부재 · enum 밖 `availability`) 검출. 계약 본문의 값 공간·대응표 등재와 대문자 자산 `kind` 잔존 0 확인 | PASS — 20 검사 0 실패 |
| V15 | (2차) CALL-18: clip provenance가 canonical `AssetSpan`(초 단위 중첩·`sequence` 필수)인지 · 단일 파일·복수 파일·경계 잘림 정상 3건 · 위반 5건(평탄화+ms 혼재 · `sequence` 누락 · 합성 `source_span_ref` · provenance revision 누락 · span이 materialize 범위 미설명) 검출. readout `input_ref`에 `span_ref` 부재·`incident_clip_ref` 필수(정상 2 · 위반 2) · `evidence.interval` ref가 `incident_clip`/`candidate_event`만(정상 2 · 위반 2 — `asset_span`·대문자). 계약 본문 대조: 파생 계약 `IncidentClip` 예시 · plate/overlay 예시 2건 · 헤더 `v1.2` · `EvidenceNeeds`의 `asset_span` 잔존 0과 `candidate_event` 등재 | PASS — 17 검사 0 실패 |
| V7 | `python scripts/check_boundaries.py` | PASS — exit 0. **NOTE 7건**(boundary: 모듈 코드 파일 0개). 선행 회차의 coverage NOTE 5건(`SourceAsset`·`MediaStream`·`RemoteCopy`·`IncidentClip`·`DerivedAsset` 전용 절 없음)과 adr-pair NOTE 2건은 Draft·짝 ADR이 생겨 사라졌다. 이 스크립트는 헤더·번호·enum 변형·짝 존재만 본다. **2차 재실행에서도 FAIL 0** — plate 계약의 새 고지를 헤더 필수 3항목 뒤로 옮겨 `head[:1500]` 검사가 계속 통과한다 |

### 실행 결과 (2026-09-08)

1차 반영 시점:

```text
python scripts/check_contract_fixtures.py
  == 문서 구조: PASS (58 검사, 0 실패)
  == JSON 파싱: PASS (23 검사, 0 실패)
  == 의미 fixture: PASS (54 검사, 0 실패)
python scripts/check_boundaries.py
  PASS — 경계·계약 정합성 위반 0건   NOTE 7 (boundary only)
```

2차 반영(§4.7~§4.10) 후 재실행:

```text
python scripts/check_contract_fixtures.py
  == 문서 구조: PASS (60 검사, 0 실패)
  == JSON 파싱: PASS (26 검사, 0 실패)
  == 의미 fixture: PASS (104 검사, 0 실패)
python scripts/check_boundaries.py
  PASS — 경계·계약 정합성 위반 0건   NOTE 7 (boundary only)
```

의미 검사가 54 → 104로 늘어난 것은 V13·V14·V15 3건(정상 17 · 위반 검출 24 · 계약 본문 대조 3)과 V10의 `source_ref` 확장이다. NOTE 7건은 모두 「모듈 코드 파일 0개」이며 이번 변경으로 생긴 것이 아니다(`NOTE_EXISTING`).

**추가 구조 검사(일회성 스크립트, 저장소에 두지 않음).** 수정·신설 문서 25건(저장소 밖 PM 내부 기록 포함)의 코드 펜스 균형 · 빈 `>` 인용 잔존 · ```json 파싱 — PASS. H1 개수: 신설 문서 전부 1개. **NOTE:** recording 계약·`AnalysisRun` 계약·`EvidenceRecord` 계약·recording 짝 ADR·`module-architecture.md`·`ownership.md`는 절 제목에 `# N.` 단일 `#`을 쓰는 기존 관례라 H1이 여러 개다 — 이번에 도입된 것이 아니고 고치지 않았다(역사적 본문·타 Owner 문서).

**검사 결과의 의미 분리.** 문서 구조·JSON·의미 fixture PASS는 계약 규칙을 코드로 옮겼을 때 서로 다른 구현이 나오지 않는다는 증거이며 제품 동작 증거가 아니다. **구현 통합 PASS — 확인 불가**(`src/daesingo/*`·`apps/web`·`eval/*`에 실행 코드 0개, `apps/prototype`은 계약을 소비하지 않는 UI 프로토타입). **실제 E2E PASS — 확인 불가**(`ownership.md` §7-④ 6기준 실행 기록 없음, Mock Pack fixture는 저장소에 없음). 검사기는 CI에 붙이지 않았다.

## 8. 범위 밖 · 후속 항목

### 8.1 새 결정 회차가 필요한 것

**데이터 계약 영역에 열린 회차는 없다.** §4.6 표의 3건(`MissingRange.source_ref` · 자산 `kind` 표기 · `AssetSpan` identity)은 모두 2026-09-08에 종결됐다 — §4.7·§4.8·§4.9.

**새 회차를 만들지 않은 판단.** 2차 반영에서 처리한 항목 중 서로 다른 Owner의 명시적 결론이 충돌한 것은 없었다. 이견이 있었던 `AssetSpan` identity는 한 Consumer의 **선호**(변경 범위가 작다)와 Decider의 **결정**(영속 모델을 지킨다)의 차이였고, 그 Consumer 본인이 「recording·readout·evidence가 수정 범위를 감당할 수 있다면 막을 근거는 없다」고 확인해 충돌이 해소됐다(§4.9). 나머지는 단일 Owner 범위의 표기·단위·필드표 정리이거나, 확정된 규칙에서 직접 유도되는 예시·fixture·검사기 보정이었다. **다음 항목은 3자 이상이 값 공간을 나눠 가져야 하므로 회차 후보로 남지만, 계약 의미를 막지 않아 지금 회차를 열지 않는다** — `AnalysisSource` profile 값 목록(정철원·서어진·신유민). 계약은 필수성·소유·opaque성을 확정했고 소비 코드는 동등성 비교만 하므로 값이 정해지지 않아도 payload를 만들고 읽을 수 있다.

### 8.1-1 이번 범위 밖의 기존 미결 (`NOTE_EXISTING`)

2차 반영의 대상이 아니었고 이번 변경 때문에 생긴 것도 아니다. 억지로 닫지 않았다.

- **W04 잔여** — `JobExecution` 소비자 확인과 domain `PARTIAL` ↔ runtime `status` 접합. `PENDING_OWNER`, common/runtime ↔ case·search·eval. `v3-readout-run-chain.json`이 실패 run의 status 매핑을 넣지 않은 이유가 이것이다.
- **N02** — `CorrectionRecord` Draft의 Consumer Review(case ↔ evidence) · readout `failure-taxonomy.md`의 `OVERCONFIDENT` 분리(신유민) · eval 정답지 C tier(김대원). `PENDING_OWNER`.
- 경계 검사기 NOTE 7건(모듈 실행 코드 0개) · 일부 문서의 복수 H1(절 제목에 단일 `#`를 쓰는 기존 관례).

### 8.2 결정은 끝났으나 담을 문서·필드가 없는 것 (`ACCEPTED_PENDING_IMPLEMENTATION`)

- recording `SpanResolution.failure.kind` 값 집합을 담을 recording 소유 문서 → 정철원
- `CaseView.candidates[]` stale-revision 표시 필드명 → 유소연(선행 문서 §8.2 유지)
- `TimeResolution` revision provenance 필드 → 김준영(유지)
- readout `failure-taxonomy.md`의 `OVERCONFIDENT` 분리 → 신유민(유지)
- `UsageRecord.run_ref=null`의 「아직 정식 연결 방식이 없는 호출」 존재 여부 판단 → 김준영(§4.2 말미). 현재 계약은 B05 D4 그대로

### 8.3 Consumer Review 대기 (`PROPOSED`)

- **자산 계약 2건 — 종결됐다(§4.10).** 4 Consumer의 검토가 모두 들어오고 필수 조건이 계약에 반영되어 `Final — Accepted`(`…/v1`)로 전환했다. 공개 기록은 두 짝 ADR §7이 소유한다.
- **남아 있는 Consumer Review:** `contract-correction-record.md`(Draft) — case ↔ evidence. N02 항목이며 이번 범위 밖이다(§8.1-1).

### 8.4 별건으로 명시된 것 (`OUT_OF_SCOPE_FOLLOWUP`)

- `timeline_id`+ms offset ↔ eval 정답지 `clip_id` 대응 — eval(김대원) ↔ recording/case. §4.4
- `Abstention Recall`·Wrong Accept Rate 정답지(C tier) — eval(유지)
- `UsageRecord` §10 잔여(통화 · 가격표 · `purge_case`와 원장) — 각 Owner(유지)
- `ReadoutRun.outcome=PARTIAL` 판정 기준 — readout Technical Spec(유지)
- W04 잔여 `JobExecution` 소비자 확인 · domain `PARTIAL`↔runtime `status` 접합 — common/runtime ↔ case/search/eval(유지)
- Mock Pack 재작성 시 relative range·reread·failure fixture 반영 — case(유소연)
- `CorrectionRecord` Draft Consumer Review — case ↔ evidence(유지)
- **profile 태그 체계 — 재판정 완료(2026-09-08).** `profile_ref`의 필수성(non-null)·canonical 값 공간의 **소유(recording)**·opaque성은 계약에 확정됐다(`contract-analysis-source-derived.md` §4.4). 남은 것은 **값 목록과 각 값이 보장하는 media 속성**뿐이며 정철원·서어진·신유민 3자 합의 항목이다. Consumer가 opaque 값의 동등성 비교만 하므로 계약 의미·Mock payload·E2E 정의를 막지 않아 **회차를 열지 않았다**(§8.1)

## 9. 감사 폐쇄 매트릭스 (2026-09-08 현재)

최종 상태 어휘: `CLOSED_VERIFIED` · `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` · `PENDING_OWNER` · `CALL_REQUIRED` · `PENDING_IMPLEMENTATION` · `PENDING_CONSUMER_REVIEW` · `PENDING_VALIDATION` · `NOTE_ACCEPTED`. 결정이 끝났어도 계약 반영과 fixture 검증이 끝나지 않았으면 `CLOSED_VERIFIED`로 쓰지 않는다. 선행 문서에서 바뀌지 않은 행은 「(유지)」로 표시하고 근거는 선행 문서 §9다.

| 감사 ID | 원래 지적 | 공개 결정 근거 | 계약 반영 | 의미 검증 | 최종 상태 | 남은 Owner/작업 |
| --- | --- | --- | --- | --- | --- | --- |
| B01 | (유지) | 선행 §4.1 | 완료 | V1 PASS | `CLOSED_VERIFIED` | — |
| B02 | (유지) | 선행 §4.2 | 완료 | V2 PASS | `CLOSED_VERIFIED` | — |
| B03 | 결과 schema/JSON에 run 연결 없음 | 선행 §4.3 · **이 문서 §4.1(재판독 kind)** | 완료 | V3 PASS · **V8 PASS** | `CLOSED_VERIFIED` | 재판독 `kind` 별건도 종결 |
| B04 | (유지) | 후속 보정 ADR §2 | 완료 | V3 | `CLOSED_VERIFIED` | — |
| B05 | `UsageRecord.run_ref`가 `AnalysisRun` 전용 | 선행 §4.4 · **이 문서 §4.2(`AnalysisRun.usage_refs` 지위)** | 완료 | V3 PASS · **V9 PASS** | `CLOSED_VERIFIED` | `run_ref=null` 확장 문장은 채택 안 함(§8.2) |
| B06 | 미설명 10초 · 완전성·FAILED 원인 규칙 없음 | 선행 §4.5 · **이 문서 §4.3 · §4.7** | recording §8.1·§9·§10.1·§10.2·§23(6~14) · `span-resolution/v1.2` | V4 PASS · V10 PASS · **V13 PASS** | **`CLOSED_VERIFIED`** (2차 반영으로 `source_ref` 잔여 1건도 닫혔다) | 정철원: `failure.kind` 값 집합을 담을 recording 소유 문서(`PENDING_IMPLEMENTATION`, §8.2) |
| B07 | evidence에 필요한 자산 사실·표면 미작성 | 선행 §4.6 · **이 문서 §4.5 · §4.8 · §4.9 · §4.10** | 계약 2건 `Final — Accepted`(`…/v1`) · 짝 ADR 2건 `Accepted` | **V14 PASS · V15 PASS** | **`CLOSED_VERIFIED`** (`PENDING_CONSUMER_REVIEW`에서 진전) | 비차단 Pending: profile 값 목록(3자) · `stream_selector` · thumbnail 전달 방식. evidence ASSET 판정 policy fixture는 evidence 소유 |
| B08 | relative timeline ↔ ISO8601 scope | 선행 §4.7 · **이 문서 §4.4** | `AnalysisScope` 1.1.0 | **V11 PASS** | **`CLOSED_VERIFIED`** | `clip_id` 대응은 별건(§8.4) |
| B09 | (유지) | 선행 §4.8 | 완료 | V5 PASS | `CLOSED_VERIFIED` | 표시 필드명·TimeResolution 필드는 `PENDING_IMPLEMENTATION` 별도 추적 |
| B10 | (유지) | 후속 보정 ADR §2 | 완료 | 문구 | `CLOSED_VERIFIED` | fingerprint 알고리즘 미결 유지 |
| B11 | (유지) | 후속 보정 ADR §2 | — | — | `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` | 정철원 확인 없음 |
| B12 | (유지) | 후속 보정 ADR §2 · 선행 §4.10 | — | — | `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` | 수락일 **확인 불가** 유지 |
| W01~W03 · W05 · W06 | (유지) | 선행 §9 | 완료 | — | `CLOSED_VERIFIED` | — |
| W04 | (유지) | 선행 §4.4 | — | — | `PENDING_OWNER` | `JobExecution` 소비자 확인 · domain PARTIAL↔status |
| W07 | ref 접두어/위치 인코딩 · `thumb_ref` 자산 종류 | 선행 §4.9 · **이 문서 §4.5 · §4.8 · §4.9 · §4.10** | `FrameRef` 필드가 수락된 계약 §5에 존재 · `thumb_ref=FrameRef` §7 명시 · 자산 `kind` 값 공간 소유 확정 · 합성 span ref·위치 인코딩 금지 명문화 | V1 PASS · **V14·V15 PASS** | `CLOSED_VERIFIED` | — |
| N01 | (유지) | 선행 §7 · 이 문서 §7 | 검사기 범위 확장 | V7 재실행 | `NOTE_ACCEPTED` | E2E 아님 |
| N02 | (유지) | 선행 §4.10 | — | — | `PENDING_OWNER` | 신유민 · 김대원 · 유소연↔김준영 |
| N03 | (유지) | 이 문서 §7 말미 | — | — | `NOTE_ACCEPTED` | Trajectory 1회차 기록 비어 있음 |

**집계 (2차 반영 후).** BLOCK 12건 중 `CLOSED_VERIFIED` **10**(B01·B02·B03·B04·B05·B06·**B07**·B08·B09·B10) · `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` 2(B11·B12). **종결되지 않은 BLOCK ID는 0건이고 열린 결정 회차도 0건이다.** WARN 7건 중 6건 `CLOSED_VERIFIED`, W04만 `PENDING_OWNER`. NOTE 3건 중 N01·N03 `NOTE_ACCEPTED`, N02 `PENDING_OWNER`.

## 10. 종결 판정

### 10.1 1차 반영 시점의 판정 (기록)

**데이터 계약 감사 — `CONTRACT_AUDIT_PARTIAL`.** 종결 조건 6개 중 ①(Owner 결정) B07 자산 스키마의 Consumer Review와 CALL-16~18이 남아 부분 충족 · ②(공개 ADR) 충족 · ③(계약 반영) `ACCEPTED` 범위 충족 · ④(fixture 검증) V1~V5·V8~V11 충족 · ⑤(BLOCK 상태 0건) 충족 · ⑥(새 CALL이 필요한 계약 BLOCK 0건) **미충족** — B06 잔여 CALL-16, B07 선행 CALL-17·CALL-18이 열려 있다. 따라서 「데이터 계약 감사 종결」을 선언하지 않는다. 선행 문서의 `CALL_REQUIRED` 2건(B06·B08)은 닫혔고 B07이 `PENDING_IMPLEMENTATION`에서 `PENDING_CONSUMER_REVIEW`로 진전했다.

### 10.2 2차 반영 후의 판정 (§4.7~§4.10 반영 · 현재)

**BLOCK 축은 종결됐다.** 종결 조건 6개가 모두 충족됐다 — ①(Owner 결정) B07 자산 스키마의 Consumer Review 4건과 결정 회차 3건이 모두 닫혔다 · ②(공개 ADR) §4.7~§4.10과 두 짝 ADR §7 · ③(계약 반영) 계약 6건·짝 ADR 5건 · ④(fixture 검증) V1~V5·V8~V15 · ⑤(BLOCK 상태 0건) · ⑥(새 CALL이 필요한 계약 BLOCK 0건). **BLOCK 12건 전부 종결이고 열린 결정 회차는 0건이다.**

**그러나 감사 전체는 `CONTRACT_AUDIT_PARTIAL`로 유지한다.** 종결 조건 6개는 BLOCK(B01~B12) 축만 본다 — 감사 원문의 지적은 BLOCK 12건 · WARN 7건 · NOTE 3건이고, 그중 **두 건이 아직 Owner 결정 대기**다.

| 남은 항목 | 상태 | Owner | 왜 이번에 닫지 않았나 |
| --- | --- | --- | --- |
| W04 잔여 — `JobExecution` 소비자 확인 · domain `PARTIAL` ↔ runtime `status` 접합 | `PENDING_OWNER` | common/runtime ↔ case·search·eval | **이번 회차 범위(자산 계약·`MissingRange`·`AssetSpan`)와 무관한 기존 미결이다.** 계약 의미 수준의 접합이며 구현 확인 수준이 아니다. 억지로 닫지 않고 `NOTE_EXISTING`으로 분리했다(§8.1-1) |
| N02 — `CorrectionRecord` Draft Consumer Review · readout taxonomy `OVERCONFIDENT` 분리 · eval 정답지 C tier | `PENDING_OWNER` | 유소연↔김준영 · 신유민 · 김대원 | 같은 이유. `CorrectionRecord`는 여전히 Draft이며 이번 Review 대상이 아니었다 |

**따라서 「데이터 계약 감사 종결」을 선언하지 않는다.** 대신 다음을 명확히 구분한다.

- **B07·B06을 포함한 BLOCK 축과 자산 계약 영역: 종결.** 추가 Owner 결정도, 추가 Consumer Review도 필요하지 않다. 자산 계약 2건에 남은 Pending은 전부 비차단이며 각각 소유와 비차단 근거가 §4.10·두 짝 ADR §7.4에 적혀 있다.
- **감사 전체: `CONTRACT_AUDIT_PARTIAL`** — W04·N02 두 건의 `PENDING_OWNER`가 남았다. 둘 다 이번 회차 범위 밖이고 각각 Owner가 지정되어 있다.

**다음 단계(Mock 생성·통합 E2E) 준비도 — `READY_WITH_NON_BLOCKING_GAPS`.** 근거:

1. **schema·enum·null·identity·reference가 모두 확정됐다.** Mock payload를 만드는 데 필요한 것 — 필드 목록과 타입, 키 부재 vs `null`, enum 값 공간과 소유 문서, identity의 발급·재사용 규칙, ref가 가리키는 대상 — 이 자산 계약 2건과 §4.7·§4.9로 전부 채워졌다. 남은 Pending 중 payload 값이 필요한 것은 `profile_ref` 하나이고 그것은 **opaque**로 확정돼 어떤 문자열이든 유효하다.
2. **Producer와 Consumer가 같은 직렬화를 읽는다.** 자산 `kind`의 값 공간이 한 문서에 있고 정확 문자열 비교가 강제되며, `asset_kind` ↔ `asset_ref.kind` 대응표가 있어 두 필드를 각자 해석할 여지가 없다. 단위(초)와 revision 동반 규칙이 recording 경계 전체에 통일됐다.
3. **fixture가 정상·부분·실패·경계를 표현한다.** V1~V5·V8~V15 12세트 = 정상 40여 건 + 위반 검출 60여 건. 부분 성공(`PARTIAL` + `OUT_OF_TIMELINE_RANGE`), 실패(위치 특정/불특정 `FAILED`), 경계(clip의 timeline 경계 잘림 · `start_ms == end_ms` · legacy absolute range · `SOURCE_ASSET`의 빈 lineage)가 모두 있다.
4. **통합 E2E 시나리오의 입력·출력·권위 데이터·판정 지점을 계약만으로 정의할 수 있다.** 권위 데이터의 소유가 각 계약에 명시돼 있고(자산 사실 → `AssetFacts`·`checked_at` / 사용량 → `UsageRecord.run_ref` / 사건 구간 → `IncidentClip.source_provenance` / 시간 → `TimeResolution` / 요건 판정 → `RequirementReport`), 판정 지점의 소유(evidence policy vs recording 사실)가 분리돼 있다.
5. **비차단 gap과 그 회피 방법.** ① `AnalysisSource` profile 값 목록 — Mock은 opaque 값 하나로 만들고 재사용 판정은 동등성 비교로 검증한다. ② `stream_selector` 직렬화·기본 선택 정책 — Mock은 stream을 명시적으로 지정하고 selector 경로를 E2E 판정 대상에서 제외한다. ③ thumbnail 이미지 전달 방식 — `thumb_ref`(FrameRef)까지만 검증하고 이미지 획득은 제외한다. ④ **W04의 domain `PARTIAL` ↔ runtime `status` 매핑 — E2E에서 이 셀을 PASS/FAIL 판정 대상으로 삼지 않는다.** `v3-readout-run-chain.json`이 이미 같은 이유로 그 매핑을 넣지 않았다. ⑤ `derived_role` 추가 값·`transform_ref` schema·retention — 등재 2값과 「조회 가능」 보장만으로 시나리오를 쓴다.
6. **계약 불확정과 실행 코드 부재를 구분했다.** 위 gap은 계약 불확정이고, 두 짝 ADR §7.6의 항목은 **계약은 확정됐으나 실행 코드가 없어 확인할 수 없는** 것이다. 후자는 Mock·E2E 착수를 막지 않고 오히려 그 단계에서 확인할 대상이다.

**이 문서가 하지 않은 것.** 이번 반영에서 Mock을 생성하거나 통합 E2E를 구현·실행하지 않았다. 준비도 판정까지다.

**모든 외부 감사 — 선언 불가.** `SECURITY_REVIEW_PENDING`(`pre-deploy-security-review.md` §1 표의 확인일·판정 칸이 모두 비어 있다) · `TRAJECTORY_REVIEW_PENDING`(`tool-trajectory-review.md` §4 두 회차 표가 비어 있다) · `IMPLEMENTATION_NOT_VERIFIED`(모듈 실행 코드 0개) · `E2E_NOT_VERIFIED`(통합 실행 기록 없음). **데이터 계약 감사의 BLOCK 축이 닫혔더라도 이들은 자동으로 닫히지 않는다.** 이번 회차에서 그 별도 감사를 새로 수행하지 않았고 현재 근거로 상태만 판정했다.

## 11. 후속 변경 규칙

### 11.1 이 회차에 적용한 규칙

1차 반영 때 적힌 규칙은 「CALL-16~18 답이 오거나 자산 계약 Consumer Review가 끝나면 이 문서를 고치지 않고 **변경 ADR**을 쓴 뒤 §3·§9 표의 해당 행만 갱신한다」였다.

**이번에는 같은 문서 안에 §4.7~§4.10으로 이어 붙였다.** 근거:

- 결정이 **같은 날(2026-09-08)** 들어왔고, 이 문서가 이미 그 결정들을 `CALL_REQUIRED`로 지목한 원장이다. 별도 문서로 나누면 같은 날짜의 결정 원장이 둘이 되어 「어느 것이 현재인가」를 매번 판단해야 한다.
- 이 문서의 역할(「2026-09-08 이후의 현재 결정 원장」)로 표현할 수 없을 만큼 독립된 아키텍처 결정이 아니었다 — 세 결정 모두 §4.3·§4.5가 남긴 잔여를 닫는 것이고, Consumer Review 결과는 각 계약의 **짝 ADR §7**이 자기완결적으로 소유한다.
- **§4.1~§4.6의 본문은 고치지 않았다.** §4.5·§4.6에는 「이후 경과는 §4.7~§4.10」이라는 포인터만 붙였고, 갱신한 것은 상태표(§3·§9)와 검증·영향·판정 절(§6·§7·§8·§10)이다 — 상태표는 원장이므로 갱신 대상이라는 1차 규칙 그대로다.
- 중복 ADR을 기계적으로 만들지 않는다는 원칙을 따랐다. 이 예외와 그 근거는 문서 헤더에도 적었다.

### 11.2 이후 규칙

- **데이터 계약 영역에 열린 결정 회차는 없다.** 새 결정이 필요해지면(§8.1의 profile 값 목록 3자 합의 등) 이 문서를 고치지 않고 **새 결정 원장 ADR**을 쓴 뒤 §3·§9 표의 해당 행만 갱신한다.
- 자산 계약 2건의 개정은 각 계약과 그 **짝 ADR**이 소유한다. 두 짝 ADR은 수락됐으므로 본문을 고치지 않고, 결정이 바뀌면 새 ADR을 쓴다(`README.md`).
- W04·N02는 각 Owner의 항목이다. 닫히면 이 문서 §9 표의 해당 행만 갱신하고 그때 감사 전체의 `CONTRACT_AUDIT_*` 판정을 다시 내린다.
- 과거 감사 보고(`../../../management/contract-consistency-audit-2026-09-06.md`)·선행 ADR 본문은 수정하지 않는다.
