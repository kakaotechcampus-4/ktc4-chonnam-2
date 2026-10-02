# Draft Contract — Case Command (web → case)

**Status:** `Draft` — 팀 합의 전 초안. 합의되면 `docs/architecture/contracts/`로 옮기고(`contract-case-command.md` + `adr/adr-case-command.md`) 이 사본은 지운다(`docs/architecture/contracts/README.md`).

**Contract Version:** `case-command/v0` (초안)

**Owner:** 유소연(`case`) · **Consumer 확인 대상:** 신유민(`web`)

**근거 이슈:** #106 (공용 command 표면) · #171 B-2(상황 응답 전송 경로) · #173 E-4(결과 화면 다른 후보 선택)

---

## 1. 목적

`module-architecture.md` §4-모듈6은 web을 「CaseView를 표현하고 **사용자 명령을 case에 전달**하는 UI」로 정의하지만, 계약은 읽기 방향(`web → case.get_view() → CaseView`)만 있다. 쓰기 방향이 없어서 「무엇을 보낼지는 정했는데 보낼 길이 없는」 명령이 여럿 쌓였다(#106 신유민 정리).

이 문서는 그 명령들이 **함께 쓰는 표면 모양 하나**를 정한다: 어디로 보내나 · 결과를 어떻게 돌려받나 · 실패를 어떻게 알리나. 각 명령의 도메인 규칙은 새로 정하지 않고 이미 정해진 곳을 가리킨다.

## 2. 범위

**이 판본에 넣는 command**

| `kind` | 사용자가 하는 일 | 도메인 규칙의 원문 |
| --- | --- | --- |
| `SELECT_OTHER_CANDIDATE` | 결과 화면에서 「다른 후보 보기 → 다른 후보 선택」 | `contract-correction-record.md`(`OTHER_CANDIDATE`) · #173 E-4 |
| `RECORD_SITUATION_RESPONSE` | 결과 화면 「신고 상황」에서 `[맞아요]`·`[잘 모르겠어요]`(`[다른 상황]`은 §5 — 입력형 판본) | #171 B-2 · ADR-EVIDENCE-005 |
| `MARK_REVIEWED` | 신고자료 최종 확인(`USER_REVIEWED`) | `module-architecture.md` §3-6 · CaseView 계약 B절 `user_reviewed` |
| `RUN_NOTICE_ACTION` | notice에 붙은 발주형 버튼(`GENERATE_REPORT_VIDEO` · `RETRY_PLATE_READ` · `RETRY_SEARCH` · `GENERATE_PLATE_IMAGE`) | CaseView 계약 B절 §7 「`notices[].actions[]` → 발주 매핑」 |

**이 판본에 넣지 않는 것**

- **입력형 action**(`EDIT_EVENT_TIME` · `MANUAL_PLATE_INPUT` · `REVIEW_TIME` · `EDIT_HINT`) — 사용자 입력값이 `CorrectionRecord`로 들어가는 경로라 payload 모양을 `contract-correction-record.md`와 함께 정해야 한다. 다음 판본.
- **초기 후보 선택** — `rank=1` 자동 선택이라 사용자 명령이 아니다(#168 결정 1, #194). 후보 command는 결과 화면에서 다른 후보를 고를 때만 쓴다(#106 신유민 09-23).
- **`rejected_candidate_ids`** — 받지 않는다(#106 결론). 개별 후보를 「아니다」로 지목하는 화면 신호가 생기면 다시 본다.
- **시간 보정 버튼 4종**(조금 전·조금 후 등) — W7 밖(#106 결론).
- **transport**(HTTP 경로·인증·직렬화) — 누가 만들지부터 정한다(`design-refinement-w7-baseline.md` 6순위). 이 문서는 transport와 무관한 요청·응답 모양만 정한다.

## 3. 책임 경계

- **web:** 사용자가 누른 것을 command로 보낸다. 결과 CaseView를 그대로 다시 그린다. 선택·응답을 로컬에서 확정하지 않고, readout·evidence를 직접 부르지 않는다(#106 신유민 09-23).
- **case:** command를 받아 상태 전이·기록·발주를 한다. 성공이든 실패든 **그 시점의 CaseView**를 돌려준다. 신고요건·번호판·시각 값을 command에서 판정하지 않는다(`module-architecture.md` §4-모듈5 ⑦).
- 실제 Job 실행은 command 응답에 포함되지 않는다. 발주가 됐다는 것까지만 돌려주고, 진행은 다음 CaseView의 `running_jobs[]`·`progress[]`로 본다.

## 4. 스키마

**요청**

```json
{
  "case_id": "string",
  "expected_case_rev": "int",
  "kind": "SELECT_OTHER_CANDIDATE | RECORD_SITUATION_RESPONSE | MARK_REVIEWED | RUN_NOTICE_ACTION",
  "payload": "object — kind별(§5)"
}
```

**응답**

```json
{
  "ok": "boolean",
  "error": "null | { \"code\": \"string\", \"message_key\": \"string\" }",
  "case_view": "CaseView | null — 성공이면 command 반영 후, 실패면 변경 없는 현재 값. case_id가 없을 때만 null"
}
```

- `case_view`는 **성공·실패 모두** 싣는다. stale 실패일 때 web이 따로 다시 읽지 않고 최신 화면을 그리게 하기 위해서다.
- `error.code`는 `notices[].code`와 같은 dotted-lowercase 규칙을 따른다(CaseView 계약 B절 §7). `message_key`는 web 문구 키다.

## 5. `kind`별 payload와 규칙

| `kind` | `payload` | 허용 상태 | 성공하면 |
| --- | --- | --- | --- |
| `SELECT_OTHER_CANDIDATE` | `{ "candidate_id": "string" }` | `EVIDENCE_REVIEW` · `READY` | `OTHER_CANDIDATE` CorrectionRecord 1건, `selection_rev` +1, `case_rev` +1. `READY`였으면 `EVIDENCE_REVIEW`로 돌아가고 `user_reviewed=false` |
| `RECORD_SITUATION_RESPONSE` | `{ "value": "CONFIRMED \| USER_UNSURE" }` | 선택된 후보가 있을 때 | `situation_response` 기록(`candidate_ref`=현재 선택 후보, `responded_at`=case가 받은 시각), `case_rev` +1. `READY`였으면 `EVIDENCE_REVIEW`로 돌아간다(아래 「READY에서 다시 조립되는 변경」). 이 응답으로 Package가 준비되면 아래 「성공 뒤 `READY` 재확인」으로 `READY`가 되고 `case_rev`가 +1 더 오른다 |
| `MARK_REVIEWED` | `{}` | `READY` | `user_reviewed=true`, `case_rev` +1 |
| `RUN_NOTICE_ACTION` | `{ "notice_code": "string", "action": "GENERATE_REPORT_VIDEO \| RETRY_PLATE_READ \| RETRY_SEARCH \| GENERATE_PLATE_IMAGE" }` | 현재 CaseView의 `notices[]`에 **그 `code`를 가진 notice가 있고, 그 notice의 `actions[]`에 그 `action`이 있을 때** | CaseView 계약 B절 §7 매핑대로 새 `JobRecord` 1건 |

- **성공 뒤 `READY` 재확인(2026-09-30).** command가 성공하고 stage가 `EVIDENCE_REVIEW`면 case가 `PACKAGE_READY`(FINAL `PASS`/`WARN` + ReportPackage, #167 gate 그대로)를 다시 보고, 성립하면 같은 command 안에서 `READY`로 올린다. `READY` 전이도 `case_rev`를 올리므로 그때는 위 표의 증가분에 +1이 더해진다. transport·web이 따로 전이를 부르지 않는다 — 통로에 판단을 넣지 않는다(#106). 실패한 command 뒤에는 보지 않는다(§6).
- **`READY`에서 다시 조립되는 변경(2026-10-02, orchestration 지표 4차 측정).** `READY`에서 상황 응답(과 입력형 판본의 값 정정)을 받으면 case가 먼저 `EVIDENCE_REVIEW`로 내리고, 위 재확인이 gate가 여전히 성립할 때만 다시 올린다. 내리지 않으면 재조립으로 Package가 사라져도 `READY`로 남아 CaseView 계약 §10-9(「`stage=READY`이면 `requirements_package`가 `PASS`/`WARN`」)를 어긴다. 내려가는 것은 같은 요청의 결과라 `case_rev`를 따로 올리지 않는다(`SELECT_OTHER_CANDIDATE`와 같다) — 그래서 gate가 그대로면 응답 +1, 다시 `READY` +1로 +2다. `user_reviewed`는 그대로 둔다(필드 수정과 별개 — CaseView 계약 B절 `user_reviewed` · #173 값별 경계표). 새 초안이 되는 `SELECT_OTHER_CANDIDATE`만 되돌린다.
- `RUN_NOTICE_ACTION`의 허용 조건은 「화면에 그 버튼이 떠 있었는가」와 같다. web은 `notices[].actions[]`에 있는 값으로만 버튼을 그리므로(CaseView 계약 B절 §7), case도 같은 근거로만 받는다.
- `SELECT_OTHER_CANDIDATE`의 「새 후보 초안을 준비하는 중에는 다시 고르지 않는다」(#173 E-4 조건 1)는 case domain에 「준비 완료」 신호가 없어 이 판본에서 검사하지 않는다 — 진행 화면에서 버튼을 주지 않는 web 규칙에 기대고, worker 배선 때 case가 막는다(PR #190 — W7 기준 문서 6.6순위로 추가 중).
- `responded_at`은 web이 보내지 않고 case가 채운다 — 사용자 기기 시계를 기록값으로 쓰지 않는다.
- **`CORRECTED`(`[다른 상황]`)는 이 판본에서 받지 않는다**(`case.command.invalid_payload`). evidence는 `CORRECTED` 응답에 `SITUATION_CHANGE` CorrectionRecord가 정확히 1건 있어야 조립하고, 없으면 조립 자체를 거부한다(`src/daesingo/evidence/assembly.py` — `CORRECTED requires one SITUATION_CHANGE head`). 바뀐 상황을 보내는 입력형 경로가 없으므로(§2) 입력형 판본에서 둘을 한 command로 함께 연다.

## 6. 실패 코드

| `error.code` | 뜻 | 예 |
| --- | --- | --- |
| `case.command.stale_revision` | `expected_case_rev`가 현재 `case_rev`와 다르다 — 사용자가 본 화면이 이미 바뀌었다 | 다른 탭에서 먼저 후보를 바꿨다 |
| `case.command.unknown_target` | 가리킨 대상이 이 case에 없다 | 없는 `candidate_id` · 없는 `case_id` · 현재 notices에 없는 `notice_code`/`action` 조합 |
| `case.command.not_allowed` | 대상은 있지만 지금 상태에서 할 수 없다 | `CANDIDATE_REVIEW`에서 `MARK_REVIEWED` · 이미 선택된 후보를 다시 선택(무변경) |
| `case.command.invalid_payload` | payload 모양이 틀렸다 | 등재되지 않은 `value` · 필수 키 누락 |

- 실패하면 **아무 상태도 바뀌지 않는다** — `case_rev`·CorrectionRecord·JobRecord·선택 상태 모두 그대로다(#166과 같은 원자성).
- 검사 순서는 `invalid_payload` → `unknown_target`(case) → `stale_revision` → `unknown_target`(대상) → `not_allowed`다. 화면이 낡았으면 대상 검사 전에 먼저 알린다.

## 7. 불변조건

1. command 하나는 CaseView 한 번의 변경이다. 실패한 command는 변경이 없다.
2. 응답의 `case_view.case_rev`는 성공이면 요청의 `expected_case_rev`보다 크거나 같고, 실패면 현재 값이다.
3. command는 신고요건·번호판·시각 값을 판정하지 않는다. 판정 결과는 다음 CaseView 조립에서 evidence가 준 값으로만 바뀐다.
4. web은 command 응답을 받기 전까지 선택·응답을 화면에서 확정값으로 그리지 않는다.

## 8. 예시

```json
// 요청 — 결과 화면에서 다른 후보 선택
{ "case_id": "case_h001", "expected_case_rev": 3, "kind": "SELECT_OTHER_CANDIDATE",
  "payload": { "candidate_id": "candidate_h002" } }

// 응답 — 성공
{ "ok": true, "error": null,
  "case_view": { "case_id": "case_h001", "case_rev": 4, "stage": "EVIDENCE_REVIEW", "user_reviewed": false, "...": "..." } }

// 응답 — 화면이 낡음
{ "ok": false,
  "error": { "code": "case.command.stale_revision", "message_key": "command.stale_revision" },
  "case_view": { "case_id": "case_h001", "case_rev": 5, "...": "..." } }
```

## 9. 미결

- **`case_rev`로 잡히지 않는 변경.** 탐색 시작(`start_search`)·후보 선택(`select_candidate`)처럼 `case_rev`를 올리지 않는 전이가 있다(`src/daesingo/case/domain.py` docstring — `case_rev`는 「요청 시점 케이스 리비전」이다). 그 사이의 command는 stale로 잡히지 않는다. 이 판본의 command는 모두 사용자 결과 화면(`EVIDENCE_REVIEW`·`READY`)이나 notice에서 나와 영향이 작다고 보지만, 확인 필요.
- **`RUN_NOTICE_ACTION` 중복 제출.** 발주가 `case_rev`를 올리는지는 kind마다 정해져 있지 않다(재판독 발주는 올린다고 적혀 있고 나머지는 확인 필요). 올리지 않으면 같은 버튼을 두 번 눌렀을 때 stale 검사로 막히지 않는다. `idempotency_key`를 둘지 함께 정한다.
- **`error.message_key` 값 목록.** web 문구 키라 web과 함께 정한다.
- **transport** — §2.

## 10. 구현할 때 맞출 것 (case 내부)

규칙이 아니라 현재 코드와의 차이다. 진입 함수는 `case.handle_command(request, *, store)`(`src/daesingo/case/command.py`)다.

- `CaseAggregate.mark_reviewed()`에는 여전히 stage 가드가 없다 — command 층이 `READY`만 받는다.
- domain이 「알 수 없는 후보」와 「지금 상태에서 불가」를 같은 `InvalidTransition`으로 던진다 — command 층이 대상을 먼저 확인해 §6의 두 코드로 나눈다.
- `RUN_NOTICE_ACTION`은 같은 kind의 가장 최근 `JobRecord`에서 `input_fingerprint`·`scope_ref`를 그대로 쓴다(`jobs.issue_needed_jobs()`와 같은 원칙). case는 fingerprint를 계산하지 않으므로 이전 발주가 없으면 `not_allowed`다 — `GENERATE_PLATE_IMAGE`처럼 처음 발주되는 kind는 fingerprint 출처가 정해질 때까지 이 경로로 열리지 않는다.
- 성공 뒤 `READY` 재확인은 `service.mark_ready_if_package_ready()`를 그대로 부른다. real(fixture) 경로는 최종 신고영상 관찰(I4, `observation_facts`)이 없어 상황 응답 뒤에도 FINAL이 `UNKNOWN`이라 `READY`에 가지 않는다(ADR-EVIDENCE-008 §6.2) — 이 재확인과 별개로 evidence 쪽 입력이 있어야 한다.
- `RECORD_SITUATION_RESPONSE`는 PR #177이 머지돼야 develop에서 동작한다.
