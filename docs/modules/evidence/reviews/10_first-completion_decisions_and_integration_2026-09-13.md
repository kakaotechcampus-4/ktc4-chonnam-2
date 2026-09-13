# evidence 1차 Mock 통합 후속 결정·논의·통합 항목

> 작성일: 2026-09-13
>
> 기준: `docs/evidence-first-completion-checklist` branch, 기준 커밋 `2a4302ecda6969f45da86543546c827d194be328` + confirmation guard 작업본
>
> 현재 상태: `PARTIAL_READY`
>
> 이 문서의 상태 표기는 회의·작업 관리용이며 Runtime Contract enum이 아니다.

## 결론

지금 다른 담당자와 먼저 결론 내야 하는 핵심은 **U Package의 위치 표현(Q1)** 한 건이다. 김준영이 지금 정책값을 확정하면 바로 구현 가능한 것은 **첨부 용량, 신고기한, 적용 rule catalog, 발생시각 이외 Correction의 source provenance**다. 신고문 Fixture 동기화, 실제 사용자 응답 전달, 영상 가시성 관찰, `EvidenceNeeds` 재발주, CaseView gate 검증, timeline revision 확인은 실제 산출물과 Consumer가 만나는 **통합 단계**에서 처리하는 편이 낫다.

아래 “결정 없이 먼저 고칠 항목”은 기준 커밋 `2a4302e` 이후 반영했다. 새 합의 없이 이미 확정된 정책을 코드와 Artifact에 적용한 것이다.

## 0. 결정 없이 먼저 고칠 항목

| 항목 | 확인된 사실 | 적용 결과 | 상태·증빙 |
| --- | --- | --- | --- |
| H specific template 사전조건 | [`safety-report-policy-v1.md`](../decisions/safety-report-policy-v1.md)는 specific template을 “사건 유형과 위반행위를 사용자가 확인하거나 수정해 확정”한 경우로 제한한다. 공용 H의 selected candidate는 `situation_confirmation=NOT_ASKED`이고 Evidence에 `situation_response`가 없다. | renderer가 specific에는 `CONFIRMED`/`CORRECTED`, generic에는 `USER_UNSURE`를 요구하도록 fail-closed 처리했다. 공용 H 그대로는 정상 Report/Package를 만들지 않고, test-derived `CONFIRMED`를 명시한 별도 경로에서만 `pkg_h001`을 만든다. | **검증 완료.** `test_renderer_rejects_specific_report_without_user_confirmation`, H 통합 test, H baseline의 `policy_guard_check` |

기준 커밋 `2a4302e`의 `pkg_h001`은 “함수 연결 성공” 증거로만 본다. 현재 작업본의 `pkg_h001`은 test-derived confirmation을 사용하므로 정책 guard 증거이지만 실제 case confirmation 접합 증거는 아니다. 실제 공용 H 입력을 `CONFIRMED`로 보완하는 일은 아래 I1에서 case와 처리한다.

## 1. 다른 담당자와 논의·확정 후 진행할 항목

### D1. U Package의 위치 표현 — Q1

| 구분 | 내용 |
| --- | --- |
| 현재 충돌 | 공용 U는 `report_inputs.location=null`이지만 Final `report-package/v1`은 `{display_text, search_keyword?}` 구조를 필수로 요구한다. U의 위치 부재·WARN 방향과 정상 Package 목표가 동시에 성립하지 않는다. |
| 논의자 | 김준영(`evidence`, Package/Requirement Owner) + 유소연(`case`, 입력·Consumer/CaseView Owner) + 신유민(`web`, projection 표시 확인) |
| 결정할 선택지 | ① Final에서 위치 없는 WARN Package를 명시적으로 허용하도록 계약 개정, ② 위치가 수집될 때까지 Package를 발행하지 않고 공용 U 기대값 수정, ③ case flow에서 Package 전에 실제 위치 입력을 필수화. placeholder 주소나 임의 좌표는 선택지에서 제외 |
| 권장안 | 현재 Final을 보존하려면 **② Package 보류**가 가장 작다. 제품상 위치 없는 WARN Package가 반드시 필요하다는 합의가 있을 때만 ①로 계약을 개정한다. |
| 결정 산출물 | Final Contract/ADR 또는 case 결정의 revision, 공용 U Fixture 기대값, CaseView의 Package 유무·위치 미확정 표시 규칙 |
| 완료 조건 | 동일 U 입력에 대해 evidence Package 생성 여부와 case/web 표시가 하나의 결정으로 일치하고 공용 validator 및 H/U 통합 검사가 통과 |

Q1은 실제 U Package 완료를 막으므로 통합 회의에서 처음 발견하도록 미루지 않는다. 결정만 먼저 하고, 실제 Fixture/CaseView 동기화는 통합 단계 I2·I5에서 수행한다.

## 2. 김준영이 지금 결정하면 바로 작업 가능한 항목

### K1. 첨부 용량 policy

현재 코드는 채택된 `report_video_max_bytes`가 없으면 `PolicyConfigurationError`로 정상 RequirementReport를 만들지 않는다. 과거 Research의 `동영상 130MB`, `이미지 30MB`, `총 180MB`는 보조 조사값이며 현재 정책으로 자동 승격하지 않는다.

지금 정해야 할 값:

1. 제한 대상: 신고영상 단일 파일, 이미지 단일 파일, 전체 첨부 합계 중 무엇을 검사할지
2. 각 byte 상한과 단위 해석(MB/MB decimal/MiB)
3. `byte_size=null`은 `UNKNOWN`, 초과는 `BLOCK`으로 둘지
4. 내부 target을 외부 상한보다 낮게 둘지
5. 근거 출처·확인일·policy version

결정 후 바로 할 수 있는 일은 versioned policy data 추가, `measurement.actual/limit/unit` 출력, 경계값/미측정/초과 테스트, H/U baseline 재실행이다. 외부 서비스의 현재 제한을 정책 근거로 삼으려면 예전 PDF가 아니라 적용 시점의 공식 출처를 다시 확인해야 한다.

### K2. 신고기한 policy

현재 코드는 채택된 deadline rule이 없으면 정상 Report를 만들지 않는다. 다음을 한 묶음으로 정해야 한다.

1. 기산점과 비교 시각: `occurred_at` → `evaluated_at`
2. 기간, 초일 포함 여부, 마감 경계의 inclusive/exclusive
3. Asia/Seoul 기준과 주말·공휴일 연장 여부
4. 공휴일 데이터 출처와 실패 시 처리
5. 기한 초과를 `WARN`으로 둘지 `BLOCK`으로 둘지
6. `occurred_at`이 UNKNOWN/NEEDS_REVIEW일 때의 outcome
7. 근거 출처·확인일·policy version

결정 후 deadline check, 경계일·공휴일·UNKNOWN 단위 테스트, RequirementReport measurement/provenance를 바로 구현할 수 있다. 달력 공급자나 외부 API 선택까지 필요하면 그것만 별도 기술 결정으로 분리한다.

### K3. evidence-owned 적용 rule catalog

현재 통합 adapter가 `rule_codes`를 명시적으로 넣어 H/U/P/R을 재현하지만, 이것은 Runtime wire schema가 아니다. 실제 Consumer가 임의 rule 목록을 선택하게 두지 않으려면 김준영이 아래를 policy version으로 확정하면 된다.

- `EVIDENCE` 기본 rules와 적용 조건
- `FINAL_PACKAGE` 기본 rules와 overlay 존재/사후 각인/USER_UNSURE별 분기
- K1·K2 rule의 포함 여부
- 신고유형별 번호판·위치·첨부 필수성
- rule 실행 자체가 실패했을 때 정상 Report 미발행 원칙

결정 후 `evaluate_requirements`가 policy version을 기준으로 rule을 선택하도록 바꾸고, adapter의 rule 목록은 “expected policy selection” 검사용으로만 남길 수 있다.

### K4. 발생시각 이외 Correction의 `EvidenceValue.source` provenance

`correction-record/v1.1`은 event·차량번호·위치 등 10개 semantic path를 evidence가 소비하도록 확정했다. 반면 [`source-kind-registry.md`](../decisions/source-kind-registry.md)는 `case.user_correction`을 TimeResolution/`occurred_at` 전용이라고 설명한다. 현재 단위 구현은 비시각 정정에도 같은 kind와 correction ref를 사용하므로 Merge 전에 registry 의미를 맞춰야 한다.

권장 결정:

- `case.user_correction`을 실제 반영된 모든 사용자 Correction의 `EvidenceValue.source.kind`로 확장
- `source.ref={kind: correction_record, ref: ...}`와 `provenance.correction_refs`를 함께 보존
- `observability=OBSERVED`, `user_corrected=true`, `needs_review=false`
- UI label이 확정되기 전 `label_key=null`을 사용하고 Consumer fallback을 허용

이 값 공간과 registry는 evidence 소유이므로 김준영이 바로 결정할 수 있다. 다만 CaseView가 `source_label_key`를 전달하므로 변경 문서를 유소연에게 통보하고 통합 단계에서 projection만 확인한다. 다른 kind를 새로 만들거나 label key를 신설하려면 그 이름도 같은 결정에 포함해야 한다.

## 3. 통합 단계에서 진행할 항목

| ID | 통합 작업 | 함께 볼 담당자 | 시작 조건 | 완료 증거 |
| --- | --- | --- | --- | --- |
| I1 | H의 `CONFIRMED` 또는 `CORRECTED` 응답을 실제 case 입력으로 전달하고 specific template 조건 검증 | 유소연(case) | 0번 fail-closed 반영, case 입력 경계 준비 | 공용 원본의 `NOT_ASKED`와 확인 응답을 추가한 파생 입력을 구분한 전후 JSON; 확인 없는 Package 미생성 |
| I2 | Q2의 H/U 제목·본문·`template_ref`·`policy_ref`를 `safety-report-policy/v1`과 동기화 | 유소연(Mock/Consumer), 필요 시 신유민(web) | 0번과 D1 결론 | 공용 또는 명시적 파생 Fixture가 exact renderer 결과와 일치; 기존 옛 문구를 PASS 처리하지 않음 |
| I3 | `situation_response`의 `value/responded_at/candidate_ref` 전달 경계 연결 | 유소연(case) | case 공개 함수 준비 | adapter 보조값 없이 case가 세 필드를 전달; USER_UNSURE는 CorrectionRecord 미생성, CORRECTED는 SITUATION_CHANGE ref 존재 |
| I4 | 최종 신고영상의 번호판·시각 표시 여부를 실제 관찰로 전달 | 신유민(readout), 정철원(recording), 유소연(case) | REPORT_VIDEO가 실제 ref로 존재 | readout 관찰 ref + report video ref를 case가 evidence에 주입; 문자열 번호판/`post_stamp.needed`만으로 가시성 PASS 금지. 기존 Contract로 표현 불가하면 그때 Contract 변경 검토 |
| I5 | U 위치 결론과 H/U Package/CaseView 반영 | 유소연(case), 신유민(web) | D1 확정, I2 완료 | U의 Package 유무·WARN·위치 표시가 Final과 일치; H/U 두 scope와 Package gate 보존 |
| I6 | P의 `PLATE_REREAD` Need를 case가 `PLATE_READ` Job intent로 번역하고 stale Need를 재발주하지 않는지 검증 | 유소연(case), 신유민(readout) | case orchestration과 readout 경계 준비 | 첫 Need의 basis, `force_rerun`, 새 PlateReadout, `ev_p001_v2`, 빈 Needs, UNKNOWN→PASS 연결 |
| I7 | R correction append → evidence 재조립 → 실패 시 과거 snapshot 보존 검증 | 유소연(case) | case correction 저장/호출 경계 준비 | CorrectionRecord가 먼저 남고 time/evidence/report supersede 연결; 실패를 주입해도 이전 결과와 correction 유지 |
| I8 | `EVIDENCE_SUFFICIENT`·`PACKAGE_READY`·`USER_REVIEWED` 및 source/needs_review를 CaseView에 투영 | 유소연(case), 신유민(web) | 실제 CaseView projection 준비 | raw evidence를 web이 직접 읽지 않고 CaseView에서 세 상태가 독립적으로 관찰됨 |
| I9 | timeline revision/range 역추적(Q3) | 정철원(recording), 유소연(case) | 실제 IncidentClip/CandidateEvent 전달 | `base_input_ref`/candidate span/IncidentClip provenance로 revision·범위 복원. 복원 불가한 입력이 나올 때만 새 필드 Contract 논의 |
| I10 | AssetFacts의 role·availability·byte size·lineage와 Package source/derived refs 연결 | 정철원(recording), 유소연(case) | 실제 또는 통합용 DerivedAsset 준비, K1 확정 | opaque ID 추측 없이 REPORT_VIDEO/optional PLATE_IMAGE 판정, AVAILABLE/UNKNOWN/UNAVAILABLE 분리, lineage 보존 |
| I11 | H/U/P/R 통합 회귀 및 evidence artifact 갱신 | 관련 Producer/Consumer | I1~I10 중 해당 Scenario 경로 완료 | evidence tests, 공용 validator 3종, boundary, `git diff --check`; Fixture/baseline/실제 Consumer 범위를 각각 표시 |

I4처럼 실제 영상이 있어야 의미 있는 항목은 지금 별도 Contract를 서둘러 만들지 않는다. 통합 입력으로 기존 `Observation<T>`와 readout/ref 조합이 충분한지 먼저 확인하고, 표현이 불가능할 때만 구체적인 누락 필드와 Consumer 요구를 근거로 Contract 변경을 제안한다.

## 권장 진행 순서

1. **완료:** 0번 specific-template fail-closed 수정과 H 전후 Artifact 분리
2. **김준영 결정:** K1~K4를 각각 versioned policy/registry로 기록하고 단위 테스트 추가
3. **짧은 Owner 합의:** D1에서 U 위치 정책 한 가지 선택
4. **통합 착수:** I1~I5로 H/U, I6으로 P, I7로 R 연결
5. **projection·provenance 검증:** I8~I10
6. **최종 회귀:** I11 후 체크리스트 수행 결과와 Artifact 갱신

Q1 한 건이나 실제 Consumer 부재를 이유로 K1~K4의 독립 작업을 멈출 필요는 없다. 반대로 K1/K2가 미정인 상태에서 Fixture 숫자를 정책으로 채우거나, H의 `NOT_ASKED`를 사용자 확인으로 간주하거나, test-only visibility fact를 실제 readout 결과로 보고해서는 안 된다.

## 이번 정리에서 제외한 것

- Queue, Worker, lease, heartbeat, retry, 취소, 비용 장부, 마스킹 로거, config/storage 계층, CI/CD
- `JobExecution`, `UsageRecord` 생산
- 실제 AI/OCR 호출, ffmpeg 영상 생성, 안전신문고 자동입력·제출
- `scenario_empty_001`, `scenario_infra_failure_001`, `scenario_relative_rebase_001`를 evidence가 완료시키는 작업

이들은 evidence 후속 결정표에 다시 넣지 않는다. 통합 과정에서 상태를 관찰할 수는 있지만 김준영의 evidence 구현 완료로 보고하지 않는다.

## 근거

- [`first-completion-checklist.md`](../first-completion-checklist.md)
- [`first-completion-result.md`](../first-completion-result.md)
- [`safety-report-policy-v1.md`](../decisions/safety-report-policy-v1.md)
- [`source-kind-registry.md`](../decisions/source-kind-registry.md)
- [`contract-requirement-report-package.md`](../../../architecture/contracts/contract-requirement-report-package.md)
- [`contract-evidence-record-needs.md`](../../../architecture/contracts/contract-evidence-record-needs.md)
- [`contract-correction-record.md`](../../../architecture/contracts/contract-correction-record.md)
- [`ownership.md`](../../../management/ownership.md)
