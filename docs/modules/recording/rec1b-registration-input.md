<a id="rec-1b-registration-input"></a>

# REC-1(b) 등록 입력

상태: IN_PROGRESS · Refs #302 (REC-1(b)) · PR pending · merge SHA pending.
이 문서는 구현 메모이며 새 Contract나 Owner Decision이 아니다.

<a id="sources-and-implementation-boundary"></a>

## 근거와 구현 경계

Runtime Implementation Plan REC-1/§12, Ops §4-2, RD-17/#246(최종 결정 댓글 포함),
HTTP Contract §5.2/§9.1, Baseline B-C3, 현재 #302 본문/댓글, REC-1(a) 영속화 메모,
Implementation Log, Recording 모델/서비스/저장소/마이그레이션/테스트 및 PR #379로
병합된 구현과 직접 대조했다. 검사 당시 #302에는 댓글이 없었다.

PR #379는 develop에 `978fed34d8bedf2cf5cf6d2c7d04e557cd670004`로 병합됐다.
해당 PR HEAD는 `dd2ec4957748af40c6dc9708158c5c03082aea26`이었다.
원격 [boundary-check 실행](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39212568969)과
[python-tests 실행](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/39212568964)은
모두 성공적으로 완료됐으며, 후자의 전체 pytest 및 strict MySQL gate 단계도 성공했다.
이 결과는 REC-1(a)에 속하며 이 미커밋 diff의 결과가 아니다.
현재 원격 develop 커밋은 GitHub connector로 검증했고, 수정 전 로컬 HEAD와
origin/develop은 모두 merge SHA와 일치했으며 index는 비어 있고 worktree는
깨끗했다. branch/worktree는 생성하지 않았다.

<a id="filename-and-locator"></a>

## 파일 이름과 locator

`register_local_source(path, *, original_filename=None, case_id=None)`는 계속
기존 SourceAsset/MediaStream contract만 반환한다. 선택적 파일 이름은 비공개
LocalSource 등록 메타데이터이며 repr에서 제외한다. 기존 local_source JSON payload에
영속화하며 새 저장소/서비스에서 복원한다. 시간 관측에는 정규 저장 basename 대신
해당 원문을 사용한다. 정규 모델에는 filename 필드를 추가하지 않는다.

HTTP §5.2는 사용자 파일 이름을 전달하도록 요구하고 이를 저장 경로로 쓰는 것을
금지한다. 현재 SoT는 공백 제거, Unicode 정규화, basename 추출, 확장자 허용 목록,
파일 이름 길이 제한을 정의하지 않는다. 여기서도 도입하지 않는다. 문자열은 공백,
결합 Unicode, 구분자, 빈 문자열, NUL을 포함해 정확히 보존한다. 이는 비활성
메타데이터이며 검증된 파일시스템 이름이 아니다. 문자열이 아닌 값과 UTF-8 인코딩이
불가능한 Python surrogate 문자열은 의존성 접근 전에 고정 ValueError로 실패하며
입력 문구를 그대로 출력하지 않는다. 잘못된 파일 이름에 대한 HTTP status/code는
추가하지 않는다. 향후 거부/정규화 정책은 구현 전에 그 권한 근거를 확인해야 한다.

정규 locator는 storage_root 아래의 검증된 상대 경로를 유지한다. 원본 파일 이름은
파일을 선택하거나 이름 변경, 열기, 게시하지 않는다. 기존 절대 경로/경로 이탈/
다른 루트/심볼릭 링크/junction 검사는 유지한다. original_filename이 없는 기존 JSON은
저장 행을 다시 쓰지 않고 None으로 복원한다. 경로만 받는 기존 등록은 기존 basename
관측 동작을 유지한다. 이전 데이터에 원래 업로드 파일 이름을 지어내지 않는다.

<a id="failure-taxonomy"></a>

## 실패 분류 체계

HTTP §5.2는 이미 UNSUPPORTED_MEDIA를 422 http.source_rejected로,
TEMPORARY_FAILURE를 503 http.dependency_unavailable로 매핑한다. 여기서는 route를
구현하지 않는다. 예기치 않은 오류와 COMMIT 불확실성은 기존 경계를 유지한다.

Ffprobe는 이제 `-show_error`로 구조화된 오류 코드를 요청한다. 입력이 안정적이고
AVERROR_INVALIDDATA가 발생하거나, 유효한 성공 메타데이터에 지원되는 비디오 스트림이
없으면 UNSUPPORTED_MEDIA다. 숫자 태그는 FFmpeg의
[libavutil 오류 정의](https://www.ffmpeg.org/doxygen/trunk/group__lavu__error.html)를 따른다.
도구 누락, 접근/읽기 실패, timeout, 입력 변경, 알 수 없는 nonzero 결과, 잘못된 JSON,
잘못된 도구 메타데이터는 TEMPORARY_FAILURE를 유지한다. Stderr, 예외 문구,
파일 확장자, part Content-Type으로 입력을 분류하지 않는다. 결정적 거부를 신뢰하기
전에 읽기/해시 안정성을 확인한다. 메시지에는 subprocess stdout/stderr/argv나
로컬 경로를 포함하지 않는다.

<a id="transaction-linkage-and-ownership"></a>

## 트랜잭션, 연결 관계와 소유권

등록은 제공된 Connection에 참여한다. 선택적 case 연결은 기존 Recording 소유
case_asset 행 표현을 재사용한다. SourceAsset, 스트림, 인덱스, locator, 파일 이름,
해당 연결을 하나의 InnoDB statement로 쓰므로 호출자가 statement 오류를 잡은 뒤
커밋해도 부분 등록을 남길 수 없다. 저장소/서비스는 커밋, 롤백, 재시도를 수행하지
않으며 Connection을 소유하지 않는다. 같은 파일을 다시 등록해도 새 논리 asset을
받으며 중복 제거 또는 업로드 멱등성을 약속하지 않는다. 동시 등록은 서로 구별된다.
COMMIT ACK 손실은 불명확하다. 호출자 오류와 영속 등록이 공존할 수 있다.

새 Case 인터페이스/callback, 역방향 의존성, Case 스키마나 의무는 필요 없다.
Case의 기존 `record_source_registered(case_id, source_asset, *,
media_streams, store)`가 INTAKE 수락과 manifest 개수의 권한을 계속 가진다.
테스트는 Case를 먼저 잠근 뒤 같은 Connection에서 기존 함수를 조합한다. Case 거부는
등록과 Recording 연결을 롤백한다. Recording 단독으로 Case 존재/단계를 검증하거나
Case 개수를 변경하지 않는다. 실제 HTTP 조합은 RT-11(a)에 남는다. Case 또는 Runtime
제품 코드 변경은 없다. 미결 Owner 결정 중 이 Recording 전용 범위를 막는 것은 없다.
최종 공개 소유권 조회와 Case 의미 변경에는 여전히 기존 Owner 경계가 필요하다.

<a id="schema-and-verification"></a>

## 스키마와 검증

스키마 변경이나 revision은 필요 없다. 비공개 JSON payload가 이미 메타데이터 추가를
지원한다. recording_0001과 모든 동결된 마이그레이션은 그대로 유지한다. 기존 신규/
이전 upgrade, 재실행, 실패 안전성, 거부되는 downgrade, 이전 행 보존 테스트는 계속
필수다. FrameRef 바이트는 MySQL에 유지하며 DerivedAsset 메타데이터/ref 내구성과
원본 저장 의미는 변경하지 않는다.

새 registration_input과 registration_taxonomy family는 독립 인수 목록과 strict
checker 목록을 모두 확장한다. 기존 필수 증거, checker 함수, JSON/JUnit 검사,
skip/xfail 거부, workflow 30분 timeout과 중첩 MySQL 900초 timeout은 보존한다.
매개변수, 메타데이터, family 누락 변이에 새 의무도 자동 포함한다.

실행 증거는 무시되는 `.codex-scratch/rec1b-20261019/`에 격리한다.
기존 scratch/RAW/archive/reports와 무관한 untracked 파일은 전달 범위 밖이다.
최종 결과와 독립 검토는 Runtime Implementation Log의 후속 항목으로 기록하며
과거 기록은 보존한다.

제외 범위: 최종 sources HTTP route, 최종 ref-to-case 소유권 API, DerivedAsset
바이트/Content-Type, 공개 FrameRef 이미지 형식, retention/purge/object storage,
고아 데이터 정리, RT-10 Worker 및 RT-11 HTTP 조합. 이 작업에서는 staging, commit,
push, PR 생성을 수행하지 않는다.

<a id="final-verification-2026-10-19"></a>

## 최종 검증 (2026-10-19)

아래는 범위가 겹치는 서로 다른 실행이다. 고유 테스트 커버리지로 횟수를 합산하면
안 된다. 원시 실패와 미완료 시도는 그대로 보존한다.

| 실행 | 관측 결과 |
| --- | --- |
| 최초 unit RED | 21 FAIL / 1 PASS; 잘못된 기능 동작이며 최초 tmp 접근 오류와 별개 |
| 최초 실제 MySQL RED | 두 선택 실행에서 10 FAIL |
| 추가 입력 검증 RED | surrogate 1 FAIL; case-id 입력 4 FAIL |
| 새 검토 재현 | 비디오 없는 잘못된 duration: 2 FAIL, 영구 회귀 2 FAIL / 9 PASS, 이후 GREEN |
| 최종 Recording 모음 | 616 PASS / 명시적 외부 미디어/배치 opt-in 15 SKIP; 통과한 MySQL Recording 테스트 43개 포함 |
| 전체 필수 실제 MySQL 목록 | 743 PASS / 통과 phase 2,229개 / skip 0 / xfail 0; JUnit 884.009초 |
| 원본 필수 통합 함수 | 1,092.42초에 1 PASS; wrapper 1,096.5초, source drift 0 |
| strict JSON/JUnit CLI | PASS; 새 검토자가 독립 반복 |
| 원본 매개변수 변이 | Recording layer 변형 559개를 포함해 4,814개 거부 |
| Recording 메타데이터/family 누락 | 메타데이터 172개와 전체 family 누락 11개 거부 |
| Gate 단위 회귀 | 5,261 PASS |
| API process-safety 최초 최종 선택 실행 | 44 PASS / 1 FAIL, GO trigger 전 setup_import_watchdog_5s |
| 같은 실패 API node 격리 실행 | 원래 watchdog으로 1 PASS |
| 같은 전체 API process-safety 파일, 유휴 상태 재검사 | 45 PASS / 기존 Starlette deprecation warning 하나 |
| 최종 경계 / Contract fixture / 정적 검사 | 경계 0; 구조 62 / JSON 26 / 의미 104 PASS; diff-check PASS |

독립 검토자는 P2 분류 순서 결함 하나를 발견했다. 잘못된 format duration이 비디오
없음 거부에 가려질 수 있었다. 영구 RED 사례 두 개를 먼저 작성한 뒤 duration 검증을
그 거부 앞에 옮겼다. 이후 검토자는 원래 재현을 반복해 2 PASS를 얻었다. 이 수리를
위해 timeout이나 failure-kind 정책을 완화하지 않았다. 이후 모든 필수/집중 실행의
소스 해시는 최종 제품/테스트 코드와 일치한다.

첫 전체 pytest 시도는 76%에서 exit 124와 F 진행 표식 일곱 개로 종료됐으며 최종
JSON/JUnit이나 완료된 내부 증거가 없었다. 설정된 제한은 1,800초였지만 중단을
가로질러 관측한 wrapper 경과 시간은 5,715.203초였고 원인은 확인되지 않았다.
소스 차이는 probe.py와 영구 검토 테스트뿐이었다. 수집 순서 재구성으로 실패 후보
일곱 개를 얻었으나 확정적인 traceback은 아니다. 이후 그 후보 범위를 완전한 원본 필수
테스트, gate 단위 모음, API process-safety 재실행으로 실행했다. 이는 해당 부분 전체
시도를 PASS로 바꾸거나 원래 실패의 정확한 원인을 확정하지 않는다.

새 독립 검토자 `/root/rec1b_independent_review`는 이 한정된 Recording/입력/목록
변경에 전체 pytest 중복 재실행이 불필요하다고 판단했다. 최종 완전한 Recording
테스트, 실제 모듈 간 MySQL/마이그레이션, strict 보고서와 정확한 변이 커버리지,
gate 단위 검사, 제한 시간을 바꾸지 않은 API 검사가 변경된 동작을 다룬다.
수정하지 않은 모듈의 전체 unit 모음은 재실행하지 않았다. **완료된 최종 전체 pytest
PASS는 없다.** 최초 API watchdog 실패도 이후 통과와 별개로 실패 시도로 남는다.
장비/부하 설명은 추론이며 확인된 진단이 아니다.

원본 strict checker 함수, 기존 필수 목록, 동결된 마이그레이션, workflow 30분과
중첩 MySQL 900초 제한은 변경하지 않았다. JUnit 884.009s는 중첩 제한 아래 여유가
작으며 인터프리터 시작도 subprocess 예산을 사용하므로 JUnit 차감은 정확한 실시간
여유가 아니다. 이는 성능 위험이지 timeout을 늘려도 된다는 허가가 아니다.
이전 REC-1(a) 증거 manifest의 파일 150개와 원본 Implementation Log 전체 바이트
prefix를 다시 해싱하고 보존했다.

commit/push/PR을 생성하지 않았으므로 현재 diff의 원격 CI는 pending이다.
REC-1(a)의 원격 PASS가 이를 대체하지 않는다. 전체 모음 GREEN이나 병합 준비
완료를 주장하지 않는다. 남은 Recording skip 15개는 사용자 제공 외부 미디어/배치가
필요하며 MySQL skip이 아니다. 구현한 Recording 전용 경계 안에서는 새 Owner 판단이
필요 없다. 향후 정규화 정책, 최종 소유권/미디어 API, 실제 RT-11 조합은 기존 권한과
범위를 유지한다.

<a id="delivery-files"></a>

## 전달 파일

| 목적 | 파일 |
| --- | --- |
| 등록과 관측 | `src/daesingo/recording/probe.py`, `service.py`, `time_sources.py` |
| 호출자 Connection 영속화와 메모리 내 동등성 | `src/daesingo/recording/repository.py`, `mysql_repository.py` |
| 테스트 | `tests/recording/test_registration_input.py`, `test_local_source_registration.py`, `test_recording_repository_mysql.py` |
| 독립 목록과 checker 목록 | `tests/recording_acceptance.py`, `scripts/check_mysql_test_report.py` |
| 문서와 추가 전용 이력 | `src/daesingo/recording/README.md`, `docs/modules/recording/local-source-registration.md`, `docs/modules/recording/rec1b-registration-input.md`, `docs/runtime/runtime-implementation-log.md` |

이 작업 증거를 포함한 모든 `.codex-scratch/**` helper, 원시 보고서, 미디어,
pytest 임시 자원은 향후 PR에서 제외한다. 기존 RAW, archive, 무관한 untracked
파일은 변경하거나 삭제하지 않는다. 최종 자원 감사, manifest, 검토자 판정은
Implementation Log에 추가한다.

자원 검사에서 system 스키마와 작업 소유 base 스키마만, 기본 MySQL 계정만 확인했고
테스트 client나 transaction은 남아 있지 않았다. 작업 소유 서버를 helper로 중지하고
datadir를 제거했다. 중단된 서버의 알려진 datadir는 이미 없었으며 원래 로그는 읽을
수 없어 보존했다고 주장하지 않는다. 재개한 서버 로그 두 개는 중지 전에 복사했다.
최종 Windows/WSL 검사에서 작업 소유 Python/MySQL 프로세스나 기록된 서버 포트
두 개의 listener는 없었다. 작업 소유 junction 끝점 네 개는 일반 파일을 삭제하지 않고
제거했다. 이전 REC-1(a) 증거 해시 150개는 변경되지 않았다.
