# 후보 시각 출처(`at_provenance`) 값 공간 정의 + `at_provenance_label_key` 신설

> 결정일 2026-09-14 · 담당 유소연(`case`) · 근거 `docs/erd-review-case-decisions` PR 리뷰 코멘트 Q-3(신유민 지적) · 이슈 #39 Required-3 후속

## 배경

`contract-job-record-case-view.md` B절 스키마는 `candidates[].at_provenance`를 `"string"`으로만 선언하고 값 공간을 등재하지 않았다. §8 정상 예시는 `TIMELINE_ANCHOR+OFFSET`(SCREAMING+`+` 결합)을 썼는데, 실제 Mock Pack v5 fixture는 전혀 다른 dotted-lowercase 표기(`recording.filename_time` 10건, `readout.overlay_ocr` 2건, `recording.timeline_relative_only` 2건)를 쓰고 있었다 — 신유민이 PR 리뷰에서 지적했다. web이 후보 목록에서 시각 옆에 출처를 붙이는 자리(`value-state-display.md` 규칙 2)가 있어, 값 공간이 없으면 문구 매핑도 미등록 값 fallback도 정할 수 없었다.

case가 fixture를 전수 조사한 결과, `at_provenance`는 사실 한 개가 아니라 **성격이 다른 두 값이 한 필드에 섞여 있었다**:

1. evidence 조립 이후(=`occurred_at` 존재, candidate가 selected) — 값은 `occurred_at.source.kind`(`TimeResolution.resolved.source.kind`의 snapshot) 그대로다. 즉 case가 만든 값이 아니라 evidence가 이미 연 값 공간을 보여주는 것뿐이다.
2. evidence 조립 이전(예: `scenario_relative_rebase_001`의 `CANDIDATE_REVIEW` 단계, `at=null`) — search가 주는 `CandidateEvent`엔 `span{timeline_id, timeline_revision, start_ms, end_ms}`만 있고 시각/출처 필드가 아예 없다. 이건 case가 "아직 절대시각이 없다"는 상태를 설명하려고 자체적으로 만든 값(`recording.timeline_relative_only`)이고, repo 전체에서 이 fixture 한 곳에만 쓰인다.

web은 이어서 raw 문자열을 직접 안 봐도 되도록 `at_provenance_label_key`(`stale_revision_label_key`와 같은 관례) 신설을 제안했고 case도 동의했다. 처음에 web은 스코프를 좁히는 가설을 냈다 — "post-evidence 12건은 `occurred_at.source.label_key`(=`event_time_display.source_label_key`)의 pass-through이므로 새 매핑은 pre-evidence 1개(`candidate.at_provenance.timeline_relative_only`)만 있으면 된다". case가 fixture 16개 스냅샷을 `at_provenance`와 `event_time_display.source_label_key`를 나란히 놓고 전수 대조한 결과 이 가설은 기각됐다.

## 결정된 것

### 1. `at_provenance` 값 공간은 두 갈래다

- **evidence 조립 이후**: `occurred_at.source.kind` pass-through. evidence가 소유한 열린 namespaced string이며, case는 이 값을 별도로 닫힌 목록으로 등재하지 않는다(case가 다시 닫으면 evidence 값 공간과 case 값 공간, 원천이 둘이 된다).
- **evidence 조립 이전**: case 소유의 별도 enum. 현재 `recording.timeline_relative_only` 1개만 등재(열린 enum, 필요해지면 값만 추가).
- §8 예시의 `TIMELINE_ANCHOR+OFFSET`은 fixture 실사용 0건으로 확인돼 폐기하고 실제 값으로 교체한다.
- `readout.overlay_ocr`가 `Observation.source.kind`와 문자열이 같다고 해서 같은 값 공간으로 합치지 않는다 — `contract-plate-overlay-readout.md` §6이 이미 그은 선(「누가 관찰했나」와 「확정 시각의 출처」는 별개 질문)과 같은 원칙이다.

### 2. `candidates[].at_provenance_label_key`(string | null) 신설

raw `at_provenance`가 authoritative이고, `at_provenance_label_key`는 case가 그 값을 보고 골라주는 순수 표시용 파생값이다. web은 raw 문자열을 직접 해석하지 않고 이 키로만 문구를 고른다(§10-12, `stale_revision`/`stale_revision_label_key`와 같은 원칙). 필드는 항상 존재하고(Y) 값만 `null`일 수 있다 — "미등록 값"과 "raw 자체가 case에 알려지지 않음"을 별도 케이스로 나누지 않고 둘 다 `label_key=null`로 합친다.

### 3. 매핑은 pass-through가 아니라 case 소유의 독립 테이블이다

**기각된 가설과 반증.** web의 pass-through 가설(post-evidence 12건 = `event_time_display.source_label_key`와 같은 값)은 fixture 대조로 성립하지 않았다. 가장 명확한 반증은 `scenario_correction_rerun_001.json`이다:

| revision | `at_provenance` | `event_time_display.source_label_key` |
| --- | --- | --- |
| rev0 | `recording.filename_time` | `time.source.filename` |
| rev1 (correction 이후) | `recording.filename_time` (불변) | `time.source.user_correction` |

correction이 `event_time_display`는 갱신하지만 `at_provenance`는 건드리지 않는다 — 「후보의 시각을 어떻게 구했나」와 「확정 시각의 출처가 무엇인가」는 다른 질문이다. 추가로 `scenario_infra_failure_001`은 `at_provenance`가 4개 revision 내내 채워져 있는데 evidence 객체 자체가 없어 `event_time_display`가 없다 — `at_provenance`는 evidence 해결 여부와 무관하게 이미 존재한다.

이 문제는 이슈 #39 Required-3(`_build_candidates_view()`가 `evidence_record["occurred_at"]`로 `at`/`at_provenance`를 덮어쓰던 버그— evidence가 candidate의 `at`/`at_provenance`를 건드리면 안 된다는 원칙 위반)와 같은 종류다. pass-through를 채택했다면 `_label_key` 레이어에서 그 버그의 변종이 재발할 위험이 있었다.

**채택한 매핑** — 관측된 raw 값 3종 각각에 case 소유 label_key를 독립적으로 붙인다:

| raw `at_provenance` | 건수(Mock Pack v5) | `at_provenance_label_key` |
| --- | --- | --- |
| `recording.filename_time` | 10 | `candidate.at_provenance.filename_time` |
| `readout.overlay_ocr` | 2 | `candidate.at_provenance.overlay_ocr` |
| `recording.timeline_relative_only` | 2 | `candidate.at_provenance.timeline_relative_only` |

미등록 raw 값은 `label_key=null` — web이 fallback 문구를 쓴다. 별도의 `candidate.at_provenance_unknown` raw 마커는 두지 않는다(§10-14와 같은 이유로, "null"이 이미 그 상태를 뜻한다).

### 4. `at=null`(pre-evidence) candidate 렌더링

값이 없는 상태(「시각 미확정」)가 출처 문구보다 먼저 보여야 한다는 web 제안은 case 원칙(값이 없으면 `INFO_UNKNOWN`이 먼저 표시되는 `report_field_states` 패턴)과 충돌이 없다. 필드 순서 자체를 스키마가 강제하지는 않으며 web 렌더링 재량이다.

## 아직 미결로 남는 것

- `data/mock/case/` 7개 fixture 파일의 candidates 14곳(post-evidence 12 · pre-evidence 2)에 `at_provenance_label_key` 실값 반영 — 이 문서/계약 확정의 후속 커밋.
- `src/daesingo/case`의 `_build_candidates_view()`(또는 동등 projection 로직)에 매핑 테이블 구현 — 위 fixture 반영과 같은 후속 작업.
- 실제 화면 문구(한국어 라벨 텍스트) 매핑은 web 소관이며, 이 문서가 확정한 label_key 3종 이름을 기준으로 web이 진행한다.

## 소유 경계

| 무엇 | 소유 |
| --- | --- |
| `at_provenance` post-evidence 값 공간(`occurred_at.source.kind`) | `evidence`(`contract-time-resolution.md`) — case는 재등재하지 않는다 |
| `at_provenance` pre-evidence 값 공간(`recording.timeline_relative_only`) | `case`(이 문서, `contract-job-record-case-view.md`) |
| `at_provenance_label_key` 매핑표·파생 규칙 | `case`(이 문서) |
| label_key에 대응하는 실제 표시 문구 | `web` |

## 관련

- `contract-job-record-case-view.md` B절 §6·§7·§8·§10(불변조건 14)·§15
- `contract-plate-overlay-readout.md` §6 (관찰 source와 시각 source를 분리하는 선례)
- 이슈 #39 Required-3
- `docs/modules/case/decisions/candidate-stale-revision-display.md` (`_label_key` 동반 필드 관례의 원조)
