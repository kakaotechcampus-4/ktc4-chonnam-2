<a id="rt-13b-local-logical-backup--restore"></a>

# RT-13(b) 로컬 논리 백업 / 복원

**상태: IN_PROGRESS · Refs #300 (RT-13(b))**

사용자 제공 명세: 이 세션의 RT-13(b) 요청. 정규 범위:
Runtime Plan RT-13/§12 및 #300 Owner 승인 댓글 6433879506.
현재 세션에서 TDD로 구현하고, 이력이 없는 읽기 전용 검토자 한 명의 검토 및 같은
검토자의 후속 검토를 받는다. staging/commit/push/PR/Issue 변경은 없다.

<a id="design-and-constraints"></a>

## 설계와 제약

기존 Compose service, helper guard, 합성 HTTP 업로드를 재사용한다.
MySQL 8.4 client의 기존 읽기 전용 password 파일을 사용하는, 표준 라이브러리만의
호스트 측 논리 도구를 추가한다. `daesingo`만 지원한다(Compose DB).
애플리케이션 writer 중지, 컨테이너 로컬 단일 작업 lock, 배타적 산출물 생성을 요구한다.
복원은 빈 데이터베이스와 정확한 로컬 migration head를 요구한다. SQL 주위에
길이/SHA256을 두는 버전 지정 단일 파일 envelope를 사용한다. 가져온 후 다시 dump해
모든 스키마/데이터 바이트를 비교한 뒤 성공으로 처리한다.
envelope는 손상을 탐지하며 악의적 교체/진위를 검증하지는 않는다.
DB 전용 백업은 미디어 바이트를 보존하지 않는다. 인수 테스트는 동일한 미디어
volume을 유지하며 깨끗한 DB 복원 후 영속 메타데이터/ref/바이트를 검증한다.

대안: 원시 SQL에는 무결성/식별자 검사가 없다. 물리 volume 복사는 승인된 논리
경계 밖이다. 운영 정책을 도입하지 않는다.
기존 migration, readiness, UID, secret, rotation, recovery 의미는 유지한다.

<a id="tasks--ledger"></a>

## 작업 / 기록

- [ ] 1. envelope, DB 선택, 충돌, 명령 실패, 부분 복원, migration, 중복/취소,
  비공개에 대한 집중 테스트를 작성하고 RED를 보존한다.
  `scripts/backup_compose.py`를 구현하고 GREEN 및 deploy 회귀를 검증한다.
- [ ] 2. 실패하는 인수 guard/probe 테스트를 작성한다.
  `scripts/smoke_backup_restore.py`, `tests/deploy/backup_probe.py`를 추가하고
  RT-13(a)의 격리 project/정리 guard를 재사용해 실제 Docker 복원을 실행한다.
  case/업로드 + terminal job execution을 seed하고 영속 식별자,
  migration head, 테이블, media ref/hash, API ready, Worker dispatch를 비교한다.
- [ ] 3. 관련 실제 MySQL 테스트, 경계/Contract/workflow/diff 검사를 실행한다.
  원래 실패를 유지하고 unit 테스트, 직접 Docker 실행, 과거 증거, 보존 보고서
  검사를 구분한다. 사용자 지정 확장 조건이 적용되지 않으면 전체 pytest/MySQL/
  strict gate는 실행하지 않는다.
- [ ] 4. 구현 Notes/log와 README 포인터를 추가한다. 새 읽기 전용 검토로
  diff/SoT/테스트/정리/privacy를 확인하고 TDD로 P1/P2를 수정한 뒤 후속 확인을
  받는다. worktree는 unstaged로 두고 남은 모든 격차를 보고한다.

검토 초점: Docker exec가 계속되는 중 취소, 부분 DDL 실패, 잘못되거나 위조된 dump
식별자, 무관한 Docker 자원과 기존 산출물 충돌, subprocess 오류/증거/diff의 민감값.

Preflight (직접): branch `codex/rt13b-backup-restore`, HEAD/develop
`071bbcca53fc7381592abcb0df7bcb3060324aa2`, 깨끗한 index/worktree; #417 merge
`61adb7c377719237e0b5659dd5c69bb4447220bc`는 조상이다. GitHub #300 본문과
Owner 승인을 가져왔다. 권한을 높인 읽기 전용 검사로 Engine 29.9.2 사용 가능,
Linux WSL root 사용 가능을 확인했다. sandbox 전용 접근 실패는 Engine 사용 불가를
뜻하지 않는다. 사용자가 선택한 저장소/branch를 현재 위치에서 사용한다.

<a id="completion-ledger-append-only"></a>

## 완료 기록 (추가 전용)

작업 1: RED24 → GREEN24; 검토 회귀2 이후 최종 focused/deploy109PASS.
작업 2: helper RED4; 실제 acceptance1 19PASS/cleanupPASS. P2 source-object
누락 실제 Engine RED2 (exit0) → GREEN2 (exit25); 최종 코드 acceptance2는
별도로 19PASS/cleanupPASS이며 실행 간 합산하지 않는다.
작업 3: 경계/Contract/Compose/workflow/diff PASS. 관련 MySQL 원본은
85PASS/1FAIL (Windows helper env 누락), 기존 binary 경로로 실패 테스트만 재실행해
1PASS; 원본 결과를 다시 이름 붙이지 않았다. 전체 pytest/MySQL/strict는 미실행.
작업 4: Notes/Log/README 갱신. 새 검토자 최초 P1=0/P2=1; 같은 검토자의
소스 후속 검토에서 기존 P2 수정/새 P1P2=0, 직접 deploy109PASS.
최종 acceptance2/audit 증거 검사는 pending이다. 작업 소유 Docker/temp 자원은
제거했으며 공유 cache/network는 유지했다. stage/commit/push/PR/Issue 변경은 없다.

작업 4 최종: 같은 검토자가 acceptance2/audit/문서를 검사하고 기존 P2 수정 및
남은/새 P1/P2 없음을 확인했다. 검토자의 직접 deploy109PASS는 보존된 실제 Engine
증거 검사와 별개다. 승인된 로컬 범위 안에서 작업 네 개를 모두 완료했으며
IN_PROGRESS #300과 미커밋/unstaged 상태를 유지한다. 전체 원격 gate와 실제 취소
결함 주입은 여전히 미검증이며 명시적으로 공개한다.
