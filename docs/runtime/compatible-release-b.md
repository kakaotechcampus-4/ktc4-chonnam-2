# 호환 중간 release B — 구현·검증 기록

**LOCAL IMPLEMENTATION · NOT DEPLOYED · Refs #452.** 2026-11-05, 전용 브랜치 `codex/issue452-compatible-release`. 시작 HEAD/고정 최종 후보 C는 `ceb6f5fa010f1f541179e9d3ab95aecd5a82d3cb`, O는 운영자 보고 `e50b2976ef4edc3a030cfc5b03a5206340dd917b`다. 서버 최신 current/previous/schema/controller는 미조회다. 이 미커밋 B에는 release SHA/image/승인 tuple이 없다.

> **Coarse 예산 후속 결정:** 아래 150초 복귀 절차는 이 기록 작성 당시의 계획이다. 공개 RC에서는 [Case 대기 결정](../modules/case/decisions/case-wait-timeout.md) §3-10에 따라 첫 Coarse 실행 예산 600초를 유지한다.

## 제품 변경과 release 정책

제품 변경은 Recording repository의 신규 prepared-media 쓰기 정책이다. `mysql_repository.PREPARED_WRITE_FORMAT="legacy"`가 B의 기본이며, API/Worker의 기존 repository facade도 이 기본을 소비한다. env/runtime 설정은 추가하지 않는다. 테스트에서 명시하는 `prepared_write_format="chunked"`는 유지된 청크 writer를 검증하는 seam이며 운영 설정 완료의 증거가 아니다.

- B의 신규 AnalysisSource/IncidentClip metadata는 native JSON, content는 기존 `recording_entry.content` BLOB, integrity descriptor는 기존 형태다. metadata-only 등록도 같다.
- 새 reader는 legacy BLOB·청크와 native metadata·envelope를 계속 읽는다. public ref/model/provenance/fingerprint를 바꾸지 않는다.
- 기존 ref는 no-op INSERT/current locking read 아래 exact 모델과 descriptor를 대조한다. 기존 envelope/native payload를 덮어쓰지 않는다. 기존 BLOB은 서버 길이/hash, 청크는 detached reader의 count/size/hash 검증 뒤 재사용한다. 새 case link는 검증 후에만 추가한다.
- REPEATABLE READ에서 이미 열린 오래된 snapshot도 검사했다. metadata 잠금뿐 아니라 BLOB 길이/hash·청크 count/content·metadata-only content 부착의 조회까지 current read를 사용한다. 서로 다른 조회 시점 때문에 올바른 재전달을 거절하는 반례를 세 형식에서 재현하고 보완했다.
- metadata-only ref에 content를 붙일 때도 payload는 보존한다. native/envelope와 BLOB/chunk는 별도 축이다. B에 이미 존재하는 C envelope를 native로 바꾸지 않는다.
- native MySQL JSON이 숫자를 바꿔 exact 모델 비교가 실패하면 신규 metadata-only/content 등록 전체를 SAVEPOINT로 되돌린다. caller가 예외를 잡고 commit해도 신규 부분 등록은 남지 않는다. 반올림·epsilon·guard 완화는 하지 않는다.
- 따라서 B는 native JSON의 기존 1ULP 제약을 해결하지 않는다. 표현이 정확하게 보존되지 않는 신규 입력은 실패할 수 있다. 이 한계 때문에 B를 26분 E2E 실행 release로 사용하지 않는다.
- legacy BLOB SQL은 실제 session packet에서 64KiB를 뺀 예산과 명시 command budget을 적용하고, escaping 이후 길이를 보내기 전에 검사한다. 청크 writer의 기본 command 1MiB·256KiB chunk·packet 검사는 유지한다. BLOB 전체 allocation·materializer·일부 Export의 전체 bytes 할당은 남는다.

`recording_0002`는 기존 additive migration 그대로이며 새 migration/controller 예외는 없다. Case/Worker/600초 정책은 이 변경에서 수정하지 않는다. 이전 상태의 모르는 Case 키를 보존하는 기존 코드를 사용한다. job 형식이 같다는 사실을 모든 handler/사용자 영상 호환 증거로 확대하지 않는다.

## O → B → C → B 계약

1. 운영자가 실제 tuple·schema authority/heads·데이터 형식·job 상태·controller hash를 읽어 대조한다. O를 최신 조회값으로 대신하지 않는다.
2. B가 생성하는 모든 새 형식과 실제 job/case 경로를 O가 처리한다는 근거가 있어야 B의 `rollback_targets`에 O를 승인할 수 있다. B의 source SHA/push CI/exact image/config/DB-media backup 근거를 별도로 확보한다. 이 기록만으로 그 승인을 완료하지 않는다.
3. C의 `rollback_targets`에는 C 데이터/job/case를 처리하는 검증된 B를 넣고 O를 제외한다. `schema_parent`는 current code가 아니라 실제 `schema.json` authority revision에 맞춘다.
4. C에서 B로 rollback해도 schema authority는 C에 남는다. B의 과거 목록을 재사용하여 O로 다시 내리지 않는다. queue drain·동일 heads·backup만으로 O의 청크/envelope 비호환을 해소하지 않는다.
5. migration_pending/부분 DDL·pointer 불일치·unknown COMMIT은 정상 전이 성공이 아니다. 현재 controller의 fail-closed/reconcile 규칙을 유지한다. backup/restore는 별도 빈 target·동일 heads·동일 write-stop DB/media·hash/mtime/소유권 검증과 onboarding 검토가 필요하며 운영 DB overwrite/downgrade를 제공하지 않는다.

최종 writer release는 기본 정책을 명시적으로 chunked로 전환한 별도 source SHA여야 한다. 현재 고정 C는 B 변경 전의 실제 Git source다. B가 구현됐다는 사실만으로 C image를 B의 새 writer 정책으로 바꿔 읽지 않는다.

### B 병합 후 C 준비 순서

1. 이번 B PR을 검증·리뷰하고 병합한 실제 B revision을 고정한다. B의 기본 신규 쓰기는 계속 `legacy`다. B 병합만으로 26분 E2E용 writer가 준비된 것으로 보지 않는다.
2. 병합된 B 위에서 별도 C PR을 만든다. `PREPARED_WRITE_FORMAT` 기본값을 `chunked`로 복귀해 청크 content와 metadata envelope를 함께 활성화하고, 이번 reader·exact 비교·SAVEPOINT·RR 보완을 유지한다. env 토글이나 B image 재명명으로 C를 만들지 않는다.
3. C에서는 release별 기본값 검사를 구분한다. B의 legacy 계약 검사는 명시 legacy writer 또는 고정 B source를 대상으로 남기고, C의 실제 API/Worker facade 기본 쓰기가 chunk/envelope임을 별도로 검증한다. 실제 revision 하네스의 `bridge=ROOT`도 C 작업 tree를 B라고 부르지 않도록 고정 B SHA source로 바꾸고 C는 새로운 후보로 대조한다.
4. C의 canonical gate와 B→C→B 데이터/schema/job 검증을 새 source에서 실행한다. 현재 `ceb6f5fa`는 이번 대조에 사용한 과거 chunked-writer source이며, B 병합 후 만들어질 C의 최종 SHA를 미리 대신하지 않는다.
5. 운영자는 B/C 각각의 실제 SHA·image digest·config·controller 승인·DB/media 복구 증거를 결속한다. 승인된 O→B→C 순서로만 전환하고 C 이후 rollback 대상은 검증된 B다. 당시 계획에는 E2E 이후 새 형식 reader를 유지하며 기본 Coarse를 150초로 복귀하는 D가 있었다. 이번에는 병합·C 구현·배포를 실행하지 않는다.

## 검증 구성과 범위

- `test_compatible_release.py`: B 기본 metadata 정책과 잘못된 정책 거부.
- `test_compatible_release_mysql.py`: 두 kind의 native/BLOB 신규 쓰기·metadata-only, C 형식 exact replay·충돌·손상, native 정밀도 거부·원자성, packet guard·facade 기본·caller rollback·혼합 형식 attach.
- `test_compatible_revisions_mysql.py`와 `compatibility_revision_driver.py`: O/C의 Git archive에서 실제 src/migrations를 별도 경로에 읽기 복사한다. 각 revision은 독립 Python process에서 import 경로를 확인한다. 같은 새 시험 DB에서 O schema/seed→B upgrade→C 읽기/쓰기→B replay를 검증하고, O의 C envelope 읽기 거부를 대조한다.
- job 대조는 실제 Case 저장·AnalysisScope·enqueue/claim·T1 produced+finish·T2 CaseReflector·receipt 재전달이다. O 발주 150 scope와 B/C 발주 600 scope를 읽는다. provider/Recording handler를 호출하지 않는 빈 후보 Coarse 결과를 사용한다. 모든 handler·비어 있지 않은 후보의 전체 후속 pipeline·운영 재시작 검증을 대신하지 않는다.
- 추가로 B 발주600 scope를 실제 O가 claim/finish/T2 반영하고 B가 receipt를 재조회하는 방향도 검증했다. O의 대기 정책은 준비 여유가 없는 이전 정책이다. 저장 형식/작업 프로토콜 호환을 현재 대기 시각·프리뷰 동작까지 동일하다는 뜻으로 확대하지 않는다.
- 기존 청크/exact MySQL 테스트는 명시 chunked writer로 계속 검증한다. B 기본 쓰기는 별도 실제 MySQL 테스트가 검증한다. 새 MySQL identity는 필수 inventory와 독립 checker에 각각 등록한다.

Case/Worker 범위 대조: O..C에서 common jobs 프로토콜 파일과 `worker/case_reflector.py`, `case/store_mysql.py`에는 변경이 없다. Case의 state_version은1이며 모르는 state/Candidate 키는 보존한다. C의 준비 여유·진행/실패 표시·preview/incident frame 결과 소비에는 변경이 있다. B는 사용자가 준비한 C 기준 브랜치를 사용하며 이 기능들을 다른 구버전 브랜치에 일괄 이식하지 않았다. 이번 제품 diff는 Recording repository 한 파일이고 추가 Case/Worker 보완은 하지 않았다.

## 실제 실행 기록

아래 수치는 서로 겹치는 별도 실행이며 더해서 고유 검사 수로 보고하지 않는다. 근거는 로컬 `.codex-scratch/compatible-release-b/`의 로그·JSON·JUnit·고정 source identity다. 합성 영상만 사용했다.

| 검사 | 확인된 결과 | 근거 파일 |
| --- | --- | --- |
| 기본 정책 TDD | 변경 전 신규 검사6 실패 → 구현 후 기존37+신규6 통과 | `red-unit.log`, `green-unit.log` |
| 최종 Recording/MySQL+실제 revision5+controller+Case 대기 | **97 passed**, skip0 | `linux-1793861948747288300.log`, `native-focused.json/xml` |
| 확장 실제 revision6+Worker42 | **46 passed, 2 failed**; 두 실패는 spawn이 하네스를 재진입해 `/tmp/compatible-work`를 중복 생성한 오류 | `linux-1793862395291690500.log`, `native-worker-final.json/xml` |
| 위 별도 Worker/API 프로세스2 재검증 | 하네스 `__main__` 경계 보완 뒤 **2 passed** | `linux-1793862760825189900.log`, `worker-spawn-rerun.json/xml` |
| 신규 unit6+독립 MySQL checker/gate mutation | **9423 passed**; 23개 B 필수 identity를 inventory/checker 양쪽에 등록 | `checker-post-final.log` |
| 정규 regression과 동일한 선택의 Linux 전체 실행 | **14739 passed, 10 failed, 33 skipped, 1273 deselected**. 전체 PASS 아님 | `linux-1793861946363299800.log`, `native-regression.xml` |
| 변경 파일 Ruff / Runtime 품질 | Ruff 통과; Linux/Windows mypy 각각89파일 통과 | 최종 명령 출력, `quality.log` |
| 경계·계약 | 경계 위반0; 문서62·JSON26·의미fixture104 통과 | `boundaries-utf8.log`, 최종 명령 출력 |

전체 회귀 실패는 다음과 같이 대조했다. 실패를 삭제하거나 PASS 보고서로 덮어쓰지 않았다.

| 실패/제약 | 후속 대조와 남는 한계 |
| --- | --- |
| 합성1GiB 업로드2 | 초기 임시 공간512MiB는 부족했다. 2GiB에서도 비선언 길이 시험은 성공 파일+진행 중 파일이 함께 있어 부족했다. 별도4GiB 메모리/3GiB tmpfs runner에서 **2 passed** (`upload-large.xml`). 운영 메모리 요구량 측정이 아니다. |
| FFmpeg720p 생성 SIGKILL1 | 별도3GiB runner에서 통과 (`resource-rerun.xml`). 최초 실행은 자원 제약하의 실패로 보존한다. |
| pytest/ruff/mypy 누락 관련5 | 기존 시험 이미지 자체에는 해당 도구가 없다. 특히 PYTHONPATH를 바꾸는 child는 복사한 pytest도 못 찾았다. 설치된 Windows venv에서 해당 누락 검사·실제 partition collection·품질 self-test를 포함해 **21 passed** (`tools-rerun.xml`). 같은 Linux 전체 실행의 재통과는 NOT_RUN이다. |
| diagnostic CLI2 | Linux 시험 이미지에 Git이 없음을 직접 확인했다. Git이 있는 Windows에서는1 passed/1 failed(MEDIA_PREPARATION). 변경 전 C의 실제 공개 tree를 별도 경로에서 실행해도 동일한1 passed/1 failed를 재현했다 (`diagnostic-rerun.xml`, `baseline-diagnostic.xml`). 이 기존 입력/환경 실패는 미해결이며 B 변경으로 고치지 않았다. |
| 앞선 Windows Recording/Worker 오프라인 실행 | 1419 passed/16 failed/15 skipped/550 deselected. Linux의 변경 전 C 대응 Recording5파일은74 passed/6 skipped였다 (`baseline-recording.xml`). Windows 전용 결과를 Linux 전체 PASS로 치환하지 않는다. |

그 밖의 시험 하네스 오류/중단도 보존했다: Windows 전체 실행 정체 후 소유 pytest만 중단, Windows controller symlink 권한 실패, Windows bind temp의 `utime` EPERM/child timeout, 순수 pytest 보조 `py` 누락, 시험 URL의3306 포트 누락으로 fault proxy가 연결하지 못한 실행이다. 포트 누락 실행은 SIGINT 후 각각6/12 passed에서 중단했으며 완료로 세지 않는다. native 임시 파일시스템·포트 명시·spawn 경계는 시험 도구에만 적용했다. 검사 assertion·제품 오류 분류는 약화하지 않았다.

초기 독립 리뷰는 사용자 요청에 따라 별도 reviewer가 diff·계획·실행 근거를 읽는 방식으로 수행했다. 당시 확정 P1/P2는 보고되지 않았다. reviewer는 합성 Coarse T1/T2 검증이 실제 handler 전이와 같지 않다는 한계를 지적했고 본 기록에 반영했다. 이후 작성자가 RR 세 반례를 RED로 재현해 제품 코드와 테스트를 보완하고97개 검사로 확인했다. 초기 구현 종료 때에는 후속 독립 재리뷰를 NOT_RUN으로 기록했으며, 아래 PR 준비 후속에서 실제 재리뷰 결과로 갱신했다. reviewer가 DB 시험을 직접 실행한 것은 아니다.

### PR 준비 후속 — RR 재리뷰와 회귀10건 정산

2026-11-05 사용자 후속 요청에 따라 별도 reviewer가 RR current read 수정·세 RED 로그·97개 보고서·제품 hash를 다시 대조했다. **확정 P1/P2 지적 없음**이다. reviewer의 제안으로 RR 테스트에 raw metadata/chunk 보존, 기존 full registration snapshot 불변성, 실제 MP4 bytes/MIME 확인을 추가했다. 이 보강 diff도 독립 확인해 잔여 확정 지적이 없음을 보고받았다. 따라서 앞 문단의 후속 독립 재리뷰 NOT_RUN은 이 기록으로 갱신한다. reviewer의 직접 DB 실행은 계속 NOT_RUN이며 보강 assertion의 실행 판정은 canonical gate에 결속한다.

전체 회귀10건은 실제 실패 testcase10개 각각을 후속 PASS JUnit에 대조했다(`pr-regression-10.json`, 원본/후속 report hash 포함). 이미 확인한8건의 통과는 재사용하고, 도구가 갖춰진 Linux에서 확인되지 않았던 diagnostic2건만 추가 실행했다.

| 원래 실패 testcase | 분류 | 후속 실제 근거 |
| --- | --- | --- |
| API 기본1GiB 스트리밍 `[False]` | 시험 임시 공간 부족 | `upload-large.xml`: PASS |
| API 기본1GiB 스트리밍 `[True]` | 시험 임시 공간 부족 | `upload-large.xml`: PASS |
| `test_require_missing_dependency_fails_without_skip` | child에 pytest 없음 | `tools-rerun.xml`: PASS |
| diagnostic fixture trace CLI | 초기 Linux image에 Git 없음 | 고정 의존성+Git Linux의 `pr-diagnostic.xml`: PASS |
| diagnostic output failure 분류 | 초기 Linux image에 Git 없음 | `pr-diagnostic.xml`: PASS |
| `test_fine_height_at_most_720` | 초기 FFmpeg SIGKILL/시험 자원 제약 | `resource-rerun.xml`: PASS |
| 실제 partition collection | child 도구 부족 | `tools-rerun.xml`: PASS |
| Runtime quality self-test `[None]` | ruff/mypy 없음 | `tools-rerun.xml`: PASS |
| Runtime quality self-test `[lint]` | ruff/mypy 없음 | `tools-rerun.xml`: PASS |
| Runtime quality self-test `[type]` | ruff/mypy 없음 | `tools-rerun.xml`: PASS |

이10건에서 **확인된 B 회귀는0건**이다. 별도 Windows diagnostic은 B와 변경 전 C에서 같은1 failed/1 passed를 재현했고, 준비된 Linux에서는2 passed다. Windows MEDIA_PREPARATION의 정확한 환경 원인은 미확정이며 제품의 기존 결함이라고 단정하지 않는다. 원래 Linux10 실패는 환경 문제로 후속 통과가 확인됐지만, 전체 regression을 새로 실행해 통과했다는 뜻은 아니다. 전체 재실행은 NOT_RUN이며 assertion·skip·timeout을 바꾸지 않았다.

### Canonical 전체 실행에서 발견한 추가2건

원래 regression10건과 별개다. 첫 완료된 mandatory MySQL 전체 실행은 **1272 passed/2 failed**였다. 두 실패는 `test_analysis_source_limits_mysql.py`의 rollback/commit에서 기본 writer가 청크 행을 생성해야 한다는 과거 C 전제였다. B의 의도된 legacy 기본값 도입으로 드러난 **테스트 전제 회귀2건**이며 환경 문제로 분류하지 않는다. 제품 저장 정책을 청크로 되돌려 숨기지 않았다.

이 파일을 writer2×mode3으로 확장했다. legacy는 기존 default_adapter를 인자 변경 없이 사용하고 chunked는 명시 constructor를 사용한다. 기존 C의 `chunk >= 1`·limits before INSERT·caller transaction·rollback/commit·fresh read·원본 fingerprint·temp 정리를 유지하고, B의 chunk0과 fresh BLOB bytes를 추가했다. 독립 reviewer가 assertion/skip/timeout 완화나 Bdefault 우회가 없음을 확인했다. 실제 MySQL 집중 검증 **6 passed** (`namespace8-policy-limits.xml`) 뒤 수정 source를 별도 고정해 전체 canonical을 재실행했다. 집중 검증을 전체 gate 대신 사용하지 않는다.

기존 보고서와 source를 덮어쓰지 않았다. `pr-source-initial.json/zip`은 최초 source, `pr-source-policy-fix.json/zip`은 추가 한도 검사 보강 source다. source 제품 파일은 동일하며 추가 변경은 테스트와 기록이다. 현재 총 변경은13파일(제품1·검사/driver7·gate2·문서3)이다.

### Canonical 재실행 결과 — PR 차단

`tests.ci_orchestration mysql`의 canonical mandatory 전체 pytest 단계는 **1276 passed / 1 failed / 4 collection skipped / 14790 deselected**, 1036.31초였다. 전체 단계 제한1500초를 변경하지 않았으며 orchestration은 실패를 감지해 종료했다. collection skip4개는 선택 밖의 optional Search 의존성 `typer` 누락이며 mandatory 실패를 skip한 것이 아니다. canonical 뒤의 strict checker와 실제 보고서 변조 단계는 **NOT_RUN**이다. 따라서 **canonical mandatory MySQL strict gate는 FAILED/BLOCKED이며 PR 준비 완료가 아니다**. 별도 checker9423개·집중6개 또는 과거 부분 보고서로 대체하지 않는다.

남은 실패는 `tests/worker/test_cancel_checkpoint_mysql.py::test_cancel_metrics_end_at_durable_commit_ack[retry]`의171행이다. 서버 cancellation age와 독립 COMMIT OK 관측으로 만든 상한 `289.17097500012443 + 30 ms`에 대해 terminal metric이 `552.3955000001494 ms`였다. checkpoint-to-terminal의 기존 assertion은 통과했다. 로그는 `pr-canonical-mysql-namespace8.log`, 고정 source manifest는 `pr-source-policy-fix.json`이다. 변경 전/후 Worker 코드와 해당 테스트에는 diff가 없지만 이것만으로 기존 결함이나 환경 문제라고 판정하지 않는다. 첫 canonical에서는 같은 node가 통과했다.

SQL 조회 전 client sample과 조회 후 server sample 사이의 지연이 중복 반영될 가능성은 **가설**이다. 실제 C baseline과 동일 노드의 정상/조회 전 지연 대조를 위한 별도 probe는 준비했으나 다음 절의 로컬 디스크 문제로 시작하지 못했다(**NOT_RUN**). 따라서 이1건은 **원인·B 인과관계 확인 필요**이며 원래 회귀10건 정산에 섞지 않는다. 관련 없는 Worker를 수정하거나 ±30ms assertion·skip·timeout을 완화하지 않았다. 원인 대조와 필요한 수정·독립 리뷰 후 동일 canonical 전체→strict→실제 보고서 변조 검증이 모두 성공해야 PR 차단을 해제한다.

### PR #587 원격 CI — 고정 revision 누락 보완

[python-tests run42011517523의 MySQL job127191459266](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/42011517523/job/127191459266)의 실제 로그를 읽어 확인했다. PR HEAD는 `551350779e08bc79c5483c747474bd61ba3039dc`이며 Actions checkout은 PR merge ref `d166d78fc2f225ee850920bcc5c643583d868e52`다. checkout의 `fetch-depth: 1`과 실제 `git fetch --depth=1`이 기록돼 있다.

canonical MySQL 결과는 **1271 passed / 6 setup errors / 4 collection skipped / 14793 deselected**, 1176.31초다.6개 모두 session fixture가 고정 O `e50b2976ef4edc3a030cfc5b03a5206340dd917b`를 `git archive`할 때 `fatal: not a tree object`로 실패했다. fixture에는 고정 C `ceb6f5fa010f1f541179e9d3ab95aecd5a82d3cb`도 필요하다. canonical 단계가 실패했으므로 원격 후속 strict JSON/JUnit·실제 보고서 변조는 **NOT_RUN**이며 required `test`도 실패했다. quality/regression job은 success다. 이것을 전체 MySQL gate 통과로 기록하지 않는다.

이번 변경은 MySQL job의 checkout에만 `fetch-depth: 0`을 지정하고, 의존성 설치 전에 두 전체 SHA의 실제 commit·root tree와 archive 대상 `src`·`migrations` tree의 존재를 검사한다. 두 revision은 현재 로컬 HEAD의 조상임을 확인했다. 누락·잘못된 object type은 즉시 실패하며 skip·최신 소스 대체·별도 snapshot 주입은 추가하지 않는다. 다른 job·제품 코드·기존 호환성 assertion·timeout·strict gate는 변경하지 않는다.

변경 검사는 YAML 파싱·MySQL checkout/사전검사 외 workflow 의미 동일성·fixture의 두 고정 SHA 일치·Git Bash 문법·`git diff --check`를 통과했다. workflow에서 추출한 실제 Bash 사전검사는 로컬의 두 고정 revision에서 성공했다. e50 누락·C 누락·commit 대신 blob·commit은 존재하지만 root tree가 없는4개 음성 대조는 모두 exit128로 거부했다. 마지막 대조는 기존 e50 commit object의 동일 bytes만 별도 임시 object directory에 복사해 실행했으며 새 commit/ref/index를 만들거나 원본 Git object를 수정하지 않았다. 첫 제한 실행의 MSYS 권한 오류는 별도 실행 권한으로 같은 검사를 재시도해 해소했으며 Ubuntu/Docker는 기동하지 않았다. 세부 결과는 Windows `.codex-scratch/compatible-release-b/pr587-workflow-checks.json`에 보존했다. 이 변경 검사를 전체 MySQL/원격 CI 통과로 대신하지 않는다.

같은 원격 로그에서 `test_cancel_metrics_end_at_durable_commit_ack[retry] PASSED`를 확인했다. **이번 원격 실행 PASS와 기존 로컬 실패 원인 미확정은 별개**다. 앞선 로컬1276 passed/1 failed를 취소하거나 조회 전 지연 가설이 입증·해결됐다고 하지 않는다. 실제 C/B baseline 대조는 계속 **NOT_RUN**이다.

원격 decoded job log는 Windows `.codex-scratch/compatible-release-b/pr587-mysql-55135077.log`에 보존했다. Ubuntu namespace8 내부 JSON/JUnit 미발견을 이 로그로 복구했다고 표시하지 않는다. 후속은 로컬 Docker/전체 테스트 환경을 재구축하지 않고 workflow와 사전검사만 검증한다. 수정 후 원격 CI·canonical MySQL·strict·실제 보고서 변조 재실행은 commit/push 전이므로 **NOT_RUN**이다. Draft PR 제출 가능과 병합·배포 준비 미완료를 계속 구분한다.

### 로컬 검증 환경 장애와 보존 상태

추가 baseline probe를 준비하던 중 이번 작업이 만든 여러 격리 Docker image cache가 C: 실제 공간을 소진했다. 작성자가 호스트 여유 공간 대신 WSL 가상 `df`에 의존한 자원 관리 오류다. Ubuntu ext4에서 `emergency_ro`/I/O 오류를 확인했고, 추가 시험을 중단했다. 기존 volume·원본·보호 증거를 삭제하는 복구는 수행하지 않았다.

이번 scratch의 JSON/XML/log5400개, 논리 크기261206724bytes를 무손실 NTFS 압축했고 전후 파일 SHA256 동일을 확인했다. C: 여유는 약0.49GB까지 확보했으나 복구 완료나 전체 자료 무결성의 증거는 아니다. 사용자 승인 범위에서 Ubuntu 종료·재시작을 수행했지만 `WSL_E_DISK_CORRUPTED` 및 이후 `Wsl/Service/CreateInstance/E_FAIL`로 시작하지 못했다.

실행 중 Docker Desktop container0개를 확인하고, mount root가 정확히 이번 `/tmp/daesingo-compatible-b-pr-6c746182dfd2`인 사용하지 않는 bind만 정상 `umount`했다. 강제/lazy unmount, 전체 WSL/Docker Desktop 종료, `fsck` 수정·강제 remount, 기존 VHD/volume 삭제는 하지 않았다. 정상 해제 뒤 Ubuntu는 계속 시작 오류이며 디스크 device는 detach되어 `e2fsck -n`도 검사하지 못했다. **복구 및 Ubuntu 내부 증거의 읽기/무결성 확인은 미완료**다. namespace8의 전체 로그는 Windows에 있으나 내부 core report를 Windows로 회수·검증하는 작업도 중단됐다. 강제 복구를 승인받은 것으로 해석하지 않는다.

사용자는 전체 WSL/Docker Desktop 추가 재시작 없이 현 상태와 PR 차단 사유만 정리하도록 결정했다. 추가 복구는 수행하지 않는다. 향후 재개하려면 백업 가능 공간과 영향 범위를 먼저 확인하고 별도 사용자 승인을 받아야 한다. 이번 환경 장애를 MySQL gate 통과 또는 제품 데이터 호환성 실패로 바꾸어 해석하지 않는다.

### PR source 검증과 남겨둘 image 검증

PR source 준비에서 RR 재리뷰·실제 canonical mandatory MySQL·원래 회귀10건 정산·합성 Recording media smoke·변경 파일 lint·경계/계약/diff를 확인한다. 처음 실행한 별도 synthetic media smoke는 **1 passed**다. 기존 Runtime 품질89파일, 경계/계약, collection audit는 대상 source/collection이 바뀌지 않은 범위에서 기존 근거를 재사용하며 이유 없이 반복하지 않는다.

현재 `python-tests.yml`의 required `test`는 quality/regression/mysql 모두 성공해야 한다. regression job의 **CI용 image media/OCR/process acceptance도 병합 전 CI 항목**이며 이번에는 NOT_RUN이다. 원격 required check 전체 성공이나 병합 승인을 로컬 source 검사 통과로 대신하지 않는다. commit/push/PR 실행 허용 후 실제 SHA의 CI에서 확인해야 한다.

배포 전에는 별도로 **운영에 사용할 B/C exact SHA·image digest·config**의 startup/health/media/OCR/code rollback, controller tuple/schema authority·승인 목록, write-stop 시점의 일관된 DB/media backup과 빈 target restore rehearsal를 결속해야 한다. CI용 synthetic image acceptance와 운영 image/복구 검증은 서로 대신하지 않는다. B/C의 release image build/publish와 운영 backup/restore는 NOT_RUN이다.

고정 시험 source ZIP의 제품 파일 SHA256은 `9346ac66e2a4391ed5bc0df526c6df7c920986fc4652b8bf411112df6586314f`다. `native-workspace-identity.json`은 C 기준 공개 tree+명시한 변경만 결속한다. O/C snapshot은 각 Git SHA와253/265개 source/migration 파일 hash를 검사한 뒤 독립 process에서 import했다. 이 hash는 release SHA, image digest 또는 운영 artifact 승인 증거가 아니다.

## 운영 배포물과 시험 하네스

`src/daesingo/recording/mysql_repository.py`만 제품 변경이다. `tests/recording/compatibility_revision_driver.py`는 합성 fixture와 시험 DB URL을 stdin으로 받는 테스트 도구다. `.codex-scratch/compatible-release-b/`의 Docker supervisor·고정 source snapshot·로그는 로컬 시험물이며 이미지 publish/SSM/서비스 전환 도구가 아니다.

Windows Docker Desktop pipe가 없었다. 첫 Ubuntu 조사 이후 Docker 이미지와 작업 자원이 바뀌어 초기 owner 자원의 cleanup은 입증하지 못했고, 원인을 확정하지 않는다. 첫 실행 실패와 상태 파일을 보존했다. 후속 실행은 새 owner·실제 daemon ID·정확한 runner/MySQL image ID에 결속하고 identity 변화 시 거부한다. internal network, 새 DB volume, runner/DB 각각 메모리·CPU·PID 제한을 사용한다. 기존 container/volume은 사용하지 않았고 원본·보호 증거는 시험 입력으로 지정하지 않았다. repo는 read-only, 쓰기는 이 작업 전용 evidence 경로/임시 영역으로 제한했다.

최종 owner `compat-b-3e001f3b46`의 시험 container·새 DB volume·internal network는 daemon ID와 owner label 대조 후 회수하여 **PASS_EXACT_OWNED_CLEANUP**을 확인했다(`cleanup.json`). 최초 정리 시 이미 종료된 container의 inspect `[]`를 처리하지 못한 하네스 오류는 보완 후 재실행했다. 기존 volume을 삭제하지 않았다. 초기 별도 daemon 상태의 cleanup 미입증과 최종 owner의 확인된 정리를 구분한다. 로그·revision snapshot·합성 시험 artifact와 기존 보호 증거는 남겼다.

## 600초와 150초 복귀

B는 현재 `InitialSearchBudget.max_latency_sec=600`, Fine70초, 준비 여유와 60분 Case ceiling, late `STOPPED_WAITING`을 유지한다. 이 B의 기능은 현재 E2E 예산을 일반 운영값으로 확정하지 않는다.

당시 계획의 D는 E2E 종료 후 새 reader와 데이터 호환을 유지하며 기본 예산을 150초로 복귀하는 별도 PR/source/image였다. 이미 저장된600초 scope는 기본값 변경으로 수정되지 않는다. D 검증에는 실행/재전달·기존 scope 정산과 새 발주 150초 확인이 포함됐으며, O로의 code rollback은 복귀 방법에서 제외됐다.

## NOT_RUN / 승인 미완료

AWS·운영 DB 조회/변경·서비스 중단·publish·배포·실제 code rollback·운영 backup/restore·사용자 원본15개·provider·Upload→Package READY→다운로드·600→150 복귀 배포는 NOT_RUN이다. 실제 운영 tuple/권한·B release SHA/image/config·양방향 전 handler 호환·최신 크기의 복원 rehearsal는 확인 필요다. 테스트 통과를 배포 승인으로 취급하지 않는다.

canonical 전체 MySQL pytest 단계는 실행 후 **FAILED(1276 passed/1 failed)**이며 후속 strict·실제 보고서 변조 단계는 **NOT_RUN**이다. 실제 release image의 startup/health/rollback rehearsal도 **NOT_RUN**이다. 부분 MySQL JSON/XML과 checker 자체의 mutation 통과를 canonical strict gate 증거로 제출하지 않는다. 현재 gate 차단은 테스트 실패와 로컬 환경 장애이며 AUTH_REQUIRED라고 추정하지 않는다. 금지된 운영 작업과 실제 원본 검증을 실행하지 않았으므로 해당 상태는 NOT_RUN이다.
