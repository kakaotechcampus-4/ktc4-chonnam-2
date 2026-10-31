# RT-14 운영 후속·복구 acceptance 준비 계획

> **실행 방식:** `superpowers:executing-plans`로 현재 브랜치에서 직접 준비한다. 사용자가 현재 브랜치·미커밋 종료·fresh 읽기 전용 reviewer 1명과 같은 reviewer의 delta 확인을 명시했다.

**목표:** 기존 운영 이력을 보존하면서 운영자 제공 후속 증거와, 실행 조건이 채워지면 사용할 DB/media 백업·격리 복원 절차를 추가한다.

**설계 근거:** [승인된 RT-14 설계](../../runtime/rt14-deployment-design.md), [RT-13(b)](../../runtime/rt13b-backup-restore.md), Issue #450의 본문·댓글 5개 및 이번 사용자 요청. 승인된 설계를 재개방하지 않는다.

**구조:** 기존 도구를 변경하지 않는 문서 작업이다. 용량·heads·소유권이 불명확하면 실행을 차단하며, 부족한 도구 기능은 완료한 것처럼 쓰지 않는다.

## 제약과 검토 초점

- `codex/rt14-recovery-acceptance`, 시작 `42fb2e691b8685b44e38767674d7f64b73c345b2`, worktree 생성·전환 없음.
- AWS/SSM/dispatch/배포/서비스 정지/실제 backup·restore 없음. commit/push/PR/외부 댓글 없음.
- 한국어 문서, 식별자·기존 CLI/API 유지. 제품·migration·Contract·workflow·timeout·gate 변경 없음.
- 운영자 제공 증거와 직접 로컬 검증을 분리한다. 403을 외부 Web 200/public smoke 성공으로 승격하지 않는다.
- 4GiB 용량·dump 메모리 복사, media 별도 복원, 외부 writer/DDL, 두 종류 lock, migration 전 비교, offline Worker와 소유 자원 정리를 검토한다.

## 작업

- [x] Issue #450 최신 본문·댓글, 지정 문서·도구·controller와 관련 테스트 확인.
- [x] 실행 runbook 작성: 읽기 전용 조사 → 자원/호환성 gate → 같은 중단 시점 backup → 운영 복귀 → 빈 격리 target restore → migration 전/후 확인 → 정리.
- [x] 기존 실험 기록·Runtime Log에 운영자 제공 조치 append, 기존 Notes에서 새 절차 연결.
- [x] 문서 링크·명령/내장 Python 구문·비노출·diff 검사. 문서만 변경하므로 새 테스트/전체 pytest/MySQL은 실행하지 않는다.
- [x] 구현 이력을 상속하지 않는 fresh reviewer 1명에게 전체 변경 읽기 전용 검토 요청, 지적 수정 후 같은 reviewer의 delta 재확인.
- [x] 최종 파일·검증·실제 실행 입력/중단/복귀·잔여 acceptance 보고, index 빈 상태 유지.

## 판단 기록

문서만으로 기존 도구의 대용량 처리를 개선했다고 주장하지 않는다. DB 크기 추정은 SQL dump 상한이 아니므로, 실측 메모리 근거가 없으면 기존 in-memory 경로 실행을 허용하지 않는다. 스트리밍·별도 승인 자원은 필요한 최소 후속 대안이며 이번에 구현/할당하지 않는다.

## 검증 기록

쉘16/Python5 구문·추가 로컬 링크13·기존 이력 prefix·메모리 안에서만 실행한 target 생성 검사 PASS.
Compose CLI help 확인으로 create flag를 정정했다. fresh reviewer 초기 3건과 같은 reviewer의
추가 timeout 경계 지적을 수정하고 최종 delta에서 기존 지적 해결·새 actionable P1/P2 없음을 확인했다.
실제 Docker/AWS/backup/restore는 미실행이며 전체 pytest/MySQL도 반복하지 않았다.
Git Bash IPC 오류와 Windows 검사 대역의 os.chown 오류는 수정/재실행 근거와 구분한다.
