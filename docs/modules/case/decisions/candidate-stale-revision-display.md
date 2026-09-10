# `CaseView.candidates[]` stale-revision 표시 필드 — case 소유 구현 결정

> 결정일 2026-09-09 · 근거 [이슈 #18](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/18) 정철원(recording) 답변 · `contract-job-record-case-view.md` §13 note("candidates[]의 stale-revision 표시 필드... 필드명·모양은 case Owner가 구현 시 정한다") · `docs/mock/05_mock_deep_review_report.md` P1-10
>
> **담당:** 유소연(`case`) · **Consulted:** 정철원(recording, B09 규칙 원 결정자)

## 배경

`contract-recording-timeline-asset-span.md` §5(B09, 2026-09-07 확정)는 "Search 결과는 `CandidateEvent.span`에 `timeline_revision`을 보존하고, 과거 Candidate는 rebase 후 최신 revision 기준으로 mutate하지 않는다"고 정했다. 같은 문서 §13 note는 "`CandidateEvent.span.timeline_revision`이 현재 `RecordingTimeline.revision`과 다르면 `case`가 비교해 「과거 timeline revision 기준」임을 표시한다"면서도 **정확한 필드명·모양은 명시적으로 case Owner에게 위임**했다("여기서 임의로 만들지 않는다").

## 결정된 것

`CaseView.candidates[]`의 각 항목에 다음 두 필드를 추가한다:

- `timeline_revision: integer` — 이 candidate가 생성될 당시 참조한 `RecordingTimeline.revision`(=`CandidateEvent.span.timeline_revision`을 그대로 투영). rebase 이후에도 절대 mutate하지 않는다(B09).
- `stale_revision: boolean` — `timeline_revision`이 이 candidate가 속한 `RecordingTimeline`의 **현재** `revision`과 다르면 `true`. case가 매 투영 시점에 비교해 계산하는 파생값이며 recording이 별도로 내려주지 않는다.
- `stale_revision_label_key: string | null`(2026-09-10 추가, 이슈 #26 B-web-8 후속) — `stale_revision=true`일 때 표시 문구를 고를 키. `stale_revision=false`면 `null`. 등록값은 `candidate.stale_timeline_revision` 1개.

## 이유

- `timeline_revision`만 노출하면 web이 "현재 revision"을 다시 조회해 직접 비교해야 한다 — `contract-job-record-case-view.md` §7-(4)/§12 "web은 `info_state`만 보고 표시하며 직접 해석하지 않는다"는 원칙과 같은 방향으로, 비교 결과(`stale_revision`)까지 case가 미리 계산해 내려준다.
- `timeline_revision`은 그대로 남겨 감사(audit)·디버깅 시 "몇 번째 revision 기준이었는지"를 알 수 있게 한다.
- `stale_revision_label_key`가 없으면 web이 "과거 timeline 기준" 같은 문구를 코드에 직접 하드코딩해야 한다 — 신유민이 이슈 #26 A-⑤·B-web-8에서 지적한 그대로다. `*_display.source_label_key`·`running_jobs[].label_key`와 같은 원칙으로 case가 키만 내려주고 문구는 web이 고른다.
- 세 필드 모두 기존 `candidates[]` 스키마(§6 compact schema)에 추가하는 것이며 기존 필드를 변경하지 않는다 — 하위 호환.

## Fixture 반영

`data/mock/case/scenario_relative_rebase_001.json` — `case_rev:1`(rebase 전, `timeline_revision:1`·`stale_revision:false`·`stale_revision_label_key:null`) → `case_rev:2`(rebase 후, `timeline_revision:1` 그대로·`stale_revision:true`·`stale_revision_label_key:"candidate.stale_timeline_revision"`)로 전환하는 두 `CaseView` 스냅샷.

## 남은 것

- ~~`contract-job-record-case-view.md` 본문에 이 필드를 정식 등재할지는 PM/case 협의 대상~~ → **종결(2026-09-10)**: 세 필드 모두 B절 §5(JSON schema)·§6(필드 정의표)에 정식 등재했다(이슈 #26 B-web-8).
- ~~`timeline_revision`/`stale_revision`/`stale_revision_label_key`는 현재 `scenario_relative_rebase_001`에만 존재하고 나머지 6개 시나리오의 `candidates[]`에는 없다~~ → **종결(2026-09-10, 같은 날 후속)**: 나머지 5개 시나리오(`happy`·`correction_rerun`·`plate_reread`·`unknown_abstain_partial`·`infra_failure`, `empty`는 `candidates=[]`라 대상 없음)의 모든 `candidates[]`에 `timeline_revision:1`·`stale_revision:false`·`stale_revision_label_key:null`을 backfill했다 — 전부 단일 `RecordingTimeline`(revision 1)만 쓰는 시나리오라 값 자체는 자명하다(recording fixture로 확인). 이제 계약 §5의 `Y`(필수) 표시와 fixture가 7개 시나리오 전부 일치한다.
