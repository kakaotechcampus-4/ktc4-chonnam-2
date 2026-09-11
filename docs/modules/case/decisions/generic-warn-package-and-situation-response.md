# "잘 모르겠어요" 응답 경로 — case state·CaseView 신규 필드·WARN Package 투영

> 결정일 2026-09-10 · 근거 [이슈 #25](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/25) A절(김준영) · comment(uminshin 2026-09-09, cheol1203 2026-09-09) · 담당 유소연(case) · Consulted 김준영(evidence)·신유민(web)·정철원(common/runtime)

> **후속 갱신 (2026-09-10, 4차 통합·evidence 3차 검수 재확인 · 유소연).** 아래 「남은 것」 4건 중 3건이 이후 4차 통합에서 이미 처리됐는데 이 절이 갱신되지 않아 "계약 미등재"로 오독될 수 있는 상태였다 — evidence 3차 검수(김준영)가 이 불일치를 지적해 여기서 정정한다. 상세는 「남은 것」 절 참고. `candidates[].situation_confirmation` 값 공간도 이 문서 작성 이후 `NOT_ASKED|CONFIRMED|REJECTED|UNKNOWN`에서 `NOT_ASKED|CONFIRMED|CORRECTED|USER_UNSURE`로 정정됐다(`evidence-record/v1.3`의 `situation_response`와 정렬, `contract-job-record-case-view.md` §7 ①) — u001의 실제 값도 `UNKNOWN`이 아니라 `USER_UNSURE`다. 아래 「결정된 것」 목록은 **작성 당시 시점의 기록**으로 그대로 두고 고치지 않는다.

## 배경

`scenario_unknown_abstain_partial_001`(u001)은 `VisualEvidence.verification=UNCERTAIN`(사건 유형 자체 불확실)일 때 `EvidenceRecord.event`가 필수 필드라 레코드 자체를 못 만드는 표현력 gap을 그대로 fixture화하고 있었다(`evidence_records=[]`, blocking notice로 종료). 이슈 #25 A절에서 evidence가 `visual_event_type=null`인 `EvidenceRecord`를 제한적으로 허용하기로 답했고, uminshin(web)·cheol1203(common/runtime) 코멘트로 남은 표시·발주 경계까지 확인됐다. 이 문서는 그 답변들을 case가 fixture에 반영하며 내린 구현 결정을 기록한다.

## 결정된 것

1. **`candidates[].situation_confirmation: "NOT_ASKED" | "CONFIRMED" | "REJECTED" | "UNKNOWN"`** — "아직 미확인"과 "잘 모르겠어요"를 같은 null로 합치지 않는다는 A절 요구를 이 필드로 만족한다. `CorrectionRecord`가 아직 Draft(N02)라 case 자체 state로 둔다. u001에서는 `UNKNOWN`.
2. **`case_type_display`에 `info_state`/`source_label_key` 추가** — `visual_event_type.value=null`이면 기존 `plate_display`/`location_display`와 같은 파생 규칙(`contract-job-record-case-view.md` B절 §7)을 그대로 적용해 `value==null → INFO_UNKNOWN`. 새 규칙을 만들지 않았다.
3. **`violation_display`에 `info_state`/`source_label_key` 추가** — generic 신고문(evidence A절 예시 문구)은 값이 존재하고 출처가 `evidence.violation_expression`(INFERRED)이므로 `INFO_AI_ESTIMATED`. pack에 없던 `INFO_AI_ESTIMATED` 예시를 이 필드가 채운다(uminshin ⑥-5, 재검수 완료 조건 4번과 동일 건).
4. **`report_type_display`는 이번엔 `info_state` 추가 보류** — 4→2 mapping registry(#25 항목 ②, evidence 소유)가 아직 없어 `source_label_key`를 정할 근거가 없다. `code: null, label: "교통위반(고속도로 포함)"`으로 값만 갱신하고 표시 상태 필드는 registry 완성 후 별도 반영한다.
5. **`package.unconfirmed_fields: string[]`** — 기존 `report_fields`(`{필드명: 문자열}`) 구조는 유지하고 배열을 추가하는 방식으로 확장했다(uminshin ⑥-3, #26 B-5와 동일 건). 하위 호환을 깨지 않는 쪽을 택했다. u001은 `["safety_report_type", "occurred_at"]`.
6. **notices `code`는 dotted-lowercase** — u001 기존 notice 3건이 이미 이 표기였다(`time.conflict_needs_notice` 등). `evidence.visual_event_unconfirmed`의 `blocking`만 `true→false`로 바꿔 재사용했다 — 코드 자체는 새로 안 만든다.
7. **EVIDENCE WARN → FINAL_PACKAGE WARN → `stage=READY`** — 계약 변경 없이 기존 불변조건(§10-3·§10-9, `readiness ∈ {PASS, WARN}`)으로 성립. `requirements_package`·`package` 체크·투영을 채워 실제로 이 경로를 예시화했다.
8. **WARN Package도 `capabilities`(`DOWNLOAD_ASSETS`·`COPY_FIELDS`·`OPEN_DESTINATION`) 유지** — uminshin ④ 답변 그대로, WARN이 다운로드/복사/이동을 막지 않는다.
9. **u001에 `REPORT_VIDEO_EXPORT` Job은 추가하지 않았다** — cheol1203 코멘트가 이 체인을 happy 성공 chain 1건에 한정했다(이슈 범위). u001의 report video/plate image `DerivedAsset`은 happy가 이 Job 도입 전부터 그랬듯 Job 없이 존재하는 recording 사실로 둔다.

## 신규 recording 사실 (provisional)

u001에 report video(`da_u001_report_video`, 60초 = `clip_u001` 길이)·plate image(`da_u001_plate_image`) `DerivedAsset`을 새로 추가했다. 기존 값(byte_size 등)에서 비례 추정한 것이라 **recording Owner(정철원) 확인 전까지 provisional**이다 — #24는 이 두 자산이 생기기 *전* u001을 검수했다.

## 이유

- `needs_review`가 아니라 `info_state`(`INFO_UNKNOWN`/`INFO_AI_ESTIMATED`)로 "미확정"과 "AI 추정"을 구분한 것은, evidence A절이 "잘 모르겠어요를 `INFO_USER_CONFIRMED`로 올리는 우회는 하지 않는다"고 명시한 것과 같은 방향 — 새 정책을 만들지 않고 기존 5-state 파생 규칙을 그대로 확장했다.
- `report_type_display`를 미루기로 한 건 placeholder 값(`UNSAFE_*`)을 새 placeholder로 바꿔치기하지 않기 위해서다 — mapping registry가 나오기 전에 손대면 두 번 고치게 된다.

## Fixture 반영

- `data/mock/case/scenario_unknown_abstain_partial_001.json` — `case_rev:3`(EVIDENCE_REVIEW, WARN evidence) → `case_rev:4`(READY, WARN package) 2개 스냅샷으로 재구성
- `data/mock/evidence/scenario_unknown_abstain_partial_001.json` — `EvidenceRecord`·`RequirementReport`(EVIDENCE·FINAL_PACKAGE)·`ReportPackage` 신설
- `data/mock/recording/scenario_unknown_abstain_partial_001.json` — `DerivedAsset`·`AssetFacts` 2건 추가(provisional)
- 검증: `validate_mock_pack.py`·`check_contract_fixtures.py`·`check_boundaries.py` 전부 PASS

## 남은 것

- ~~`report_type_display` `info_state`/`source_label_key` — 4→2 mapping registry 완성 후~~ → **완료(2026-09-10, 4차 통합).** 김준영이 `SafetyReportType` registry(`docs/modules/evidence/decisions/safety-report-policy-v1.md`)를 확정하면서 근거가 생겨, `case_type_display`와 같은 rule (1)을 적용해 `report_type_display.info_state`/`.source_label_key`도 채웠다. u001은 `INFO_NEEDS_REVIEW`(`USER_UNSURE` fallback 경로, `source_label_key=event.source.category_mapping`).
- **u001 신규 recording 자산 2건 — 정철원 확인.** 아직 미확인, provisional 그대로다. 유일하게 진짜로 남은 항목.
- ~~이 CaseView 신규 필드들(`situation_confirmation`·`unconfirmed_fields`) 계약 문서(`contract-job-record-case-view.md`) 본문 정식 등재 — 별도 PR~~ → **완료(2026-09-10, 4차 통합).** `case-view/v1.3`에 정식 등재했다(`CONTRACT_CONFLICTS.md` 불명확 항목 5 종결).
- ~~notices `code` 표기 규칙 자체를 계약 문서에 명문화하는 것 — #26 결정과 함께~~ → **완료(2026-09-10, 이슈 #26 A-⑤).** `contract-job-record-case-view.md` B절 §7에 dotted-lowercase(`<producing-module>.<detail>`) 표기 규칙과 `time.*` 4종의 실제 근거 모듈 접두어 정정까지 명문화됐다.
