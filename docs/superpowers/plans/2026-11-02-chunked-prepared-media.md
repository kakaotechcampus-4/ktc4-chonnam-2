# 준비 미디어 청크 저장 구현 계획과 설계

> **실행 에이전트 지침:** superpowers:executing-plans를 사용하고 이 대화에서 구현한다. 새 읽기 전용 검토자가 최종 diff를 리뷰한다.

**목표:** 공개 미디어 식별자·소유권·상한·재시도 정책을 바꾸지 않고 준비 미디어 SQL 명령/결과의 작업 메모리를 줄인다.

**구조:** `recording_media_chunk` 테이블을 추가하고 기존 prepared-content 행에 버전이 있는 descriptor를 둔다. canonical media 행으로 발행자를 직렬화하고 중첩 SAVEPOINT 안에서 청크·manifest·Case 연결을 발행한다. 크기가 제한된 조각을 한 번에 하나씩 소유 임시 파일로 읽고 길이·SHA-256·컨테이너 시그니처를 검증한 뒤 분리된 stream을 반환한다.

**기술 구성:** 기존 SQLAlchemy Core, PyMySQL, Alembic, tempfile, pytest/MySQL 8.4.

**명세:** 이 대화에 첨부된 사용자 요청, #530 head `fdcccfa9` P2-0b/0c와 Decision Gate, #537, 현재 소스 `f1e8d82f`.

## 제약과 결정

- 시작: `codex/issue452-chunked-media-storage`, HEAD `f1e8d82f44e2bcf630a3f2fde009035f1436d7ec`, 작업 트리/staging 변경 없음. 일반 checkout이며 사용자가 지정한 checkout/브랜치를 그대로 사용한다. #538이 이 HEAD에 병합됐음을 GitHub에서 독립 확인했다.
- 사용자는 Runtime/Recording 내부 선택을 위임하고 즉시 구현을 요청했다. 추가 설계 승인 없이 진행한다. 커밋·staging·푸시·PR·외부 댓글·CI 실행·병합은 하지 않는다.
- 대안 비교: packet 증가는 전체 payload 할당을 유지한다. 파일시스템/객체 저장소는 영속성·백업 계약을 바꾼다. DB 청크는 요청된 기존 트랜잭션·백업 경계를 충족한다.
- 초기 최대 청크는 256 KiB다. 최악의 escaping은 입력 byte당 2 bytes이며(#537의 PyMySQL hex 경로와 설치된 driver 검사로 확인), 명령/메타데이터 여유 16 KiB와 추가 packet 예비 공간을 둔다. 청크 INSERT를 일괄 묶지 않는다. session packet과 비공개 주입 가능 명령 예산에서 실제 청크 크기를 결정하고 메타데이터 명령도 같은 예산으로 검사한다.
- 기존 `get_prepared_content` bytes 호출자(export materializer/스냅샷)는 문서화한 호환 할당으로 인터페이스를 유지한다. 분석 stream과 메타데이터 경로는 제한된 읽기를 사용하고 전체 bytes를 조립하지 않는다. 기존 BLOB은 SQL substring 조회와 서버 측 길이/hash로 불변 비교한다.
- 익명 TemporaryFile은 설정된 Recording 임시 root를 사용한다(Unix 0600). 실패·취소 시 닫고 성공 시 반환 stream이 소유한다. 분리된 BytesIO처럼 service 종료 후에도 유지된다. 영속 파일 발행·보관 정책은 추가하지 않는다.
- 외부 commit/rollback은 호출자가 소유한다. SAVEPOINT 정리 실패 시 최초 예외를 보존하고 안전하지 않은 연결을 무효화해 호출자가 예외를 잡고 commit하더라도 부분 데이터가 발행되지 않게 한다. 새 재시도는 추가하지 않는다.
- 전진 전용 추가 리비전이며 일괄 변환은 하지 않는다. 신규 쓰기는 기존 content가 NULL이고 구 코드로 읽을 수 없다. 기존 형식 읽기 지원이 애플리케이션 rollback을 승인하는 것은 아니다.
- 현재 백업은 BLOB을 hex 인코딩하고 확장 INSERT를 묶으며 전체 dump를 메모리에 수집한다. skip-extended-insert로 dump 문장 크기를 제한하고 전체 dump 메모리 한계는 보존·문서화한다.
- 자원 사전 점검: 최초 가용 RAM 851,412 KiB / disk 3.27 GiB. 자원이 개선되기 전까지 38,359,627-byte 대형 대조 시험은 유예한다. 보존된 `issue452-capacity-db`는 사용하지 않는다.

## 검토 중점

- SAVEPOINT rollback/release 실패·연결 단절·deadlock에서 원래 DB 오류 분류를 보존한다.
- 같은/충돌하는 동시 발행과 Case 연결 실패가 불변 데이터 및 무관한 호출자 작업을 보존한다.
- 과대·손상·누락·추가·순서 오류 청크가 무결성 검증을 통과하거나 파일/cursor를 누수하지 않는다.
- 기존 형식 읽기와 추가 migration에서 과거 migration 실패/downgrade 시험을 유지한다.
- 분리 stream 정리, 호출자 소유 연결 수명, 논리 백업과 빈 target 복원을 확인한다.

## 작업

- [x] 1. 메타데이터 전용 투영·제한된 stream/manifest 검증 시험의 실패를 확인하고 메타데이터 투영과 비공개 stream helper를 구현한다.
- [x] 2. 실제 MySQL 명령 예산·SAVEPOINT 실패·충돌/동시성·분리·기존 형식/migration 시험의 실패를 확인한다. 청크 스키마/발행/읽기 경로를 구현하고 과거 의미를 바꾸지 않고 현재 head 기대값·목록을 갱신한다.
- [x] 3. 백업 문장 상한의 실패를 확인한다. 최소 dump 옵션을 구현하고 백업 → 빈 전용 target → 다시 열기/hash 검증을 직접 실행한다.
- [x] 4. 영속성/service/Search/migration/백업 집중 회귀와 Runtime 품질·경계·계약·Ruff·diff 검사를 실행한다. 로컬 전체 pytest나 필수 MySQL 전체 검사는 하지 않는다.
- [x] 5. 새 독립 읽기 전용 리뷰를 수행한다. 지적을 실패→통과로 수정하고 같은 검토자가 재확인한다. 구현 기록·Runtime 로그에 증거·상한·NOT_RUN/UNKNOWN/NOT_REACHED를 추가한다.

최종 증거와 보존한 실패는 [Runtime 로그](../../runtime/runtime-implementation-log.md)와
[구현 기록](../../modules/recording/chunked-prepared-media.md)에 있다.
