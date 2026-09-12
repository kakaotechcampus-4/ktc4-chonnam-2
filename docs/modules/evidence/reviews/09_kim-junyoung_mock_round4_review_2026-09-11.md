# 김준영 담당 Mock Pack v4 4차 검수 보고서

> 검수일: 2026-09-11
> 기준 브랜치: `develop`
> 기준 커밋: `d9d8e2b` (`origin/develop`과 동기화 확인)
> 비교 기준: Mock Pack v3 통합 `e056d64` → Mock Pack v4 통합 `d9d8e2b`
> 검수 범위: 김준영 담당 `data/mock/evidence/` 4개 + `data/mock/common/` 7개, 담당 Final Contract 6건, 변경된 case/readout/web 접합부, 공지의 PR #27·#28 확인 요청
> 검수 관점: Contract 일치 / 현실적인 값 조합 / UNKNOWN·ABSTAIN·실패 / Consumer 사용 가능성 / 3차 검수 회귀 / correctness·readability·architecture·security·performance
> 선행 보고서: `docs/modules/evidence/reviews/08_kim-junyoung_mock_round3_review_2026-09-10.md`

## 0. 이번 검수에서 누가 무엇을 확인하나

이번 검수는 case가 각 모듈 결정을 fixture와 계약 초안에 대신 반영한 Mock Pack v4를 evidence/common-runtime Owner 관점에서 재확인한 기록이다. 원시 JSON을 자동 검사한 결과만으로 승인하지 않고, 각 값이 실제 Producer/Consumer 경계를 지키는지와 이전 Required 7건이 의미까지 종결됐는지를 다시 대조했다.

### 김준영 확인 결과

1. **[확인 완료] `TimeResolution`의 사용자 시각 정정 값**: `computation.mode=USER_OVERRIDE`인 현재 fixture에서 `resolved.verification=AGREED`를 사용한 해석을 수용한다. 다만 이 대응은 아직 Final Contract에 불변조건으로 적혀 있지 않으므로 계약과 validator에 명문화해야 한다.
2. **[확인 완료] PR #27 overlay 상태 이름**: `readout.overlay.not_present → readout.overlay_not_present`, `readout.overlay.presence_undetermined → readout.overlay_presence_undetermined`, `readout.overlay.ocr_failed → readout.overlay_ocr_failed` 매핑은 evidence/case 소비 관점에서 수용한다. 앞의 두 값은 현재 fixture와 일치하고, 마지막 값은 향후 재사용을 위한 등록값이다.
3. **[확인 완료] PR #28 happy location**: `EvidenceRecord.location.user_hint/search_keyword`가 `user_corrected=true`, `needs_review=false`인 것은 evidence 기준으로 맞다. CaseView에서는 대표값이 사용자 hint이면 별도 표시 규칙에 따라 `INFO_NEEDS_REVIEW`이고 object-level `review_needed=true`가 된다. 두 축은 모순이 아니다.
4. **[확인 완료] `UsageRecord` v1.2 fixture 값**: 24개 row 모두 `run_ref`와 `run_ref_reason` 조합이 맞고, `JobExecution.usage_refs` 양방향 연결 및 실행 구간 내 `occurred_at`도 맞다.
5. **[확인 완료] 3차 Required의 주요 fixture 보강**: happy export 순서, u001 post-stamp chain, CaseView 신규 필드 백필, `USER_UNSURE` provenance, SafetyReportType 정규화, `run_ref_reason`, plate reread crop/selection 값은 의도한 방향으로 반영됐다.

### case 통합 결과를 그대로 승인할 수 없는 이유

fixture의 값 대부분은 맞지만 다음은 Owner 확인이나 기계적 보완이 남았다.

- case가 Producer인 `CorrectionRecord` 객체가 `module=evidence` 파일 안에 들어가 모듈 소유 경계를 거꾸로 만들었다.
- correction 시나리오는 같은 Search candidate를 유지하면서 CaseView candidate 시각과 `selection_rev`를 바꿔, “후보 재선택이 실제로 있었다”는 설명을 데이터가 증명하지 못한다.
- `UsageRecord v1.2`의 새 규칙과 같은 문서 안의 v1/v1.1 잔존 문구가 서로 충돌한다.
- v4에서 닫힌 결정을 여전히 Draft/미결이라고 설명하는 canonical 문서가 남아 있다.
- 검증기가 새 필드를 존재 여부와 일부 enum 수준으로만 보고, 이번 v4에서 중요해진 교차 불변조건을 검사하지 않는다.

따라서 이 보고서는 fixture를 직접 고치지 않고, 김준영 Owner 답변과 case가 수정할 재검수 조건을 분리해 기록한다.

## 1. 최종 판정

**판정: `REQUEST_CHANGES` — 11개 담당 fixture의 주된 값 조합은 수용하지만, canonical seed로 승인하기 전에 6개 Required를 해소해야 한다.**

| 검수 축 | 판정 | 요약 |
| --- | --- | --- |
| `evidence` 4개 fixture | `PASS_WITH_REQUIRED_FIXES` | EvidenceRecord/TimeResolution/Requirement 흐름은 대체로 맞다. 다만 case 소유 CorrectionRecord 위치와 correction selection context가 잘못됐고 USER_OVERRIDE 대응이 계약에 없다. |
| `common/runtime` 7개 fixture | `PASS_DATA` | 24개 UsageRecord의 ref/reason·execution 연결·시각은 모두 정합하다. canonical UsageRecord 문서 내부 충돌과 validator 미비가 남았다. |
| 3차 Required 7건 회귀 | `6 RESOLVED / 1 PARTIAL` | fixture 보강은 전부 반영됐다. CaseView/UsageRecord 신규 불변조건을 validator가 충분히 강제하지 않아 Required-3·5·7의 회귀 방지는 부분 완료다. |
| 공지의 PR #27 | `PASS_FOR_EVIDENCE` | overlay reason→notice 값 이름은 현 fixture와 맞다. `crop_ref`는 opaque identity로 비교만 한다는 전제도 evidence Consumer와 충돌하지 않는다. 발급 주체 최종 확인은 recording Owner 몫이다. |
| 공지의 PR #28 | `UPDATE_REQUIRED` | 요청했던 `report_type_display.info_state`와 `report_field_states`는 develop v4에 이미 들어왔다. PR 문서는 여전히 “없다”고 쓰고 v3 fixture를 설명하므로 최신 develop 기준으로 갱신해야 한다. |
| 문서 정합 | `REQUEST_CHANGES` | CorrectionRecord Draft/opaque 설명, UsageRecord 이전 규칙, 미결 개수 등이 v4와 충돌한다. |
| 자동 검증 | `PASS_BUT_INCOMPLETE` | 공식 검사 3종, cp949, build, diff-check는 통과했다. 이번 검수의 모듈 소유·correction context·신규 필드 불변조건은 잡지 못한다. |
| 보안 | `NO_NEW_FINDING` | 비밀정보·인증·외부 전송·의존성 변경이 없다. |
| 성능 | `NOT_APPLICABLE` | fixture·계약·문서 중심 변경이다. build 성공은 구현 성능 증거가 아니다. |

---

## 2. 공지 확인 요청 답변

### A-1. `TimeResolution.resolved.verification`과 `USER_OVERRIDE`

**답: `USER_OVERRIDE → AGREED`로 해석하는 현재 fixture를 수용한다.** 사용자가 사건 발생시각을 명시적으로 정정한 것은 source 검증(`VERIFIED`)이 아니라 사용자와 최종값을 합의한 상태이기 때문이다.

최소 불변조건은 다음처럼 한 방향으로 닫는 것이 안전하다.

```text
resolved.computation.mode == USER_OVERRIDE
  => status == OK
  => resolved.verification == AGREED
  => resolved.user_corrected == true
  => provenance.selected_input_ref.kind == correction_record
  => selected considered item.input_kind == USER_INPUT
  => selected considered item.verification == AGREED
  => referenced CorrectionRecord.kind == EVENT_TIME_MANUAL
```

`AGREED → USER_OVERRIDE` 역방향까지 닫지는 않는다. 사용자가 기존 Observation을 값 변경 없이 확인하는 별도 흐름까지 `AGREED`로 표현할 가능성이 있으므로, 역방향 규칙은 실제 제품 동작을 확인한 뒤 별도로 결정해야 한다.

현재 `scenario_correction_rerun_001`의 `tres_r001_v2` 값은 위 해석과 맞지만 `contract-time-resolution.md` §3~§5에는 enum 의미와 사용자 입력 허용만 있고 이 대응 자체는 없다. `CONTRACT_CONFLICTS.md`도 이를 유일한 잔여 불명확 항목으로 기록한다. 계약과 validator를 함께 보완하면 이 질문은 종결할 수 있다.

### A-2. PR #27 「실패가 아닌 상태」 값 이름

**답: evidence/case Consumer 기준으로 세 매핑을 수용한다.**

| Readout observation reason | CaseView notice | 현재 fixture |
| --- | --- | --- |
| `readout.overlay.not_present` | `readout.overlay_not_present` | correction/u001에서 사용, 일치 |
| `readout.overlay.presence_undetermined` | `readout.overlay_presence_undetermined` | infra_failure에서 사용, 일치 |
| `readout.overlay.ocr_failed` | `readout.overlay_ocr_failed` | 등록만 됨, fixture 없음 |

세 상태를 합치지 않고, overlay 부재/판정 불가/OCR 판독 실패를 각각 보존하는 방향이 UNKNOWN·NOT_APPLICABLE 경계와 맞다. 현재 fixture가 없는 `overlay_ocr_failed`는 등록값으로 수용하되 향후 해당 갈래를 추가할 때 동일 이름을 써야 한다.

`crop_ref`를 `(frame_ref, bbox, extraction params)` 기준 opaque identity로 보고 run 간 동일 입력 비교에 쓰는 전제도 evidence가 crop 이미지를 직접 조회하거나 재해석하지 않는 한 문제없다. recording이 발급하지 않는다는 생산자 경계는 정철원 확인 항목으로 남긴다.

### A-3. PR #28 happy location과 v4 동기화

**답: evidence fixture의 `needs_review=false`가 맞다.**

- `ev_h001.location.user_hint/search_keyword`: 사용자가 직접 제공한 값이므로 `user_corrected=true`, 이미 사용자에게 재확인할 EvidenceValue가 아니므로 `needs_review=false`.
- `CaseView.location_display`: 대표값이 `user_hint`이므로 `info_state=INFO_NEEDS_REVIEW`를 사용한다.
- `CaseView.evidence.review_needed`: display의 `INFO_NEEDS_REVIEW`를 OR 집계하므로 `true`다.

즉 EvidenceValue의 “사용자 입력 자체를 다시 검토해야 하는가”와 web display의 “이 위치 단서를 확정 위치처럼 보여도 되는가”는 다른 축이다.

develop v4에는 `report_type_display.info_state/source_label_key`, `package.report_field_states`, display↔report field 매핑, `unconfirmed_fields` 파생 규칙이 모두 반영됐다. 반면 현재 PR #28의 `value-state-display.md` diff는 이 두 항목을 아직 미결로 설명하고 Mock Pack v3의 누락 상태를 전제로 한다. PR 작성자는 develop v4로 rebase/merge한 뒤 §4~§6과 fixture 표를 현재 상태로 갱신해야 한다.

---

## 3. 담당 fixture 전수 검수

### 3.1 `data/mock/evidence/` 4개

| fixture | 판정 | 확인 내용 |
| --- | --- | --- |
| `scenario_happy_001.json` | `PASS` | `VERIFIED/DIRECT/OK`, user location의 `user_corrected=true`·`needs_review=false`, SafetyReportType 정규화, EVIDENCE→export→FINAL_PACKAGE→Package 시간 순서가 모두 맞다. |
| `scenario_unknown_abstain_partial_001.json` | `PASS` | `UNVERIFIED/BASE_PLUS_OFFSET/NEEDS_REVIEW`, `situation_response=USER_UNSURE`, `visual_event_type=null`, generic report type의 review 필요, post-stamp 검사와 WARN Package가 일관된다. |
| `scenario_plate_reread_001.json` | `PASS` | 같은 candidate 위 재판독이므로 v2 EvidenceRecord `selection_rev=1` 유지, 최초 abstain과 성공 재판독 revision이 함께 보존된다. |
| `scenario_correction_rerun_001.json` | `REQUEST_CHANGES` | TimeResolution/EvidenceRecord supersede 값은 맞지만 case 소유 `correction_records[]`가 evidence 파일에 있고, `selection_rev=2`와 CaseView candidate 시각 변경의 근거가 없다. |

### 3.2 `data/mock/common/` 7개

| fixture | 판정 | 확인 내용 |
| --- | --- | --- |
| `scenario_happy_001.json` | `PASS` | Report Video export 실행이 FINAL_PACKAGE 이전에 끝나고 UsageRecord가 같은 execution에 연결된다. |
| `scenario_unknown_abstain_partial_001.json` | `PASS` | post-stamp report-video JobExecution/UsageRecord 체인이 추가됐고 `DIRECT_NO_RUN` 의미가 맞다. |
| `scenario_plate_reread_001.json` | `PASS` | 재판독 실행·usage가 별도 attempt/Run에 연결된다. |
| `scenario_correction_rerun_001.json` | `PASS` | 4개 execution과 4개 usage가 양방향으로 연결된다. |
| `scenario_infra_failure_001.json` | `PASS` | STALE attempt는 실제 invocation이 시작된 시각에 `RUN_NOT_PRODUCED` row를 남긴다. |
| `scenario_empty_001.json` | `PASS` | run이 존재하는 호출의 `run_ref_reason=null`이 맞다. |
| `scenario_relative_rebase_001.json` | `PASS` | analysis run 연결과 비용 row가 정합하다. |

전 7개 common fixture의 합계는 JobExecution 24개, UsageRecord 24개다. 추가 스크립트로 다음을 확인했다.

- `run_ref != null`인 row는 `run_ref_reason=null`.
- `run_ref == null`인 row는 `DIRECT_NO_RUN` 또는 `RUN_NOT_PRODUCED`.
- 모든 `JobExecution.usage_refs[]`는 실제 UsageRecord를 가리키고, 모든 UsageRecord의 `execution_ref`가 역방향으로 일치한다.
- terminal execution의 UsageRecord `occurred_at`은 `started_at ≤ occurred_at ≤ ended_at` 범위 안에 있다.

---

## 4. 상세 검수

### 4.1 happy Report Video 순서 — 해소

3차 Required-1의 미래 package 참조와 시간 역전은 해소됐다. Report Video execution이 `18:23:15~18:23:45`, EVIDENCE report가 `18:23`, FINAL_PACKAGE가 `18:25`, Package가 `18:26` 순서라서 “존재하지 않는 산출물을 먼저 PASS”하는 순환이 없다. `job_h001_report_video.case_rev=2`도 export 발주 시점 snapshot과 맞는다.

### 4.2 u001 post-stamp와 사용자-unsure — 해소

3차 Required-2·4는 해소됐다.

- `TimeResolution.post_stamp.needed=true`와 대응하는 report-video Job/Execution/Usage가 존재한다.
- `DerivedAsset.transform_ref=tr_u001_trim_poststamp_v1`로 post-stamp 적용 provenance를 구분한다.
- FINAL_PACKAGE에 `package.time.post_stamp_applied=PASS`가 있다.
- EvidenceRecord에 `situation_response={value:USER_UNSURE, responded_at, candidate_ref}`가 있어 `visual_event_type.value=null`의 사용자 응답 근거를 독립적으로 재현할 수 있다.
- CaseView rev3/rev4 notice와 `situation_confirmation=USER_UNSURE`가 함께 유지된다.

### 4.3 CaseView v1.3 백필 — fixture 해소, 회귀 검사는 부분

12개 candidate snapshot 모두 `situation_confirmation`을 가지고, evidence display 객체도 `info_state`와 `source_label_key`를 가진다. happy/u001 Package에는 `report_field_states`와 그 상태에서 파생한 `unconfirmed_fields`가 있다.

다만 validator는 candidate 필드의 존재·값 공간, 여섯 display의 전체 필수 키, report_fields↔report_field_states 키 집합, `unconfirmed_fields` 파생 결과를 끝까지 검사하지 않는다. 현재 데이터는 맞지만 필드를 하나 지워도 일부 위반이 통과할 수 있어 3차 Required-3의 “validator 보강”은 부분 완료다.

### 4.4 UsageRecord v1.2 — fixture 해소, 문서 내부 충돌

새 §5 필드 표와 §7-1 예시는 `run_ref=null`의 두 이유를 올바르게 구분한다. 그러나 같은 Final Contract의 다음 문구는 아직 이전 규칙을 말한다.

- §7 설명: `null`은 “Run 개념이 없는 직접 호출만” 뜻한다고 단정.
- §8 불변조건 10: 같은 단정이 남아 신규 불변조건 13과 충돌.
- §9-5 표: `null`은 Run 없는 직접 호출만이라고 설명.
- §10 미결: `run_ref=null` 의미가 §8-10 그대로라며 같은 이전 문구를 다시 고정.

`RUN_NOT_PRODUCED` fixture를 Final Contract가 동시에 허용하고 금지하는 상태이므로 구현자는 어느 문단을 따라야 하는지 결정할 수 없다. v1.2에서 폐기한 문구는 역사 설명으로 명확히 표시하거나 현재 규칙으로 교체해야 한다.

### 4.5 CorrectionRecord — 객체는 생겼지만 Producer 경계와 context가 어긋남

`contract-correction-record.md`는 Owner와 Runtime Producer를 모두 `case`로 명시한다. 그런데 유일한 실제 객체 `cr_r001_time`은 `data/mock/evidence/scenario_correction_rerun_001.json`의 `correction_records[]`에 있다. validator 주석도 이 잘못된 위치를 정상 예시로 고정했다.

또한 Search의 `candidate_r001`은 timeline revision 1, representative 930000ms인 동일 stable candidate다. 최초 CaseView는 이를 13:15:30으로 표시한다. 사용자 정정 후 CaseView는 같은 candidate ID를 계속 selected로 두면서 `at=13:13:00`, `at_provenance=case.user_correction`으로 바꾸고 EvidenceRecord/CorrectionRecord `selection_rev`를 2로 올렸다.

하지만 사용자 `EVENT_TIME_MANUAL` correction은 `occurred_at`을 바꾸는 것이고 CandidateEvent의 timeline 위치를 바꾸는 작업이 아니다. CaseView 계약도 candidate absolute display time을 현재 Recording Timeline에서 projection한다고 한다. 실제 `OTHER_CANDIDATE` 선택, 새 candidate ID, selection event는 어느 fixture에도 없다. 따라서 둘 중 하나로 정리해야 한다.

1. 같은 candidate context를 유지한다면 CaseView candidate `at=13:15:30`과 `selection_rev=1`을 유지하고, 최종 13:13:00은 `event_time_display`에만 반영한다.
2. 정말 후보 재선택이 있었다면 그 선택을 증명할 새 candidate/selection context를 fixture에 materialize하고 왜 같은 stable ID를 유지하는지 계약 근거를 추가한다.

현재 데이터만 보면 1안이 기존 계약과 가장 직접적으로 맞는다.

### 4.6 canonical 문서와 PR #28 — v4 상태로 동기화 필요

다음 문서는 v4와 반대 상태를 현재형으로 설명한다.

- `docs/mock/01_mock_dataset_overview.md`: Final 14 + Draft 1, CorrectionRecord Draft/opaque, 미결 7건, correction ref exempt, correction scenario overlay NOT_RUN 등의 이전 설명.
- `data/mock/scenarios/scenario_correction_rerun_001.json`: CorrectionRecord가 Draft라 별도 객체가 없고 opaque ref만 쓴다고 설명.
- `docs/mock/02_mock_scenario_catalog.md`: v4 note 아래의 예상 흐름은 여전히 Draft/opaque라고 설명하고, plate 절은 correction 시나리오에서 실제 후보 재선택이 있었다고 근거 없이 단정.
- `docs/modules/evidence/contracts/README.md`: Final v1.1 Consumer Review를 여전히 “Draft 검토”로 표기.
- `docs/modules/case/decisions/eval-round2-ground-truth-and-usage.md`: UsageRecord 생성 규칙이 계약에 아직 미등재라고 설명.
- `docs/mock/04_mock_validation_report.md` 결론부: 이미 종결한 EvidenceNeeds gap과 이전 미결 개수를 현재 조건처럼 남김.
- PR #28 `value-state-display.md`: develop v4가 추가한 `report_type_display.info_state`와 `report_field_states`를 여전히 미결로 설명.

append-only 이력 문서라면 “당시 상태”임을 명확히 표시할 수 있다. 하지만 개요·scenario manifest·Final Contract README·현재 UX 규칙처럼 구현자가 현재값을 찾는 문서는 v4 상태로 직접 갱신해야 한다.

---

## 5. Findings

### Required-1. `USER_OVERRIDE → AGREED` 대응을 TimeResolution 계약과 validator에 명시한다

**영향:** case가 “임의 해석”한 현재 값은 Owner 관점에서 수용 가능하지만, 계약에 없으면 다른 Producer가 `VERIFIED` 또는 `UNVERIFIED`를 써도 자동 검증을 통과한다.

**수정 요청:** §2 A-1의 한 방향 불변조건을 `contract-time-resolution.md`에 추가하고, `validate_mock_pack.py`에서 selected USER_INPUT/CorrectionRecord/status/user_corrected까지 함께 검사한다.

### Required-2. `CorrectionRecord` fixture를 case 모듈로 이동한다

**영향:** Producer/Owner가 case인데 evidence 출력처럼 저장돼 모듈 경계와 테스트 fixture 책임이 뒤집힌다.

**수정 요청:** `correction_records[]`를 `data/mock/case/scenario_correction_rerun_001.json`으로 이동한다. validator는 `correction_records`를 case의 허용·필수 검사 대상으로 등록하고 다른 모듈에 등장하면 실패시킨다. 관련 주석과 문서 경로도 함께 고친다.

### Required-3. correction 시나리오의 candidate 시각과 `selection_rev`를 실제 선택 이력에 맞춘다

**영향:** 현재 fixture는 사건 발생시각 correction이 Search candidate의 canonical timeline 위치를 바꾼 것처럼 보이고, 존재하지 않는 후보 재선택을 `selection_rev=2`로 기록한다. evidence 재조립과 candidate 선택을 구현에서 혼동하게 한다.

**수정 요청:** 같은 candidate 유지라면 `candidate_r001.at=13:15:30`, EvidenceRecord/CorrectionRecord `selection_rev=1`을 유지하고 `event_time_display`만 13:13:00으로 바꾼다. 다른 선택이 실제 요구라면 새 selection context를 materialize한다. catalog의 “후보 재선택이 실제로 있었다” 설명도 결과에 맞춘다.

### Required-4. UsageRecord v1.2 안의 폐기된 `run_ref=null` 문구를 정리한다

**영향:** `RUN_NOT_PRODUCED`를 허용하는 §5·§7-1·§8-13과 금지하는 §7·§8-10·§9-5·§10이 동시에 Final 규칙으로 읽힌다.

**수정 요청:** 현재 규칙을 한 문장으로 통일한다. `run_ref=null`은 `DIRECT_NO_RUN` 또는 `RUN_NOT_PRODUCED`이고 반드시 `run_ref_reason`으로 구분한다. v1/v1.1 문구를 보존해야 하면 “폐기된 이전 규칙”으로 명확히 표시한다.

### Required-5. v4 신규 계약 불변조건을 validator가 실제로 강제하게 한다

**영향:** 현재 공식 검사 3종이 모두 PASS지만 Required-1~3을 발견하지 못한다. green 결과가 canonical seed 의미 정합을 과대 대표한다.

**최소 추가 검사:**

- `CorrectionRecord` required keys, semantic target별 value 타입, `supersedes_ref`, case 모듈 소유.
- `UsageRecord.contract`, `contract_version`, `run_ref_reason` required keys와 ref/reason 양방향 조건.
- `USER_OVERRIDE`/`AGREED`/USER_INPUT/CorrectionRecord 교차 조건.
- `EvidenceRecord.situation_response`의 값 공간과 `USER_UNSURE → visual_event_type.value=null` 조건.
- 모든 CaseView candidate의 `situation_confirmation`, 여섯 display 필수 키, report field state key 집합, `unconfirmed_fields` 파생 결과.
- EvidenceRecord/CorrectionRecord의 `selection_rev`가 실제 case selection context와 일치하는지 확인하는 시나리오 검사.

### Required-6. 현재형 문서와 PR #28을 develop v4에 맞춘다

**영향:** 새 구현자가 overview/manifest/README/UX 문서를 따라가면 Final 계약을 Draft로 취급하고, 이미 존재하는 필드를 fallback으로 우회하거나 UsageRecord 이전 규칙을 구현할 수 있다.

**수정 요청:** §4.6 목록을 갱신하되 역사적 결정 기록은 삭제하지 않고 당시 상태임을 표시한다. PR #28은 최신 develop을 반영한 뒤 “미결” 두 항목을 완료 상태로 바꾸고 v4 fixture 표를 사용한다.

### Should-1. `overlay_ocr_failed`와 CANCELLED→PARTIAL 경로 fixture를 후속 pack에 추가한다

두 값 모두 계약에는 등록됐지만 실제 scenario가 없다. 이번 v4의 기존 7개 시나리오 수정 범위를 막는 Required는 아니지만 web/eval 구현 전에 최소 한 번은 실데이터 조합으로 검증하는 편이 안전하다.

---

## 6. 3차 검수 항목 회귀 확인

| 3차 항목 | v4 결과 | 판정 |
| --- | --- | --- |
| Required-1 happy export 순서 | EVIDENCE→export→FINAL_PACKAGE→Package 순으로 수정 | `RESOLVED` |
| Required-2 u001 post-stamp chain | Job/Execution/Usage/DerivedAsset/check/notice 추가 | `RESOLVED` |
| Required-3 CaseView 신규 필드 백필 | 12개 candidate와 display/package 상태 백필 | `RESOLVED_DATA / VALIDATOR_PARTIAL` |
| Required-4 u001 사용자-unsure provenance | EvidenceRecord `situation_response` 추가 | `RESOLVED_DATA / VALIDATOR_PARTIAL` |
| Required-5 UsageRecord 생성 기준 | 실제 invocation 기준 계약·fixture 반영 | `RESOLVED_DATA / DOC_CONFLICT` |
| Required-6 SafetyReportType 정규화 | 4개 evidence fixture 모두 registry code 사용 | `RESOLVED` |
| Required-7 비용 집계와 run 연결 | `case_id`/`run_ref` 분리, `run_ref_reason` 전량 백필 | `RESOLVED_DATA / DOC_CONFLICT` |
| Should-1 CANCELLED/partial fixture | 계약만 등재, 실제 fixture 없음 | `OPEN_NON_BLOCKING` |
| Nit-1 trailing whitespace | `git diff --check` clean | `RESOLVED` |

---

## 7. 재검수 통과 조건

- [ ] `contract-time-resolution.md`에 `USER_OVERRIDE → AGREED`와 선택 provenance 불변조건이 명시돼 있다.
- [ ] `cr_r001_time`이 case fixture에 있고 evidence는 ContractRef로만 소비한다.
- [ ] correction 시나리오의 candidate `at`/`at_provenance`와 `selection_rev`가 실제 선택 이력을 증명한다.
- [ ] `contract-usage-record.md`에서 `run_ref=null`의 현재 의미가 한 가지 규칙으로 읽힌다.
- [ ] validator가 CorrectionRecord/UsageRecord/TimeResolution/CaseView v4 신규 불변조건을 검사한다.
- [ ] overview/scenario manifest/catalog/evidence README/case decision/validation report의 현재형 설명이 v4와 일치한다.
- [ ] PR #28이 develop v4의 `report_type_display.info_state`와 `report_field_states`를 반영한다.
- [ ] 아래 검사와 추가 의미 검사가 다시 통과한다.

위 조건이 모두 충족되면 evidence/common-runtime Owner 관점에서 Mock Pack v4를 `PASS`로 전환할 수 있다. `overlay_ocr_failed`, CANCELLED→PARTIAL fixture는 별도 후속 항목으로 남겨도 이번 승인 자체를 막지 않는다.

## 8. 검증 실행 기록

### 공식 검사와 호환성 확인

```powershell
python data/mock/validate_mock_pack.py
# Scanned 46 JSON files across 7 scenarios.
# VALIDATION PASSED — no errors found.

python scripts/check_contract_fixtures.py
# 문서 구조 PASS: 60
# JSON 파싱 PASS: 26
# 의미 fixture PASS: 104

python scripts/check_boundaries.py
# PASS — 경계·계약 정합성 위반 0건
# NOTE — 7개 구현 디렉터리는 아직 골격 단계

$env:PYTHONIOENCODING='cp949'; python data/mock/validate_mock_pack.py
# Windows cp949 출력 PASS

npm run build
# tsc -b && vite build PASS

git diff --check e056d64..d9d8e2b
# 출력 없음
```

### 추가 의미 검사

```text
담당 fixture: evidence 4개 + common 7개 = 11개
UsageRecord: 24개
run_ref/run_ref_reason 위반: 0개
JobExecution↔UsageRecord 연결/시각 위반: 0개
CaseView candidate snapshot: 12개
situation_confirmation 누락: 0개
CorrectionRecord 객체: 1개, 현재 module=evidence (경계 위반)
correction EvidenceRecord selection_rev: 1 → 2
correction CaseView candidate_id: candidate_r001 → candidate_r001
correction CaseView candidate at: 13:15:30 → 13:13:00
```

자동 검증 PASS는 JSON 형식·등록된 일부 enum·참조 존재를 증명하지만, 구현 통합 PASS·E2E PASS·Owner 수락을 뜻하지 않는다.

## 9. 결론

Mock Pack v4는 3차 검수에서 지적한 실제 흐름 오류를 상당 부분 잘 고쳤다. 특히 happy Report Video 순서, u001 post-stamp와 사용자-unsure provenance, plate reread, SafetyReportType, UsageRecord reason 백필은 구현 seed로 쓸 수 있는 수준까지 왔다. PR #27의 evidence 관련 이름도 수용 가능하고, happy location의 `needs_review=false` 역시 의도된 값이다.

그러나 이번 통합에서 새로 구체화한 CorrectionRecord가 잘못된 모듈에 놓였고, correction scenario가 사건시각 정정과 candidate 선택 revision을 섞었다. UsageRecord Final Contract와 현재형 문서도 v4 이전 설명을 동시에 유지하며 충돌하고, 공식 validator는 바로 이 문제들을 잡지 못한다. 따라서 지금은 **데이터 값 다수 PASS, canonical pack 전체 `REQUEST_CHANGES`**가 정확한 판정이다.

이 보고서는 검수 기록만 추가한다. fixture·계약·PR에는 직접 수정이나 댓글을 남기지 않았다.
