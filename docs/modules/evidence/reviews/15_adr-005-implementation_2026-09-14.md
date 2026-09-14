# ADR-EVIDENCE-005 구현 및 검수 보고서

> 검수일: 2026-09-14
> 범위: D2의 evidence 소유 catalog·코드·테스트·Artifact·문서
> 상태: **evidence 범위 검증 완료 / 전체 제품은 PARTIAL_READY**

## 결론

`policy/requirement-rules-v4`를 발행하고 활성 catalog를 v4로 전환했다. `FINAL_PACKAGE` 무조건 rule에서 `package.event.violation_visible_in_report_video`, `package.event.pre_context_present`, `package.event.post_context_present`만 제거했으며, EVIDENCE 4개·남은 FINAL_PACKAGE 12개·시각 조건부 selector 네 갈래·나머지 outcome 매핑은 v3와 같다.

재실행 결과 H는 FINAL_PACKAGE `UNKNOWN → PASS`로 바뀌어 `pkg_h001`, U는 `UNKNOWN → WARN`으로 바뀌어 `pkg_u001`이 발행됐다. P와 R은 FINAL_PACKAGE 평가 대상이 아니므로 기존 EVIDENCE 결과가 그대로다. 이것은 남은 판정을 완화한 결과가 아니라 제품 안에 판정 주체가 없던 세 rule을 제거한 결과다.

경찰민원24 요건 자체가 사라진 것은 아니다. 사건 동일성은 사용자의 사건 선택을 입력 전제로 두고, 상황 확인은 `package.evidence.situation_response`가 계속 fail-closed로 맡으며, 신고영상의 전후 포함 보장은 생성 주체인 `recording`으로 이관됐다. 녹화 경계 처리(D2-e)는 `recording` Owner 미결로 남는다.

## ADR §9 검증표

| 확인 | 실제 결과 | 증빙 |
| --- | --- | --- |
| 활성 catalog `policy_ref` | **PASS** — `policy/requirement-rules-v4` | `policy_catalog.py`의 단일 파일 선택점, `test_active_catalog_applies_adopted_size_and_deadline_rules`, `test_k3_catalog_selects_four_and_thirteen_rules_from_data` |
| `FINAL_PACKAGE` 무조건 rule 수 | **PASS** — 12개, 조건부 1개 선택 후 `checks[]` 13개 | `test_k3_catalog_selects_four_and_thirteen_rules_from_data`; v3/v4 구조 비교 |
| H overall·Package | **PASS** — `PASS`, `pkg_h001`, `PACKAGE_READY=true` | `test_happy_connects_refs_and_emits_ready_package`; H baseline |
| U overall·Package | **PASS** — `WARN`, `pkg_u001`, `PACKAGE_READY=true` | `test_unknown_preserves_uncertainty_and_emits_warn_package`; U baseline |
| `situation_response=NOT_ASKED` | **PASS** — `UNKNOWN` 유지, 정상 Package 미발행 | `test_k3_not_asked_and_incomplete_render_are_unknown`; H `policy_guard_check` |
| 제거된 세 rule code | **PASS** — 활성 catalog와 네 baseline의 모든 `checks[]`에서 0건 | `test_d2_removed_event_context_rules_are_absent_and_legacy_inputs_are_ignored`; Artifact 전수 scan |
| 관찰 fact 입력 | **PASS** — 번호판·시각 표시·사후 각인만 소비하고, 제거된 legacy key는 malformed 값이어도 판정 무영향 | 같은 D2 회귀 테스트; `test_k3_selector_and_observation_configuration_errors`로 남은 번호판 fact 구조 검증 |
| Artifact v3 참조 | **PASS** — baseline 4종과 `run-summary.json`에서 `policy/requirement-rules-v3` 0건 | 재실행 후 UTF-8 전수 scan |
| v3 보존 | **PASS** — 파일 존재, 작업 트리 diff 0건, SHA-256 `0d6bb106e5a637a6405eb74c353c4d06fc29f4a7e04a1594985db35d981d3e47` | `git diff --exit-code -- src/daesingo/evidence/requirement_rules_v3.json`; Artifact의 이전 fingerprint와 동일 |

## 전후 비교

| Scenario | v3 | v4 | 변화 이유 |
| --- | --- | --- | --- |
| H | EVIDENCE `PASS`, FINAL_PACKAGE `UNKNOWN`, Package 0건 | EVIDENCE `PASS`, FINAL_PACKAGE `PASS`, `pkg_h001` | 유일한 UNKNOWN이던 세 check 제거. 나머지 13 check는 모두 PASS |
| U | EVIDENCE `WARN`, FINAL_PACKAGE `UNKNOWN`, Package 0건 | EVIDENCE `WARN`, FINAL_PACKAGE `WARN`, `pkg_u001` | 유일한 UNKNOWN이던 세 check 제거. 남은 분포는 PASS 10·WARN 3 |
| P | EVIDENCE `UNKNOWN → WARN`, FINAL_PACKAGE 평가 없음, Package 0건 | 동일 | FINAL_PACKAGE 비대상 Scenario라 변경 없음 |
| R | EVIDENCE `WARN → WARN`, FINAL_PACKAGE 평가 없음, Package 0건 | 동일 | FINAL_PACKAGE 비대상 Scenario라 변경 없음 |

사라진 check는 정확히 세 개다.

- `package.event.violation_visible_in_report_video`
- `package.event.pre_context_present`
- `package.event.post_context_present`

## 완료 조건과 테스트 대응

| 완료 조건 | 확인 수단 |
| --- | --- |
| v4가 v3의 나머지 내용을 문자 의미상 그대로 계승 | JSON 구조 비교: 메타데이터와 세 rule 제거 후 v3/v4 동등 |
| 활성 선택점 한 곳, 출력 `policy_ref`는 catalog 유래 | `policy_catalog.py`; catalog loader와 출력값을 비교하는 K3 테스트 |
| 남은 관찰 fact 구조 검증 유지 | `test_k3_selector_and_observation_configuration_errors` |
| 제거된 legacy fact 입력 무영향 | `test_d2_removed_event_context_rules_are_absent_and_legacy_inputs_are_ignored` |
| H/U Package 발행, P/R 무변화 | `test_mock_integration.py`와 네 baseline |
| 공용 Mock 원본 비변경 | `test_adapter_does_not_mutate_shared_sources`; 공용 validator 3종 |
| v3 보존·Artifact v3 ref 제거 | 파일 diff/hash와 Artifact 전수 scan |

## 실행 검사

```text
python -m unittest discover -s tests/evidence -p 'test_*.py'
42 tests OK

python -m daesingo.evidence.mock_integration
H PASS + pkg_h001 / U WARN + pkg_u001 / P·R FINAL_PACKAGE 없음

python data/mock/validate_mock_pack.py
46 JSON / 7 scenarios, 0 errors

python scripts/check_contract_fixtures.py
structure 60 / JSON 26 / semantic 104 PASS

python scripts/check_boundaries.py
0 violations

python -m ruff check src/daesingo/evidence tests/evidence
All checks passed

python -m compileall -q src/daesingo/evidence tests/evidence
PASS

git diff --check
PASS
```

공용 validator 결과는 그 validator가 검사하는 fixture 구조·의미 정합성만 뜻한다. 실제 case projection, Runtime E2E, AI/OCR 정확도, 외부 신고 성공, Consumer Owner 수락을 증명하지 않는다.

## 증명하지 못한 것과 남은 차이

- **I4 Runtime 관찰 배선:** H/U의 `plate_visible_in_report_video`와 시각 표시 fact는 adapter가 `mock_only: true`로 주입한다. 특히 번호판 가시성은 v4 FINAL_PACKAGE에 남는 유일한 무조건 관찰 rule이다. 실제 Runtime에서는 I4가 끝나기 전 `not_observed → UNKNOWN`으로 Package가 다시 막힌다. Mock Package 발행을 Runtime 준비 완료로 해석할 수 없다.
- **I2 공용 fixture 차이:** 디스크의 `pkg_h001`·`pkg_u001`은 아직 `report-package/v1`이고 provenance는 `policy/package-assembly-v1`이다. 공용 U는 위치가 없는데도 `tmpl/safety-report-generic-v1`을 쓴다. 실행 baseline은 `report-package/v1.1`, `safety-report-policy/v1.1`, U의 `tmpl/safety-report-generic-no-location-v1`을 쓴다. 이는 `case` 소유 I2 재렌더 미완의 기존 차이이며 D2 회귀가 아니다. `comparison.known_differences`에 보존했다.
- **실제 Consumer:** `consume_contracts`는 공개 Contract reader Mock이며 실제 CaseView projection이나 `USER_REVIEWED` 산출을 증명하지 않는다.
- **신고영상 내용과 경계:** 세 rule 제거는 경찰민원24 요건 충족이나 REPORT_VIDEO가 실제 사건 전후를 포함한다는 사실을 증명하지 않는다.

## 후속·통합 대기

| 항목 | 담당 | 상태와 필요한 조치 |
| --- | --- | --- |
| D2-e 녹화 경계·span 정책 | `recording` Owner 정철원, 필요 시 `case` 협의 | **OPEN.** 사건이 파일 시작·끝에 걸릴 때 생성 실패/경고/사용자 고지를 결정한다. evidence가 대신 닫지 않는다 |
| I4 번호판·시각 관찰 전달 | `readout` 생산, `case`·`recording` 접합 | `plate_visible_in_report_video`, `time_overlay_visible` 또는 `post_stamp_applied`를 실제 Runtime에서 evidence 호출 입력으로 전달한다 |
| I2 공용 H/U Package 재렌더 | Mock Pack / `case` Owner | v1.1 contract·policy·no-location template으로 공용 fixture를 재렌더하고 Consumer를 검증한다 |
| D1 case 표시·고지 | `case` Owner | 위치 부재 field state와 사용자 고지 code·발동 조건을 반영한다 |
| 실제 CaseView projection | `case` Owner 유소연 | 동일 Artifact를 실제 projection 호출 경로에 연결한다 |
| PLATE_IMAGE 생성·측정 | `recording`·`case` | review 11의 생성·크기 handoff 경계를 종결한다 |
| 비시각 correction Consumer 검증 | `case` | I7·I8의 실제 9개 path projection을 확인한다 |
| 2028+ 기한 정책 | evidence policy Owner | 새 공휴일 snapshot과 policy/catalog revision을 발행한다 |

## 변경 이력

- `963f5b5` `feat(evidence): v4 catalog로 판정 주체 없는 rule 제거`
- `a34c8cb` `mock(evidence): v4 정책 baseline으로 H U Package 복구`

## 주간 회의 보고 요약

판정 주체가 없어 H/U Package를 영구 `UNKNOWN`으로 막던 사건 장면·전후 상황 rule 세 건을 ADR-EVIDENCE-005에 따라 v4 catalog에서 제거했고, Mock 재실행에서 H `PASS`·U `WARN` Package 발행을 확인했다. 요건 확인 책임은 사용자 확인과 `recording` 생성 경계로 이관됐으며, 녹화 경계 D2-e와 실제 번호판·시각 관찰 I4 배선은 통합 대기다.
