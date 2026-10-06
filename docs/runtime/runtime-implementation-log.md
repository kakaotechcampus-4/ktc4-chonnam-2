# Runtime Implementation Log

**Status:** workflow §8 Implementation Log — 구현이 진행되며 누적하는 living record**Owner:** Runtime/Ops 김준영(@flosure23) · Primary Implementer 정철원(@cheol1203)**Plan:** [Runtime Implementation Plan](./runtime-implementation-plan.md) — 구현 **전** 계획. 이 Log는 **실제로** 구현된 것이다(Plan §12.5)**Started:** 2026-10-06 · 기준 `origin/develop` `960a046`

> 이 문서는 무엇이 만들어졌고 Plan에서 무엇이 달라졌는지를 한곳에 남겨, Runtime/Ops Owner가 PR마다 따라가지 않고 나중에 이 문서와 PR Implementation Notes만으로 확인(Plan §12.6 Audit)할 수 있게 한다. **규칙을 만들지 않는다.** Contract · Accepted Decision · Baseline이 바뀌면 그 결정은 각 SoT에 있고 여기에는 「바뀌었다 + 어디」만 적는다. 실행 모델(merge authority · 멈춰야 하는 경우 · PR Notes 형식)의 원문은 Plan §12다.

## 사용 규칙

- **언제** — RT Task의 구현 PR이 merge될 때, 가능하면 **같은 PR에서** 해당 Task 절을 갱신한다. merge 전이라 SHA가 없으면 `pending`으로 두고 다음 PR이나 정리 PR에서 채운다. Log 갱신을 이유로 구현 PR merge를 막지 않는다.
- **최소 기록** — Task · Issue · PR · Merge SHA · 구현 요약 · Plan 대비 변경 · Owner 확인 포인트 · Tests · 남은 위험.
- **출처** — PR 본문의 Implementation Notes(Plan §12.4)를 Task 단위로 요약해 옮긴다. 상세는 PR이 원문이다.
- **Plan을 고치지 않는다** — Plan과 다르게 구현했으면 Plan을 다시 쓰지 않고 아래처럼 「Plan 대비 변경」에 적는다.

  ```text
  (예시)
  Plan:          heartbeat.py + cancel.py 분리 예상
  Actual:        execution_lifecycle.py로 통합
  Reason:        공유 state · fencing 경계가 하나라 분리하면 순환 dependency 발생
  Contract 영향: 없음
  ```

- **implementation detail** — 나중에 중요해질 수 있는 구현 선택(값 · 구조)은 Task 절과 함께 아래 「Implementation detail 색인」에 한 줄 남긴다. 별도 RD Issue를 만들지 않는다(Plan §12.3).
- **Baseline 조정 후보** — 실측으로 Baseline 값을 바꿀 근거가 생기면 구현 PR에서 바꾸지 않고 「Baseline revisit 후보」에 적는다. 결정은 workflow §10 → §11 경로다.
- **Status 값** — `NOT_STARTED` · `IN_PROGRESS` · `DONE`(Task의 PR 전부 merge · acceptance 통과) · `AUDITED`(Plan §12.6 Audit 확인 뒤).
- 비어 있는 항목은 `—`로 둔다.

## Implementation detail 색인

Plan §0.1이 Task PR로 넘긴 선택은 미리 행을 둔다. 그 밖의 선택은 구현하며 추가한다.

| 항목 | 선택 | Task · PR | 근거 위치 |
| --- | --- | --- | --- |
| Baseline 밖 config key 이름 — DB 접속 · 공유 mount root · service별 temp root (Plan P-8) | pending | RT-01 | — |
| `DECIMAL` precision/scale (Plan P-10) | pending | RT-07 | — |
| type checker 도구 (Plan RT-15) | pending | RT-15 | — |
| secret scan 배치 — PR gate 편입 여부 (Plan RT-15) | pending | RT-15 | — |
| Compose smoke의 CI 편입 여부 (Plan RT-13) | pending | RT-13 | — |

## Baseline revisit 후보

| Baseline ID | 관측 | Evidence | 처리 (workflow §10 → §11) |
| --- | --- | --- | --- |
| 없음 | — | — | — |

## Owner 확인 기록

Plan §12.3에서 「멈추고 확인」에 해당해 Owner에게 확인한 건만 남긴다.

| 날짜 | Task · PR | 확인 내용 | 확인처 | 결과 · 기록 위치 |
| --- | --- | --- | --- | --- |
| 없음 | — | — | — | — |

## Milestone audit

묶음 정의는 Plan §12.6이다. workflow gate가 아니다.

| Audit | Task | 상태 | 확인일 | 결과 · 후속 |
| --- | --- | --- | --- | --- |
| A — Runtime Core | RT-01 ~ RT-06 | 대기 | — | — |
| B — Integration | RT-07 ~ RT-11 (+ REC-1 소비 surface) | 대기 | — | — |
| C — Operations | RT-12 ~ RT-15 | 대기 | — | — |

---

## RT-01 — Runtime config · composition bootstrap · structured log 기반

Status: NOT_STARTED · Issue: #288 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-02 — DB access 기반 · Alembic 배치 · MySQL integration harness · CI

Status: NOT_STARTED · Issue: #289 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-03 — `job_execution` schema · queue repository

Status: NOT_STARTED · Issue: #290 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-04 — Worker core: claim loop · kind registry · dispatch · T1/T2 (E2E-0)

Status: NOT_STARTED · Issue: #291 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-05 — Lease · heartbeat · fencing · 협력적 중단

Status: NOT_STARTED · Issue: #292 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-06 — STALE sweep · 자동 retry · T2 재전달

Status: NOT_STARTED · Issue: #293 · Audit: A

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-07 — Usage ledger: in-flight · Final UsageRecord · reconciliation

Status: NOT_STARTED · Issue: #294 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-08 — API composition root: `/cases` · `/commands` · `/view` · `/health/*`

Status: NOT_STARTED · Issue: #295 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-09 — 첫 비동기 E2E (integration acceptance)

Status: NOT_STARTED · Issue: #296 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-10 — Worker composition root: 실제 kind handler 등록 · cross-process E2E

Status: NOT_STARTED · Issue: #297 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-11 — Media HTTP: `POST /sources` · frames · assets

Status: NOT_STARTED · Issue: #298 · Audit: B

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-12 — 운영 위생: cleanup · 관측 집계

Status: NOT_STARTED · Issue: #299 · Audit: C

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-13 — Docker / Compose local runtime

Status: NOT_STARTED · Issue: #300 · Audit: C

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-14 — EC2 배포 · 운영 (Issue는 RT-13 착수 때 생성)

Status: NOT_STARTED · Issue: — (RT-13 착수 때 생성) · Audit: C

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## RT-15 — CI 품질 gate · Runtime import 경계

Status: NOT_STARTED · Issue: #301 · Audit: C

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## REC-1 — recording 영속화 · HTTP/Worker용 capability (recording Owner)

Status: NOT_STARTED · Issue: #302 · Audit: B (Runtime이 소비하는 surface만)

recording Owner(정철원) 작업이다. 여기에는 Runtime이 소비하는 surface(RT-10 · RT-11 · RT-12 입력)만 기록하고, recording 내부 결정은 `docs/modules/recording/`이 원문이다.

| PR | 내용 | Merge SHA |
| --- | --- | --- |
| — | — | — |

### 구현 결과

—

### Plan 대비 변경

—

### 새 implementation detail

—

### Owner 확인 포인트

—

### Verification

—

### 남은 위험

—

---

## Change log

| 날짜 | 변경 | 기준 |
| --- | --- | --- |
| 2026-10-06 | 생성 — Plan §12 Single Implementer + Deferred Owner Review 실행 모델의 기록 문서. RT-01 ~ RT-15 · REC-1 절 · implementation detail 색인 · Baseline revisit · Owner 확인 · Milestone audit 표 | PR #305 |
