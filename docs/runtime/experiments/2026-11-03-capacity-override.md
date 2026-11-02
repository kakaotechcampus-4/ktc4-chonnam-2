# P2-0c 격리 capacity override — 2026-11-03

최종 상태: **240/480초 준비 경계 PASS, 720초 Search40MiB guard 거부, 1200초 NOT_RUN**. 이번 경계는 Recording→commit→새 물리 연결→detached stream→Search 준비→SDK 송신 직전 차단이다. 배포·provider·Case·Package READY·최종20분 E2E 성공을 뜻하지 않는다.

## 시작과 사전 결정

브랜치 `codex/issue452-capacity-override`, HEAD `bc8799e1`. 최초 working tree/index는 비어 있었다. #538 `f1e8d82f`·#544 `52585e38`·#546 `fb404026`·#548 `bc8799e1` 병합 커밋 각각의 HEAD 포함을 `git merge-base --is-ancestor` exit0으로 확인했다. 사용자 AGENTS 지침, 실제 존재하는 CLAUDE 라우터·README·docs 규칙과 [P2 계획](elice-runtime-capacity-smoke-plan.md)의 P2-0c/G2/G4/G6/Decision Gate를 적용했다. 저장소 검색에서 별도 AGENTS.md는 발견되지 않았다.

[#548 결과](2026-11-03-metadata-publish-fix.md)의10/100초 성공과240초48MiB 거부를 보존한다. [기존 실제 실패](2026-11-03-real-media-recheck.md)·[합성 DB 대조](2026-11-03-chunked-capacity-recheck.md)·[청크 저장 메모](../../modules/recording/chunked-prepared-media.md)와 현재 materialization/multi_analysis/analysis_limits/process/repository/transactional/Search 코드를 대조했다. 과거 pending 문장을 현재 미구현의 근거로 사용하지 않는다.

| 설정 | baseline | 첫 experimental240초 |
| --- | --- | --- |
| 입력·placement | 보호 manifest input-01→02→03, 요청0–240초 | 동일. 경계0/117.933333/206.5/313.733333초 |
| Analysis | 480/veryfast/CRF23, profile `aws-e2e-v1` | 유지 |
| duration cap | 240000ms | 유지 |
| byte cap | 50,331,648B | 100,663,296B (96MiB) |
| Recording 도구 | 호출당120초 | 유지. 전체 timeline 처리 시간과 다름 |
| Search | source512/media40/request56MiB, 준비150초 | 유지 |
| DB | packet67,108,864B, 256KiB 청크 | 유지 |
| 전체 감독 | runner900초/host930초, 별도 정리60초 후보 | 유지 |

96MiB 선택 근거는 **실행 전 추정**이다. 기존100초38,363,450B를240/100배 하면92,072,280B이며, 선택값은 이 값보다8,591,016B 크다. 내용·VFR·인코더 차이 때문에 충분함은 아직 확인할 수 없다. 기존240초는 완성 크기를 측정한 적이 없다. 원 실패를 반복하기 위한 baseline 재실행은 하지 않는다.

runner1280+DB512+host reserve700+collector/daemon 예비512=3004MiB를 시작 기준으로 유지한다. 이는 cap 합계와 여유의 계산이며 실제 동시 peak 보장이 아니다. 96MiB 출력의 part+최종 bytes 약2N, concat/검사/동일 stream/Search copy 중첩을 보수적으로3N+40MiB=328MiB로 잡아 temp512MiB와 대조한다. product의 전체 part/final bytes·ffprobe JSON·driver buffers·base64/guard 할당은 남아 있다. kernel cgroup1100MiB soft/1280MiB hard로 실행 중 확인한다. DB512MiB hard/440MiB soft, DB data1GiB·C 시작6GiB/reserve4GiB/증가2GiB를 유지한다. WSL 여유를 Windows RAM에 더하지 않는다.

원본은 ro mount로만 사용하고 보호 manifest·등록 알고리즘의 순서를 재사용한다. metadata 합계1,584.173332초(약26분24초)는 기존 manifest 값이며 실제 연속 주행 길이를 입증하지 않는다. 명시 placement의 gap/overlap과 출력 frame coverage를 검증하더라도 독립적인 촬영 시각/실제 주행 seam 연속성은 별도 근거가 없으면 UNKNOWN이다.

## 구현·검증·실측

240-a는 **PASS_STOP_BEFORE_SEND**다. 최종79,323,248B/303청크, writer10→reader11, callback 후 checkout0, metadata 차이0·길이/SHA-256 일치, 서비스 종료 후 같은 detached stream의 strict decode와 Search source hash 일치를 확인했다. 정상 prepared rollback은 같은 writer 연결에서 통과했고 Aborted_clients0→0, 외부 socket/HTTP 시도0·provider0·SDK sentinel1회다. 영상/서비스 임시 파일·자식·cleanup 오류0이다. 전체6880frame, 최종clock1/30, firstPTS0/last7199+duration1tick=240초다. frame 수가7200이 아닌 것은 첫 VFR span의 관측이며 nominal FPS로 frame을 생성하지 않았다. strict increase/coverage discontinuity0을 확인했다.

시간은 각 run의 monotonic seconds이며 아래 중첩 phase는 합산하지 않는다. 준비 시간에는 DB publish가 포함되고 Search context 시간에는 request가 포함된다. 실제 API/Worker/Case E2E 시간과 다르다.

| 직접 관측 | 240-a |
| --- | ---: |
| 입력 등록 | 45.668초 |
| 개별 encode | 33.418 / 38.280 / 13.104초 |
| 개별 materialize | 91.414 / 69.062 / 37.982초 |
| part bytes / 누적 | 33,665,675 / 33,347,841 / 12,310,354B, 합79,323,870B |
| chain / concat mux | 241.397 / 0.314초 |
| Recording 준비 | 269.005초 PASS |
| metadata+청크 publish / commit | 10.749 / 1.028초 PASS |
| 정상 신규ref rollback | 12.182초 PASS, 동일 물리 연결 |
| fresh physical read / 추가 detached strict decode | 41.506 / 8.626초 PASS |
| 실제 SQL command / result packet 최대 | 524,467 / 262,155B |
| Search source copy / reencode | 0.144 / 18.575초 |
| Search media / base64 / guard JSON | 17,715,118 / 23,620,160 / 23,623,824B |
| base64 / guard dumps | 0.075 / 0.092초 |
| Search context 전체 | 20.058초 |

Search playback duration480초는 기존 Coarse2fps→playback1fps 준비 결과다. 원본 요청240초와 혼동하지 않는다. 실제 SDK body/HTTP wire 직렬화·provider 결과는 NOT_RUN이다. packet 수치는 PyMySQL payload/command 길이이며 TCP 전체 wire나 드라이버 allocation peak가 아니다.

| 자원 직접 관측 | 240-a |
| --- | ---: |
| runner RSS 표본 / ru_maxrss | 256,765,952B / 250,664KiB |
| ffmpeg / ffprobe RSS 표본 | 107,737,088 / 26,390,528B |
| runner cgroup 표본 / kernel peak | 525,484,032 / 525,484,032B |
| temp 표본(anonymous open 포함) | 176,361,614B |
| DB RSS / cgroup 표본 / data 표본 | 241,008KiB / 280,739,840 / 307,872,334B |
| runner CPU 누적 표본 | 18.75초 |
| 관측 child PID별 CPU 최댓값의 합 | ffmpeg177.96 / ffprobe97.65초. 표본에서 놓친 실행 말미 때문에 하한 |
| DB cgroup CPU 표본 window 차이 | 19,175,637µs |
| Windows RAM / C free 최소 표본 | 4,549,103,616 / 12,728,176,640B |

runner200ms 목표1774표본의 실제 최대 간격0.606초다. child 전체 연속 peak와 더 짧은 process 생존 누락은 UNKNOWN이다. DB kernel cgroup peak280,989,696B는 DB 초기화부터의 lifetime 값으로 runner run별 RSS와 다르다. 같은 host의 일반 앱·daemon·입력 cache를 통제/flush하지 않았으며 단회 실행 간 시간 차이를 cap의 인과 효과나 운영 처리량으로 단정하지 않는다.

### 480초 실행 전 결정

240초가 모든 대상 경계를 통과한 뒤 다음 길이를 결정했다. input-01→05의 명시 placement0–511.433333초에서 요청0–480초 전체를 선택한다. baseline을 덮어쓰지 않고 새 config/별도 schema를 사용한다. Analysis192MiB=201,326,592B/480000ms, runner1500초/host1530초·정리60초 후보를 명시한다. 도구당120초와 Search150초·512/40/56MiB, Case 정책, MySQL packet64MiB와 청크 크기는 유지한다.

근거는240-a 직접 관측: 준비269.005초, 전체 표본 window404.944초, Search media17,715,118B/reencode18.575초, runner cgroup kernel peak525,484,032B/temp 표본176,361,614B다. 길이 비례480초 출력158,646,496B·전체약810초·Search media35,430,236B/reencode약37.15초는 **추정**이다. 새로운 영상 내용 때문에 실제 Search40MiB guard 통과는 미확정이다.

현재 코드의 mixed-part 임시 파일은 encoded N+순차 remux 한 part, 이후 remux N+final N이며, Search는 detached N+copy N+media M이다. 이 경로의 후보 temp 계산2×192+40=424MiB는512MiB soft 아래88MiB 여유다. 앞 절의3N 보수 추정은 첫 실행 후 코드·직접 표본으로 위 중첩 경로를 구체화한 것이며 threshold를 낮춘 것이 아니다. 메모리는 part/final bytes·파일 cache를4N으로 잡고 tool/probe/runtime 예비240MiB를 더해1008MiB를 후보로 잡는다. 이 예비는240-a peak에서4×실제N을 뺀198.55MiB보다 크지만 아직 추정이며1100MiB soft stop을 유지한다. DB 기존data307,872,334B에 추가 저장·rollback의 보수적4N을 더하면1,113,178,702B로1GiB 경계를 넘을 수 있다. 따라서 다음 부하 전에240-a의 검증된 소유 schema를 삭제하고 data 여유를 다시 확인한다. 공유/보존 DB는 건드리지 않는다.

직전 Windows RAM/C, DB cgroup/data·OOM/restart·원본 stat와 work 잔여를 다시 대조한다. 부족하면480초는 NOT_RUN이다. 1200초를 자동 실행하지 않는다.

### 480초 결과와720초 실행 전 결정

480-a는 **PASS_STOP_BEFORE_SEND**다. 최종139,182,254B/531청크, Search media33,532,690B다. 준비442.509초, publish21.336초, commit1.561초, 정상rollback27.041초, fresh read86.245초, 추가 strict decode18.012초, Search source copy0.248초/reencode41.737초/context43.048초다. runner cgroup kernel659,509,248B/temp 표본311,897,198B, RSS391,319,552B다. 새 물리 연결/metadata·길이·hash/checkout0/원본 provenance/HTTP·socket0/SDK sentinel1회와 temp·자식·cleanup 오류0을 확인했다.

**정확한 길이 구분:** 요청은480초이나 반환 format duration은480.033333초, timeline_range.end_sec는480.0333326666667초다. 새 조회에서 두 float 값과 hex가 정확히 일치했다. 기존 [실제 선택 frame의 범위 규칙](../../modules/recording/local-analysis-source.md)에 따라 마지막 선택 frame 끝이 요청 end를 넘을 수 있다. duration cap은 [요청 범위 검사](../../modules/recording/analysis-source-limits.md)이며 완성 MP4 길이를480.000초로 고정하는 기능이 아니다. 이 차이를 임의로 자르거나 metadata를 요청값으로 덮어쓰지 않았다.

다음 후보는 input-01→08, 명시 placement0–765.133333초 중 요청0–720초다. 새 실험 config는 **208MiB=218,103,808B/720000ms, runner1800초/host1830초·정리60초**다. 기존 byte/duration 외의 Search/Case/packet/CPU/RAM/temp/도구 한도는 유지한다. 480-a 길이 비례 추정은 Recording208,773,381B·Search50,299,035B·전체약961초다. Search 추정값은40MiB cap을 넘지만 실제 내용에 따른 값은 실행 전 확정할 수 없다. 이 실험은 guard를 올리지 않고 그 최초 경계를 관측하는 목적이다. 208MiB가 충분하다고 확정하지 않는다.

실행 전 후보 자원 계산: temp2×208+40=456MiB(512MiB soft보다56MiB 작음), 메모리4×208+240=1072MiB(1100MiB soft보다28MiB 작음). 480-a peak의1.5배989,263,872B는 별도 길이 비례 추정이다. 새 frame 객체/JSON/cache 차이와 짧은 peak를 보장하지 않으므로 기존 sampler/host 중단을 유지한다. DB data 증가는240/480 각각 약2.27/2.29×출력 bytes였고, 다음은3N=654,311,424B로 보수적 추정한다. 이전 소유 schema 삭제 후 실제data와 더해1GiB 미만을 요구한다. C 누적 증가2GiB 중 **남은 예산**과도 DB3N+temp456MiB+추가 collector/log64MiB=1,199,570,944B를 대조한다. 값이 부족하면720초는 부하를 실행하지 않고 RESOURCE_BUDGET_STOP/NOT_RUN이다. 삭제가 C 물리 여유를 즉시 돌려준다고 가정하지 않는다.

Search guard가 거부해도 변환 직후 stat bytes를 기록하는 observer를 보완했다. 작은 실제 Search media cap 거부/파일 cleanup control은 RED1 FAIL 후 GREEN, 기존·새 harness+소유 감독기 controls 합계50 PASS다. 이전240/480 결과는 보완 전 artifact로 보존하고 성공 영상을 다시 encode하지 않는다. 다음 실행은 별도 source/runner hash로 식별한다.

720초 시작 조건은 Windows available4,755,275,776B/C free13,088,952,320B, DB data127,267,406B, work0이었다. C 증가 잔여2,167,836,672B를 직접 확인했다. Linux 최신44 controls도 PASS다. 실행 후 예산 검토에서 Search media guard가 **encode 후** 검사라는 점을 명시적으로 보완한다. 거부될 파일은40MiB를 초과할 수 있으므로720초의 Search 출력 후보는64MiB로 잡는다. temp2N+64=480MiB, C 추가 후보 DB3N+temp480MiB+log64MiB=1,224,736,768B로 정정하며 위 직접 잔여보다 작다. guard/중단값은 변경하지 않았다.64MiB는 새 Search cap이 아니라 자원 계산의 추정이다. 실제 temp512MiB soft와 host reserve를 계속 관측한다. 메모리4N+240MiB는 concat phase 후보이며, 서비스/connection 반환 후 Search의 파일2N+M과 한 시점으로 더하지 않는다.

raw·JSON/JUnit·개인 경로·원본 식별자는 ignored 보호 scratch에만 보존한다. 운영 설정·`.env.example`·과거 계획/실패 원문은 변경하지 않는다. 실험 config 복귀는 process 종료와 소유 자원 정리로 수행한다. 구버전 reader의 청크/envelope 비호환을 운영 rollback 승인으로 해석하지 않는다.

## 최종 비교와 최초 병목

세 run은 같은 manifest 순서의 **중첩된 prefix 시험**이다. 가장 긴 logical 요청은720초이며 각 길이를 합쳐20분 탐색으로 표현하지 않는다. 원본 파일 순서·VIDEO index0·명시 placement를 등록 사실과 대조했고 requested range의 resolve COMPLETE 및 출력 PTS/coverage를 검사했다. 실제 촬영 seam·순서·gap/overlap의 독립적 연속성은 UNKNOWN이다.

| 직접 관측 | 240-a | 480-a | 720-a |
| --- | ---: | ---: | ---: |
| 선택 원본 수 / 요청 | 3 / 0–240초 | 5 / 0–480초 | 8 / 0–720초 |
| Analysis byte/duration cap | 96MiB / 240000ms | 192MiB / 480000ms | 208MiB / 720000ms |
| 최종 bytes / 청크 수 | 79,323,248 / 303 | 139,182,254 / 531 | 215,411,995 / 822 |
| 실제 format duration | 240.0초 | 480.033333초 | 720.033333초 |
| 출력 frame 수 / clock | 6880 / 1/30 | 14081 / 1/30 | 21281 / 1/30 |
| 최종 PTS 첫/끝+duration(tick) | 0 / 7199+1 | 0 / 14400+1 | 0 / 21600+1 |
| PTS 단조·coverage gap·native strict decode | PASS / 0 / PASS | PASS / 0 / PASS | PASS / 0 / PASS |
| Recording 준비 | 269.005초 | 442.509초 | 706.412초 |
| chain / concat mux | 241.397 / 0.314초 | 412.880 / 0.458초 | 662.565 / 0.800초 |
| publish / commit | 10.749 / 1.028초 | 21.336 / 1.561초 | 27.143 / 1.925초 |
| 신규ref 정상rollback | 12.182초 | 27.041초 | 32.373초 |
| 새 물리 연결 read / 추가 strict decode | 41.506 / 8.626초 | 86.245 / 18.012초 | 107.560 / 27.080초 |
| writer → reader CONNECTION_ID | 10 → 11 | 14 → 15 | 18 → 19 |
| metadata·길이·SHA-256 / 반환 후 checkout | 일치 / 0 | 일치 / 0 | 일치 / 0 |
| SQL command / result packet 최대 | 524,467 / 262,155B | 524,467 / 262,155B | 524,467 / 262,155B |
| Search source copy | 0.144초 | 0.248초 | 0.451초 |
| Search reencode | 18.575초 | 41.737초 | 60.454초 |
| Search 출력 bytes | 17,715,118 | 33,532,690 | **52,577,684 → 거부** |
| base64 / guard JSON bytes | 23,620,160 / 23,623,824 | 44,710,256 / 44,713,920 | NOT_REACHED |
| SDK sentinel | 1회 STOP_BEFORE_SEND | 1회 STOP_BEFORE_SEND | 0회, NOT_REACHED |
| runner 외부socket/HTTP 시도·provider 호출 | 모두0 | 모두0 | 모두0 |
| runner 원문 status | PASS_STOP_BEFORE_SEND | PASS_STOP_BEFORE_SEND | FAIL / MediaTooLargeError |

모든 run에서 packet67,108,864B·청크 최대262,144B를 유지했다. read callback을 모두 반환하고 service를 닫은 뒤에도 동일 detached stream의 길이/hash·strict decode가 유효했고 그 stream이 Search에 전달됐다. 원본 provenance가 생산 모델과 같고 신규ref rollback 후 동일 writer 연결이 유지됐다. 720초 실제 timeline_range.end_sec도720.033333으로 새 연결의 값·타입·hex와 정확히 일치했다. Search의 긴 playback 길이를 logical 원본 길이로 사용하지 않는다.

720-a의 최초 거부는 `_verify_output`의 기존 media40MiB=41,943,040B다. 변환 파일은 이를 **10,634,644B 초과**했다. encode는 완료됐고 observer가 cleanup 전에 stat 길이를 보존했다. Search source512MiB는 통과했으며 준비 context61.061초에서 거부돼150초 deadline이 최초 병목은 아니었다. base64·JSON request56MiB guard·SDK body·HTTP wire·provider는 NOT_REACHED다. actual error code를 Recording typed code로 바꾸지 않고 `MediaTooLargeError`와 supervisor `RUNNER_FAILED` 원문을 보존했다. 어느 Search/Case 한도도 올리지 않았고 자동 retry·1200초 재실행도 하지 않았다.

독립 읽기 전용 collector가 Search 진입과 runner report 직후, 소유 DB 중단 **전에** MySQL8.4.13/packet67,108,864B/Aborted_clients0→0을 확인했다. 두 조회는 별도 보호 기록이며 runner 자체의 성공 경로 final-health와 구분한다. 720 거부 후 runner temp0·자식0·sampler/cleanup 오류0, 이후 감독기가 소유 DB를 정상 중단했다. DB 수동 재시작은 없었다.

### 자원과 시간의 관측 범위

| 직접 관측 | 240-a | 480-a | 720-a |
| --- | ---: | ---: | ---: |
| runner RSS 표본 | 256,765,952B | 391,319,552B | 557,682,688B |
| runner ru_maxrss | 250,664KiB | 381,976KiB | 544,428KiB |
| ffmpeg / ffprobe RSS 표본 | 107,737,088 / 26,390,528B | 108,756,992 / 26,263,552B | 109,350,912 / 26,144,768B |
| runner cgroup 표본 / kernel memory.peak | 525,484,032 / 525,484,032B | 659,509,248 / 659,509,248B | 1,041,342,464 / 1,041,342,464B |
| temp 표본(open-unlinked 포함) | 176,361,614B | 311,897,198B | 483,401,674B |
| DB RSS 표본 | 241,008KiB | 243,292KiB | 245,436KiB |
| DB cgroup / data 표본 | 280,739,840 / 307,872,334B | 283,029,504 / 446,284,366B | 269,148,160 / 614,072,910B |
| runner CPU 누적 표본 | 18.75초 | 28.72초 | 45.94초 |
| child CPU 관측 하한: ffmpeg / ffprobe | 177.96 / 97.65초 | 385.84 / 171.91초 | 603.90 / 274.04초 |
| DB cgroup CPU window 차이 | 19,175,637µs | 33,400,529µs | 50,570,019µs |
| Windows 가용RAM 최소 표본 | 4,549,103,616B | 4,200,333,312B | 3,669,377,024B |
| C free 최소 표본 | 12,728,176,640B | 12,229,840,896B | 12,858,216,448B |
| runner 표본 수 / 최대 간격 | 1774 / 0.606초 | 2897 / 0.487초 | 4398 / 0.476초 |
| runner 표본 window | 404.944초 | 640.923초 | 978.307초 |

시간은 중첩되므로 합산하지 않는다. DB CPU는 mysqld뿐 아니라 컨테이너 내 계측 프로세스를 포함한다. child CPU 합은 PID별 관측 최댓값의 합으로 종료 직전 누락 때문에 하한이다. 표본 RSS/temp/host disk는 실제 연속 peak 보장이 아니다. kernel memory.peak는 해당 runner cgroup 생애의 값이며 다른 공유 cgroup에 귀속된 cache를 모두 포함하는 host peak가 아니다. DB kernel peak는 같은 DB 생애의 누적값으로 480/720 종료 관측283,250,688B다. 일괄 background·cache 통제나 collector 순수 overhead의 분리 실험은 NOT_RUN/UNKNOWN이다. 목표200ms가 항상 유지됐다고 표현하지 않는다.

계측한 Recording·변환 도구 호출에서120초 초과나 timeout으로 중단된 run은 없었다. 유지한120초가 더 긴 영상/더 느린 환경에 충분한지는 UNKNOWN이다. 향후1200초 후보도 별도 tool별·전체·Search150초 예산 검토가 필요하다. baseline2100MiB를 표시하는 재사용 원본 감사 helper는 부하 허가에 사용하지 않았으며 실제 단계 감독은3004MiB 시작 계산을 적용했다.

### 식별·controls·실패 보존

고정 image는 `sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`다. 각 run에서 FFmpeg/ffprobe8.1 버전·binary hash와 media-preflight를 확인했고 현재 checkout source를 ro mount/PYTHONPATH로 사용했다. image 내장 source를 현재 checkout으로 간주하지 않았다. baseline config SHA는 `10255f8e64b12f1c87ec02e208f6ede83d114fea307b29238fd8e10132ada5a5`다.

| 실험 ID | 실제 config SHA-256 |
| --- | --- |
| p2-0c-240-96m | `cf66b966ffcaa381e92a2b1628bb49ae7545568a643671b140d5bcfadf4fb061` |
| p2-0c-480-192m | `2c5d21887eab099028faad30c0f1ab8dcdb6fc49a81f127e7ac27c478920aba8` |
| p2-0c-720-208m | `03d12d55536619ec1b30a13340bdc5d5d2eb4f478f75476ef4eebaafa7acd7bb` |

source/runner/supervisor hash·각 runner 사본·입력 manifest identity는 보호 scratch에 보존했다. 720의 Search stat observer는240/480 후 보완됐으므로 이전 산출물을 최신 코드로 재실행한 것처럼 쓰지 않는다. 실제 product source의 시작/종료 path+content hash는 동일하다.

| 검사 | 직접 결과와 범위 |
| --- | --- |
| 새 config/selection/placement/network 등 | RED17 FAIL 후 기존과 합42 PASS. 최초 temp 부모 누락9 setup ERROR는 별도 실패로 보존 |
| CLI 긴 요청 | RED1 FAIL 후 GREEN |
| 모든 result packet 길이 관측 | RED1 FAIL 후 합43 PASS |
| Search 크기·실제 media cap 거부·파일 cleanup | RED1 FAIL 후 harness44+감독기6=50 PASS |
| 최종 Linux offline controls | 44 PASS, 3.83초, network none/원본·DB 없음 |
| missing script 사전검사 | RED1 FAIL 후 감독기7 포함51 PASS, 4.46초 |
| 실험 config로 manifest 누락/손상 실제 Linux 실패 | 각각 의도한 FAIL 보고, DB/Search NOT_REACHED·sampler/temp/child/cleanup 정리 PASS |
| 최종 focused: 위51+Analysis limits/chunk/metadata 단위 | **107 PASS, 22.54초** |
| Runtime quality | Ruff + Linux/Windows mypy 각87 source PASS |
| boundary / Contract | UTF-8 재실행 PASS, 구조62/JSON26/의미104 |
| 변경 harness/test Ruff·diff whitespace | PASS |

종료용 negative control 첫 시도는 보조 script source 경로가 **빈 디렉터리**여서 실패했다. 일반 controls도 미사용 control 경로를 bind하던 준비 문제이며 Docker bind 준비 과정에서 생성된 것으로 **추정**한다. 내부 생성 원인은 독립 확정하지 않았다. 빈 디렉터리·실패 컨테이너 로그를 보존하고 올바른 파일과 `is_file` 사전 거부를 RED/GREEN으로 보완했다. 새 이름으로 성공 재실행했으며 제품 실패나 실제720 거부를 덮지 않았다. boundary 최초 실행도 cp949가 결과 문자의 em dash를 출력하지 못해 exit1이었다. 코드를 바꾸지 않고 `python -X utf8`로 별도 결과를 생성해 두 검사 exit0을 확인했다. 최초 로그를 보존한다.

### 종료·Decision Gate

최종 원본15/15의 SHA-256·size·mtime과 보호 manifest hash가 시작과 같다. 04:53:32 KST 원본 감사 직후 Windows available4,869,701,632B/C free13,054,717,952B였고, 04:55:08 KST 별도 정리 검증은4,788,469,760B/13,053,689,856B였다. 순차 순간 표본으로 이후 여유를 보장하지 않는다.

소유 컨테이너13개 모두 stopped·OOM false·자동 RestartCount0을 기록한 뒤 exact-name/owner/미사용 검사로 제거했다. 이번 DB/work volume2개·internal network1개도 제거했고 owner 자원 재조회0을 확인했다. 성공/거부의 runtime temp와 최종 work audit files0/bytes0이다. 보존 volume3개는 남아 있으며 사용/변경/삭제하지 않았다. 공유 Docker/WSL 재시작·앱 강제 종료·image/cache prune·swap·운영 변경은 하지 않았다. raw/실패/검증 증거만 ignored 보호 scratch에 보존한다.

**Decision Gate:** 480초가 이번 전체 준비 경계의 가장 긴 성공 표본이며720초의 Recording/청크 저장·새 연결 준비는 통과했으나 Search 전송 media cap에서 멈췄다. 최소1200초 logical timeline·최종 신고영상 다운로드는 **미도달/NOT_RUN**이다. 이 결과는 일반적인8분 ceiling이나20분 불가능의 증명이 아니다.

다음 결정은 Search Owner와 Runtime/Recording/Case가 **40MiB 한도·Coarse media 준비 방식·장시간 요청 구조와 시간 좌표/파일 경계·후속 후보 merge/dedup**을 함께 검토하는 것이다. cap 변경 후보와 bounded 요청 설계는 품질·자원·deadline/Case 대기 비용을 비교한 뒤 결정해야 하며 채택 방식은 미정이다. 현재 packet64MiB와 청크 저장은 이번 크기에서 병목이 아니었고, 저장 성공만으로 materializer의 전체 bytes·Search base64/JSON working set·20분 경로를 해결했다고 판단하지 않는다. Search/Case/스토리지 구조·제품 지원 범위·운영 profile 승격은 이번에 변경하지 않았다.

NOT_RUN: 전체 pytest·전체 mandatory MySQL/strict/inventory gate·provider·Case 전체 흐름·Package READY·AWS·배포·rollback 호환·backup/restore·최소20분 E2E. NOT_REACHED(720): base64·request guard·SDK/provider. UNKNOWN: 독립 촬영 연속성·표본 사이 host/process peak·일반적 처리량·운영 동시 지원 수·장시간 timeout 충분성.

최초 구현 대화/이력을 전달하지 않은 fresh 읽기 전용 reviewer가 검토했고 수정·실측 뒤 **같은 reviewer**가 재확인했다. 최종 직접 실행은 harness44+감독기7=51 PASS/4.11초와 diff whitespace·빈 index 확인이다. 실제 영상·Docker·DB·107 focused·Linux44·quality/계약 결과는 **작성자 증거 열람·재집계**이며 reviewer 직접 실측이 아니다. 최종 P1/P2 및 확인한 표·계산 오류는 없었다.

최종 공개 변경은 아래5개다. 나머지 raw·실행 보조 도구·실패 로그는 ignored 보호 scratch에만 있다.

| 파일 | 변경 |
| --- | --- |
| `scripts/recording_real_media_recheck.py` | 명시적 유한 실험 config/요청 길이·placement 검증, 전체 result packet·정확 PTS 경계·누적part·송신 시도·Search 실패 출력 크기 계측 |
| `tests/runtime/test_real_media_recheck.py` | override/CLI/실제 guard/논리 coverage/송신/packet/출력 cleanup controls |
| `docs/runtime/experiments/2026-11-03-capacity-override.md` | 사전 예산·단계별 결과·최초 병목·한계·실패·정리·Decision Gate |
| `docs/runtime/experiments/README.md` | 결과 라우팅 |
| `docs/superpowers/plans/2026-11-03-capacity-override.md` | 승인 범위의 실행 계획·완료 항목 |

HEAD/브랜치를 유지하고 미커밋·미스테이징으로 남겼다. commit/push/PR/외부 게시·운영 설정/제품 source 변경은 없다.
