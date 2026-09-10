# CONTRACT_CONFLICTS.md

이 파일은 Mock Pack 생성 지침이 요구하는 "Contract 충돌 기록 파일(CONTRACT_CONFLICTS.md 또는 동급)"이다. 전체 상세 내용과 근거는 `04_mock_validation_report.md` §3에 있고, 여기서는 그 절의 항목만 인덱스로 모았다 — 이 작업 중 발견한 어떤 설계 문제도 임의로 고치지 않았고, 전부 아래 목록 + `04_mock_validation_report.md`에만 기록했다.

## Contract 충돌 (0건 잔여 · 1건 종결, 표현력 gap — 서로 부정하는 충돌은 없음)

~~4. `EvidenceNeeds`(v1)가 "AI가 사건 유형 자체를 확정하지 못했다"는 상황을 표현하지 못함 — 신규(2026-09-09, 유소연) → **fixture 레벨에서 해소(2026-09-10)**, 계약 문서 정식 등재는 잔여. 이슈 #25 A절(김준영)이 `event.visual_event_type.value=null`인 `EvidenceRecord`를 제한적으로 허용하기로 답했고, `scenario_unknown_abstain_partial_001`을 이 값으로 재구성해 EVIDENCE/FINAL_PACKAGE WARN → `stage=READY` 경로까지 실제로 예시화했다(`docs/modules/case/decisions/generic-warn-package-and-situation-response.md`). 단 `contract-evidence-record-needs.md` §3 스키마 자체("event는 필수")는 아직 이 null 허용을 명문화하지 않았고, `EvidenceNeeds`에 신규 `kind`는 만들지 않기로 확정(evidence A절: "사용자 workflow action이 아니다") — 이 두 가지는 evidence 소유 계약 문서 수정 대상으로 남는다.~~

→ **종결(2026-09-10, wording 수준 수정 · 유소연 직접 반영).** 남아있던 두 갈래 중 (a) 스키마 미명문화는 `contract-evidence-record-needs.md` §3에 `event.visual_event_type`의 `value: T | null` 허용 절을 추가해 닫았다 — 값 의미·값 공간을 바꾸지 않는 wording 수준 수정이라 `evidence-record/v1.3`을 유지한다(버전 미변경). (b) `EvidenceNeeds` 신규 `kind` 미생성은 애초에 "만들지 않기로" 확정된 결정 자체이므로 잔여 작업이 아니다. 두 갈래 모두 닫혀 항목 전체를 종결한다.

→ 상세: `04_mock_validation_report.md` §3.1

## 반려된 제안 (1건 — 이미 확정된 결정과 충돌)

5. 이슈 #23 B-3(서어진 제안): `AnalysisRun.input_ref.kind = ANALYSIS_SCOPE`를 소문자 `analysis_scope`로 통일하자는 제안 — **반려**. `contract-source-asset-media-stream.md` §84(항목 5)와 `adr/adr-data-contract-call-closure-2026-09-08.md` §218(항목 6)에 이미 "`ANALYSIS_SCOPE`는 자산 계층 ref가 아니며 별도 accepted 값이고, 이를 근거로 전역 대문자 규칙을 적용하지 않는다"는 명시적 결정이 있다. 제안 당시 이 선행 결정을 참조하지 못한 것으로 보임. Mock fixture(`ANALYSIS_SCOPE` 대문자 유지)는 그대로 두었고 계약 문서도 수정하지 않았다 — 수정하면 오히려 기존 ADR을 위반한다. 서어진에게 이 선행 결정을 알려 이슈 #23 B-3을 close하도록 회신 필요.

## 불명확한 Contract (1건 잔여 · 9건 종결)

1. `TimeResolution.resolved.verification`과 `computation.mode=USER_OVERRIDE`의 대응 관계 미명시
2. ~~순수 사용자 입력 값의 `EvidenceValue.source.observability`/`user_corrected` 판정 기준 미명시~~ → **종결(2026-09-10, 재확인 · 유소연)**: 실제로는 이미 명시돼 있었다 — `contract-evidence-record-needs.md` §"`source.observability` · `source.label_key`"(줄 189-190)가 "사용자 입력에는 별도 [observability] 값을 두지 않는다 — `user_corrected=true`가 이미 그 사실을 갖고 있고, 파생 규칙에서 `observability`보다 먼저 판정된다"고 명시한다. 즉 순수 사용자 입력값은 **`user_corrected=true`**로 표시해야 하고 `observability`는 (어떤 값을 넣든) 파생 규칙상 소비되지 않는다. `scenario_happy_001`의 `ev_h001.location.search_keyword`/`user_hint`(둘 다 `case.user_location_hint` 출처의 순수 사용자 입력)가 이 규칙과 반대로 `user_corrected: false`로 잘못 채워져 있던 **fixture 버그**를 발견해 `true`로 수정했다. `CaseView.location_display`는 대표값이 `user_hint`일 때 별도 규칙(§7-(3))으로 `INFO_NEEDS_REVIEW`를 강제해 이 수정으로 값이 바뀌지 않는다 — 재검증 완료.
3. ~~`CaseView.evidence.review_needed`의 파생 규칙 미명시~~ → **종결(2026-09-09, 유소연)**: 여섯 `*_display.needs_review`의 OR 집계로 확정, `contract-job-record-case-view.md` B절 §6·§7 등재
4. ~~`EvidenceRecord.event.safety_report_type`의 실제 값 공간(등록된 enum) 부재~~ → **종결(2026-09-10, 4차 통합 · 유소연)**: 김준영이 이슈 #33에서 `SafetyReportType` registry(`docs/modules/evidence/decisions/safety-report-policy-v1.md`, ACCEPTED)를 확정했다 — 내부 코드 `TRAFFIC_VIOLATION`(교통위반(고속도로 포함))/`MOTORCYCLE_VIOLATION`(이륜차 위반) 2종과 4-이벤트유형→2-코드 매핑, `USER_UNSURE` fallback 규칙(`TRAFFIC_VIOLATION` 기본값+`needs_review=true`)까지 등재됐다. 이를 근거로 전 시나리오의 placeholder 값(`UNSAFE_*`, 한글 라벨을 코드로 오용한 값)을 정식 코드로 교체하고, 같은 이유로 보류돼 있던 `CaseView.evidence.report_type_display`의 `info_state`/`source_label_key`도 `case-view/v1.3`에서 채워 넣었다.
5. ~~`CaseView.candidates[].situation_confirmation`·`CaseView.package.unconfirmed_fields`가 fixture로만 구현되고 계약 본문에 미등재~~ → **종결(2026-09-10, 4차 통합 · 유소연)**: `contract-job-record-case-view.md`를 `case-view/v1.3`으로 올려 `situation_confirmation` 값 공간을 `NOT_ASKED|CONFIRMED|CORRECTED|USER_UNSURE`(구 `REJECTED`/`UNKNOWN` placeholder 제거)로 정식 등재하고, `unconfirmed_fields` 파생 규칙도 명문화했다.
6. ~~Fine 단계에서 `AnalysisRun.input_ref`(`{analysis_source, as_*_fine}`)와 그 결과 `VisualEvidence.input_ref`(`{incident_clip, clip_*}`)가 서로 다른 자산 종류를 가리킴(이슈 #23 B-2, 서어진)~~ → **종결(2026-09-10, 이슈 #35 · 서어진 RT7 재확인 완료 · 유소연 fixture 반영)**: 서어진이 RT7 재확인을 마치고 이슈 #35에서 **`VisualEvidence.input_ref`를 `analysis_source`(`as_*_fine`)로 맞추는 쪽**으로 확정 답변했다 — 처음 이 항목을 적을 때 예시로 들었던 "(b) incident_clip으로 맞춤" 방향이 아니라 **반대 방향(run.input_ref 기준으로 ve.input_ref를 맞춤)**으로 결정됐다. 근거: ① `verify_visual × candidates`는 coarse 이후·사용자 선택 이전이고 `build_incident_clip`은 그보다 더 다운스트림(선택 이후, readout/evidence 전용)이라 verify 시점엔 clip이 아직 없음 ② coarse/fine이 1회 업로드를 공유하고 fine은 offset만 바꾸는 비용 설계상 fine마다 clip을 따로 만들면 이 설계가 깨짐 ③ RT7의 candidate-independent 일반화 때문에 `verify_visual(input_ref)`는 candidate/span에 종속된 `incident_clip`을 받을 수 없다(A-tier에 candidate가 없음) — `analysis_source`만 제품·eval 양쪽에서 성립 ④ `incident_clip`은 애초에 readout/evidence 전용 입력이지 fine-verify 입력이 아니다. `data/mock/search/scenario_{happy_001,plate_reread_001,unknown_abstain_partial_001,correction_rerun_001}.json`의 `visual_evidences[].input_ref`와 `data/mock/case/`의 대응 `FINE_VERIFY` `input_fingerprint`를 전부 `as_*_fine` 기준으로 수정 완료(검증 스크립트 3종 재확인).
7. ~~`CandidateEvent.span`이 (a) coarse 후보 창인지 (b) 사건 구간인지 계약 문구가 명확히 답하지 않음(이슈 #22 B-2, 김대원)~~ → **종결(2026-09-10, 서어진 답변 반영 · 유소연)**: 서어진이 **(a) coarse 후보 창이 맞다**고 확정 답변했다 — span을 만드는 `operation=CANDIDATE_SEARCH`는 정밀 사건 구간이 아니라 대략적 후보 창이 산출물이고, 정밀 시각은 Fine `temporal_facts[].at_offset_ms`·최종 `occurred_at`이 따로 담당한다(`representative_ms = span.start_ms + fine.at_offset_ms`가 전 fixture에서 성립). `contract-analysis-run-candidate-event.md` §4-1에 이 설명을 명문화하고, eval Consumer 규칙도 "span IoU가 아니라 `|representative_ms − gt_onset_ms|` point/onset error로 매칭, span containment는 sanity 신호로만 보조 사용"으로 정정했다(§Consumer eval). 서어진이 case에 넘긴 부수 fixture 수정도 반영했다 — `relative_rebase_001`의 candidate span이 요청 scope(500000~560000ms)와 완전히 동일해 localization 정보가 0이던 문제를 `502000~527000ms`(scope 내부의 진짜 부분창)로 좁혔다.
8. ~~실패/STALE attempt도 `UsageRecord`를 발행해야 하는지 계약이 명문화하지 않음~~ → **종결(2026-09-10, 4차 통합 · 유소연, 이슈 #33 Required-5/7)**: `contract-usage-record.md`를 `usage-record/v1.2`로 올려 이 컨벤션을 정식 등재했다 — `run_ref_reason`(`DIRECT_NO_RUN|RUN_NOT_PRODUCED|null`) 필드를 신설하고, 실제로 시작된 provider/capability 호출에 한해 row를 발행한다는 규칙(큐만 걸렸다가 dispatch 전 취소된 attempt는 제외)을 §9-6에 명문화했다.
9. ~~`CaseView.progress[].state`가 제품 정의 "중단" 상태를 표현하지 못함(대응할 `JobExecution.status` 값 부재)~~ → **종결(2026-09-10, 4차 통합 · 유소연)**: `contract-job-execution.md`를 `job-execution/v1.1`로 올려 `status` enum에 `CANCELLED`(`QUEUED→CANCELLED`, `RUNNING→CANCELLED`)를 추가했고, `CaseView`의 JobExecution→progress 투영표에 `CANCELLED→PARTIAL`(기존 `PARTIAL` 값 재사용, 신규 enum 값 아님) 행을 추가해 닫았다. 단 실제로 이 경로를 타는 fixture 데모는 여전히 만들지 않았다 — 리뷰에서 non-blocking으로 명시된 Should 항목이라 이번 라운드에서도 의도적으로 유보했다(`05_mock_deep_review_report.md` §13 row 24 참고).
10. ~~`CaseView.package.report_fields`가 필드 단위 상태(에러/치환/검토 필요 등)를 실을 자리가 없음~~ → **종결(2026-09-10, 4차 통합 · 유소연)**: `case-view/v1.3`에 `package.report_field_states`(`report_fields`와 병렬인 map, 필드별 `{info_state, source_label_key}`)를 신설했다. `vehicle_number`←`plate_display`, `occurred_at`←`event_time_display`, `location`←`location_display`, `violation_expression`←`violation_display`, `safety_report_type`←`report_type_display` 매핑으로 파생하며(`case_type_display`는 `report_fields`에 대응 키가 없어 매핑 밖), `scenario_happy_001`·`scenario_unknown_abstain_partial_001` fixture에 실제로 반영했다.

→ 상세: `04_mock_validation_report.md` §3.2

## Architecture 확인 필요 (0건 잔여 · 2건 종결)

1. ~~`JobRecord.kind`에 Report Video export / `purge_case()` 발주용 값 미등재~~ → **종결(2026-09-09, 유소연)**: `FINE_VERIFY`·`REPORT_VIDEO_EXPORT` 등재, `purge_case()`는 Job 밖 관리 동작으로 확정. `contract-job-record-case-view.md` A절 §7·§12·§13
2. ~~`contract-visual-evidence.md` 예시의 stale non-opaque frame ref 형식~~ → **종결(2026-09-10, 서어진)**: 이슈 #23 A절에서 계약 소유자(서어진)가 직접 답함 — `input_ref`는 `AnalysisRun.input_ref`와 같은 `{kind, ref}` 구조체, frame ref는 `fr_<opaque-id>`(위치 인코딩 폐기). 예시·문구 정정이라 `visual-evidence/v1.0` 유지, `contract-visual-evidence.md` §2·§3·§5·§6·§7·§8 갱신.

→ 상세: `04_mock_validation_report.md` §3.3

## Fixture 생성 불가 (0건 잔여 · 1건 종결)

1. ~~`contract-correction-record.md`가 아직 Draft라서 `CorrectionRecord` 자체 필드 fixture를 생성하지 않음(opaque ref만 사용)~~ → **종결(2026-09-10, 4차 통합 · 유소연)**: `contract-correction-record.md`가 `correction-record/v1.1`(Final — Accepted)로 승격됐다. `scenario_correction_rerun_001`에 실제 `correction_records[]` fixture(`cr_r001_time`, `kind=EVENT_TIME_MANUAL`)를 신규 생성했고, `validate_mock_pack.py`의 `EXEMPT_KINDS`에서 `correction_record`를 제거해 다른 kind와 동일하게 참조 무결성 검사를 받도록 했다.

→ 상세: `04_mock_validation_report.md` §3.4
