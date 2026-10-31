<a id="rec-1a-implementation-boundary"></a>

# REC-1(a) 구현 경계

Refs #302. 이 문서는 구현 메모이며 Contract나 Owner Decision이 아니다.

<a id="acceptance-and-storage"></a>

## 인수 조건과 저장

호출자가 활성 SQLAlchemy Connection을 제공하고 해당 트랜잭션을 소유한다.
저장소/서비스는 커밋, 롤백, 재시도를 수행하지 않으며 연결을 소유하지 않는다.
같은 데이터베이스와 저장 루트를 사용하는 새 서비스/저장소 인스턴스는 재등록 없이
SourceAsset, MediaStream, FrameRef, DerivedAsset 메타데이터와 기존 case/ref
연결 관계를 복원한다. 타임라인, span 해석, 저장된 fixture 메타데이터는 기존
저장소 의미를 유지한다.

원본 미디어는 제공된 파일시스템 루트에 그대로 둔다. 검증된 상대 locator,
등록 fingerprint, 스트림 인덱스만 MySQL에 저장한다. 절대 경로, 경로 이탈,
심볼릭 링크를 통한 이탈, 다른 루트의 locator는 경로를 출력하지 않고 안전하게
거부해야 한다. 어댑터는 파일을 복사, 게시, 이름 변경, 삭제하지 않는다.
FrameRef 메타데이터와 이미지 바이트는 MySQL에 함께 저장한다(트랜잭션이 적용되는
InnoDB 행). 프레임 파일 게시는 없다. 롤백하면 메타데이터와 바이트가 모두 제거된다.
DerivedAsset ref, 메타데이터, 명시적 case 연결은 영속적이며 최종 바이트/Content-Type
읽기 인터페이스는 REC-1(c) 범위로 남는다.

비공개 `recording_entry` 테이블은 종류별로 payload를 구분한다. 불투명 식별자의
SHA-256 다이제스트가 고유 조회 키이고, 자동 증가 ordinal은 기존 목록/등록 순서를
유지한다. 기존 Contract JSON은 `payload`에 저장하며, FrameRef 행만 nullable
`LONGBLOB content`에 이미지 데이터를 갖는다. 원본 파일, AnalysisSource 바이트,
로컬에서 구체화된 IncidentClip 바이트는 이 열로 복사하지 않는다. 상대 source locator는
원래 등록 당시의 크기/mtime/hash와 스트림 인덱스를 유지한다. 해석된 루트의
다이제스트는 절대 경로를 저장하지 않고 locator를 동일한 설정 루트에 결속한다.
등록 시와 매번 locator를 복원할 때 심볼릭 링크/junction 포함 여부 검사까지 검증한다.

Case/ref 연결은 기존 내부 associate_case_asset/get_case_assets 경계를 사용한다.
case A 목록의 ref는 case B 목록에 나타나면 안 된다. 이것은 최종 공개 소유권 API가
아니며 ref 문자열로 소유권을 추론해도 된다는 뜻도 아니다. 등록 입력과 실제 Case
연결/조합은 REC-1(b)/RT-11 범위로 남는다.

<a id="alternatives-and-transaction-boundary"></a>

## 대안과 트랜잭션 경계

| 접근법 | 평가 |
| --- | --- |
| 호출자 Connection을 사용하는 SQL 어댑터, JSON contract payload, 트랜잭션 적용 프레임 바이트 | 선택: 기존 모델 유지, 파일시스템/DB 이중 게시 없음 |
| 메모리 내 스냅샷을 복원하고 나중에 flush | 기각: 오래된 스냅샷, 숨겨진 flush 경계, 롤백 캐시 위험 |
| 파일시스템 프레임 게시와 메타데이터 행 | 연기: 이 작업 범위 밖의 게시/고아 데이터 조정 필요 |

이 모듈에는 Recording 테이블과 recording_alembic_version만 속한다.
공통 마이그레이션 실행기에는 명시적 Recording registry 항목이 필요하며, 다른
모듈의 스키마와 동결된 revision은 변경하지 않는다. MySQL DDL은 전진만 허용하고
암시적으로 커밋되므로 트랜잭션 방식의 downgrade를 보장할 수 없다. 테스트는 DML
롤백과 실패한 revision 이후 부분 적용된 DDL을 구분해야 한다.

AnalysisSource 바이트/스트림 factory와 inspection 캐시는 프로세스 로컬로 유지한다.
기존 로컬 IncidentClip 구체화 수명을 여기서 내구성 보장으로 격상하지 않는다.
완전한 미디어 게시와 DerivedAsset 바이트는 후속 인수 조건이다. HTTP route, 공개
소유권 인터페이스, purge 정책, 고아 데이터 조회, Worker 조합, 분류 체계 변경,
새 Case/Runtime 의무를 도입하지 않는다. exactly-once 보장이나 COMMIT ACK 손실이
미커밋 데이터를 의미한다는 주장도 하지 않는다.

<a id="verification-sequence"></a>

## 검증 순서

1. 복원, 롤백, 소유권, 저장, 마이그레이션, 오류에 대한 실제 MySQL RED.
2. 최소 어댑터/인터페이스/마이그레이션 구현과 GREEN.
3. Recording 및 API/Worker 회귀, 전체 필수 MySQL JSON/JUnit 목록.
4. 매개변수/메타데이터/family 누락 변이, 경계/Contract/workflow 검사.
5. 새 읽기 전용 검토와 명시적 자원 정리 감사.

<a id="changed-file-inventory"></a>

## 변경 파일 목록

아래 경로는 모두 저장소 기준 상대 경로다. staging, commit, push, PR 생성은
이 작업에 포함되지 않는다.

| 목적 | 파일 |
| --- | --- |
| 어댑터와 기존 저장소 타입 경계 | `src/daesingo/recording/mysql_repository.py`, `src/daesingo/recording/repository.py`, `src/daesingo/recording/service.py`, `src/daesingo/recording/spans.py` |
| Recording 마이그레이션과 실행기 registry | `migrations/recording/alembic.ini`, `migrations/recording/env.py`, `migrations/recording/script.py.mako`, `migrations/recording/versions/0001_recording.py`, `src/daesingo/common/db/migrate.py` |
| 실제 MySQL 인수 테스트와 독립 목록 | `tests/recording/test_recording_repository_mysql.py`, `tests/recording/test_recording_repository_compatibility_mysql.py`, `tests/recording_acceptance.py` |
| 엄격한 증거와 기존 마이그레이션 회귀 | `scripts/check_mysql_test_report.py`, `tests/common/db/test_mysql_gate.py`, `tests/common/db/integration/test_migration_gate.py`, `tests/common/db/integration/test_migrations.py` |
| 구현 메모와 추가 전용 이력 | `README.md`, `src/daesingo/recording/README.md`, `docs/modules/recording/rec1a-persistence.md`, `docs/runtime/runtime-implementation-log.md` |

실행 보고서와 진단 helper는 전달 목록 밖에 있는, 무시되는 작업 소유 디렉터리
`.codex-scratch/rec1a-20261019/`에 둔다.

<a id="verification-and-readiness-2026-10-19"></a>

## 검증과 준비 상태 (2026-10-19)

구현은 작업에서 소유한 MySQL 8.4.7 서버를 대상으로 테스트했다. 아래는 범위가
겹치는 별도 실행이며, 횟수를 합산하면 안 된다.

| 증거 | 관측 결과 |
| --- | --- |
| 어댑터 구현 전 최초 실제 MySQL 인수 테스트 | 25 FAIL, 이후 구현과 GREEN |
| 최종 Recording 인수 테스트와 독립 검토 재현 | 필수 테스트 28개 + 재현 3개: 31 PASS |
| 전체 필수 MySQL 목록 | 728 PASS, 통과 phase 2,184개, skip/xfail 0, JUnit 883.700초 |
| 해당 원본 JSON/JUnit에 대한 strict CLI | PASS, 검토자가 독립적으로 반복 |
| 별도 실행한 원본 mutation 함수 suffix | 매개변수 변이 4,619개 거부; Recording 364 layer와 메타데이터 112개 및 family 누락 9개 거부 |
| 기존 gate 단위 목록 | 5,094 PASS, 이 구현 세션의 결과 보존; 해당 실행 이후 checker 함수와 목록은 변경 없음 |
| 최종 경계 / Contract fixture / 정적 검사 | 위반 0; 구조 62 / JSON 26 / 의미 104개 검사 PASS; 기존 목록과 동결된 마이그레이션 보존 |

통합 scratch 실행기는 변이 검사 중 자체 1,200초 제한에 걸렸다. **PASS가 아니다**.
완료된 원본 728-test MySQL JSON/JUnit은 수정하지 않고 직접 검증한 뒤,
`report = json.loads(...)`부터 최종 산출물 쓰기까지 정확한 원본 테스트 함수 AST
suffix를 원래 globals와 assertions로 실행했다. subprocess 결과를 모킹하거나
실행 보고서를 조작하지 않았다. 소스/AST/입력 해시와 정상 완료는
`mutation-recovery-command.json` 및 `mutation-recovery-result.json`에 기록했다.
검토자는 AST 동일성을 독립적으로 확인했다. workflow 30분과 중첩 MySQL 900초는
변경하지 않았다. 중첩 제한까지의 16.3초 여유는 성능 위험이다.

호출자 롤백, 미커밋 가시성, 같은 스트림 직렬화, 실제 lock timeout, 다중 행 쓰기
실패, 연결 해제, 무관한 SQL 오류, COMMIT ACK 손실을 실제 MySQL에서 실행했다.
ACK 손실 결과는 여전히 불명확하다. 호출자가 CommitOutcomeUnknown을 받아도
커밋된 ref가 복원될 수 있다. exactly-once나 미커밋 보장을 도입하지 않는다.
새 인스턴스 복원, 원본 삭제 후 실제 PNG 바이트, case 간 부정 조회가 모두 통과했다.
신규/이전 revision upgrade, 데이터 보존, 재실행, 스키마 메타데이터 비교가 통과했다.
Downgrade는 거부하며, 실패한 DDL은 기존 전진 전용 MySQL 마이그레이션 정책에 따라
부분 적용 상태로 남을 수 있다.

최종 비 MySQL 소비자 선택 실행은 **1,224 PASS / 17 SKIP / 2 FAIL**이었다.
Recording은 544 PASS / 외부 미디어 skip 15개, Worker는 91 PASS, Case는 475 PASS /
외부 비디오 skip 2개였다. API process-safety 테스트는 변경하지 않은 총 5초 제한을
초과했다. 파일 재검사는 43 PASS / 2 FAIL, 실패 시나리오 격리 실행은 8 PASS / 1 FAIL
이었다. **전체 회귀 GREEN이 아니다**. 읽기 전용 가상 HEAD 비교에서는 변경된
import 모듈 네 개를 HEAD 소스로 대체했다. 세 쌍의 사례에서 현재 소스와 가상 HEAD
모두 제한 시간을 초과했다. 두 실행 모두 추가 import loader를 포함하므로, 이는
차등 진단 증거이며 수정 없는 HEAD pytest 결과가 아니다. 별도의 20초 진단 제한에서는
변경하지 않은 lifecycle/listener/signal assertions가 6.963 / 7.025초에 완료됐다.
이는 원래 5초 테스트를 대체하거나 완화하지 않는다. 환경/타이밍 원인은 추론이며
정확한 원인은 확인되지 않았다. API 구현이나 프로세스 timeout 정책은 변경하지 않았다.

설정, 정리, timeout 실패를 포함한 모든 원시 시도는 따로 보존했다. 앞선 완전한
전체 pytest 시도는 3 FAIL이었고 이후 전체 시도는 의도적으로 중단했으며, 둘 다
최종 PASS가 아니다. `verification-final.json`은 이 현재 결과들을 구분한다.
검토자는 경계/Contract/정적/strict 검사를 직접 실행하고 구현 실행의 MySQL/pytest/OS
증거를 검사했으며 전체 데이터베이스 모음을 다시 실행하지는 않았다.

최초 자원 감사에서 통합 timeout 이후 작업 소유 테스트 스키마 두 개를 발견했다.
이를 명시적으로 제거한 뒤 새 감사에서 client, transaction, lock, 테스트 계정이
없음을 확인했다. 작업 소유 서버를 정상 종료하고 로그를 복사한 뒤 정확한 임시
데이터 디렉터리를 제거했다. 최초 실패한 정리 검사는 수정된 감사와 별도로
`pre-cleanup-leftovers.json`에 남아 있다.

Contract, Accepted Decision, Baseline의 의미/값은 변경하지 않았다. 이 작업은 새
Case/Runtime 의무를 추가하지 않는다. REC-1은 IN_PROGRESS / Refs #302를 유지하고
PR과 merge SHA는 pending이다. source 등록/조합은 (b)/RT-11 범위로, 최종 소유권과
DerivedAsset 바이트/Content-Type은 (c) 범위로 남는다. 원본 IncidentClip 바이트
게시 수명은 후속 제한 사항으로 남는다.
현재 diff에는 원격 CI 결과가 없다. 병합 준비 상태에서는 원래 API 타이밍 실패와
현재 CI를 계속 드러내야 하며, REC-1(a) 코드/인수 준비 상태는 깨끗한 전체 프로젝트
회귀나 REC-1 완료와 별개다.
