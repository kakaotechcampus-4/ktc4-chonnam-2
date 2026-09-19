# Evidence `source.kind` Registry — Mock이 신설한 5종 승인 기록

> 활성 revision: **v2** (2026-09-14) · v1은 아래에 역사 기록으로 보존

> 결정일 2026-09-08(승인) · 등재일 2026-09-09 · Decider 김준영(evidence Owner) · 근거 [이슈 #19](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/19) "A. 정합 검토 답변 · 미등재 `source.kind` 5종 승인/교체"
>
> Mock Pack 심층 검토(`docs/mock/05_mock_deep_review_report.md` P1-2)가 계약에 등재되지 않은 `source.kind` 값 5종을 발견했다. 김준영이 이슈 #19에서 5종 전부를 승인했고, "새 kind를 더 만들기 전에 위 대응을 evidence 소유의 versioned registry/문서에 먼저 등재해야 한다"고 명시했다. 이 파일이 그 등재다.

## 등재 값 (v1)

| `source.kind` | `observability` | `source.label_key` | 용도 |
| --- | --- | --- | --- |
| `recording.file_metadata_time` | `OBSERVED` | `time.source.file_metadata` | 파일 메타데이터(생성/수정 시각)에서 얻은 시각 후보. `recording.filename_time`과 별개 소스 |
| `case.user_location_hint` | `OBSERVED` | `location.source.user_hint` | 사용자가 직접 입력한 위치 힌트(주소·좌표 아님) |
| `evidence.category_mapping` | `INFERRED` | `event.source.category_mapping` | `VisualEventType` → 사건 유형 표시값 매핑 결과 |
| `evidence.violation_expression` | `INFERRED` | `event.source.violation_expression` | 위반 사실을 신고문 표현으로 변환한 결과 |
| `case.user_correction` | (TimeResolution/`occurred_at` provenance 전용, `EvidenceValue.source`에는 `observability` 필드를 추가하지 않는다) | `time.source.user_correction` | 사용자가 명시적으로 정정한 시각 값의 provenance |

## 이 registry의 성격

- **닫힌 목록이 아니다.** 다른 모듈과 마찬가지로 접두어 규칙(`<module>.<detail>`)을 지키는 열린 enum이며, 신규 `source.kind`가 필요하면 여기 추가하고 evidence Owner 승인을 받는다.
- 이 5종은 이미 `data/mock/{evidence,case}/*.json`의 `EvidenceValue.source.kind`/`TimeResolution.resolved.source.kind`에서 실제로 쓰이고 있었다 — 승인은 기존 mock 관례를 추인한 것이며, 이 등재로 인한 fixture 변경은 없다(2026-09-09 3라운드 재확인, 값 5개 전부 이미 이 형태로 사용 중임을 grep으로 확인).
- `contract-evidence-record-needs.md`/`contract-time-resolution.md`가 `source.kind`의 최종 스키마(값 자체는 열려 있되 `{kind, label_key}` 구조·`observability` 결합 규칙)를 소유한다. 이 파일은 그 스키마 안에서 이 프로젝트가 실제로 쓰는 값 목록만 관리한다.

## 다른 registry가 소유하는 것

- `safety_report_type` 값 공간(사건 유형 → 신고유형 표현) — 이슈 #19에서 반려된 `UNSAFE_LANE_CHANGE` 등 placeholder를 승인하지 않는다. 복원된 evidence 원본 조사 PDF와 현재 Architecture를 근거로 4종 `VisualEventType` → 신고유형 → 표현/template을 `safety-report-policy-v1.md`에 별도 등재했다.
- `EvidenceNeeds`(v1)에 "AI가 사건 유형 자체를 확정하지 못함"을 표현할 신규 `kind` — evidence/PM 결정 대상(`docs/mock/05_mock_deep_review_report.md` §12 김준영 ⑥).

## v2 revision — `case.user_correction` 적용 범위 확장

> 결정일 2026-09-13 · 반영일 2026-09-14 · Decider 김준영(evidence Owner) · 근거 ADR-EVIDENCE-002 §6(K4)

v2는 신규 kind를 추가하지 않고 v1의 `case.user_correction` 행 하나만 다음과 같이 확장한다. 나머지 네 행은 v1과 동일하다.

| `source.kind` | 컨테이너 | `observability` | `source.label_key` | 용도 |
| --- | --- | --- | --- | --- |
| `case.user_correction` | 비시각 `EvidenceValue` | `OBSERVED` | `null` | 실제 반영된 head correction이 고친 `event.visual_event_type`, `event.safety_report_type`, `event.violation_expression`, `vehicle_number`, `location.coord`, `location.address`, `location.place_name`, `location.search_keyword`, `location.user_hint`의 값 단위 provenance |
| `case.user_correction` | `occurred_at` | 필드 없음 | `time.source.user_correction` | `TimeResolution`이 실제 선택한 발생시각 correction provenance. 기존 경로와 의미를 유지 |

비시각 값은 `source.ref={kind: correction_record, ref: <correction_id>}`, `support_refs`의 같은 ref, `user_corrected=true`, `needs_review=false`를 함께 가진다. 정정값에서 파생된 신고유형·위반표현은 이 행으로 바꾸지 않고 각 매핑 kind와 `INFERRED`를 유지한다. 실제 Consumer와 CaseView 검증은 공용 비시각 correction fixture가 생긴 뒤의 통합 항목 I7·I8에 남는다.
