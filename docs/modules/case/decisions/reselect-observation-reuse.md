# 다른 후보를 골랐다가 돌아올 때(A→B→A) 관찰 결과 재사용

> **상태: 결정 — (b) 채택** · 결정일 2026-09-30 · 담당 유소연(`case`) · 근거 W7 고도화 7순위 orchestration 지표 러너 2차 측정(PR #214)
> 정책 표(`doc-research/부분 재실행 정책 표 초안 v1`)의 해석이라 case 단독 결정 범위다(`ownership.md` — case는 「무엇을 왜 언제 다시」를 정한다).

## 배경

결과 화면에서 사용자는 「다른 후보 보기 → 선택」으로 후보를 바꿀 수 있다(#173 E-4, command `SELECT_OTHER_CANDIDATE` #216). 후보 A를 보다가 B를 골랐다가 다시 A로 돌아오는 순서(A→B→A)는 web이 이 경로를 붙이면 자연스럽게 나온다.

지금 case는 A로 돌아올 때 **A의 관찰(Fine 2차 확인 · IncidentClip · 번호판·시각 판독)을 처음부터 다시 돌린다.** 두 adapter 모두 관찰 캐시가 하나뿐이고, 키가 `(candidate_id, selection_rev)`라 재선택마다 `selection_rev`가 올라 키가 바뀐다(`RealAdapter`·`RealVideoAdapter`의 `_observations_key`). 실영상 경로에서 Fine은 유료 호출이라, 돌아올 때마다 같은 장면에 비용이 다시 든다.

정책 표 2행은 이 경우를 이렇게 적는다.

| 사용자가 고친 것 | kind | 다시 도는 것 | 폐기되는 것 | 절대 안 건드리는 것 |
| --- | --- | --- | --- | --- |
| 다른 후보 선택 | OTHER_CANDIDATE | 2차 확인(**필요시**) + 병렬 보강 | 증거 기록(무효화) | 1차 탐색 |

「필요시」가 무엇인지는 정해진 적이 없다. orchestration 지표 조합표 초안(v2)은 「같은 후보로 돌아오면 재호출은 위반」으로 해석했지만, 러너와 구현은 「새 선택이면 다시 관찰」로 되어 있어 **해석이 서로 반대**다. 그래서 러너는 지금 이 비용을 위반으로 세지 않는다.

## 왜 키에 `selection_rev`가 들어갔나 (지켜야 할 것)

`selection_rev`는 이유가 있어서 들어갔다. 시간 단서를 고치면(`TIME_HINT_EDIT`) 정책 표 1행대로 **후보·2차 확인·선택·증거를 버리고** 1차 탐색부터 다시 돈다. 재탐색 결과에 같은 `candidate_id`가 다시 나와도 이전 Fine 결과를 쓰면 안 된다 — `candidate_id`만 키로 쓰면 이걸 잘못 재사용한다(`test_real_video_new_selection_of_same_candidate_observes_again`). 즉 **「같은 후보」와 「같은 입력」은 다르다.**

## 선택지

| | 규칙 | 장점 | 문제 |
| --- | --- | --- | --- |
| (a) 지금 동작 | 새로 선택하면 항상 다시 관찰한다 | 단순하다. 오래된 관찰을 쓸 위험이 없다 | A→B→A마다 유료 Fine·판독이 다시 돈다. 「필요시」를 「항상」으로 읽는 셈이다 |
| **(b) 채택** | **같은 탐색 결과 안에서** 이미 관찰한 후보로 돌아오면 그 관찰을 재사용한다. 재탐색(`TIME_HINT_EDIT` 등으로 후보 목록이 바뀜)하면 전부 버린다 | 「필요시」를 「그 후보에 대한 관찰이 아직 없을 때」로 읽는다. 실영상 비용이 A→B→A에서 B 한 번만 든다 | 캐시가 후보별로 여러 개가 된다. 「같은 탐색 결과」를 무엇으로 알아볼지 정해야 한다 |
| (c) | `candidate_id`만 같으면 재사용 | 가장 단순한 캐시 | 재탐색 뒤 같은 id를 잘못 재사용한다 — 위 「지켜야 할 것」 위반. 채택 불가 |

## 결정: (b)

근거:

1. **정책 표 문구.** 2행은 「2차 확인(필요시)」다. 1행(`TIME_HINT_EDIT`)처럼 「2차 확인」을 폐기 목록에 넣지 않았다 — 다른 후보 선택은 관찰을 버리는 행동이 아니라, **증거 기록만 무효화**하는 행동이다.
2. **캐시 규칙과 같은 원칙.** JobRecord 캐시는 「같은 `(case_id, kind, input_fingerprint)`에 SUCCEEDED 결과가 있으면 재사용」이다(`contract-job-record-case-view.md` A절 §7). A→B→A에서 A의 관찰 입력(같은 탐색 결과의 같은 후보 span)은 바뀌지 않았다 — 입력이 같으면 재사용한다는 기존 원칙을 동기 관찰 경로에도 그대로 적용하는 것이다.
3. **정정 승계와 충돌하지 않는다.** #173 E-1(정정은 같은 `selection_rev` 안에서만 잇는다)은 **사용자 정정**의 범위이고, 이 문서는 **관찰 결과**의 범위다. A로 돌아왔을 때 이전 A에서 한 정정은 지금처럼 따라오지 않는다(새 선택 context). 관찰은 AI가 본 사실이라 선택 context와 무관하고, 정정은 사용자가 그 선택에서 한 행동이라 선택 context에 묶인다.

「같은 탐색 결과」 알아보기(구현 방향 — 이 문서가 정하는 것은 규칙까지다):

- case가 후보 목록을 교체하는 곳은 `receive_candidates()` 하나이고, 역행(`regress_to_searching()`)은 후보를 비운다. **후보 목록이 교체되거나 비워지면 관찰 캐시를 전부 버린다.** 그 사이에는 후보별로 관찰을 보관한다.
- 캐시 키는 `candidate_id`와 「후보 목록 세대」(교체될 때마다 바뀌는 case 내부 값)로 한다. `selection_rev`는 키에서 뺀다 — 정정의 선택 context용으로는 그대로 쓴다.
- 조립(`assemble_evidence_bundle()`)은 지금처럼 매번 현재 `selection_rev`·그 선택의 정정으로 다시 한다. 재사용하는 것은 관찰 단계뿐이다.

## 바뀌는 것

> **2026-09-30 반영 완료.** 러너 3차 측정: ③ 322 → 0(그중 Fine 100회) — `experiments/orchestration-metrics-2026-09-30.md` 「3차 측정」. 「후보 목록 세대」는 `CaseAggregate.candidate_generation`이다.

| 무엇 | 변경 |
| --- | --- |
| `RealAdapter`·`RealVideoAdapter` | 관찰 캐시를 후보별로, 후보 목록 교체 시 비움 |
| `tests/case/test_correction_partial_rerun.py` | `test_real_video_new_selection_of_same_candidate_observes_again`은 그대로 통과해야 한다(재탐색 뒤라 재관찰). A→B→A에서 A 재관찰이 없는지 새 테스트 |
| orchestration 지표 러너 | ③의 입력 키를 (후보, 세대)로 — A→B→A 재관찰을 ③ 위반으로 센다. 지금 수치(0)가 수정 전에 몇 건으로 나오는지 먼저 재서 기록 |
| 정책 표 2행 비고 | 「필요시 = 같은 탐색 결과에서 그 후보의 관찰이 아직 없을 때」 한 줄 |

## 결정하지 않는 것

- **Fine 결과의 유효 기간.** 같은 탐색 결과 안에서 시간이 오래 지나도 재사용한다. 영상과 입력이 그대로면 결과가 달라질 이유가 없다고 보지만, provider 쪽 모델이 바뀌는 경우 등은 search 판단이다.
- **worker 경로.** 비동기 Job으로 관찰이 돌면 이 재사용은 JobRecord 캐시 규칙(A절 §7)으로 성립해야 한다. 그때 `input_fingerprint`에 무엇을 넣을지는 `input-fingerprint-implementation-label-deferred.md`의 재검토 트리거와 함께 본다.
- **정정 승계.** A로 돌아왔을 때 이전 A의 정정을 되살릴지는 #173 E-1 범위다 — 이 문서로 다시 열지 않는다.

## 관련

- `doc-research/부분 재실행 정책 표 초안 v1` 1·2행
- `case-selection-revision-persistence.md` — `selection_rev`의 뜻
- `contract-job-record-case-view.md` A절 §7 — 캐시 재사용 조건
- `contract-correction-record.md` #173 E-1 명확화 — 정정 supersede chain은 같은 `selection_rev` 안에서만
- `experiments/orchestration-metrics-2026-09-30.md` — 러너 2차 측정 (PR #214, 머지 전)
