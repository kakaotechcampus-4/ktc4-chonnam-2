# 재개("이어서 찾기") 시 Job identity 정책 — 새 job_id

> 결정일 2026-09-13 · 담당 유소연(`case`) · 근거 `docs/architecture/erd-draft.md`(`codex/erd`, 미머지) 리뷰 항목 ③, `contract-job-execution.md` §10/v1.1 노트가 위임한 판단

## 배경

`JobExecution.status=CANCELLED`(`job-execution/v1.1`, 이슈 #33 A-2)가 추가되면서, "중단 후 재개(`이어서 찾기`) 시 같은 `job_id`를 재사용할지 새 `Job`으로 볼지"를 `JobRecord` 소유자인 case의 판단으로 남겨뒀다(`contract-job-execution.md` v1.1 노트). `codex/erd` ERD 리뷰 과정에서 이 항목을 처음엔 "같은 `job_id`+새 `attempt`"로 답했으나, 기존 컨벤션과의 일관성을 재검토해 아래로 정정한다.

## 결정된 것

**"이어서 찾기"도 새 `job_id`(새 `JobRecord`)로 발주한다.** 같은 `job_id`+`attempt` 증가는 사용자 Intent 없이 벌어지는 자동 인프라 재시도(`STALE`)에만 쓴다.

근거:

1. `JobRecord`는 "작업 1건당 하나의 Intent 기록"이다(`contract-job-record-case-view.md` A절 §4). 사용자가 "이어서 찾기" 버튼을 누르는 행위 자체가 새 Intent이므로, 정의상 새 `JobRecord`/`job_id`가 맞다.
2. 기존 `actions[]` → 발주 매핑 컨벤션(`RETRY_PLATE_READ`, `RETRY_SEARCH`, `PLATE_REREAD` 발주 규칙)이 전부 "사용자가 재요청하면 새 `job_id`"로 일관돼 있다. "이어서 찾기"만 예외로 두면 이 원칙이 깨진다.
3. "이미 찾은 후보를 버리지 않는다"(`docs/product/core-user-flow.md` §4)는 이 결정과 무관하게 이미 만족된다 — `CandidateEvent`는 case에 종속된 독립 레코드지 특정 `job_id`/`JobExecution.produced`에 갇혀 있지 않다. 어느 `job_id`가 만들었든 `CaseView.candidates[]`는 case 단위로 계속 유지된다. `RETRY_SEARCH`(조건 변경 후 재검색)도 이미 새 `job_id`를 쓰면서 "후보를 버리지 않는다"를 만족시키고 있어 이 요구가 job_id 재사용을 강제하지 않는다는 걸 보여준다.

## 아직 미결로 남는 것

- 실제 데모 fixture는 여전히 없다(mock pack `Should-1`류 비차단 항목, 다음 라운드 반영 예정).
- `RESUME_SEARCH` 발주 시 이전 실행이 이미 찾아둔 시간 범위를 다시 스캔하지 않고 이어가는 것(재스캔 회피)은 `search`(서어진) 구현 세부이며 이 문서가 정하지 않는다 — case는 identity(`job_id` 분리) 여부만 정한다.

## 소유 경계

| 무엇 | 소유 |
| --- | --- |
| `JobRecord`/`job_id` identity 의미(새 job인가 재시도인가) | `case` (이 문서, `contract-job-record-case-view.md`) |
| 실행 상태(`QUEUED`/`RUNNING`/.../`CANCELLED`) 표현 | `contract-job-execution.md` (common/runtime) |
| 재개 시 실제 스캔 범위 최적화 | `search` |

## 관련

- `contract-job-execution.md` 2026-09-13 명확화 노트
- `contract-job-record-case-view.md` `RESUME_SEARCH` 행(actions[] 매핑표)
- `docs/product/core-user-flow.md` §4 "중단"/"이어서 찾기"
