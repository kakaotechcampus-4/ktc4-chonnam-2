# ADR-EVIDENCE-002·003 구현 및 검수 보고서

> 검수일: 2026-09-14
> 범위: K1·K2·K3·K4, D1의 evidence 소유 코드·정책·계약·테스트·Artifact
> 상태: **evidence 범위 구현 완료 / 전체 제품은 PARTIAL_READY**

## 결론

ADR-EVIDENCE-002 K1~K4와 ADR-EVIDENCE-003 D1을 evidence 모듈에 반영했다. 활성 rule catalog는 `policy/requirement-rules-v3`이며 v2는 채택됐지만 첫 실행 전에 대체된 revision으로 보존했다. `ReportPackage`는 v1.1에서 `location` 키를 반드시 가지되 값은 `null`일 수 있고, renderer는 위치가 없으면 별도 no-location template을 선택한다.

공용 H/U/P/R 재실행은 신규 사건 장면·전 상황·후 상황 관찰 fact를 만들어내지 않는다. 따라서 H와 U의 FINAL_PACKAGE는 `UNKNOWN`이고 Package는 0건이다. D1의 위치 없는 WARN Package는 이 세 관찰을 명시한 test-derived U 입력에서 `pkg_u001_d1_unit`으로 별도 검증했다. 이는 위치 부재 때문에 Package가 막힌 결과가 아니다.

## 작업 항목별 증빙

| 항목 | 반영 | 공개 경계에서 확인한 테스트 |
| --- | --- | --- |
| W1 / K1 | `attachment_policy_v1.json`, FINAL 여섯 첨부 rule, decimal byte·개수·dedup·부분합 처리 | `test_k1_exact_limit_one_byte_over_and_null_measurement`, `test_k1_partial_total_distinguishes_block_from_unknown`, `test_k1_count_rules_deduplicate_and_cover_each_kind`, `test_k1_policy_missing_or_malformed_emits_no_report` |
| W2 / K2 | `deadline_policy_v1.json` loader와 `deadline.py`, Asia/Seoul 2개 달력일·휴일 연장·exclusive upper bound | `test_k2_weekday_friday_consecutive_holidays_and_year_boundary`, `test_k2_exclusive_boundary_and_status_mapping`, `test_k2_missing_unknown_and_bad_coverage` |
| W3 / K3 | 활성 catalog 단일 선택점, EVIDENCE 4개·FINAL 15+조건부 1개, `time_resolution` 인수 | `test_k3_catalog_selects_four_and_sixteen_rules_from_data`, `test_k3_time_selector_covers_all_four_branches`, `test_k3_configuration_errors_emit_no_normal_report`, `test_k3_selector_and_observation_configuration_errors` |
| W4 / K4 | source-kind registry v2, 비시각 9개 correction provenance | `test_nine_non_time_corrections_have_k4_value_provenance`, `test_visual_correction_keeps_derived_mapping_inferred_until_direct_override`, `test_occurred_at_correction_does_not_gain_evidence_value_source_fields` |
| W10 / D1 계약 | `report-package/v1.1`, location 키 필수·null 허용, v1 의미 보존 | `test_report_package_v1_1_requires_nullable_location_key` |
| W11 / D1 template | `safety-report-policy/v1.1`, 위치 없는 specific/generic template | `test_d1_location_null_warn_package_and_template_are_reproducible`, `test_location_snapshot_skips_empty_higher_priority_value` |
| W12 / D1 catalog·구현 | v3의 위치 WARN·template별 필수 입력, nullable snapshot·validator | `test_d1_location_null_warn_package_and_template_are_reproducible`, `test_d1_both_catalog_changes_are_required` |

## Scenario 재실행

| Scenario | Time | Requirement overall | Package | 해석 |
| --- | --- | --- | --- | --- |
| H | `OK` | `PASS / UNKNOWN` | 0 | 사건·전·후 상황 관찰 fact 부재 |
| U | `NEEDS_REVIEW` | `WARN / UNKNOWN` | 0 | 위치는 WARN이지만 사건·전·후 상황 관찰 fact 부재 |
| P | `OK` | `UNKNOWN / WARN` | 0 | 재판독 전후 EVIDENCE 평가 |
| R | `NEEDS_REVIEW / OK` | `WARN / WARN` | 0 | correction 전후 EVIDENCE 평가 |

`docs/modules/evidence/artifacts/first-completion/`의 baseline 네 파일과 `run-summary.json`을 재생성했다. 다섯 파일에서 `policy/requirement-rules-v2`는 0건이고 v3만 사용한다. `base_revision`은 구현 커밋 `427ebb980361f7b2d41f6024e476a5269f7d91bc`이며 구현 파일 해시는 각 Artifact의 `implementation_fingerprints`가 보존한다.

## 검수 결과

```text
python -m unittest discover -s tests/evidence -p 'test_*.py'
41 tests OK

python -m ruff check src/daesingo/evidence tests/evidence
All checks passed

python -m compileall -q src/daesingo/evidence tests/evidence
PASS

python data/mock/validate_mock_pack.py
46 JSON / 7 scenarios, 0 errors

python scripts/check_contract_fixtures.py
structure 60 / JSON 26 / semantic 104 PASS

python scripts/check_boundaries.py
0 violations

git diff --check
PASS (line-ending conversion warning only)
```

공용 validator 결과는 해당 validator가 검사하는 fixture 정합성만 뜻한다. 실제 case projection, Runtime E2E, AI/OCR 정확도, 외부 신고 성공, Consumer Owner 수락은 증명하지 않는다.

## 코드 품질 검토

- Correctness: 정책 경계값·날짜 경계·UNKNOWN/BLOCK precedence·ready-only Package를 테스트로 확인했다. 빈 `address` 객체가 유효한 `place_name`을 가리던 위치 선택 문제와 중첩 차량번호 값 부재가 예외로 새던 렌더 입력 문제를 수정했다.
- Readability: 활성 catalog 파일명은 `policy_catalog.py` 한 곳에만 있고, 조건 판정과 data outcome 매핑을 분리했다.
- Architecture: evidence는 순수 함수로 남고 다른 모듈을 호출하지 않는다. 관찰 fact는 Python 호출 입력이지 새 Contract나 Runtime wire schema가 아니다.
- Security: 외부 API·파일 업로드·인증정보 처리가 추가되지 않았다. 정책 JSON은 패키지 내부 정적 파일만 읽는다.
- Performance: 정책 파일은 평가마다 읽고 검증한다. 파일 크기가 작아 현재 비용은 제한적이며, 캐시는 hot reload·테스트 patch 가능성을 없앨 만큼의 이점이 없어 두지 않았다.

## 발견한 지시 간 불일치

발주 문서 W5와 ADR-EVIDENCE-002 §5.15는 공용 H/U/P/R에 신규 사건·전후 상황 관찰 fact가 없으므로 세 rule을 `UNKNOWN`으로 두고 값을 만들지 말라고 한다. 반면 W6·W12와 같은 ADR §5.15의 D1 정정 블록은 U의 FINAL_PACKAGE가 `WARN`이고 `pkg_u001`이 유지돼야 한다고 요구한다. RequirementReport precedence가 `BLOCK > UNKNOWN > WARN > PASS`이므로 동일한 공용 입력에서는 두 요구를 동시에 만족할 수 없다.

이번 구현은 입력 사실을 만들지 않는 상위 의미 경계를 따랐다. 공용 U는 `UNKNOWN`·Package 0건으로 기록하고, D1 자체는 관찰 fact를 명시한 test-derived 입력에서 `WARN`·Package 발행으로 증명했다. ADR-EVIDENCE-002·003 본문은 수정하지 않았다. Owner가 문구를 정리할 때에는 “D1이 위치 관련 UNKNOWN 두 건을 제거한다”와 “I4 관찰 입력이 들어온 경우 PACKAGE_READY가 성립한다”를 구분해야 한다.

또한 W12의 `validate_report_package(pkg_u001) == []`은 공용 fixture를 고치지 말라는 같은 절의 금지와 충돌한다. 공용 `pkg_u001`은 여전히 `contract_version=report-package/v1`이면서 `location=null`이다. 테스트는 같은 payload를 메모리에서 v1.1로 해석해 validator 결과 `[]`를 확인했으며, 디스크 fixture 갱신은 I2에 남겼다.

## 후속·통합 대기

| 항목 | 담당 | 영향 경로 | 완료에 필요한 조치 |
| --- | --- | --- | --- |
| D1 case 표시·고지 | `case` Owner | `CaseView.report_field_states.location`, notices | 위치 부재 field state 필수 문구와 사용자 고지 code·발동 조건 등재 |
| I2 공용 fixture 재렌더 | Mock Pack / 관련 Owner | 공용 H/U `ReportPackage` | v1.1 contract/template/policy ref로 재렌더하고 Consumer 검증 |
| ④ 선택적 위치 질의 | evidence/PM 후속, 현재 `DEFERRED` | 사용자 검증 flow | C-1 사용자 관찰 결과가 조건을 열 때 별도 결정 |
| WARN/blocked Scenario 확장 | Mock Pack | Scenario coverage | U 외 WARN Package와 `scenario_blocked_001` 추가 |
| I4 관찰 전달 확장 | `case`·`recording` 관련 Owner | FINAL_PACKAGE rule inputs | 사건 장면·전 상황·후 상황 관찰 fact 생산·전달 연결 |
| Package assets 최대 4개 | Contract Owner 협의 | `ReportPackage.assets` | Contract 변경 검토 후 schema와 Consumer 동기화 |
| 대상별 label key | evidence + UI 문구 Owner | source registry | UI 문구 확정 뒤 새 registry revision |
| PLATE_IMAGE 생성·측정 | `recording`·`case` | AssetFacts / K1 | review 11의 생성·크기 handoff 경계 종결 |
| 비시각 correction 실제 Consumer 검증 | `case` | I7·I8, CaseView | 실제 9개 path fixture와 projection 검증 |
| 2028+ 기한 판정 | evidence policy Owner | K2 calendar | 새 holiday snapshot과 policy/catalog revision 발행 |
