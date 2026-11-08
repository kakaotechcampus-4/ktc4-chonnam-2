# RT-06(b) T2 재전달과 강제 종료 복구

**목표:** 기존 T2와 Case 8-8 포트로 미반영 SUCCEEDED/FAILED 실행을 복구한다. 관련 이슈 #293. 최종 독립 리뷰 전까지 RT-06은 IN_PROGRESS를 유지한다.

**구조:** 잠금 없이 후보를 조회하고 연결을 반환한 뒤 후보마다 B-D8 트랜잭션 하나를 사용한다. Runtime 잠금 없이 반영 확인 기록을 다시 읽고, Runtime 반영 기록·enqueue 쓰기 전에 Case가 먼저 잠금을 획득하도록 한다. Case 실행 식별자와 원자적인 Runtime 반영 기록으로 동시성과 COMMIT 결과 불명을 처리한다. Worker 조립부가 Case adapter와 주입된 reader/timeline/store factory를 관리한다.

**명세:** runtime-implementation-plan §6 RT-06 / §12, runtime-tech-spec §6.2/6.3/7.2/7.3/12.2, provisional-baseline-v0.1 B-L3–5/B-R1–3/§2.4/3.2/9, Case 결과 반영 결정, 이슈 #293과 병합된 PR #342/#343. 제공된 AGENTS.md를 적용하며 저장소의 AGENTS.md는 발견되지 않았다.

## 선택 사항

| 항목 | 선택 | 대안 또는 선택한 보장이 없을 때의 실패 |
| --- | --- | --- |
| 조회 | 잠금 없는 후보 조회 + 후보별 짧은 트랜잭션 | 전체 순회를 한 트랜잭션으로 묶으면 실패·잠금이 결합됨. Runtime 선행 잠금은 Case 우선 순서를 위반함 |
| 동시성 | 기존 Case 잠금 + 실행 중복 제거 + Runtime 반영 기록 재확인 | 프로세스 mutex는 다른 프로세스를 보호하지 못함. 전달 lease는 별도 복구 정책을 추가함 |
| COMMIT 결과 불명 | 영속 반영 기록을 사용하는 기존 B-D8 재실행 | rollback으로 가정하면 이미 commit된 효과를 놓침. 무조건 enqueue하면 Job이 중복됨 |
| adapter | ProducedReader·timeline·선택적 store factory를 주입하는 Worker adapter | common→Case import는 경계 위반. Case에 Runtime 타입을 넣으면 다른 Owner의 공개 영역이 바뀜 |
| 강제 종료 동기화 | IPC barrier, 독립적인 영속 DB 조회, kill/join | sleep만으로 종료 지점을 입증할 수 없음. 종료 모사는 lease 복구를 입증하지 못함 |
| 미지원 kind | Case ValueError 보존, 반영 기록 없음, 후보별 격리 | 조용히 APPLIED로 처리하면 결과가 소실됨. kind 필터링은 배선 결함을 숨김 |

## 실행 내역(직접 실행, 커밋·푸시·PR 없음)

- [x] 실패 확인: 후보 자격·오류·반영 기록/동시성·시작 순서·Case 원자성·강제 종료 시험과 gate 계열 누락. 매개변수 누락의 통과 확인은 gate 회귀에 포함한다.
- [x] common/jobs/redelivery.py, worker/case_reflector.py, SweepService/조립 배선을 구현한다.
- [x] commit 응답 proxy와 동시 Case 잠금을 포함한 대상 단위·통합 시험 통과. 읽기 전용 리뷰의 P2 fixture를 영속 kind 실패→통과로 수정하고, 실제 DB 연결 강제 종료 격리를 검증했다.
- [x] 실제 MySQL 필수 목록: 전체 487 / 중첩 482, skip 0, xfail 0, JSON/JUnit gate. 신규 224개를 포함한 증거 계층 누락 2,317개와 신규 계열 누락 9개를 거부했다.
- [x] 전체 pytest: 5,363 passed / MySQL 외 skip 26개. 경계 검사·계약 fixture·전체 workflow 정적 검사·git diff --check PASS.
- [x] 구현 로그/README·읽기 전용 소스 리뷰·남은 위험을 기록하고 전용 서버/스키마/계정/프로세스 정리를 검증했다. 최종 독립 재리뷰와 Owner 감사는 대기 중이며 RT-06은 IN_PROGRESS다. RT-07 정산과 Case capability 확장은 범위 밖이다.

## 검토 중점

- CANCELLED/STALE과 기존 반영 기록은 재전달 대상에 들어가지 않는다.
- 후보·재실행 조회는 Case보다 먼저 Runtime을 잠그지 않는다. Case 처리 후 반영 기록으로 중복 enqueue를 막는다.
- reflector·DB·logger 오류는 부분 T2를 남기지 않고 다른 후보·주기를 중단하지 않는다.
- 실제 프로세스 종료를 관측하고 해당 스키마 삭제 전에 정리한다. 재시도는 DB lease/backoff 시각을 사용한다.
- KindRegistry는 FAILED/RUNTIME_UNREGISTERED_KIND를 생성하고 T2로 전달할 수 있다. RT-10이 handler/반영 호환성을 사전에 검사해야 하며 여기서 임의의 Case applier를 만들지 않는다.
