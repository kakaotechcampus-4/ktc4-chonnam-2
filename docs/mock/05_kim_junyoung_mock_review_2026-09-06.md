# 김준영 담당 Mock Pack 재검수 보고서

- 검수일: 2026-09-06
- 수정 반영일: 2026-09-07
- 작업 브랜치: `codex/fix-mock-pack-seed-consistency` (`develop` 기준)
- 기준 커밋: `12aee4d` (`origin/develop`과 일치)
- 검수 범위: `evidence`, `JobExecution`, `UsageRecord` 및 직접 연결되는 scenario/consumer projection
- 판정: **READY_FOR_SEED_CONSUMERS — 직접 불일치 3건과 집계 문구 1건 수정 완료**

## 1. 재검수 결론

공지에 명시된 **Seed Mode의 의도**와 추가 설계 문서를 반영해 다시 검수했다. Happy 1개와 Partial/UNKNOWN 1개만 제공한 것, Pending 계약을 임의로 채우지 않은 것, opaque ref를 사용한 것은 이번 Pack의 설계 선택이며 결함으로 보지 않는다.

김준영 담당 범위에서 확인한 직접 불일치는 아래 3건으로 좁혔고, 2026-09-07 수정했다.

1. `AnalysisRun.usage_summary`와 참조된 `UsageRecord`의 처리시간·비용이 불일치한다.
2. Happy 시나리오의 위치가 현재 입력보다 구체적으로 만들어졌고 provenance도 맞지 않는다.
3. `CaseView.event_time_display.source_label_key`가 실제 선택된 overlay timestamp source와 불일치한다.

별도로 fixture/계약 객체 수를 세는 문서와 validator의 집계 문구도 바로잡았다. 이 네 항목 외에는 이번 Seed 승인 조건으로 확대하지 않는다.

따라서 현재 Pack은 다음 용도로 사용할 수 있다.

- 고정된 happy/partial shape 확인
- ABSTAIN, UNKNOWN, BLOCK 분기 예시
- 모듈별 consumer parser와 초기 UI 개발

수정 후 usage 집계, 사용자 위치 단서, 사건시각 출처 projection을 validator가 함께 검사한다. 다만 제공 validator의 `0 error / 0 warning`은 전체 계약 적합 판정이 아니라 경량 참조·선택 invariant 검증 결과로 읽어야 한다.

## 2. 확인한 기준 문서

- `docs/product/product-spec.md`
- `docs/product/core-user-flow.md`
- `docs/architecture/module-architecture.md`
- `docs/architecture/mock-pack-v1-refs.md`
- `docs/management/ownership.md`
- `docs/management/contract-consistency-audit-2026-09-06.md`
- `docs/architecture/contracts/adr/adr-consistency-followup-2026-09-06.md`
- 김준영 담당 Final Contract 및 연결 계약
  - `contract-observation.md`
  - `contract-time-resolution.md`
  - `contract-evidence-record-needs.md`
  - `contract-requirement-report-package.md`
  - `contract-job-execution.md`
  - `contract-usage-record.md`
  - `contract-analysis-run-candidate-event.md`
  - `contract-plate-overlay-readout.md`
  - `contract-readout-run.md`
  - `contract-job-record-case-view.md`
- `docs/mock/01`~`04` 및 `CONTRACT_CONFLICTS.md`
- `data/mock/` 전체 fixture, manifest, index, scenario catalog
- `scripts/validate_mock_pack.py`

## 3. 요청 기준별 판정

| 검수 기준 | 판정 | 재검수 결과 |
| --- | --- | --- |
| Contract 일치 | **Seed 기준 통과** | Usage snapshot↔ledger를 정합화했다. 나머지 Pending 접합부는 Seed 결함에서 제외한다. |
| 현실적인 값 조합 | **Seed 기준 통과** | Happy 위치를 근거 없는 주소에서 사용자 hint로 낮춰 보존한다. |
| 실패·UNKNOWN·ABSTAIN | **Seed 기준 통과** | Plate ABSTAIN, GPS UNKNOWN, Requirement BLOCK, Package 미생성이 연결된다. 전체 상태 행렬 부재는 의도된 축소 범위다. |
| Consumer 사용 가능 | **Seed 기준 통과** | shape/parser 개발과 Seed scenario 기준 테스트에 사용할 수 있다. |
| Scenario 참조 일관성 | **Seed 기준 통과** | Pack이 해소한다고 선언한 ID 연결은 유지된다. 미작성 Asset 계층과 B03/B05는 명시된 opaque/Pending 경계다. |

## 4. 수정 반영 결과

### [RESOLVED R1] `AnalysisRun.usage_summary`와 `UsageRecord` 정합화

| Scenario | `AnalysisRun.usage_summary` | 참조된 `UsageRecord` |
| --- | --- | --- |
| happy | `processed_duration_ms=64000`, `total_cost=184.20 KRW` | `processed_duration_sec=64.0`, `cost=184.20 KRW` |
| partial | `processed_duration_ms=41000`, `total_cost=132.90 KRW` | `processed_duration_sec=41.0`, `cost=132.90 KRW` |

`contract-analysis-run-candidate-event.md` §3-4와 `contract-usage-record.md` §8에 따라 `UsageRecord`를 authoritative 값으로 사용해 두 scenario의 snapshot을 수정했다.

validator에는 참조된 Usage row의 processed duration, token, 동일 통화 cost aggregate 검사를 추가했다.

### [RESOLVED R2] Happy 위치를 사용자 기억 단서로 보존

현재 확인 가능한 입력은 다음과 같다.

- 사용자 hint: `미금역 근처`
- GPS Observation: `UNKNOWN`, `source_absent`
- `VisualEvidence ve_h001`: 위치 primitive/support 없음

수정 전 `EvidenceRecord.location.address`는 `미금역 사거리 인근`이고 source는 `search.visual_inference`, `support_refs=[]`였다. 이를 계약에 이미 있는 `location.user_hint="미금역 근처"`로 변경했다.

이는 불확실한 시각·번호판·위치를 새로 만들지 않는 Product Spec 경계에도 맞지 않는다.

source는 `case.user_hint`, observability는 `INFERRED`, 미합의 label key는 `null`로 두었다. 같은 값이 RequirementReport, ReportPackage, CaseView까지 이어지도록 함께 수정했다. 실제 주소로 올리려면 이후 위치 Observation과 frame/support ref가 필요하다.

### [RESOLVED R3] `CaseView` 사건시각 source label 모순 제거

두 scenario의 `TimeResolution`은 모두 `readout.overlay_timestamp`를 `VERIFIED` source로 선택하지만, 수정 전 두 `CaseView`는 다음 값을 표시했다.

```json
"source_label_key": "time.source.filename_time"
```

사용자에게 overlay 판독값을 파일명 시각으로 잘못 표시하는 projection이다. B01에서 source label key namespace가 아직 Pending이더라도, 이미 선택된 source와 반대인 확정 label을 넣는 것은 피해야 한다.

B01의 overlay label key를 새로 결정하지 않고 계약이 허용하는 `null`로 변경했다. validator에는 알려진 label key가 가리키는 source와 실제 `TimeResolution.resolved.source.kind`가 모순되는지 검사하는 assertion을 추가했다.

### [RESOLVED R4] 파일·계약 객체 수 집계 문구 수정

실제 unique 파일 수는 다음과 같다.

- `.json`: 45개
- `.jsonl`: 1개
- `.csv`: 1개
- 합계: 47개

문서는 `JSON 45개(계약/평가 fixture 42 + 관리 JSON 3) + JSONL 1 + CSV 1 = 총 47개 파일`로 수정했다. validator는 scenario JSON을 재사용해 중복 count하지 않고 `검사한 고유 JSON 파일 수: 45`를 출력한다.

Overview의 Contract 객체 수도 Inventory 번호 목록과 같은 21개로 통일했다.

## 5. 문제로 세지 않은 항목

초기 검수에서 문제 후보로 잡았지만, 공지와 추가 문서를 반영해 아래 항목은 이번 수정 요구에서 제외한다.

| 항목 | 이번 판단 | 이유 |
| --- | --- | --- |
| Happy 1개 + Partial 1개뿐임 | **의도된 Seed 범위** | 공지와 Overview가 전체 상태 행렬을 만들지 않는다고 명시한다. |
| CorrectionRecord 부재 | **정상** | 계약이 Draft이며 N02도 미해결이다. 임의 fixture가 더 위험하다. |
| JobExecution 성공 상태만 존재 | **Seed 제한** | retry/stale/failed coverage는 다음 확장 항목이지 현재 데이터 오류는 아니다. |
| RequirementReport 전체 outcome 조합 부재 | **Seed 제한** | 현재 두 scenario의 목적에 필요한 WARN/BLOCK/UNKNOWN은 표현된다. |
| `PlateReadout`/`OverlayTimeReadout`의 `run_id` 부재 | **B03/B05 Pending** | 감사 문서와 conflicts가 result↔run/usage 접합을 미합의로 기록한다. 현재 Seed의 직접 수정 요구로 잡지 않는다. |
| `PLATE_READ` Job 하나가 번호판+오버레이를 실행 | **공지된 임시 가정** | 유소연 결정에 따른 임시 모델이며 신유민 확인 대상이다. 김준영은 결정 결과만 기록·반영하면 된다. |
| `AssetSpan`/Derived Asset ref 미해소 | **B06~B09/opaque ref 경계** | `mock-pack-v1-refs.md`는 미작성 자산 계약을 대신하지 않는 non-normative helper임을 명시한다. |
| Overlay `sample_count`와 직렬화된 `samples[]` 수 차이 | **계약 예시 자체의 모호성** | 계약 예시도 같은 축약을 사용하고 전부 직렬화해야 한다는 명시 invariant가 없다. Mock 오류로 단정하지 않는다. 추후 `samples_truncated` 같은 규칙은 유용하다. |
| Candidate 대표 offset과 최종 `occurred_at` 차이 | **서로 다른 의미** | Architecture는 검색 후보 표시 시각과 evidence가 확정한 사건시각을 구분한다. |
| 15분 duration과 30분 wall-clock range | **증거 부족** | 파일 사이 gap/배치의 요약일 수 있고 현재 계약에 equality invariant가 없다. |
| runtime fixture가 `data/mock/case/`에 위치 | **저장 편의** | `04_mock_validation_report.md`의 owner 표는 `common/runtime` 책임을 올바르게 적고 있다. |
| validator가 전체 JSON Schema를 검사하지 않음 | **공개된 경량 검사 범위** | 스크립트와 문서 모두 경량 검증임을 밝힌다. R1/R3처럼 실제로 필요한 invariant만 추가하면 된다. |

## 6. 계약 후속 논의 1건 — 현재 Seed blocker는 아님

Happy `ReportPackage`의 title/description에는 `흰색 SUV`가 들어가지만 `ReportPackage.report_inputs`와 confirmed `EvidenceRecord`에는 vehicle descriptor 필드가 없다. `core-user-flow.md`의 최종 화면 예시에는 같은 표현이 있어 제품 시나리오와는 맞지만, `ReportPackage` 계약의 “confirmed Evidence + fixed template”만으로는 재생성할 수 없다.

이는 이번 fixture에서 문구를 반드시 제거할 문제라기보다 **계약 입력 범위의 빈틈**이다. Production 전에 다음 중 하나를 결정하면 된다.

- confirmed vehicle descriptor를 Evidence/Package input에 정식 추가
- vehicle descriptor는 사용자 hint임을 별도로 표시
- confirmed input이 없을 때 고정 신고문에서 차량 묘사를 생략

결정 전에는 이 문구를 `EvidenceRecord`만으로 생성 가능한 값이라고 검증하지 않는다.

## 7. 실패·UNKNOWN·ABSTAIN 검수

이번 두 scenario는 Seed 목표에 맞는 최소 분기를 제공한다.

- `PlateReadout.abstained=true`와 `Observation.status=NEEDS_REVIEW`
- ABSTAIN이어도 실행 자체는 `SUCCEEDED`
- GPS 부재를 `Observation.status=UNKNOWN`, `value=null`로 표현
- Partial Evidence에서 미확정 번호판·위치값을 만들지 않음
- `EvidenceNeeds.PLATE_REREAD`
- Requirement의 `BLOCK`과 `UNKNOWN` check를 구분하고 overall을 `BLOCK`으로 집계
- `BLOCK`일 때 `ReportPackage`를 생성하지 않음

따라서 “실패 상태 전체를 구현할 수 있는 Pack”은 아니지만, 공지된 Seed 기준에서는 부족을 결함으로 보지 않는다. 이후 Full Mock 단계에서는 TimeResolution conflict/fallback, JobExecution failed/stale/retry, Requirement scope별 상태, Package export 실패를 별도 scenario로 확장하면 된다.

## 8. Consumer 사용 범위

| Consumer | 지금 사용 가능 | 주의 |
| --- | --- | --- |
| `case` | Evidence, Requirement, Package, partial review shape | B01/B02 Pending 범위는 그대로 유지 |
| `web` | READY/WARN, EVIDENCE_REVIEW/BLOCK, ABSTAIN/UNKNOWN 정적 렌더 | 미합의 source label은 fallback 문구 사용 |
| `eval` | happy ground truth/prediction shape, 기본 usage field 파싱 | Full Mock 전까지 partial 평가 coverage 없음 |
| `evidence` | TimeResolution→Evidence→Requirement→Package 흐름 | 위치는 주소가 아니라 사용자 기억 단서임을 유지 |

## 9. 최소 수정 체크리스트

- [x] R1: 두 scenario의 `usage_summary`와 `UsageRecord` aggregate 정합화
- [x] R2: Happy 위치를 `user_hint` 수준으로 되돌리고 downstream projection 동기화
- [x] R3: 두 `CaseView`의 시각 source label을 Pending-safe한 `null`로 변경
- [x] R4: unique JSON 45개/전체 파일 47개로 집계 정리, 계약 객체 21개로 통일
- [x] R1/R3에 대한 focused validator assertion 추가
- [x] 수정 후 `validate_mock_pack.py`와 `check_boundaries.py` 재실행

위 체크가 끝나면 김준영 담당 Seed Mock은 **`READY_FOR_SEED_CONSUMERS`**로 올려도 된다. B01/B02, B03/B05, B06~B09, CorrectionRecord, 전체 실패 행렬은 Full Mock/계약 후속 과제로 남긴다.

## 10. 검증 실행 기록

```text
git rev-list --left-right --count develop...origin/develop
0  0

python scripts/validate_mock_pack.py
검사한 고유 JSON 파일 수: 45
오류(ERROR): 0
경고(WARN): 0

python scripts/check_boundaries.py
PASS — 경계·계약 정합성 위반 0건
NOTE — 코드 없는 경로 7건, 미작성 자산 계약 coverage 5건
```

위 PASS는 제공 스크립트의 경량 검사 범위 내 결과다. R1의 usage aggregate와 R3의 known source-label 모순은 자동 검증하며, 계약 의미 전체나 아직 Pending인 B01/B02, B03/B05, B06~B09를 닫았다는 뜻은 아니다.
