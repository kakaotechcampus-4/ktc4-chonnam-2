# `evidence` — 증거 확정과 신고 준비

**Owner** 김준영 · [모듈 문서](../../../docs/modules/evidence/README.md)

Evidence는 Case가 전달한 사건 후보, 영상 관찰, 번호판·시각 판독, 원본의 시각 후보·GPS, 사용자 정정을 받아 확정값과 출처를 조립한다. 신고 유형을 매핑하고, 추가 판독이 필요한지와 신고 요건을 판단한다.

Search는 사건 후보와 관찰, Readout은 OCR 판독, Recording은 원본·GPS·시간축과 신고용 자산 생성을 맡는다. Case는 후보 선택, 정정 기록 저장, 작업 발주, 화면 진행·검토 상태를 관리한다. Worker는 작업을 실행한다. Evidence는 전달받은 값과 정책으로 판단을 반환한다. 책임 경계의 원문은 [모듈 아키텍처의 Evidence 절](../../../docs/architecture/module-architecture.md#모듈-4-evidence--증거-확정--신고-정책--package)을 참고한다.

## 증거 확정

- **사건 상황.** Fine은 후보 사건을 상세 확인하는 Search 단계다. Fine 결과가 `OBSERVED`이면 조립한다. `UNCERTAIN`은 `USER_UNSURE`(“잘 모르겠어요”)일 때만 조립하고, 그 외에는 `AWAIT_SITUATION_RESPONSE`를 반환한다. 대기 중에도 발생시각·번호판·위치는 별도로 계산해 Case가 표시할 수 있다. `NOT_OBSERVED`는 정상적인 `NOT_ASSEMBLED` 결과다.
- **발생시각.** 명시적인 사건시각 정정이 우선이다. 다음으로 같은 IncidentClip과 시간축 revision에서, 사건과 같은 원본 구간에 있고 시각 흐름이 일치하는 실제 OCR 프레임 표본 두 개 이상이 덮는 범위에 사건 대표 시점이 있어야 검증된 화면 시계를 쓸 수 있다. 가장 가까운 표본 시각을 사건 시점까지 보정한다. 이 경로와 명시적 사건시각 정정은 `OK`로 기록한다. 표본 범위 밖이나 원본 경계·공백을 넘겨 계산하지 않는다. 그다음 사건이 속한 원본의 파일명·메타데이터 후보를 검토한다. 파일명 후보가 있으면 우선하며, 후보 값이 충돌하면 그 근거를 남긴다. 파일 계열 값은 `NEEDS_REVIEW`, 쓸 수 있는 근거가 없으면 `UNKNOWN`이다. 클립 없는 호출의 파일 계열 계산은 원본 하나가 시간축 0초에서 시작한다고 가정한다. 상세 조건은 [TimeResolution 계약 §17–18](../../../docs/architecture/contracts/contract-time-resolution.md#18-검증된-overlay-시계를-사건-대표-시점에-대응시키기)에 있다.
- **번호판.** 판독값의 형식이 의심스러우면 원래 문자열을 보존하고 `needs_review=true`를 붙인다. 유효한 직접 입력은 판독 결과가 없어도 사용할 수 있다. 값이 없고 조립에 사용한 `PlateReadout`이 있으면 식별 실패로 보고 번호판 없는 문구를 허용한다. 값과 판독 결과가 모두 없으면 초안은 보류되고 최종 평가의 신고문 입력은 `UNKNOWN`이다.
- **위치.** 확보한 좌표·주소·장소명·사용자 단서는 출처와 함께 보존한다. 신고문 장소는 주소 → 장소명 → 사용자 단서 순서로 선택한다. 표시할 문자열이 없으면 장소 문구를 생략하고 최종 평가에서 `WARN`으로 남긴다. 좌표만 있는 경우에도 같은 원칙을 적용한다.

## 초안, 요건 평가, 신고 묶음

1. **`EvidenceRecord` 조립.** 선택된 사건의 확정값과 입력 참조를 담는다. [EvidenceRecord·EvidenceNeeds 계약](../../../docs/architecture/contracts/contract-evidence-record-needs.md)을 따른다.
2. **신고문 초안.** 조립한 Record로 자산 준비와 독립적으로 제목과 본문을 만든다. 구체적인 유형은 `CONFIRMED`(확인), `CORRECTED`(정정), 또는 현재 Fine 관찰에 근거한 무응답일 때 허용한다. 구체적인 유형에 `USER_UNSURE`로 답하면 보류한다. 유형이 없는 `USER_UNSURE`는 일반 신고문으로 렌더링한다. 발생시각·번호판 입력 조건과 본문 길이 기준을 만족해야 하며, 본문 시각은 한국 시간으로 표시한다. [관찰된 유형의 무응답 처리 결정(#597)](../../../docs/modules/evidence/decisions/observed-report-draft.md)을 참고한다.
3. **`RequirementReport` 평가.** `EVIDENCE`는 증거 값, `FINAL_PACKAGE`는 신고문·기한·첨부 등 최종 요건을 검사한다. `PASS`는 충족, `WARN`은 고지나 확인이 필요한 상태로 진행 가능, `BLOCK`은 정책상 진행 불가, `UNKNOWN`은 정보 부족으로 판정 보류다. 종합 결과는 가장 높은 우선순위인 `BLOCK > UNKNOWN > WARN > PASS`를 따른다. 최종 영상의 번호판·시각 가시성 재검사는 v6에서 제거했고 v7도 이 결정을 유지한다. 필요한 시각 분기에서는 Recording이 남긴 사후 각인 적용 사실을 계속 검사한다. [가시성 재검사 제거 결정(#280)](../../../docs/modules/evidence/adr/adr-i4-report-video-visibility-rules-removal.md)을 참고한다.
4. **`ReportPackage` 발행.** 같은 Record에 대한 유효한 `FINAL_PACKAGE` 평가가 `PASS` 또는 `WARN`이고, 사용 가능한 신고영상의 크기를 알고 있으며, 묶을 자산이 평가에 포함돼 있고 조립에 성공해야 발행한다. 평가에 템플릿 참조가 있으면 실제 렌더링 결과와 일치해야 한다. 번호판 이미지 첨부는 선택이다. 번호판 없는 신고문도 같은 발행 조건을 충족해야 한다. 묶음 자체에 `READY` 상태 필드는 없으며 화면의 진행·검토 상태는 Case가 관리한다. [요건·묶음 계약 §8.1](../../../docs/architecture/contracts/contract-requirement-report-package.md#81-ready-only-object)을 참고한다.

현재 저장 자산 경로에서는 Case가 신고영상의 변환 기록에서 각인 적용 사실을 읽어 요건 평가에 전달하고, 조립된 Record의 초안을 CaseView에 투영한다. 연결 지점은 [저장 자산 어댑터](../case/stored_observation.py)와 [CaseView](../case/view.py)에 있다.

## 공개 함수

`daesingo.evidence`에서 가져온다. 아래 시그니처는 필수 인자를 먼저 보여준다. 생략한 선택 인자와 타입은 각 함수 정의에 있다. 계약 객체는 `dict`로 전달한다.

| 함수와 필수 인자 | 반환과 역할 |
| --- | --- |
| [`resolve_time(*, time_source_candidates, overlay_time_readout, candidate_event, case_id, selection_rev, resolution_id)`](time_resolution.py) | `TimeResolution`. 운영 경로는 `incident_clip`을 넘긴다. `correction_records`로 명시적 사건시각 정정을 전달한다. |
| [`classify_visual_evidence(visual_evidence, situation_response=None)`](disposition.py) | `VisualEvidenceDisposition`. 조립, 응답 대기, 비조립을 구별한다. 잘못된 관찰 상태나 유형 조합은 `ContractInputError`다. |
| [`resolve_independent_facts(*, case_id, selection_rev, time_resolution, plate_readout)`](assembly.py) | `dict`. 응답 대기 중에도 결정할 수 있는 `occurred_at`, `vehicle_number`, `location`만 반환한다. 위치·정정 입력을 선택적으로 받으며 Case는 이 결과를 Record ID 없이 표시할 수 있다. [#239](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/239) |
| [`assemble_evidence(*, case_id, selection_rev, candidate_event, visual_evidence, time_resolution, plate_readout, incident_clip, record_id)`](assembly.py) | `EvidenceRecord`. 위치·상황 응답·정정은 선택 인자로 받는다. `NOT_OBSERVED`를 직접 넘기면 `VisualEventNotAssembled`가 발생한다. |
| [`calculate_evidence_needs(evidence_record, plate_readout, *, emit_empty=True)`](assembly.py) | `EvidenceNeeds` 또는 `None`. 계약은 `OVERLAY_TIME_OCR`와 `PLATE_REREAD`를 허용한다. 현행 함수는 번호판 판독이 보류됐고 확정값이 없을 때 `PLATE_REREAD`를 만든다. 요청이 없고 `emit_empty=False`이면 `None`을 반환한다. |
| [`render_report_draft(evidence_record)`](requirements.py) | `title`·`description` 또는 `None`. 렌더 입력이 부족하거나 본문 길이가 범위를 벗어나면 보류한다. 계약·정책 오류는 호출자에게 전달한다. |
| [`render_report(*, visual_event_type, situation_response, occurred_at, location_display, vehicle_number, violation_expression, observed=False)`](policy.py) | 고정 템플릿으로 만든 제목·본문·템플릿 참조·글자 수. 입력이 잘못됐거나 길이가 범위를 벗어나면 `ContractInputError` 계열 예외가 발생한다. |
| [`evaluate_requirements(evidence_record, *, scope, report_id, evaluated_at, time_resolution)`](requirements.py) | `RequirementReport`. 활성 정책이 검사 항목을 고른다. `asset_facts`로 자산 정보, `observation_facts`로 필요한 각인 적용 사실을 받는다. 잘못된 정책 구성은 `PolicyConfigurationError`다. |
| [`aggregate_outcomes(checks)`](requirements.py) | 종합 결과 문자열. 빈 검사 목록이나 허용되지 않은 결과값은 `ContractInputError`다. |
| [`build_report_package(evidence_record, requirement_report, *, package_id, created_at, asset_facts)`](requirements.py) | `ReportPackage`. 발행 조건 미충족은 `PackageNotReady`로 알린다. |
| [`correction_heads(records, *, case_id, selection_rev)`](corrections.py) | Evidence가 소비하는 필드별 최신 정정 기록. 저장된 정정값이나 기록 연결이 잘못되면 `ContractInputError`다. |
| [`validate_correction_append(correction, *, existing_records)`](corrections.py) | 저장 전 검사. 통과하면 `None`을 반환한다. 허용 범위를 벗어난 새 값은 `InvalidCorrectionValue`로, 기록 구조·이전 값·연결 또는 기존 기록의 오류는 그 밖의 `ContractInputError`로 알린다. |
| [`validate_contract(value)`](validation.py) | 출력 계약의 오류 목록. 통과하면 빈 목록이다. 현재 `time-resolution/v1`, `evidence-record/v1.3`, `evidence-needs/v1`, `requirement-report/v1`, `report-package/v1.2`와 과거 Package v1·v1.1을 검사한다. |
| [`attachment_constraint(derived_role)`](attachments.py) | `PLATE_IMAGE` 개별 파일의 최대 바이트(`max_byte_size`)와 `policy_ref`. 다른 역할은 `ContractInputError`, 잘못된 정책 구성은 `PolicyConfigurationError`다. |

`correction-record/v1.2`에서는 값이 없던 상태의 첫 정정에 `previous_value=null`을 허용한다. 이 버전에서 추가로 허용한 경로는 발생시각·차량번호·좌표다. v1.1 기록의 이 세 경로에는 소급하지 않는다. v1.1에서 이미 `null`을 허용한 경로와 각 경로의 `new_value` 규칙은 그대로 적용한다. Case 전용 경로는 Evidence의 정정값 검사 대상에서 제외된다. [정정 기록 계약](../../../docs/architecture/contracts/contract-correction-record.md)과 [저장 전 검사 결정(#235)](../../../docs/modules/evidence/adr/adr-correction-append-precheck.md)을 참고한다.

### 제출 자산 제약의 책임 경계 (#47 P-1)

Evidence가 제출 제약을 정하고, Case가 전달하며, Recording이 크기 조정·인코딩 등 생성 방식을 정한다. Evidence는 생성된 자산 정보로 정책 충족 여부를 다시 평가한다.

API·Worker는 `attachment_constraint()`에서 받은 최대 바이트를 Case 어댑터에 전달한다. Case의 내보내기 요청과 재사용 판단에는 이 제한값이 반영된다. `policy_ref`를 내보내기 요청과 재사용 판단에 포함하는 연결은 후속 범위다. [#47 제안](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/47#issuecomment-6476963858) · [Case 동의](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/47#issuecomment-6488537839) · [Evidence 동의](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/47#issuecomment-6494921087)

## 정책 데이터

| 활성 파일 | 적용 내용 |
| --- | --- |
| [`requirement_rules_v7.json`](requirement_rules_v7.json) | `policy/requirement-rules-v7`. 증거·최종 묶음 요건을 선택한다. |
| [`safety_report_policy_v1_2.json`](safety_report_policy_v1_2.json) | `safety-report-policy/v1.2`. 신호위반·중앙선 침범·실선 차로 변경은 교통위반, 이륜차 안전모 미착용은 이륜차 위반으로 매핑한다. 위치와 번호판의 유무에 맞춰 템플릿을 선택한다. 본문은 5~900자다. |
| [`attachment_policy_v1.json`](attachment_policy_v1.json) | `policy/safety-report-attachment-size/v1`. 파일당 이미지 30,000,000바이트, 영상 130,000,000바이트, 전체 180,000,000바이트다. 이미지·영상은 종류별 최대 4개이며 합계도 최대 4개다. |
| [`deadline_policy_v1.json`](deadline_policy_v1.json) | `policy/safety-report-deadline/v1`. 한국 시간의 사건일 다음 날부터 2달력일을 센다. 말일이 주말·공휴일이면 그다음 평일 중 공휴일이 아닌 날로 연장한다. 기한 초과는 `WARN`이다. 공휴일은 2026~2027년 내장 자료를 사용한다. |
| [`plate_format_rules_kr_v1.json`](plate_format_rules_kr_v1.json) | `plate-format/kr-v1`. OCR 번호판 문자열을 형식 규칙으로 확인해 검토가 필요한 값을 표시한다. 사용자 직접 입력에는 이 형식 검사를 적용하지 않는다. |

활성 버전의 선택과 검증은 [정책 로더](policy_catalog.py)와 [번호판 규칙 로더](plate_format.py)에 있다. 요건 v2~v6과 신고문 v1.1은 과거 정책으로 보존한다. 개정 이유는 [결정 목록](../../../docs/modules/evidence/decisions/README.md)과 [ADR 목록](../../../docs/modules/evidence/adr/README.md)에 있다.

## 테스트

테스트 의존성을 준비한 뒤 저장소 루트에서 실행한다. 테스트는 [`tests/evidence/`](../../../tests/evidence/)에 있다.

```powershell
uv run --no-sync pytest tests/evidence/ -q
```

### 과거 Mock 시나리오 재현

[1차 Mock 통합 기록](../../../docs/modules/evidence/first-completion-result.md)은 당시의 가상 입력과 실행 결과를 보존한다. 아래 명령은 같은 종류의 가상 입력을 현재 Evidence 함수로 실행한다. 임시 디렉터리를 지정해 결과를 따로 저장한다.

```powershell
$mockOutput = Join-Path ([System.IO.Path]::GetTempPath()) ('daesingo-evidence-mock-' + [guid]::NewGuid())
uv run --no-sync python -m daesingo.evidence.mock_integration --output-dir $mockOutput
```
