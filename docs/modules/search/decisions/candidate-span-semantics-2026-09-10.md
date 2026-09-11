# `CandidateEvent.span`의 의미 — coarse 후보 창 확정 (A-1 회신)

> 결정일 2026-09-10 · 근거 [이슈 #22](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/22) B-2(김대원, eval 2차 검수) · `docs/modules/case/decisions/eval-round2-ground-truth-and-usage.md` B-2("case가 결정할 사안 아님, search 답 대기")의 후속 회신
> **Producer/Owner:** 서어진(`search`) · **전달 경로:** GitHub 이슈 댓글이 아니라 case에 직접 전달 — 이 문서가 원문을 보존하는 유일한 기록이므로 향후 재확인 시 GitHub 이슈 #22 스레드가 아니라 이 파일을 근거로 삼는다.

## 질문 (김대원, 이슈 #22 B-2)

> 제 매칭 조건은 1차에서 확정한 `event_type 일치 AND IoU >= 0.5`입니다. 실제 사건이 5~20초라면 120초 span의 IoU는 최대 0.15 — span이 (a) coarse 후보 창입니까, (b) 사건 구간(계약 §4-1 예시가 보여주는 18초 폭)입니까?

## 답 (서어진)

**(a) coarse 후보 창이 맞습니다. 사건 구간이 아닙니다.** eval의 IoU≥0.5 매칭이 실패하는 건 fixture 버그가 아니라 매칭 규칙이 coarse 산출물에 안 맞아서입니다.

### 근거

- `span`을 만드는 run은 `operation=CANDIDATE_SEARCH`(coarse)이고, 계약 §4 `uncertainties`도 "Coarse 단계에서 남은 불확실성"으로 정의돼 있다. coarse의 출력은 정밀 사건 구간이 아니라 후보 시간 창이다.
- 계약 불변조건 6-2.9 / §4-1 마지막 줄: "span은 SourceAsset/file boundary도 아니고 최종 `occurred_at`도 아니다." 즉 span은 확정 사건 위치가 아님이 이미 계약에 박혀 있다.
- 정밀 시각은 별도 레이어가 담당한다: fine(`VISUAL_VERIFY`)의 `temporal_facts[].at_offset_ms`, 그리고 최종 `occurred_at`(overlay/`TimeResolution`). span은 그 앞단의 대략적 창이다.
- fixture가 이걸 실제로 증명한다 — `representative_ms = span.start_ms + fine.at_offset_ms`:
  - happy: span 300000–420000, `representative_ms=312480` = 300000+12480, fine `temporal_facts.at_offset_ms=12480`
  - plate: span 600000–660000, `representative_ms=612000` = 600000+12000, fine offset 12000
  - unknown: span 600000–660000, `representative_ms=615000` = 600000+15000, fine offset 15000

즉 넓은 창(span) 안에서 대표 시점(`representative_ms`)이 실제 crossing 순간을 가리키도록 설계돼 있다. 이게 span 설계의 핵심이고, "창 폭이 넓다"는 건 정상이다.

### eval 매칭 규칙 제안 (김대원님께)

coarse 후보 localization은 span IoU가 아니라 `representative_ms` 기준 point/onset error로 잴 것. 계약 §7 소비자 규칙도 이미 "Recall@1/3/10은 `rank` 기준", "span/timestamp error는 timeline-relative"로 point 오차를 전제한다. 구체적으로:

- Recall@K = `rank` 기준 (변경 없음)
- localization = `|representative_ms − gt_onset_ms|` (tolerance 매칭). span IoU를 1차 매처로 쓰지 않기.
- span containment(`start_ms ≤ gt_onset ≤ end_ms`)는 sanity 신호로만 보조 사용.

### 계약 반영

이 애매함이 다시 생기지 않도록 `contract-analysis-run-candidate-event.md` §4-1에 한 줄 명확화를 넣는다(문구 명확화, `contract_version` 유지): "span은 coarse 후보 창이며 사건 길이와 같지 않다. 대표 시점은 `representative_ms`이고, 사건의 정밀 시각은 fine `temporal_facts`와 최종 `occurred_at`이 담당한다." (case가 §4-1·§7 Consumer 규칙에 반영 완료, 2026-09-10.)

### 부수 fixture 이슈 (rebase) — case/mock 소유로 이관

`relative_rebase_001`의 candidate span(500000–560000)이 요청 scope(500000–560000)와 완전히 동일하다 — coarse 후보가 요청 창 전체를 그대로 반환한 꼴이라 localization 정보가 0이다(김대원님이 "오차 정의상 0"으로 지적한 지점). point-error 매처로 바꾸면 치명도는 낮아지지만, 현실성상 span을 scope 안쪽 부분창으로 좁히는 걸 권장한다(예: 512000 근처 ±20~30s). 이건 case/mock 소유 수정이라 유소연님께 넘긴다.

→ **반영 완료(2026-09-10, 유소연)**: `502000~527000ms`(`representative_ms=512000` 유지)로 좁혔다.
