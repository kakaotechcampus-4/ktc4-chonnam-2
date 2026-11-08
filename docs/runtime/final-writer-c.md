# 최종 writer C 준비 — 고정 B 이후의 청크·envelope 쓰기

## 상태와 source identity

사용자가 준비한 `codex/issue452-final-writer`, clean HEAD `ce0750d5a3317ad1c810783d67f8a05ba88bce08`에서 시작했다. 이 SHA는 병합된 **호환 중간 release B**다. 현재 C는 그 위의 미커밋 변경이며 고정 C release SHA·image digest는 아직 없다. 브랜치 이름이나 B SHA를 C 배포 revision으로 사용하지 않는다.

**Draft PR 제출 준비 가능, 병합·배포 준비 미완료**다. 필요한 DB 검사를 작성하고 기존 원격 CI에 결속했지만 로컬 DB·수정 후 원격 CI는 NOT_RUN이다. 운영 e50은 과거 운영자 보고이며 최신 서버는 조회하지 않았다.

| 역할 | 실제 source |
| --- | --- |
| O | `e50b2976ef4edc3a030cfc5b03a5206340dd917b`의 `git archive` |
| B | `ce0750d5a3317ad1c810783d67f8a05ba88bce08`의 `git archive` |
| C | 현재 작업 tree/향후 실제 PR checkout |

과거 대조 C `ceb6f5fa010f1f541179e9d3ab95aecd5a82d3cb`는 이번 최종 C가 아니다. `test_compatible_revisions_mysql.py`의 `bridge`는 고정 B, `final`은 현재 C다. snapshot 경로를 명시한 시험 하네스도 고정 SHA·파일 hash를 검증하며 누락 시 최신 source로 대체하지 않는다. 정상 CI는 실제 Git objects를 archive한다.

## 제품 변경과 보존 조건

제품 diff는 Recording repository의 `PREPARED_WRITE_FORMAT="chunked"`와 설명뿐이다. B source AST에서 이 상수만 바꿔 현재 AST와 비교했고, **76개 함수 정의를 포함한 나머지 의미가 동일**함을 확인했다. 다음 기능을 새 구현으로 대체하지 않았다.

- legacy BLOB/native metadata와 chunk/envelope의 dual reader.
- 모델·descriptor·실제 content integrity의 exact 비교, 불일치 거부.
- 기존 ref의 raw metadata/BLOB/chunk 표현 보존과 동일 재전달 재사용.
- SAVEPOINT·실제 escaping packet guard·caller transaction 소유권.
- RR snapshot 뒤 locking current read 일관성 보완.

신규 content는 기본 청크 manifest/version1·`recording_media_chunk`로, 신규 prepared metadata와 metadata-only는 기본 envelope로 쓴다. 명시 legacy 정책은 guard 회귀 검사에 남아 있지만 C의 운영 기본값을 검증하는 근거로 사용하지 않는다. 기존 B 기본값 검사를 현재 tree가 B인 것처럼 계속 실행하지 않는다.

Case/Worker·controller·schema/migration·한도/config 제품 변경은 없다. #583의 썸네일 변경·이미지·사용자 흐름을 이 diff에 포함하지 않는다.

## 실제 production default와 전이 검사의 범위

`test_final_writer_mysql.py`의 필수6개 identity는 API command, Worker analysis factory, Worker incident factory 각각의 metadata-only/content 경로다. 각 검사는 두 prepared kind를 모두 확인한다.

- API `ApiComposition.execute_command`가 직접 만든 `RecordingService`/`ConnectionRecordingRepository`를 사용한다. Recording override는 주입하지 않는다.
- Worker `ProductionMediaFactory`/`IncidentRecordingFactory`가 직접 만든 `TransactionalRecordingRepository`를 사용한다.
- repository·transaction facade·MySQL 쓰기는 실제 구현이며 `prepared_write_format` 옵션/상수 monkeypatch는 없다. raw SQL에서 envelope, content=NULL, chunk 유무와 정확한 모델/bytes roundtrip을 검사한다.
- Case command와 provider/encoding 경계는 시험용으로 대체·중단한다. 전체 HTTP·handler·FFmpeg·provider E2E 검증을 했다는 뜻이 아니다.

실제 revision 검사는 독립 process에서 O/B archive 및 현재 C package의 import 경로를 확인한다. B의 신규 legacy/native·metadata-only를 실제 O가 읽고, C의 B ref 재전달이 기존 표현을 보존하는지 확인한다. C의 신규 metadata-only envelope를 B가 읽고 재전달한 뒤, C가 실제 기본값으로 content를 청크에 붙이고 B가 읽기·metadata-only/full 재전달해 raw snapshot을 유지하는지 검사한다. C 신규 형식에 대한 O의 `ValidationError` 거부도 유지한다. 별도4개 job 조합은 실제 Case/scope/T1/T2/receipt 대조이며 합성 빈 후보 Coarse 프로토콜 범위다.

이 DB 검사들은 **작성·수집 완료, 실행 NOT_RUN**이다. source/collection 또는 checker 자체 통과를 실제 B→C→B 데이터 검증 통과로 보고하지 않는다.

## 자원 판단과 원격 CI

실행 전 읽기 전용 조사: C: free7589703680bytes(약7.07GiB), Windows available memory6703976448bytes, Ubuntu/Docker Desktop Stopped, 시험 DB URL 없음. 이전 native 실행환경 root 미발견 이력도 있다. 로컬 Docker 기동·재구축·새 DB·대규모 image 복제는 하지 않았다. 이 수치를 실제 MySQL 최대 사용량이나 원격 runner 여유의 증거로 쓰지 않는다.

기존 `python-tests.yml`을 사용한다. MySQL과 regression job 모두 O/B Git 이력을 확보하고 commit·root tree·src/migrations tree를 사전검사한다. source identity offline 검사가 regression에도 포함되므로 해당 job도 full history가 필요하다. quality/test job과 나머지 실행 단계·timeout은 유지한다.

새6개 default identity는 Recording inventory와 독립 strict checker 양쪽에 필수 등록했다. canonical MySQL→strict JSON/JUnit→증거 봉인→실제 보고서 변조→원본 재대조 순서는 그대로다. 실패·누락을 skip하거나 gate를 느슨하게 하지 않는다. 최종 required `test`는 quality/regression/mysql 모두 성공해야 한다. 실제 PR SHA의 원격 CI 결과와 리뷰를 확인하기 전에는 병합 준비 완료가 아니다.

## 실행 근거

근거는 Windows `.codex-scratch/final-writer-c/`에 보존한다. 숫자는 서로 다른 겹치는 실행이며 합산해 고유 검사 수로 보고하지 않는다.

| 확인 | 실제 결과 |
| --- | --- |
| 변경 전 기본값/역할 RED | **3 failed / 6 passed** (`red-verified.xml`) |
| 기본값·고정 B source GREEN | **9 passed** (`green.xml`) |
| 위 검사와 metadata codec offline | **28 passed** (`offline.xml`) |
| strict checker의 완전 합성 보고서 | **1 passed** (`checker.xml`), 실제 DB 보고서 아님 |
| 새6개 default identity 누락/metadata 손상 거부 | **66 passed** (`new-identity-checker.xml`), checker 자체 검사 |
| 실제 collection 분할 audit | **PASS**: full16167 = regression14882 + mysql1283 + media1 + gate1 (`collection/summary.json`) |
| 변경 Python Ruff | **PASS** |
| 경계·계약 정합성 | **PASS**, 위반0 |
| 제품 AST·CI YAML/Bash 사전검사 | **PASS** (`source-and-workflow-checks.json`) |
| 실제 B→C→B DB·production default DB 쓰기 | **NOT_RUN** |
| C canonical MySQL·strict·실제 보고서 변조·원격 required CI | **NOT_RUN** |

수집 시 optional Search 의존성 `typer` 누락에 따른 collection skip4개가 있었다. mandatory 실행 실패를 skip한 것이 아니며 실제 DB gate의 성공 증거도 아니다. 첫 RED 실행은 시험 parent 경로 부재로1 failed/8 setup errors였고, 경로 준비 후 실제 assertion RED를 별도 실행했다. 경계 검사의 첫 출력은 Windows cp949에서 실패해 동일 검사를 UTF-8로 재실행했다. 실패 기록을 통과 보고서로 덮어쓰지 않았고 assertion·skip·timeout은 완화하지 않았다.

독립 reviewer는 제품 diff·고정 B·production default DB 검사·필수 identity를 읽기 전용 검토했다. regression shallow checkout이 source identity 검사를 깨뜨리는 P1을 지적했고, full history와 사전검사를 추가한 뒤 지적 해소를 재확인했다. 다른 확정 P1/P2 지적은 없었다. reviewer는 DB/테스트를 실행하지 않았으며 이 검토를 DB 성공으로 대신하지 않는다.

기존 B의 Worker cancellation `[retry]` 원격 PASS와 앞선 로컬 실패 원인 미확정은 계속 구분한다. 이번 C에서 그 Worker 실패를 수정하거나 원인을 규명한 것은 아니다.

## 배포·rollback과 600→150

C 신규 형식 생성 후 e50을 rollback 대상으로 승인하지 않는다. rollback 후보는 실제 데이터·schema·job 조건을 검증한 고정 B이며, 이 PR 준비는 controller 승인이나 운영 known-good 선언이 아니다. schema head 동일·queue drain만으로 호환 판정을 대체하지 않는다.

배포 전에는 실제 B/C SHA·image digest·config, controller current/previous/schema authority·승인 tuple, write-stop의 일관된 DB/media backup 및 빈 target restore rehearsal를 결속해야 한다. 운영 image build/publish·startup/health·복구 검증은 NOT_RUN이다. 새 데이터 생성 전의 code rollback, 생성 후 B rollback, backup 시점으로의 restore와 이후 쓰기 정산, 전진 복구를 서로 구분한다.

작성 당시에는 Coarse 기본 600초를 유지하고, 실제 15개/약 26분 Upload→Search/Case→후보 확인→Export→Package READY→다운로드 이후 새 reader를 유지하는 별도 source/image에서 기본 150초로 복귀할 계획이었다. 당시 계획은 이미 저장된 600초 scope의 별도 정산을 포함했고 O로의 code rollback을 복귀 방법에서 제외했다. 공개 RC에는 [Case 대기 결정](../modules/case/decisions/case-wait-timeout.md) §3-10의 600초 유지가 적용된다.

AWS·운영 DB·publish·배포·원본 E2E·provider·backup/restore·600→150 복귀 배포·commit·push·외부 게시는 NOT_RUN이다. 기존 원본·보호 증거·volume을 삭제하거나 시험 입력/DB로 사용하지 않았다.
