# ADR — 데이터 계약 감사 접합부 종결 (2026-09-07)

**Status:** Accepted — 아래 §4에 `ACCEPTED`로 표기한 결정에 한정. `PENDING`·`CALL_REQUIRED`·`OUT_OF_SCOPE` 항목의 수락을 뜻하지 않는다
**Date:** 2026-09-07 (Owner 결정 완료일 · 계약 반영일 동일)
**Decider:** 각 결정 단위의 Decider는 §4 표에 있다. 이 문서의 작성·계약 반영은 PM(김준영)이 했고, PM은 어느 결정도 Owner를 대신해 만들지 않았다
**선행 문서:** `adr-consistency-followup-2026-09-06.md`(2026-09-06 감사 후 보정 · 이 문서 이전의 Pending 원장) → **이 문서가 2026-09-07 이후의 현재 결정 원장이다**
**감사 원문:** `../../../management/contract-consistency-audit-2026-09-06.md` — 본문을 수정하지 않는다. 지적 ID(B01~B12 · W01~W07 · N01~N03)는 그 문서의 §2를 따른다

> **이 문서를 읽는 법.** 2026-09-06 감사가 남긴 BLOCK 8건(B01·B02·B03·B05·B06·B07·B08·B09)은 결정 회차 CALL-8~CALL-11에서 Owner 결정을 받았다. 회차 원문은 PM 내부 기록이며 저장소에 없다. **이 ADR은 그 원문을 열지 않아도 계약을 수정·구현할 수 있도록 결정 내용을 자기완결적으로 적은 공개 문서**이고, 계약 파일 수정의 유일한 근거다. 계약 본문이 이 문서와 다르면 계약 본문이 규칙을 소유하고 이 문서는 근거·상태만 소유한다(`README.md`).

---

## 1. 배경과 해결 대상

2026-09-06 외부 감사(`contract-consistency-audit-2026-09-06.md`)는 계약 14건이 접합부에서 서로 다른 구현을 허용한다고 판정했다. 후속 보정 ADR(2026-09-06)은 PM 권한 안의 복원·철회만 하고 BLOCK 8건을 네 회차(CALL-8~11)로 Owner에게 넘겼다. 이 문서는 그 회차의 **최종 결론**을 공개 결정으로 옮기고, 계약 반영·검증 상태·남은 Pending을 하나의 표로 닫는다.

문서 권위 순서는 바뀌지 않는다: `product-spec.md` → `module-architecture.md`(v4) → `core-user-flow.md` → `ownership.md` → 공개 ADR(이 문서) → Final Contract.

## 2. 결정 단위의 상태 어휘

| 상태 | 뜻 |
| --- | --- |
| `ACCEPTED` | Owner가 결정하고 필요한 Producer/Consumer가 확인했다. 계약 반영 대상 |
| `ACCEPTED_PENDING_IMPLEMENTATION` | 결정은 끝났으나 그 결정을 담을 계약·문서가 아직 없다(예: recording 자산 계약 2건). 임의로 필드를 만들지 않는다 |
| `PENDING_OWNER` | Owner 결정이 아직 없다. 계약에 반영하지 않는다 |
| `OUT_OF_SCOPE_FOLLOWUP` | 회차에서 「별건·범위 밖·이번에 닫지 않는다」로 명시된 항목. 해당 감사 ID의 종결 근거에 섞지 않는다 |

회차 원문에서 앞부분의 중간 의견과 뒤의 최종 절이 다르면 **최종 절만** 결정으로 취급했다. 앞부분의 「조정 필요·미해결」은 과거 논의 과정이며 이 문서에 옮기지 않았다.

## 3. 결정 요약표

| 감사 ID | 결정 상태 | 공개 결정 요약 | Decider/확인자 | 영향 영역 | 검증 조건 |
| --- | --- | --- | --- | --- | --- |
| B01 | `ACCEPTED` | `needs_review`는 `evidence`가 값과 함께 제공, `case`는 재계산 없이 변환. `occurred_at`에 `user_corrected`·`source{kind,label_key}` 추가 후 4단계 변환. 위치 대표값 `address→place_name→user_hint`, `coord`·`search_keyword`는 별도 필드. `needs_review`와 `info_state`는 독립, web은 `info_state`만 본다 | Decider 유소연(`case`) · 확인 김준영(`evidence`) · 신유민(`web`) | `CaseView` B절 · `EvidenceRecord` · `TimeResolution` | §7-V1 fixture: null·관찰·추론·사용자수정·파일명시각·`user_hint` 입력에서 기대 `info_state` 일치, evidence 보장 2건 위반 0 |
| B02 | `ACCEPTED` | `requirements_evidence`/`requirements_package` 두 객체 분리. report 선택 3단계(현재 `EvidenceRecord.record_ref` basis → `supersedes_ref` head → `evaluated_at` 최신). 세 gate 분리 유지. 미실행이면 `null` | Decider 유소연 · 확인 김준영 · 신유민 | `CaseView` B절 · `RequirementReport` §5.2-1 | §7-V2 fixture: 옛 basis `FINAL_PACKAGE` PASS가 수정 후 화면에 남지 않음, supersede head 선택, 미실행 `null` |
| B03 | `ACCEPTED` | 판독 결과 최상위 필수 `run_ref: ContractRef{kind:"readout_run", ref}`. `readout_id`·`run_ref` 둘 다 유지, 재시도는 새 `run_id`+새 `readout_id`. `Observation.produced_by.run_ref.kind="readout_run"` 등재. 정상/완전실패 예시 2건 | Decider 신유민(`readout`) · 확인 유소연(`case`) · 김대원(`eval`) | `PlateReadout`/`OverlayTimeReadout` · `ReadoutRun` · `Observation` | §7-V3 fixture: 결과→run→usage→execution 역추적, FAILED run에 결과 0건, 최상위와 `produced_by.run_ref` 동일 |
| B05 | `ACCEPTED` | `UsageRecord.run_ref`를 `ContractRef \| null`로, `kind ∈ {analysis_run, readout_run}`. 원장 `run_ref`가 authoritative, `ReadoutRun.usage_refs`는 조회 편의 파생값. `null`은 Run 개념이 없는 직접 호출만 | Decider 김준영(`common/runtime`)·신유민(`readout`) · 확인 김대원(`eval`). D5~D8은 Owner 보충, 소비자 미열람(§4.4) | `UsageRecord` · `ReadoutRun` §4 | §7-V3 fixture: readout usage row가 `readout_run` ref를 가짐, 직접 호출만 `null` |
| B06 | `ACCEPTED` (직렬화 일부 `CALL_REQUIRED`) | `spans + missing_ranges`가 `requested_range`를 빠짐없이 설명. 같은 `MediaStream`의 중복 coverage 금지, 다른 stream의 동일 시간대 허용. 범위 일부 초과는 `PARTIAL`+`missing_ranges`, 전체 불가는 `FAILED`, 입력 오류는 입력 검증 실패. `FAILED`는 machine-readable 원인 표면화. §8.1의 미설명 10초는 예시 오류 | Decider 정철원(`recording`) · 확인 김준영(`evidence`) · 서어진(`search`) | `SpanResolution` §8~§10 · §23 | §7-V4 fixture: 예시 coverage 합집합 = 요청 범위, stream별 중복 0. **범위 밖 `MissingRange.reason` 값과 top-level failure 필드는 CALL-14** |
| B07 | `ACCEPTED` (스키마 `ACCEPTED_PENDING_IMPLEMENTATION`) | opaque ref 유지 + 최소 자산 사실(asset_ref · kind/derived role · byte size · 판정 시점 존재·가용 · lineage · 조건부 duration+timeline_range)을 **recording lookup → case 수집 → evidence 입력 주입**으로 전달. evidence는 recording을 직접 호출하지 않는다. `FrameRef` 의미 6건 보장. `stream_selector` 직렬화는 미확정 | Decider 정철원 · 확인 김준영 · 유소연 · 신유민 · 서어진 | `RequirementReport` §2·§4 · recording 계약 §12 · v4 §5-3 안내 | Asset Facts 필드 계약이 `contract-source-asset-media-stream.md`·`contract-analysis-source-derived.md`에 나온 뒤 fixture. 지금은 경계·최소 목록만 반영 |
| B08 | `ACCEPTED`(방향) · 직렬화 `CALL_REQUIRED` | relative-only timeline은 정상 usable. 가짜 absolute datetime 생성 금지. anchor 부재만으로 Search 차단 금지. `AnalysisScope`는 timeline-relative range를 **명시적으로 구분해** 수용하는 방향으로 확장 | Decider 정철원(불변조건) · 확인 서어진(`search`) · 유소연(`case`). **직렬화 Decider는 유소연(`AnalysisScope` Owner)** | `AnalysisScope` §9·§10·§12 | 직렬화가 CALL-15로 확정된 뒤 fixture. 지금은 locked 스키마 유지 + 방향·금지만 기록 |
| B09 | `ACCEPTED` | `CandidateEvent.span.timeline_revision` 추가. Candidate는 rebase 후 mutate하지 않는다. 현재 표시 시각은 현재 revision projection, provenance는 생성 당시 `{timeline_id, timeline_revision}`. revision이 다르면 `case`가 비교해 `CaseView`에 「과거 revision 기준」 표시 | Decider 정철원 · 확인 서어진(필드 승인) · 유소연(표시) · 김준영(evidence provenance 동일 형태) | `AnalysisRun+CandidateEvent` §2·§4·§6 · `CaseView` §13 · `TimeResolution` 후속 | §7-V5 fixture: span에 revision 존재, 현재 revision과 비교로 stale 판정 재현. CaseView 표시 필드명·TimeResolution 필드는 `ACCEPTED_PENDING_IMPLEMENTATION` |
| W07 잔여 | `ACCEPTED` | `CaseView.candidates[].thumb_ref`는 `FrameRef`(`fr_` 계열). 실제 이미지는 case가 recording lookup을 거쳐 projection, web→recording 직접 호출 금지. 이미지 전달 형태(URL/ref/endpoint)는 recording 자산 계약에서 | Decider 정철원 · 확인 유소연 · 신유민 | `CaseView` B절 §5·§8·§13 | §7-V1: 예시 `thumb_ref`가 위치 인코딩 없는 `fr_` opaque id |
| W02 잔여 | `ACCEPTED` | `evidence`의 `case_type_display`/`report_type_display`/`violation_display`/`preview_ref` 네 필드는 **삭제 의도 없음**. 기존 방향 유지 | Decider 유소연 | `CaseView` §13 Pending 문구 | 문구 확인 |
| W04 잔여 | 부분 종결 | `UsageRecord`의 소비자 확인은 B05 회차의 신유민·김대원 회신이 첫 문서화된 확인. **`JobExecution` 쪽 소비자 확인과 domain `PARTIAL`↔runtime `status` 접합은 남는다** | 김준영 · 확인 신유민·김대원(UsageRecord만) | `UsageRecord` §9 · `JobExecution` §11 | 문구 확인 |
| B12 잔여 | `PENDING_OWNER` 유지 | `JobRecord+CaseView` 최초 수락일 — Owner가 기억하지 못함. **확인 불가**로 유지, 추정 날짜를 넣지 않는다 | 유소연 | `CaseView` 헤더 | 해당 없음 |

## 4. 결정 상세

### 4.1 B01 — `CaseView` 값 상태 파생 (Decider 유소연 · 확인 김준영 · 신유민)

**채택한 규칙**

1. **`needs_review` 출처.** `evidence`가 `EvidenceValue`마다 `needs_review: boolean`을 값과 함께 제공한다. `case`는 재계산하지 않고 그대로 파생 입력으로 쓴다. 판정 기준·threshold는 evidence 정책이 소유한다.
2. **`occurred_at` → `event_time_display`.** `case`는 `source`를 들여다보지 않는다.

   | 조건 (위에서부터 첫 일치) | `info_state` |
   | --- | --- |
   | `occurred_at` 부재 | `INFO_UNKNOWN` |
   | `occurred_at.user_corrected == true` | `INFO_USER_CONFIRMED` |
   | `occurred_at.resolution_status == NEEDS_REVIEW` | `INFO_NEEDS_REVIEW` |
   | `occurred_at.resolution_status == OK` | `INFO_SOURCE_VERIFIED` |

   이 표가 안전하려면 `evidence`가 `OK`를 엄격하게 부여해야 한다 — **검증된 영상 화면 시각 또는 사용자 확정만 `OK`**. 파일명·metadata로 계산한 시각은 값은 유지하되 `NEEDS_REVIEW`로 내려온다. `EvidenceRecord.occurred_at`에 `user_corrected: boolean`과 `source: {kind, label_key}`를 추가한다. `source`는 `TimeResolution` 결과의 snapshot이고 `observability`는 두지 않는다.
3. **`location_display` 대표값.** 우선순위 `address → place_name → user_hint` 중 존재하는 첫 값 하나만 `value`에 싣는다. 여러 값을 합쳐 새 문자열을 만들지 않는다. 대표값이 `user_hint`이면 `info_state = INFO_NEEDS_REVIEW`. `coord`와 `search_keyword`는 대표값에 합성하지 않고 `location_display` 안의 **별도 필드**로 내려보낸다(포맷은 web). `source_label_key`는 `value`의 출처만 뜻한다. 셋 다 없으면 `value = null`, `INFO_UNKNOWN`.
4. **`needs_review` ↔ `info_state`.** 독립 필드다(동치 불변조건 아님). `evidence`가 보장한다: `user_corrected=true`와 `needs_review=true` 동시 발생 금지 · `value=null`과 `needs_review=true` 동시 발생 금지 · `needs_review`는 「값은 있지만 사용자 확인이 필요한 경우」에만. **web 소비 규칙: web은 `info_state`만 보고 표시하며 `needs_review`를 직접 해석하지 않는다.** `INFO_UNKNOWN`(값 없음·입력 필요)과 `INFO_NEEDS_REVIEW`(값 있음·확인 필요)로 화면 분기가 충분하다.

`EvidenceValue` 기반 display(`plate_display`·`location_display`)의 파생 순서는 기존 5단계를 유지한다 — `value==null → INFO_UNKNOWN` / `user_corrected → INFO_USER_CONFIRMED` / `needs_review → INFO_NEEDS_REVIEW` / `source.observability==OBSERVED → INFO_SOURCE_VERIFIED` / 그 외 `INFO_AI_ESTIMATED`. 입력 세 개(`needs_review` 출처·`occurred_at` 변환·위치 대표값)가 이번에 정해져 파생이 닫힌다.

**책임 경계.** 검토 필요 판정과 `OK` 엄격성은 `evidence`(`TimeResolution`·`EvidenceRecord`). 대표값 선택·display 조립·web 소비 규칙은 `case`(`CaseView`). web은 어느 입력도 재해석하지 않는다.

**null·실패·미실행.** `occurred_at` 부재 = `INFO_UNKNOWN`. `EvidenceRecord`가 아직 없으면 `CaseView.evidence = null`(기존 불변조건 2). `needs_review=true`인 null 값은 존재할 수 없다.

**기각한 방향.** ① `case`가 선택된 source의 `observability`를 역참조해 `SOURCE_VERIFIED`를 판정 — `occurred_at`은 `EvidenceValue`가 아니고 `TimeResolution` 내부를 들여다보는 것은 projection 범위 밖이라 철회. ② `needs_review == (info_state == INFO_NEEDS_REVIEW)` 동치 불변식 — `value==null ∧ needs_review=true`가 `INFO_UNKNOWN`으로 떨어지는 반례가 있어 철회. ③ `coord`를 포맷해 대표값으로 사용 — 포맷은 값 선택이 아니라 화면 책임이라 철회. ④ `search_keyword`·`user_hint` 둘 다 대표값 제외 — GPS가 없을 때 사용자 단서를 유지하는 제품 방향에 따라 `user_hint`는 대표값 후보에 포함(확인 필요 상태 조건부).

**PM 해석 주의(결정 아님).** `event_time_display.needs_review`(boolean)는 결정 표에 직접 등장하지 않는다. 계약에는 「`occurred_at.resolution_status == NEEDS_REVIEW`를 그대로 옮긴다」로 적었다 — 입력이 그것뿐이고 web은 이 boolean으로 분기하지 않기 때문이다. 대표값이 `user_hint`이면서 `user_corrected=true`인 조합의 우선순위는 회차에서 다루지 않았다. 둘 다 Owner 이견 시 이 절을 고친다.

**계약 영향.** `contract-job-record-case-view.md` B절 §5·§6·§7·§8·§9·§10·§12·§13 · `contract-evidence-record-needs.md` §3·§4.4·§10 · `contract-time-resolution.md` §4(`OK` 부여 조건).

### 4.2 B02 — `requirements`가 어느 `RequirementReport`인가 (Decider 유소연 · 확인 김준영 · 신유민)

**채택한 규칙**

- **(b) 두 객체 분리** — `requirements_evidence`(scope=`EVIDENCE` report의 projection) · `requirements_package`(scope=`FINAL_PACKAGE` report의 projection). 각각 `{ readiness, checks }` 또는 `null`. `readiness`는 해당 report의 `overall`과 같은 값 공간.
- **report 선택 3단계** (scope별로 적용):
  1. `basis.evidence_record_ref`가 **현재** `EvidenceRecord.record_ref`와 일치하는 report만 후보로 남긴다
  2. 남은 후보 중 `supersedes_ref` 체인의 head를 쓴다
  3. 그래도 복수면 `evaluated_at` 최신값을 쓴다
- **세 gate 분리 유지.** `EVIDENCE_SUFFICIENT` = `requirements_evidence` 판정 · `PACKAGE_READY` = `requirements_package` 판정(+`ReportPackage` 존재) · `USER_REVIEWED` = case 소유 `user_reviewed`. 셋을 하나의 readiness로 합치지 않는다.
- **`null` 허용 조건.** `requirements_evidence = null` — 현재 basis의 Evidence 검사 미실행. `requirements_package = null` — package-scope 검사 미실행 또는 필요한 파생물 미생성.

**불변조건(기존 gate 정의 §5.2와 (b)의 귀결).** `package`가 non-null이면 `requirements_package`가 non-null이고 `readiness ∈ {PASS, WARN}`. `stage=READY`이면 `requirements_package`가 non-null이고 `readiness ∈ {PASS, WARN}`.

**stale 의미.** 사용자 수정으로 새 `EvidenceRecord`가 생기면 옛 basis의 report는 1단계에서 탈락한다. 따라서 수정 직후 재검사 전에는 `requirements_evidence = null`이 정상이고, 옛 `FINAL_PACKAGE` PASS가 화면에 남지 않는다.

**기각한 방향.** (a) 단일 `requirements` + `scope` + 「FINAL_PACKAGE 우선」 — `EVIDENCE` gate를 가리고 옛 basis report를 노출해 철회(2026-09-06 PM 확정 철회를 유지). (c) 별도 `gates{...}` 표시 필드 — 필요하면 두 report와 `user_reviewed`에서 **단순 파생되는 표시값**으로만 허용하고 새 authoritative 상태로 두지 않는다(이번에 필드를 만들지 않음). 「`case_rev`/`selection_rev` 일치」만으로 선택 — correction 후 `selection_rev`가 유지될 수 있어 옛 report가 다시 선택되므로 `record_ref` basis 기준으로 대체.

**계약 영향.** `contract-job-record-case-view.md` B절 §5·§6·§7·§8·§9·§10·§12 · `contract-requirement-report-package.md` §5.2-1(규칙 소유를 `CaseView`로 이관, 포인터만 남김).

### 4.3 B03 — 판독 결과와 `ReadoutRun`의 연결 (Decider 신유민 · 확인 유소연 · 김대원)

**채택한 규칙**

1. `PlateReadout`·`OverlayTimeReadout` 최상위에 **필수** `run_ref: ContractRef` — `{ "kind": "readout_run", "ref": <ReadoutRun.run_id> }`. `contract-observation.md` §3의 공통 `ContractRef` 모양을 그대로 쓴다.
2. **불변조건은 결과 존재 여부에 건다:** 「결과가 존재하면 `run_ref`가 존재하고 유효하다」. `outcome`(`SUCCEEDED`/`PARTIAL`) 값과 무관. 역방향(run → 결과)은 보장하지 않으며 `ReadoutRun.result_refs[]`를 추가하지 않는다.
3. `readout_id`(결과 식별자)와 `run_ref`(실행 식별자)는 **둘 다 유지**. 실행이 완전히 실패하면 `ReadoutRun`만 남고 결과는 생성되지 않는다(`ReadoutRun` 1건 : 결과 0~1건). **재시도는 새 `run_id` + 새 `readout_id`**. 재시도 결과 간 supersede는 `readout` 소유가 아니므로 결과 계약에 `supersedes_ref`를 추가하지 않는다 — 어느 결과가 현재 값인지는 `case` 진행 상태·`CaseView` 소관.
4. `Observation.produced_by.run_ref.kind = "readout_run"`을 `contract-observation.md` §6에 등재한다. 판독 결과의 최상위 `run_ref`와 내부 `observation.produced_by.run_ref`는 같은 실행을 가리킨다.
5. 예시는 두 경우: 정상(`ReadoutRun.outcome=SUCCEEDED`, `failure=null`, 결과가 `run_ref`로 참조) · 완전 실패(`outcome=FAILED` + `failure.kind/code`, 결과 미생성). 필드명은 `outcome`이다(`state` 아님).

**소비자 확인으로 함께 닫힌 것**

- **run ↔ execution 1:1은 `case`의 orchestration 불변조건이다.** `readout`은 `JobExecution`을 모르므로(v4 원칙 6) `readout`이 보장하는 것은 「public 함수 호출 1회 = `ReadoutRun` 1건」이다. 1:1은 **worker 구현 규칙** 「1 execution 안에서 readout public 함수를 정확히 1회 호출한다」로 성립하며, 이 규칙은 `contract-job-execution.md`(Producer common/runtime)에 둔다. `run_id`는 `job_id`처럼 재사용되지 않는 1회성 식별자이나 `execution_id`와 **동일 identity가 아니다** — `run_ref` 자리에 `execution_ref`를 넣지 않는다.
- **`ReadoutRun → JobExecution` 역추적은 `JobExecution.produced`의 `{kind:"readout_run", ref}`가 담당한다.** `ReadoutRun`에 `execution_ref`를 추가하지 않는다.
- **`JobRecord.kind`에 `OVERLAY_TIME_READ`를 등재한다**(유소연). `PLATE_READ`·`OVERLAY_TIME_READ`는 항상 별도 `job_id`로 발주한다. `ReadoutRun.operation`과의 대응은 이름이 같은 값끼리다(`PLATE_READ↔PLATE_READ`, `OVERLAY_TIME_READ↔OVERLAY_TIME_READ`). `running_jobs[].label_key`에 `job.overlay_time_read`를 등재한다.
- **`ReadoutRun.operation`에 `PLATE_REREAD`를 추가하지 않는다.** 재판독은 readout에게 `read_plate` 호출 1회이고 `operation`은 public capability와 1:1이다. `PLATE_REREAD`는 `EvidenceNeeds.kind` 값 공간이다.
- **`eval` 집계 단위(김대원):** 실패 분류는 **run 단위**(`ReadoutRun.operation`이 번호판/화면시각을 가르므로), 비용은 **execution 단위**. `readout` 쪽 추가 필드는 필요 없다.

**Owner가 함께 결정했으나 B03 종결 범위 밖으로 표시한 항목 (R-9-5 ~ R-9-7 · Decider 신유민 · 결과 계약 Producer-side).** 같은 예시 블록을 두 번 고치지 않기 위해 이번 회차에 반영했다. 소비자(`case`·`eval`)에게 별도 확인을 받지 않았으며 B03 종결 근거로 세지 않는다.

- **R-9-5** 최상위 `run_ref`가 authoritative이고 필수. `readout`이 생산하는 `Observation`은 `produced_by.run_ref`를 **항상** 채운다(`Observation` v1의 optional을 위반하지 않는 Producer-side 강화). 두 값은 항상 같다.
- **R-9-6** 판독 예시의 `observation` 블록을 `Observation<T> v1`에 맞춘다 — `contract_version`·`support_refs`(빈 배열)·`produced_by` 추가, v1에 없는 `kind` 삭제, `provenance`는 삭제하지 않고 `input_ref` 안으로 이동(Source-derived 불변조건의 실제 근거), overlay의 `source`는 `{ "kind": "readout.overlay_ocr" }`(namespaced). readout의 `source.kind`와 `TimeResolution`의 시각 source 값 공간을 같은 enum으로 합치지 않는다.
- **R-9-7** `abstain_reason`이 authoritative. `observation.reason.code`는 abstain 외 사유(`UNKNOWN`/`ERROR` 진단)에만 쓰고 `abstained=true`일 때 중복 채우지 않는다.

**기각한 방향.** (b) 평문 `run_id: string` — 다른 계약의 ref 표기와 어긋남. (c) `ReadoutRun.result_refs[]` — 「결과 → run 역추적만 보장」과 방향이 반대. 「재시도 시 같은 `readout_id`가 다른 run에서 나올 수 있다」(회차 카드의 초기 제안) — Owner 결정과 맞지 않아 옮기지 않는다. 재판독을 별도 `JobRecord.kind=PLATE_REREAD`로 두는 안 — `EvidenceNeeds` 값 공간과 겹치고 `operation`에 대응 값이 없어 readout이 반대. **재판독 발주의 `kind`·identity 처리는 `case` 소관으로 남았다(§8 CALL-12).**

**계약 영향.** `contract-plate-overlay-readout.md` 헤더·§3·§4·§6·§10 · `contract-readout-run.md` 헤더·§2·§5·§6 · `contract-observation.md` §6·§14 · `contract-job-record-case-view.md` A절 §7·§10·§12 · `contract-job-execution.md` §9.

### 4.4 B05 — `UsageRecord`의 `ReadoutRun` 참조 (Decider 김준영 · 신유민 · 확인 김대원)

**채택한 규칙 (D1~D4, 소비자 확인 있음)**

- **D1** `UsageRecord.run_ref`를 `ContractRef | null`로 바꾼다. 모양은 `contract-observation.md` §3의 `ContractRef`를 포인터로 참조한다(`JobExecution.produced`와 같은 방식).
- **D2** `run_ref.kind`는 **`analysis_run` · `readout_run`** 두 값으로 닫는다. 전역 `ContractRef.kind` 어휘를 닫는 것이 아니라 「run identity를 뜻하는 kind가 이 둘」이라는 필드 수준 제약이다. 새 run 종류는 계약 개정으로만 추가한다.
- **D3** **`UsageRecord.run_ref`가 authoritative다.** `ReadoutRun.usage_refs`는 조회 편의용 파생값이며 두 값이 어긋나면 `run_ref`가 기준이다. 필드는 남기되 「authoritative 아님」을 명시한다. 양방향 정합을 불변조건으로 강제하지 않는다 — 어긋난 순간 판정 주체가 다시 필요해지고 그 판정이 `eval`의 비용 숫자에 들어가기 때문이다(김대원).
- **D4** `run_ref = null`은 **Run 개념이 없는 직접 호출**만 뜻한다. `AnalysisRun`·`ReadoutRun`에 속한 사용량은 반드시 해당 `ContractRef`를 채운다.

**Owner(`UsageRecord` 소유 김준영)가 반영을 위해 보충한 항목 (D5~D8 · 소비자 미열람 · 이견 시 이 절을 고친다)**

- **D5** §7의 OCR 예시(`operation: READOUT_PLATE`, `run_ref: null`)는 D4 위반 예시가 되므로 `{ "kind": "readout_run", "ref": "rr_001" }`로 교체한다. §7의 원 논점(`token_usage` null vs 0)은 유지.
- **D6** `execution_ref`와 `run_ref`는 둘 다 채운다 — 전자는 「실행 1회분의 총 비용」, 후자는 「어느 logical run에 속하는가」. `ReadoutRun → JobExecution` 역추적은 `JobExecution.produced`가 담당하므로 `ReadoutRun`에 필드를 추가하지 않는다.
- **D7** 계약 버전을 `usage-record/v1.1`로 올린다(`string|null → ContractRef|null`은 타입 변경). v2로 가지 않는 근거는 후속 보정 ADR §3의 「Canonical v1 Freeze는 BLOCK 4건 반영 뒤」다.
- **D8** 불변조건 추가: ⑨ `run_ref`는 `{kind, ref}`이며 `kind ∈ {analysis_run, readout_run}` ⑩ Run에 속한 호출을 `run_ref=null`로 기록하지 않는다 ⑪ `ReadoutRun.usage_refs`와 `UsageRecord.run_ref`가 어긋나면 후자가 기준.

**기각한 방향.** (b) `readout_run_ref` 별도 필드 — run 종류마다 필드·집계 분기가 는다. (c) `ReadoutRun.usage_refs` 단방향만 — 원장을 한 번 스캔해 집계하는 `eval` 형태가 readout에서만 갈라진다.

**함께 닫힌 것.** W04 잔여 중 `UsageRecord` 부분(첫 문서화된 소비자 확인). **닫지 않은 것:** `AnalysisRun.usage_refs[]`의 지위(파생값 표기)는 `search` Owner 확인 대상 — §8 CALL-13. `Abstention Recall`은 별건(§8). `UsageRecord` §10의 통화·가격표·`purge_case` 3건은 B05와 무관하게 남는다.

**계약 영향.** `contract-usage-record.md` 헤더·§4·§5·§7·§8·§9·§10 · `contract-readout-run.md` §4·§5 · `contract-job-execution.md` §11.

### 4.5 B06 — `SpanResolution` 요청 범위 완전성 (Decider 정철원 · 확인 김준영 · 서어진)

**채택한 규칙**

- `spans + missing_ranges`는 `requested_range` 전체를 **빠짐없이** 설명한다. 설명되지 않는 구간이 없어야 한다.
- 같은 `MediaStream`에서 동일 logical coverage가 중복되면 안 된다. 서로 다른 `MediaStream`이 같은 시간대를 가리키는 것은 허용한다.
- timeline 범위를 일부 벗어나는 정상 요청은 usable 구간이 있으면 `PARTIAL`, 범위 밖 부분은 `missing_ranges`로 명시한다. 요청 전체가 resolve 불가능하면 `FAILED`.
- `start >= end`, 음수 범위, 잘못된 timeline reference 같은 **입력 오류**는 정상 `SpanResolution`이 아니라 입력 검증 실패로 처리한다.
- `FAILED`는 `spans=[]`만으로 끝내지 않고 원인을 machine-readable하게 표면화한다. 위치를 특정할 수 있는 전체 실패는 요청 범위 전체를 `missing_ranges`로 설명하고, 그것만으로 표현할 수 없는 실패는 top-level failure reason을 둔다. recording은 실패 사실과 원인만 제공하고, 그것이 신고 규칙상 `BLOCK`/`UNKNOWN`인지는 `evidence`가 판단한다.
- §8.1 예시의 `[120,130)` 미설명 10초는 별도 의미가 없는 **예시 오류**다. 새 reason 값을 만들지 않는 최소 수정으로 `requested_range.end_sec`를 `120.0`으로 고친다.

**결정되지 않아 반영하지 않은 것 → CALL-14.** ① 범위 밖 구간을 담는 `MissingRange.reason` 값(현재 enum은 `TIMELINE_GAP`/`SOURCE_UNAVAILABLE`/`STREAM_UNAVAILABLE`) ② top-level failure reason의 필드명·모양. 둘 다 임의로 만들지 않았다.

**계약 영향.** `contract-recording-timeline-asset-span.md` 헤더·§8.1·§9·§10·§23.

### 4.6 B07 — `evidence`가 필요한 자산 사실과 전달 경계 (Decider 정철원 · 확인 김준영 · 유소연 · 신유민 · 서어진)

**채택한 규칙**

- opaque ref 규칙은 유지한다. `ReportPackage.assets.*` 조립은 opaque ref로 충분하지만 `RequirementReport`의 ASSET 판정은 자산 사실 없이 계산할 수 없으므로 **최소 자산 사실을 별도로 제공**한다.
- 이번 통합의 최소 자산 사실: `asset_ref` · asset kind / derived role · byte size · 판정 시점의 존재·가용 여부 · derived-from / lineage. `duration + timeline_range`는 `FINAL_PACKAGE`에서 사건 전후 coverage rule을 실제 적용하는 경우 조건부.
- 제외: resolution · fps · codec · 원본 무변형 checksum · 번호판 가시성 · 화면 timestamp 표시 여부. 뒤의 둘은 recording 파일 사실이 아니라 readout observation을 근거로 `evidence`가 판정한다.
- **전달 경계:** `case/orchestration → recording asset lookup → Asset Facts → case/orchestration → evidence.check_requirements(..., assets)`. **recording이 lookup capability를 소유하고 case가 수집해 evidence에 주입한다. evidence는 recording을 직접 호출하지 않는다.** `sa_`/`da_` 접두어를 파싱해 kind를 추론하지 않고 정식 필드로 받는다.
- **`FrameRef` 보장 6건:** `fr_<opaque-id>` opaque identity · 동일 `MediaStream`의 동일 canonical frame은 같은 `FrameRef` · ref 내부를 파싱하지 않음 · `read_frame(frame_ref)`로 실제 frame 획득 가능 · `media_stream_ref`와 source-relative offset을 계약 필드로 조회 가능 · Timeline rebase가 일어나도 같은 `FrameRef`가 다른 frame을 가리키지 않음.
- `AnalysisSource`는 search가 실제 Provider 분석 입력으로 사용할 수 있는 형태를 보장한다. **`stream_selector` 직렬화는 이번에 확정하지 않는다.**
- 이번 evidence 접합 때문에 `FrameRef`·Fine input·stream selector를 앞당겨 확정할 필요는 없다.

**`ACCEPTED_PENDING_IMPLEMENTATION`.** Asset Facts의 정확한 필드명·타입·lookup 함수 서명은 recording 자산 계약 2건(`contract-source-asset-media-stream.md` · `contract-analysis-source-derived.md`, Owner 정철원)이 소유한다. 그 전까지 공용 계약에는 **경계와 최소 사실 목록**만 적고 필드를 만들지 않는다.

**계약 영향.** `contract-requirement-report-package.md` §2·§4.6(신설) · `contract-recording-timeline-asset-span.md` §12 · `module-architecture.md` §5-3 상태 안내 · `mock-pack-v1-refs.md`.

### 4.7 B08 — relative-only Timeline ↔ `AnalysisScope` (불변조건 Decider 정철원 · 확인 서어진 · 유소연)

**채택한 규칙 (방향)**

```
relative-only RecordingTimeline        → 정상 usable 상태
가짜 absolute datetime 생성            → 금지
absolute anchor 부재만으로 Search 차단  → 금지
```

따라서 ISO8601-only인 `AnalysisScope`는 **timeline-relative range를 수용하는 방향으로 확장**한다. 최소 의미: absolute range와 relative range를 명시적으로 구분 · relative range는 timeline-relative 좌표 사용 · 가짜 기준일/가짜 ISO8601 생성 금지.

**기각한 방향.** 「anchor가 없으면 case가 검색을 막고 notice로 표현」(회차 중간 의견) — recording 불변조건 「anchor 부재만으로 Search 차단 금지」와 충돌해 최종에서 채택되지 않았다.

**`CALL_REQUIRED` → CALL-15.** 정확한 serialization은 `AnalysisScope` Owner(유소연)와 Consumer(서어진)가 정한다. `AnalysisScope` §5 스키마는 **locked**이므로 이번에 필드를 바꾸지 않고 §9·§10·§12에 방향·금지·Pending만 기록한다. `eval`(김대원)은 fixture Producer라 같이 확인해야 한다.

**계약 영향.** `contract-analysis-scope.md` 헤더·§9·§10·§12.

### 4.8 B09 — 사용 Timeline revision 추적 (Decider 정철원 · 확인 서어진 · 유소연 · 김준영)

**채택한 규칙**

- `CandidateEvent.span`에 `timeline_revision`을 추가한다: `{ timeline_id, timeline_revision, start_ms, end_ms, representative_ms }`. Candidate만 보아도 좌표가 어느 `RecordingTimeline` revision 기준인지 복원된다.
- 과거 Candidate는 rebase 후 최신 revision 기준으로 **mutate하지 않는다**.
- `Candidate provenance = 생성 당시 timeline_id + timeline_revision` · `현재 화면 표시 시각 = 현재 RecordingTimeline revision으로 projection`. 둘이 다르면 `case`가 비교해 `CaseView`에 「과거 timeline revision 기준」임을 표시할 수 있게 한다. `search`는 revision 값만 노출하고 stale 판정·표시는 하지 않는다.
- `evidence`는 동일 `{timeline_id, revision}` 형태를 자기 provenance(`TimeResolution`)에 맞춘다.

**`ACCEPTED_PENDING_IMPLEMENTATION`.** ① `CaseView.candidates[]`의 stale 표시 필드명(case) ② `TimeResolution`의 revision provenance 필드 위치(evidence). 둘 다 방향은 합의됐고 필드는 구현 시 Owner가 정한다. 이번에 만들지 않는다.

**기각한 방향.** `AnalysisRun.timeline_ref`에만 두는 안(회차 중간 의견) — 최종에서 `span` 보존으로 확정. 후보를 현재 anchor로 조용히 환산 — provenance 손실이라 금지.

**계약 영향.** `contract-analysis-run-candidate-event.md` 헤더·§2·§4·§4-1·§6-2·§7·버전 · `contract-recording-timeline-asset-span.md` §5 · `contract-job-record-case-view.md` §13 · `contract-time-resolution.md` 후속 항목.

### 4.9 부록 결정 — `CaseView.candidates[].thumb_ref` (Decider 정철원 · 확인 유소연 · 신유민) — W07 잔여

`thumb_ref`는 **`FrameRef`**(`fr_<opaque-id>`)다. `CandidateEvent.thumbnail_ref`가 이미 `FrameRef | null`이므로 같은 자산 종류를 projection한다. web은 recording을 직접 호출하지 않으므로 실제 thumbnail 이미지는 B07과 같은 경계(`case → recording read/lookup → projection → CaseView → web`)로 전달한다. **이미지 전달 형태(URL/ref/endpoint)는 recording 자산 계약에서 정한다** — 이번에 정하지 않는다.

### 4.10 기타 잔여 항목

- **W02 잔여 (Decider 유소연):** `evidence`의 네 display 필드는 의도적으로 뺀 것이 아니다. 기존 방향(유지)이 맞다. `CaseView` §13의 「유지/삭제 의도 확인 대기」 문구를 종결한다.
- **B12 잔여:** 최초 수락일은 Owner가 기억하지 못한다. **확인 불가**로 유지한다.
- **N02 중 `eval` 지표 정의 (김대원 회신):** 정답 라벨은 `READABLE + 정답 문자열` / `UNREADABLE`. Wrong Accept Rate 분모는 `abstained=false`인 전체, 분자는 정답 불일치 또는 정답 `UNREADABLE`. Abstention Recall 분모는 정답 `UNREADABLE`, 분자는 그중 `abstained=true`. 계약 필드 추가는 필요 없다. **정답지는 현재 없다**(A tier는 번호판 마스킹으로 문자 정답이 없어 C tier 확보 후 항목). 이 정의는 `eval` 소유이고 이 문서는 상태만 기록한다 — `modules/eval/`은 Owner가 적는다.
- **N02 중 taxonomy `OVERCONFIDENT` 분리 (김대원 동의 · Owner 신유민):** `PLATE_RECOGNITION`과 분리해 readout `failure.kind`를 6개로 닫기로 했다. `modules/readout/decisions/failure-taxonomy.md`는 Owner가 갱신한다(`ACCEPTED_PENDING_IMPLEMENTATION`). 이 문서는 값을 복제하지 않는다.

## 5. 임의로 만들지 않은 것

새 enum 값(범위 밖 `MissingRange.reason` · stale 표시 필드) · 새 상태 전이 · threshold · retry/cache 정책 · 자산 이미지 전달 방식 · `stream_selector`/relative range/failure reason 직렬화 · 삭제·보관 정책 · 통화 정책 · 평가 데이터셋 · 수락일 · 구현 순서. 이들은 §8의 Pending·CALL 항목으로 남긴다.

## 6. 공개 계약 영향과 버전 표기

**버전 표기 규칙(PM bookkeeping, Owner 이견 시 조정).** 스키마(필드·타입·필수성)가 바뀐 계약만 minor를 올린다. 불변조건·예시·포인터·Pending 문구만 바뀐 계약은 버전을 유지한다. major bump는 하지 않는다(후속 보정 ADR §3 「Freeze는 BLOCK 반영 뒤」).

| 파일 | 바뀐 절 | 버전 |
| --- | --- | --- |
| `contract-job-record-case-view.md` | 헤더 · A§7·§10·§12 · B§5·§6·§7·§8·§9·§10·§12·§13 | `job-record/v1` 유지 · `case-view/v1.1 → v1.2` |
| `contract-evidence-record-needs.md` | 헤더 · §3 · §4.4 · §10 | `evidence-record/v1.1 → v1.2` · `evidence-needs/v1` 유지 |
| `contract-time-resolution.md` | §4 · §16(신설 후속) | 유지 |
| `contract-requirement-report-package.md` | 헤더 · §2 · §4.6(신설) · §5.2-1 | 유지 |
| `contract-plate-overlay-readout.md` | 헤더 · §3 · §4 · §6 · §10 | `plate-readout/v1 → v1.1` · `overlay-time-readout/v1 → v1.1` |
| `contract-readout-run.md` | 헤더 · §2 · §4 · §5 · §6 | 유지 |
| `contract-observation.md` | §6 · §14 | 유지 |
| `contract-usage-record.md` | 헤더 · §4 · §5 · §7 · §8 · §9 · §10 | `usage-record/v1 → v1.1` (D7) |
| `contract-job-execution.md` | §9 · §11 | 유지 |
| `contract-analysis-run-candidate-event.md` | 헤더 · §2 · §4 · §4-1 · §6-2 · §7 | `analysis-run-candidate-event/v1 → v1.1` (계약 §9 자체 규칙: serialization 변경) |
| `contract-recording-timeline-asset-span.md` | 헤더 · §5 · §8.1 · §9 · §10 · §12 · §23 | 유지 |
| `contract-analysis-scope.md` | 헤더 · §9 · §10 · §12 | 유지 (locked 스키마 불변) |
| 포인터 문서 | `../README.md`(contracts) · `adr-consistency-followup-2026-09-06.md`(§7 포인터 절 추가) · `../../module-architecture.md` 상태 안내·개정 이력 · `../../../management/ownership.md` §7-④ 안내 · `../../../README.md` · `../../mock-pack-v1-refs.md` | — |

버전이 오른 계약의 짝 ADR(`adr-job-record-case-view.md` · `adr-evidence-record-needs.md` · `adr-plate-overlay-readout.md` · `adr-usage-record.md` · `adr-analysis-run-candidate-event.md`)에는 Status 아래에 이 문서를 가리키는 한 줄 고지만 붙인다. 본문은 고치지 않는다.

## 7. 검증 조건과 결과

검사 코드는 `scripts/check_contract_fixtures.py`, fixture는 `docs/architecture/contracts/fixtures/call-closure-2026-09-07/`에 있다. fixture는 이 문서에서 `ACCEPTED`인 모양만 쓴다. 결정되지 않은 값(범위 밖 reason · relative range · stale 표시 필드명)은 하드코딩하지 않았다.

| ID | 검증 조건 | 결과 (2026-09-07 실행) |
| --- | --- | --- |
| V0 | 수정한 계약 12건의 모든 ```json 예시 + fixture 5건이 파싱된다 | PASS — 17 검사 0 실패. 언어 표시 없는 펜스(recording §8.1·§24, pseudo-schema)는 `{`로 시작할 때만 시도하고 실패를 세지 않는다 |
| V1 | B01: `EvidenceRecord` fixture 5건에서 §4.1 규칙으로 계산한 `info_state`가 기대 `CaseView` display와 일치(관찰·추론·사용자수정·파일명시각·`user_hint`·값 없음). evidence 보장 2건(`user_corrected∧needs_review` · `null∧needs_review`)의 위반 fixture를 검사기가 거부. `CaseView` §8 예시의 `thumb_ref`가 `fr_` opaque, `requirements_*` 두 키, `location_display.coord/search_keyword` 존재 | PASS — 8 검사 0 실패 |
| V2 | B02: 감사 §3.2 반례(report 4건·`EvidenceRecord` 2건)에서 3단계 선택이 t1에 `e1`/`p1`, t2에 `e3`/`null`을 고른다 — 옛 basis `FINAL_PACKAGE` PASS(`p1`)가 수정 후 화면에 남지 않고, superseded `e2`가 아닌 head `e3`를 고른다. 같은 basis·supersede 없음 → `evaluated_at` 최신 | PASS — 3 검사 0 실패 |
| V3 | B03/B05: 결과 `run_ref` → `ReadoutRun` → `UsageRecord.run_ref`(kind `readout_run`) → `JobExecution.produced`/`usage_refs` → `JobRecord.kind`(`PLATE_READ`·`OVERLAY_TIME_READ` ↔ `operation`) 정·역방향. 최상위 `run_ref` == `observation.produced_by.run_ref`. FAILED run(`rr_882`)에 결과 0건이고 그 usage는 `run_ref` non-null. `run_ref=null`은 직접 호출 1건만. execution마다 `readout_run` produced 정확히 1개(1:1). 계약 본문 예시(plate/overlay `run_ref`, `usage_205` non-null, `JobExecution.produced` ContractRef, `observation` §6 `readout_run` 등재) 대조 | PASS — 2 검사 0 실패 |
| V4 | B06: fixture(다른 stream 동일 시간대 허용 · gap 완전 설명)와 계약 §8.1·§24 예시의 `spans ∪ missing_ranges == requested_range`, 같은 stream 중복 0. 감사가 지적한 원래 §8.1(미설명 10초)과 same-stream overlap을 위반 fixture로 넣어 검사기가 잡는지 확인 | PASS — 6 검사 0 실패. FAILED·범위초과 케이스는 CALL-14 대기라 없음 |
| V5 | B09: `span.timeline_revision` 존재·`>=1`, 현재 `RecordingTimeline.revision`(2)과 비교해 stale=true, revision 1이면 false. 계약 §2·§4-1 예시에 필드 존재. `contract_version` v1.1 | PASS — 2 검사 0 실패 |
| V6 | 문서: 수정 문서 15건의 경로 표기(`../`·`adr/`·`docs/`·`contracts/`·계약/ADR 파일명)가 실제 파일을 가리킴 · 계약 본문에 「통합 Pending B0x」류 옛 머리말 잔존 0 | PASS — 32 검사 0 실패. **NOTE 3건**: 작성 대기 recording 자산 계약 2건을 가리키는 참조(`RequirementReport`·recording 계약·이 문서) — 없는 것이 현재 상태 |
| V7 | `python scripts/check_boundaries.py` | PASS — exit 0. **NOTE 12건**(boundary 7: `src/daesingo/{case,recording,search,readout,evidence}`·`eval`·`apps/web`에 코드 파일 0개 · coverage 5: `DerivedAsset`·`IncidentClip`·`MediaStream`·`RemoteCopy`·`SourceAsset` 전용 절 없음). 이 스크립트는 헤더·번호·enum 변형만 본다 |

실행 명령과 출력 요약:

```text
python scripts/check_contract_fixtures.py
  == 문서 구조: PASS (32 검사, 0 실패)   NOTE 3
  == JSON 파싱: PASS (17 검사, 0 실패)
  == 의미 fixture: PASS (22 검사, 0 실패)
python scripts/check_boundaries.py
  PASS — 경계·계약 정합성 위반 0건   NOTE 12
```

**검사 결과의 의미 분리.** 문서 구조 PASS(V6·V7) · JSON PASS(V0) · 의미 fixture PASS(V1~V5) · Owner 결정 반영 PASS(§3 표의 `ACCEPTED` 항목 전부 계약 반영) · **구현 통합 PASS — 확인 불가**(`src/`·`apps/`에 실행 코드 0개) · **실제 E2E PASS — 확인 불가**(`ownership.md` §7-④ 6기준 실행 기록 없음, Mock Pack fixture는 저장소에 없음). fixture PASS는 계약 규칙을 코드로 옮겼을 때 서로 다른 구현이 나오지 않는다는 증거이며 제품 동작 증거가 아니다. 검사기는 CI에 붙이지 않았다.

## 8. 범위 밖 · 후속 항목

### 8.1 새 결정 회차가 필요한 것 (`CALL_REQUIRED`)

| 회차 | 결정 경계 | Decider | 같이 볼 사람 | 왜 지금 닫아야 하나 |
| --- | --- | --- | --- | --- |
| CALL-12 | 재판독(`PLATE_REREAD` Need) 발주의 `JobRecord.kind`와 캐시 identity — `kind=PLATE_READ + force_rerun=true`인가, 별도 kind인가 | 유소연(`case`) | 신유민(`readout`) · 김준영(`evidence`) | 1:1 불변조건과 `operation` 대응이 이 값에 걸린다. abstain은 `outcome=SUCCEEDED`라 같은 kind 재발주는 cache hit |
| CALL-13 | `AnalysisRun.usage_refs[]`를 `ReadoutRun.usage_refs`와 같은 「조회 편의 파생값 · authoritative는 원장」으로 표기할지 | 서어진(`search`) | 김대원(`eval`) | D3의 비대칭. 계약 의미 변경이 아니라 표기 정합 |
| CALL-14 | `SpanResolution`의 ① 범위 밖 구간 `MissingRange.reason` 값 ② top-level failure reason 필드 모양 | 정철원(`recording`) | 김준영(`evidence`) · 서어진(`search`) | B06 의미는 닫혔고 직렬화만 남았다. fixture의 FAILED·범위초과 케이스가 이것을 기다린다 |
| CALL-15 | `AnalysisScope` timeline-relative range의 직렬화(absolute/relative 구분 방식·좌표 단위·필수성) | 유소연(`case`) | 서어진(`search`) · 김대원(`eval` fixture Producer) · 정철원(`recording`) | B08 방향은 닫혔고 locked 스키마 변경은 Owner 결정이 필요하다 |

회차 문서는 PM 내부 기록이다. 답이 오면 이 문서의 변경 ADR을 쓰고 §9 표를 갱신한다.

### 8.2 결정은 끝났으나 담을 계약이 없는 것 (`ACCEPTED_PENDING_IMPLEMENTATION`)

- Asset Facts 필드 · lookup 서명 · `FrameRef` 필드 · thumbnail 이미지 전달 형태 → recording 자산 계약 2건(정철원)
- `CaseView.candidates[]` stale-revision 표시 필드명 → case(유소연)
- `TimeResolution` revision provenance 필드 → evidence(김준영)
- `failure-taxonomy.md`의 `OVERCONFIDENT` 분리 → readout(신유민)

### 8.3 별건으로 명시된 것 (`OUT_OF_SCOPE_FOLLOWUP`)

- `Abstention Recall`·Wrong Accept Rate 정답지(C tier) — eval
- `UsageRecord` §10 잔여 3건(통화 KRW 고정 · 가격표 저장/개정 · `purge_case`와 원장) — 각 Owner
- `ReadoutRun.outcome=PARTIAL` 판정 기준 — readout Technical Spec
- W04 잔여의 `JobExecution` 소비자 확인 · domain `PARTIAL` ↔ runtime `status` 접합 — common/runtime ↔ case/search/eval
- Mock Pack 재작성 시 위 규칙 반영 — case(유소연). 현재 저장소에 Mock Pack fixture는 없다(2026-09-07 시점 revert 상태)
- `CorrectionRecord` Draft의 Consumer Review·값 선택 규칙 — case ↔ evidence (N02)

## 9. 감사 폐쇄 매트릭스

최종 상태 어휘: `CLOSED_VERIFIED` · `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` · `PENDING_OWNER` · `CALL_REQUIRED` · `PENDING_IMPLEMENTATION` · `PENDING_VALIDATION` · `NOTE_ACCEPTED`. 결정이 끝났어도 계약 반영과 fixture 검증이 끝나지 않았으면 `CLOSED_VERIFIED`로 쓰지 않는다.

| 감사 ID | 원래 지적 | 공개 결정 근거 | 계약 반영 | 의미 검증 | 최종 상태 | 남은 Owner/작업 |
| --- | --- | --- | --- | --- | --- | --- |
| B01 | `needs_review` 원천 없음 · `occurred_at` 비동형 입력 · 파일명 시각이 SOURCE_VERIFIED | §4.1 | `CaseView` B절 · `EvidenceRecord` §3 · `TimeResolution` §4 | V1 PASS | `CLOSED_VERIFIED` | — (PM 해석 2건은 §4.1 말미, 이견 시 수정) |
| B02 | PM 단독 scope 확정 · 옛 basis report 노출 · gate 가림 | §4.2 | `CaseView` B절 · `RequirementReport` §5.2-1 | V2 PASS | `CLOSED_VERIFIED` | — |
| B03 | 결과 schema/JSON에 run 연결 없음 | §4.3 | plate/overlay · `ReadoutRun` · `Observation` · `JobRecord` · `JobExecution` | V3 PASS | `CLOSED_VERIFIED` | 재판독 `kind`는 CALL-12(별건, B03 종결과 무관) |
| B04 | `produced` string[] 예시 | 후속 보정 ADR §2 (2026-09-06 복원) | 완료 | V3에서 `produced` ContractRef 파싱 PASS | `CLOSED_VERIFIED` | — |
| B05 | `UsageRecord.run_ref`가 `AnalysisRun` 전용 | §4.4 | `UsageRecord` · `ReadoutRun` §4 | V3 PASS | `CLOSED_VERIFIED` | D5~D8 소비자 열람은 통보 대상. `AnalysisRun.usage_refs` 표기는 CALL-13(NOTE) |
| B06 | 미설명 10초 · 완전성·FAILED 원인 규칙 없음 | §4.5 | recording §8.1·§9·§10·§23 | V4 PASS(정상·PARTIAL) | `CALL_REQUIRED` | CALL-14: 범위 밖 reason 값 · failure 필드. 확정 후 FAILED fixture 추가 |
| B07 | evidence에 필요한 자산 사실·표면 미작성 | §4.6 | `RequirementReport` §2·§4.6 · recording §12 · v4 §5-3 안내 | 불가(필드 없음) | `PENDING_IMPLEMENTATION` | 정철원: recording 자산 계약 2건. 이후 evidence ASSET 판정 fixture |
| B08 | relative timeline ↔ ISO8601 scope | §4.7 | `AnalysisScope` §9·§10·§12(방향·금지만) | 불가(직렬화 없음) | `CALL_REQUIRED` | CALL-15: 유소연·서어진·김대원 |
| B09 | Candidate에 사용 revision 없음 | §4.8 | `AnalysisRun+CandidateEvent` v1.1 · recording §5 | V5 PASS | `CLOSED_VERIFIED` | 표시 필드명(case)·TimeResolution 필드(evidence)는 `PENDING_IMPLEMENTATION`으로 별도 추적 |
| B10 | 캐시 namespace 누락 | 후속 보정 ADR §2 (복원) | 완료 | 문구 확인 | `CLOSED_VERIFIED` | fingerprint 알고리즘은 미결 유지 |
| B11 | PM 추가 작업 순서를 호출 없이 닫음 | 후속 보정 ADR §2 (철회) | `ownership.md` 제안/확인 대기 표기 | — | `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` | 정철원 확인은 받지 않았다. 순서 자체는 여전히 제안 |
| B12 | 수락일 임의 확정 | 후속 보정 ADR §2 (제거) · §4.10 | `CaseView`·`AnalysisScope` 헤더 「확인 대기」 유지 | — | `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` | 실제 수락일은 **확인 불가**(Owner 기억 없음). 다시 채우지 않는다 |
| W01 | 헤더·포인터·제목 정리 미완 | 후속 보정 ADR §2 | 완료 | V6 링크 검사 PASS | `CLOSED_VERIFIED` | — |
| W02 | 베이스·의도 단정 | 후속 보정 ADR §2·§4 · §4.10 | `CaseView` §13 문구 종결 | — | `CLOSED_VERIFIED` | 네 필드 유지가 Owner 의도로 확인됨 |
| W03 | 완료/미답/발송 대기 혼재 | 후속 보정 ADR §2 · 이 문서 §2·§9 | 이 표가 현재 원장 | — | `CLOSED_VERIFIED` | — |
| W04 | PM 신규 결정 범위 축소 서술 | 후속 보정 ADR §2 · §4.4 | `UsageRecord` §9 종결 · `JobExecution` §11 잔여 표기 | — | `PENDING_OWNER` | `JobExecution` 소비자 확인 · domain PARTIAL↔status 접합 (case·eval) |
| W05 | 규칙 복제 | 후속 보정 ADR §2 · §4.2(`5.2-1` 포인터화) | report 선택 규칙 소유를 `CaseView` 한 곳으로 | V6 | `CLOSED_VERIFIED` | taxonomy 값은 readout 문서만, ref 규약은 v4 §5-3만 |
| W06 | v4 개정 이력 불일치 | 후속 보정 ADR §2 · 이번 이력 행 추가 | `module-architecture.md` 개정 이력 | — | `CLOSED_VERIFIED` | — |
| W07 | ref 접두어/위치 인코딩 · `thumb_ref` 자산 종류 미결 | 후속 보정 ADR §2 · §4.9 | `CaseView` 예시 `fr_` · §13 종결 | V1 PASS | `CLOSED_VERIFIED` | `FrameRef` 필드 계약은 B07과 함께 `PENDING_IMPLEMENTATION` |
| N01 | 경계 스크립트는 문서 검사만 | 이 문서 §7 | `scripts/README.md`에 새 검사 범위 추가 | V7 재실행 | `NOTE_ACCEPTED` | NOTE 12건 유지. E2E 아님 |
| N02 | CorrectionRecord Draft · taxonomy · Abstention Recall 근거 | §4.10 · §8 | 반영 없음(타 모듈 소유) | — | `PENDING_OWNER` | 신유민(taxonomy) · 김대원(정답지 C tier) · 유소연↔김준영(CorrectionRecord 리뷰) |
| N03 | git만으로 수락·통합 증명 불가 | 이 문서 §7 말미 | — | — | `NOTE_ACCEPTED` | Trajectory 1회차 기록은 비어 있다 |

**집계:** BLOCK 12건 중 `CLOSED_VERIFIED` 7(B01·B02·B03·B04·B05·B09·B10) · `CLOSED_BY_REMOVING_UNSUPPORTED_CLAIM` 2(B11·B12) · `CALL_REQUIRED` 2(B06·B08) · `PENDING_IMPLEMENTATION` 1(B07). BLOCK 상태로 남은 항목은 0건이지만 **종결되지 않은 BLOCK ID가 3건**(B06·B07·B08) 있다.

## 10. 종결 판정

**데이터 계약 감사 — `CONTRACT_AUDIT_PARTIAL` (+ `CALL_REQUIRED`).** 종결 조건 6개 중 ①(Owner 결정)은 B06~B08의 직렬화·자산 스키마가 남아 부분 충족, ②(공개 ADR) 충족, ③(계약 반영) `ACCEPTED` 범위는 충족, ④(fixture 검증) V1~V5 충족, ⑤(BLOCK 상태 0건) 충족, ⑥(새 CALL이 필요한 계약 BLOCK 0건) **미충족** — CALL-14(B06)·CALL-15(B08)가 열려 있다. 따라서 「데이터 계약 감사 종결」을 선언하지 않는다.

**모든 외부 감사 — 선언 불가.** `SECURITY_REVIEW_PENDING`(`pre-deploy-security-review.md` §1 표의 판정 칸이 모두 비어 있다) · `TRAJECTORY_REVIEW_PENDING`(`tool-trajectory-review.md` §4 두 회차 표가 비어 있다) · `E2E_NOT_VERIFIED`(실행 코드·통합 실행 기록 없음). 데이터 계약 감사가 닫히더라도 이 둘은 자동으로 닫히지 않는다.

## 11. 후속 변경 규칙

CALL-12~15 답이 오면 이 문서를 고치지 않고 **변경 ADR**을 쓴 뒤 §3·§9 표의 해당 행만 갱신한다(상태표는 원장이므로 갱신 대상). recording 자산 계약 2건이 나오면 §4.6·§4.9의 `PENDING_IMPLEMENTATION`을 그 계약으로 닫는다. 과거 감사 보고·후속 보정 ADR 본문은 수정하지 않는다.
