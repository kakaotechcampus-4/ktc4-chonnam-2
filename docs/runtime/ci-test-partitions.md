# CI test partitions

## 조사와 설계 (2026-10-28)

시작: `codex/ci-split-mysql-gate`, clean index/worktree/untracked,
`git fetch origin` 후 HEAD = origin/develop = `daf6d14a6118a89e0ec54daa4280f8c7970e9a0a`.
CLAUDE.md → docs/README.md → ops-spec.md §19–20을 적용한다.
ops-spec의 “현재 실제 CI”는 2026-10-02 snapshot이며 지금의 MySQL workflow는 코드로 확인했다.

[PR #352 멘토 리뷰](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/352#pullrequestreview-5520973090)는
로컬 단위/통합, PR E2E/인프라 검증과 협업 지연 시 분리를 권고한다.
분리 기준은 실패 영향·변경 관련성·실행시간이다. 개수 기준 sharding이나 timeout 확대는 하지 않는다.

기존: `python-tests / test` (30분), MySQL 8.4 service → locked setup → ffmpeg 검사 →
media smoke → 전체 pytest → outer JSON/JUnit strict. 전체 pytest의 migration gate는
별도 MySQL child(900초, 출력 capture) → child strict/catalog → 실제 report mutation을 수행한다.
boundary-check의 `check`는 별도 workflow에서 boundary/Contract fixture를 검사한다.
2026-10-28 직접 GitHub API 조회에서 develop protection은 HTTP 404 “Branch not protected”,
적용 branch rules는 `[]`였다. 설정은 변경하지 않는다. 기존 `test` 이름도 유지한다.

직접 Windows Python 3.12.14 collection: 전체 12,774, MySQL 1,045,
child 1,027, outer∩child 1,027, child−outer 0.
child 이외 MySQL 18개는 wrapper 1 + Case/Recording/Worker 회귀 17개다.
전체 수는 환경 의존적이다. 현재 locked 환경에서도 선택 extra 밖의 `typer`가 없어
Search collection module 4개가 기존 importorskip되었다. 원격 수와 동일하다고 주장하지 않는다.
wrapper의 로컬 수집 위치는 1,181/12,774(9.25%)이며 원격 active node는 기록되지 않았다.
따라서 8% 정체의 원인을 특정 test라고 확정하지 않는다.

outer report는 모든 MySQL marked node(검증 wrapper와 child 밖 회귀 포함)의
setup/call/teardown 및 JUnit 실행을 증명한다. child report는 제한된 경로의 1,027개에
대한 동일 증거와 실제 formatter catalog를 제공한다. 기존 실제-report mutation은
child JSON/JUnit을 소비하며, 단위 gate tests는 합성 report로 독립 rejection을 검증한다.
새 canonical 집합은 전체 MySQL marker 집합에서 report 소비 wrapper만 뺀 집합이다.
기존 production strict checker의 inventory·판정 범위는 변경하지 않는다.

## 실행 구조

선택한 최소 설계: 두 required 실행 job + 호환 aggregator. 경로 필터는 쓰지 않는다.

| 실행 partition | 포함 | job |
| --- | --- | --- |
| regression | MySQL marker 없는 모든 node에서 전용 smoke 제외 | regression |
| media | 기존 실제 Recording synthetic smoke 1개 | regression |
| mysql | 전체 MySQL marked node에서 report 검증 wrapper 제외 | mysql |
| gate | 기존 실제 report strict/catalog/parameter/metadata/family mutation wrapper | mysql |

`regression`과 `mysql`은 병렬이다. `test`는 `always()`로 실행하고 모든 dependency의
정확한 `success`만 수락한다. failure/cancelled/skipped/missing은 최종 성공이 될 수 없다.
boundary workflow의 독립 check는 유지한다.
Docker/deploy configuration·smoke runner 단위 tests는 regression에 속한다.
실제 Docker Compose 배포는 기존 일반 PR workflow에도 없었으며 추가하지 않는다.
MySQL marked process E2E는 canonical mysql에 포함한다. live provider/capacity E2E는
ops-spec §20에 따라 일반 PR gate 밖이다.

대안: nested wrapper를 별도 job으로 그대로 옮기면 inventory 중복이 남는다.
합성 report mutation만 남기면 실제 실행 증거 rejection을 잃는다.
따라서 wrapper의 assertion은 유지하고 child 생성만 같은 job의 새 report 소비로 바꾼다.

각 job은 독립 runner/temp/MySQL service를 사용한다. report 전달용 upload/download는 없다.
실행마다 새 evidence 디렉터리와 token을 만들고 실제 checkout SHA/run/attempt,
JSON/JUnit/catalog/collection digest를 묶는다. 검증 wrapper는 현재 실행 context와
정확한 canonical selection을 검사한다. stale 또는 변경된 입력은 실패한다.
canonical 실제 pytest는 900초, workflow job은 30분을 유지하고 stdout을 바로 출력한다.
전체/실제 partition collection의 Counter 합집합과 중복·누락을 자동 비교한다.

## 변경하지 않는 정책

MySQL skip 0/xfail 0, required inventory, JSON/JUnit 일치, setup/call/teardown,
missing parameter/metadata/family rejection, boundary/Contract fixture, 실제 media smoke,
기존 assertion, production checker 판정, 30분/900초를 유지한다. 제품 코드는 수정하지 않는다.

## Collection·중복 제거 증거

실제 pytest collection 5회(full + 4 execution partition)를 비교하는 자동 gate를
regression job에 둔다. `mysql_harness`가 붙이는 기존 Case marker까지 실제 적용한
후 node Counter를 비교한다. 임의 경로 추론이나 테스트 개수만으로 완전성을 판정하지 않는다.

| 집합 | 변경 전 직접 수집 | 변경 후 직접 수집 |
| --- | ---: | ---: |
| 전체 unique | 12,774 | 12,810 |
| regression (전용 media 제외) | 11,728 | 11,764 |
| canonical MySQL | 1,044 | 1,044 |
| media smoke | 1 | 1 |
| 실제 report 검증 wrapper | 1 | 1 |
| 전체와 partition 합집합의 차이 | — | 누락 0 / 초과 0 / 중복 0 |

36개 추가 node는 새 orchestration 테스트뿐이다. 변경 전 전체 node와 새 전체의 차이는
누락 0이고, former full MySQL − wrapper = 새 canonical 1,044개와 정확히 일치한다.
새 코드의 작은 실제 pytest fixture는 legacy Case MySQL 자동 marker, sqlite/mysql parameter,
process marker, media, wrapper, unit을 독립 기대값과 비교한다.

기존 구조의 실행 multiset은 전체 12,774 + child 1,027 + 전용 smoke 1 = 13,802였다.
동일한 기존 테스트 범위에서 새 구조의 실행 수는 12,774다. 즉 의도적으로 제거한 반복은
MySQL 1,027 + smoke 1 = **1,028회**다. 신규 36개를 넣은 현재 실행 수는 12,810이며
이 증가를 성능 개선으로 계산하지 않는다. gate wrapper의 실제-report rejection은 그대로 실행한다.

## 기존 원격 CI 증거 (이번 직접 실행과 별개)

GitHub job/step API는 초 단위다. 0초로 표시된 strict는 1초 미만의 관측 구간이지
CPU 시간이 0이라는 뜻이 아니다. 취소 job의 최종 wall time에는 취소/정리도 들어간다.

| run | job wall | setup→smoke 직전 | media tool 설치 | smoke step | outer pytest step | strict |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [40500553791 성공](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40500553791) | 1,473초 | 59초 | 20초 | 4초 | 1,405초 | 성공, API 0초 |
| [40633989353 실패](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40633989353) | 1,587초 | 55초 | 19초 | 3초 | 1,526초 | SKIPPED |
| [40636386550 develop 취소](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40636386550) | 1,820초 | 61초 | 23초 | 4초 | 1,752초 | SKIPPED |
| [40637818339 PR #427 취소](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/actions/runs/40637818339) | 1,820초 | 85초 | 38초 | 4초 | 1,728초 | SKIPPED |

setup 열에는 media tool 설치도 포함되므로 각 열을 합산하지 않는다.
성공 로그의 pytest 자체 summary는 12,699 passed/33 skipped/1,398.04초, outer strict는
1,045 tests/skip0/xfail0다. 성공과 최신 취소의 nested child·mutation 개별 시간은 로그에서
분리할 수 없다. 최신 취소는 05:30:49→05:44:49 UTC의 8% 출력 간격(839.927초)이 관측되지만,
active node와 실행 내역은 기록되지 않았다. 최종 pytest summary도 없다.
이전 실패 run에는 child 4 failed/1,084 passed/585.66초가 기록되며, Runtime revision의
4 assertion 실패가 outer에서도 재발했다. 최신 취소에서의 재발은 확인할 수 없다.
PR #427의 head f385ecf…는 이번 base daf6d14a…와 별도 revision이므로 동일 collection으로 취급하지 않는다.

## 실행·검증 증거 구분

이번 직접 실행, 기존 원격 CI, 보존 report 재검사, 새 실제 MySQL, 추정 모델은 별도 증거다.
이전 보존 child report(2026-10-27, 1,027 node)는 현재 production strict로 재검사 PASS다.
이는 새 DB 실행이 아니다.

이번 직접 실행 환경은 Windows Python 3.12.14 + `uv sync --locked --extra test --extra eval-gemini`,
전용 WSL loopback MySQL 8.4.7, 기존 Windows ffmpeg/ffprobe다. CI의 Ubuntu 24.04 실행을 대체하지 않는다.
새 canonical 실제 pytest는 **1,044 passed**, 자체 summary 687.53초, subprocess wall 693.47초다.
기존 비-MySQL Search 모듈 4개의 `typer` collection skip은 summary에 별도로 나타나며
MySQL skip/xfail로 숨기지 않는다. MySQL JSON은 1,044 unique selection·3,132 phase,
JUnit 1,044개 일치·MySQL skip/xfail0이며 실제 strict CLI는 0.20초에 PASS했다.
catalog는 실제 formatter 경로에서 32 events·위반0을 기록했다.

새 orchestration TDD는 기능 부재 RED 36 failed → GREEN 36 passed(5.26초)다.
처음 miniature fixture가 상위 pytest root를 상속한 실패도 별도 보존한 뒤 독립 config로 고쳤다.
gate 단위·mutation helper·schema policy·새 orchestration·Deploy focused는
**8,573 passed, 161.10초**다. 앞 36개가 포함되므로 두 결과를 합산하지 않는다.
실제 media smoke는 **1 passed, 2.86초**이며 JUnit skip/failure/error0다.
boundary 위반0, Contract 구조62/JSON26/의미104, actionlint exit0, diff check PASS다.
최초 Windows boundary 출력은 cp949 인코딩 오류로 종료됐고 `-X utf8`로 다시 실행해 PASS했다.
이는 정책 위반 검출이 아니며 실패 기록을 성공으로 덮어쓰지 않는다.
추가 fixture-closure 수집 검사에서 MySQL fixture를 요청하는 비-MySQL node는 0개였다.

같은 새 실제 report에서 기존 wrapper는 **1 passed, 94.05초**이고 orchestration wall은
mutation 95.83초, 전체 789.81초다. parameter mutation **8,415건**, metadata/family omission
**1,501건** 모두 거부했다. runner는 이후 원본 JSON/JUnit/catalog/collection의 digest를 다시 확인했다.
실제 report 복사본의 strict CLI는 정상 exit0, phase 누락 exit1, JUnit testcase 누락 exit1이다.

동일 환경·동일한 기존 공통 node 2개(`test_recycle_replaces_connection_and_reapplies_session[api/worker]`)
비용 재현은 2회 실행(outer+child 모델) **4 node 실행/8.516초**, 단일 partition 모델
**2 node 실행/4.515초**다. 해당 test source는 base와 같다. 차이 4.001초는 직접 계산값이며,
이 작은 subset 결과를 전체 suite 시간으로 외삽하지 않는다. 최초 sandbox DB 연결 실패도
별도 보존한 뒤 실제 DB 접근 권한으로 재현했다. 전체 old outer를 새로 반복 실행하지 않았다.

전체 regression partition 실행·기존 전체 outer 재실행·새 Ubuntu 원격 CI·실제 Docker Compose 배포·
live provider/capacity E2E는 이번에 수행하지 않았다. Linux helper는 Windows acceptance 경로에서
실행됐지만 새 전체 Ubuntu workflow 완료를 증명하지 않는다.

추정 시간 모델(실측 전체 시간 아님): 기존 순차 경로는
`setup + smoke + regression + outer MySQL + child MySQL 중복 + mutation + strict`다.
새 구조는 대기열·runner contention이 없다는 가정에서
`max(regression setup + collection audit + smoke + regression,
MySQL setup + canonical MySQL + strict + mutation) + aggregator`다.
설치 중복과 aggregator 비용이 추가되므로 node 감소율을 wall 감소율로 환산하지 않는다.
원격의 같은 revision·같은 runner 조건에서 최종 wall 개선을 확인해야 한다.

## 로컬 실행과 rollback

ffmpeg/ffprobe와 locked test + eval-gemini 의존성을 준비하고, 비-MySQL 회귀는
`uv run --no-sync python -m tests.ci_orchestration regression <JUnit 출력 경로>`, collection은
`uv run --no-sync python -m tests.ci_orchestration collect <증거 디렉터리>`로 실행한다.
실제 MySQL gate는 폐기 가능한 MySQL 8.4 URL을 환경변수로 설정하고
`uv run --no-sync python -m tests.ci_orchestration mysql <증거 디렉터리>`를 사용한다.
기존 wrapper의 단독/bare pytest는 입력 evidence가 없으면 실패한다. skip으로 대체하지 않는다.

rollback은 workflow·test orchestration·wrapper를 base `daf6d14a…`의 조합으로 함께 되돌린다.
한쪽만 되돌리면 신구 report 전달 방식이 맞지 않는다. DB/제품 변경이 없어 data rollback은 없다.
다만 기존 구조의 중복·timeout·후속 gate SKIP도 복귀하므로 rollback을 검증 완료로 취급하지 않는다.

## 새 원격 CI에서 필요한 확인

- PR merge revision에서 regression/mysql 모두 30분 이내 성공하고 최종 test도 성공해야 한다.
- MySQL 실제 inventory 1,044 node(추후 변경 시 해당 revision의 canonical 수), node당 1회, 900초 이내.
- strict·catalog·전체 실제-report mutation 완료, skip/xfail0, JSON/JUnit/collection 일치.
- 실제 media smoke와 collection Counter 합계, 모든 기존 node 보존.
- failure/cancel/skip의 최종 전파, Linux helper/container/readonly mount/process E2E, 병렬 격리.
- 각 job setup/collection/pytest/mutation/strict 시간을 관측해 같은 revision에서 wall 개선 평가.
- develop 보호는 실제 미설정이다. workflow의 필수 의존성과 저장소 merge 보호를 혼동하지 않는다.

RAW/JSON/JUnit/profile/runner/DB/credential 등 진단물은 모두 `.codex-scratch/**`에 두고 PR에서 제외한다.
staging·commit·push·PR 생성은 하지 않는다.

## 자원 정리와 제한

전용 MySQL 종료 전 기본 schema/account와 전용 base만 존재했고 non-audit client0,
transaction0, lock0을 확인했다. 정상 shutdown·소유 datadir 제거·Linux connect refusal(111),
Linux mysqld/helper/listener 및 소유 Windows Python runner 잔여0을 확인했다.
새 실행에서 생성한 `/tmp/rt08a-stop-*` helper 디렉터리도 남지 않았다.

Windows TCP listener는 기존 공유 `wslrelay.exe`(PID1312)에 남았다. TCP connect는 성공하지만
handshake가 timeout되고 MySQL 접속은 실패한다. 따라서 Windows TCP 포트 폐쇄를 주장하지 않는다.
공유 relay/WSL 전체를 종료하는 조치는 다른 작업에 영향을 줄 수 있어 수행하지 않았다.
이전 보존 진단에서도 같은 relay 현상이 기록됐으며 새 CI 코드의 finding으로 분류하지 않는다.
원시 증거는 보존하고 공유 runtime·기존 진단물은 삭제하지 않는다.

## Fresh reviewer 최종 판정

구현 이력을 상속하지 않은 reviewer 1명이 읽기 전용으로 검토했고, 최종 증거·README·문서를
같은 reviewer가 재확인했다. 새 P1/P2/P3 finding은 없었다. reviewer는 실제 node 집합과
3,132 phase/JUnit, 원본 digest, mutation rejection 기록, append-only Log를 독립 대조했다.
리뷰어가 테스트·DB·제품 프로세스를 새로 실행한 결과는 아니다. 전체 regression·새 Ubuntu
원격 CI·원격 timeout 해소·최종 전체 wall 개선 및 merge 준비는 여전히 판단 보류다.
