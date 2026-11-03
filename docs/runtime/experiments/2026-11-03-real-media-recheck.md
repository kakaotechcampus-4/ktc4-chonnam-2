# #538·#544·#546 이후 실제 입력 재검증 — 2026-11-03

최종 상태: **10초 모듈 경계 PASS / 100초 metadata publish FAIL / 240초 NOT_RUN**.
담당: 정철원(Runtime/Recording). 100초 chain은38,363,450B·3000frame·strict decode를 통과했으나
신규 metadata INSERT 후 모델 동등성 대조에서 거부됐다. 청크 INSERT·새 연결 조회·Search는 미도달이다.
작은 합성 입력에서 DB JSON 왕복1ULP 차이와 같은 제품 거부를 재현했다. 실제100초 모델의 숫자와
직접 일치하는지는 당시 계측 공백 때문에 **유력한 추론**으로 남긴다. 제품 코드는 변경하지 않았다.

아래 시작~종료 절은 **01:42–01:46 KST의 최초 RAM 부족 세션 기록**으로 보존한다.
그 절의 미구현/NOT_RUN/UNKNOWN은 당시 상태다. 최신 실행·실패·종료는 마지막 **자원 확보 후 재개** 절을 따른다.

## 시작·근거·변경 범위

- 시작 checkout은 사용자 예상 브랜치가 아닌 `develop`이었다. HEAD는
  `fb40402676f7712fb86e67c468fb1c50f327bfed`, working tree/index는 비어 있었다.
  로컬 `origin/develop`도 같은 SHA다. fetch/merge/rebase는 하지 않았다.
- 같은 HEAD에서 요청한 `codex/issue452-real-media-recheck`를 만들었다. HEAD 이동은 없다.
  #530 `88e27d42`, #538 `f1e8d82f`, #544 `52585e38`, #546 `fb404026`의
  HEAD 포함을 각각 `git merge-base --is-ancestor` exit 0으로 확인했다.
  GitHub의 #530·#537·#538·#544·#546 본문과 #530 댓글도 읽었다.
  closed 표시만으로 merged를 단정하지 않고 로컬 merge commit과 포함 관계를 대조했다.
- 사용자 제공 AGENTS.md, 루트 CLAUDE.md, docs/README.md를 적용했다.
  저장소 파일 검색에서 별도 AGENTS.md는 발견되지 않았다.
- [#530 병합 계획](elice-runtime-capacity-smoke-plan.md)의 P2-0b/0c·§9·Decision Gate,
  [감사](../reviews/runtime-p2-plan-audit-2026-11-02.md),
  [기존 실영상 실패](2026-11-02-local-capacity-probe.md),
  [합성 DB 대조](2026-11-03-chunked-capacity-recheck.md),
  [청크 저장 구현 메모](../../modules/recording/chunked-prepared-media.md),
  [VFR 검증](../../modules/recording/experiments/2026-11-02-vfr-frame-coverage.md)을 읽었다.
  현재 Recording materializer/service/repository/transaction facade와 Search media/provider/config,
  기존 capacity runner·focused controls·비공개 DB 대조 harness를 정적으로 확인했다.
- 공개 변경은 이 결과 문서뿐이다. 제품·tracked runner·테스트·운영 설정은 수정하지 않았다.
  실행 준비를 끝냈다고 표현하지 않는다. **새 통합 focused harness 구현·동적 controls는 NOT_RUN**이다.
  예산 부족 시 부하를 실행하지 않고 가능한 준비와 부족분을 보고하라는 요청에 따라 중단한다.

## 현재 자원과 격리

기존 신규 실행 기준은 Windows available **2100MiB = 2,202,009,600B** 및
C 실제 free **6GiB = 6,442,450,944B**다. 중단 reserve는 RAM700MiB/C4GiB,
disk 증가2GiB·DB data1GiB·temp512MiB다. 어느 기준도 낮추지 않았다.

| 직접 표본 | Windows available | C 실제 free | 판단 |
| --- | ---: | ---: | --- |
| 최초 CIM 조회, 아래 시각 표본 전 | 1,528,828KiB | 11,366,584,320B | RAM 약607MiB 부족 / disk 충족 |
| 01:42:15 KST, hash 검사 직전 | 1,587,130,368B | 11,356,770,304B | RAM 614,879,232B 부족 |
| 01:42:18 KST, hash 검사 직후 | 1,978,593,280B | 11,356,618,752B | RAM 223,416,320B 부족 |
| 01:46:06 KST, 종료 hash 검사 직후 | 1,898,229,760B | 11,344,064,512B | RAM 303,779,840B 부족 |

표의 부족분은 시작 기준에서 직접 뺀 **계산값**이다. 배경 변화가 있어 RAM 증가나 disk 차이를
이 작업의 회수량/실행 증가량으로 귀속하지 않는다. 과거 실험 표본은 현재 가용량으로 사용하지 않았다.

같은 최초 조회 묶음의 Docker VM limit은 8,072,269,824B/18CPU,
WSL Ubuntu MemAvailable은 7,188,770,816B, swap 사용은 0B였다.
WSL 논리 filesystem available 1,017,051,492,352B는 C 물리 여유가 아니다.
Windows와 VM RAM을 합산하지 않는다. Docker 컨테이너는 전체 0개였고 Windows에서
ffmpeg/ffprobe/python 실행은 발견되지 않았다. Docker/WSL daemon과 일반 앱은 실행 중이므로
전용 host/완전 idle로 판단하지 않는다. 표본은 순차 조회이며 동시 peak 측정이 아니다.

기본 sandbox의 CIM 접근은 거부됐다. 읽기 전용 확장 조회로 위 값을 확인했다.
공유 WSL/Docker 재시작·다른 프로세스 종료·cache/image prune은 하지 않았다.

### 재개 후보의 단계별 예산 — 실행·적합성 미검증

다음은 기존 제한을 보존하는 **계획/추정**이며 새로 승인된 성능 보장이 아니다.
DB 대조만의 runner512MiB를 영상 encode/Search에 적용하지 않는다.

| 항목 | 후보·근거와 남은 확인 |
| --- | --- |
| 작은 10초 controls | runner CPU1.5/RAM768MiB + DB CPU0.5/RAM512MiB, 각각 swap 추가 불허. 과거 short03 ffmpeg sampled RSS257,232,896B·runner cgroup301,760,512B를 참고하되 현재 peak는 UNKNOWN. affinity2 CPU·PID 제한과 child 수를 별도로 확인 |
| 100초 후보 | 과거 영상 probe의 runner1280MiB + DB512MiB 유지 후보. RAM cap 합계1792MiB + host reserve700MiB = **2492MiB**라는 계산만으로도 기존2100MiB 시작 기준보다 큼. host/collector/daemon 여유가 추가로 필요하며 현재 예산으로 실행 불가 |
| 240초 후보 | 100초의 실제 bytes/elapsed/동시 RSS·temp·DB 건강 결과를 먼저 검토. VFR 수정 뒤 첫 part bytes가 증가한 과거 관측이 있어 기존 최종 크기를 가정하지 않음. 자동 진입 없음 |
| disk/temp | 기존 C reserve4GiB + 증가2GiB envelope 유지. DB1GiB·temp512MiB를 제외한 산술 잔여512MiB는 로그/collector/VHDX/cleanup 지연용 후보. DB rollback이 물리 파일을 줄인다고 가정하지 않음 |
| temp 중첩 | detached stream N + Search source copy N + Search media M을 같은 시점에 보유할 수 있음. N≤48MiB, M≤40MiB라면 이 세 파일 합계≤136MiB는 **계산값**. part/concat/remux/probe 출력·unlink된 open file·DB 공간을 포함한 peak가 아님 |
| 시간/정리 | Recording 도구당120초, Search preparation/guard150초 유지 후보. 과거100초 Recording137.65초를 선형 외삽하지 않음. 과거 전체900초 감독 예산 안에서 DB TCP final-server 준비·단계·cleanup을 분리해야 함. cleanup60초 예약은 후보이며 실측 전 적합성 미확정 |
| soft stop/감독 | 기존 runner1100MiB·temp512MiB, host700MiB/C4GiB, DB data1GiB·전체 증가2GiB 경계 보존. 768MiB 작은 runner에1100MiB soft stop을 적용할 수 없으므로 별도 더 낮은 soft-stop 근거와 controls 필요. DB cgroup440MiB 후보는 합성 대조에서만 검증됨 |

따라서 현재 RAM 부족을 해소하는 것과 통합 harness·단계별 예산을 검증하는 것은 별개 선행조건이다.
기존2100MiB 기준만 넘었다고 긴 입력의 동시 working set이 충족됐다고 판단하지 않는다.

## 입력 복원과 도구 identity

보호 manifest와 기존 실행 JSON/감독기/runner 알고리즘을 재사용했다. 원본은 `rb`로만 읽었고
파일명/촬영 시각으로 순서·연속성을 새로 추정하지 않았다. 경로·파일명·영상·번호판·정밀 위치는 공개하지 않는다.
15개 합계1,771,439,266B·metadata duration 합계1,584.173332초는 **기존 manifest 값**이다.
이번에 ffprobe를 다시 실행한 metadata가 아니다. 최초 manifest의 도구는 Windows9.0.1이고,
이후8.1 decode/coverage 기록과 구분한다. 이번 시작 hash/stat 대조는 **15/15 PASS**다.
같은 전방 카메라/연속 주행은 **사용자 설명**이며 실제 seam/gap·촬영 시각 독립 검증은 NOT_RUN이다.

| 후보 | 복원한 조건 | 독립 확인과 한계 |
| --- | --- | --- |
| 작은 입력 | short03의 input-02, 상대timeline0–10초 | 기존 성공 조건. 이번 실행 NOT_RUN |
| #537 DB 실패100초 | input-02→03, 상대timeline0–100초. 명시 placement: input-02 `[0,88.566667)`, input-03 `[88.566667,195.8)`초 | 기존 report의 ID·요청·candidate duration과 당시 runner의 Decimal 누적 알고리즘, 보호 metadata가 일치. VIDEO index0, time base1/30000. 새 등록의 stream ref 문자열은 재생성 대상이며 당시 문자열 재현은 아님 |
| 기존240초 | input-01→02→03, 요청0–240초. placement `[0,117.933333)`, `[117.933333,206.5)`, `[206.5,313.733333)`초 | 과거 첫 span coverage 실패 조건의 후보를 복원. 이번 actual frame coverage는 미측정 |

100초의 **선택 범위 계산**은 input-02 media0–88.566667초 + input-03 media0–11.433333초다.
이는 원본 frame 선택을 다시 측정한 결과가 아니다. 과거 최종3000frame·38,359,627B는 과거 관측으로만 보존한다.
profile은 세 후보 모두 `aws-e2e-v1 / 480 / veryfast / CRF23`,
duration240000ms/bytes50331648이고 당시 config SHA-256은
`10255f8e64b12f1c87ec02e208f6ede83d114fea307b29238fd8e10132ada5a5`다.
DB packet64MiB, Search source/media/request512/40/56MiB는 재개 시에도 유지한다.
Incident 운영 적용값을 이번 Analysis 입력으로 혼용하지 않는다.

현재 로컬 후보 image ID는 과거와 같은
`sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`다.
이는 immutable image identity 대조이며 **이번 FFmpeg/ffprobe 실행 확인은 NOT_RUN**이다.
binary 자체 hash·현재8.1 version/media-preflight 대조도 아직 미실행이다.
재개 전에 두 binary hash와 version/build를 함께 수집해야 한다.
이미지 내장 source를 현재 checkout으로 간주하지 않는다. 현재 `src`의 경로+내용 hash와
기존 runner hash를 ignored evidence에 보존했고, 재개 시 source ro mount·PYTHONPATH 우선과 실제 import 위치를 확인해야 한다.

## focused harness 준비 검토와 controls

기존 `scripts/recording_capacity_probe.py`를 **실영상 runner로 재사용하지 않았다**.
새 service지만 같은 connection을 쓰고, legacy `recording_entry.content`의 SHA2/길이를 조회하며,
전체 `opened.stream.read()` 뒤 BytesIO를 Search로 전달한다. 청크 media의 content는 NULL이므로
현재 목적을 검증하지 못한다. 이는 **정적 harness 부적합 판단**이며 새 제품 결함 재현이 아니다.

통합 harness는 미구현이다. 재개 시 필요한 구체적인 변경·controls를 다음과 같이 식별했다.

1. 현재 source의 실제 register/placement/resolve/materialize를 유지한다. `capture_materialization`과
   part/concat/strict validation observer의 반환값·옵션·기대값을 바꾸지 않는다. publish 전 content의
   길이/hash만 관측하며 영상을 로그에 넣지 않는다. Recording service가 보유하는 전체 bytes를 따로 기록한다.
2. 실제 청크 저장을 commit하고 writer의 CONNECTION_ID를 보존한 뒤 writer/service를 닫고
   engine.dispose로 pool을 비운다. 재조회는 `TransactionalRecordingRepository`와 새 RecordingService를 쓰고
   reader CONNECTION_ID≠writer를 확인한다. 실제 callback 종료 후 checkedout0을 요구한다.
   미commit 상태를 읽기 위해 isolation을 완화하지 않는다.
3. manifest/청크 행 수·총 길이·청크 최대 bytes와 실제 `_execute_command`의
   encoded SQL 길이+command byte, result packet payload 최대를 수집한다. legacy content 조회로 대체하지 않는다.
   SQLAlchemy 문자열만으로 driver command 크기를 추정하지 않는다.
4. 반환 stream을 bounded read로 hash/길이 확인하고 seek(0)한다. reader service 종료 뒤에도 stream이
   유효한지 확인하고 그 **동일 stream**을 MediaInput으로 Search에 전달한다. unbounded read·전체bytes/list
   재결합을 금지하는 wrapper control과 offset/size mismatch negative control이 필요하다.
5. Search `_materialize` source copy(현재64KiB 읽기)와 `_run_ffmpeg_encode`를 각각 관찰한다.
   `provider._video_data_url`은 실제 `Path.read_bytes()` 전체media bytes + base64 문자열을 보유하고
   guard JSON도 전체 문자열을 만든다. 이 할당은 감추거나 detached DB 조회의 메모리 성질과 혼동하지 않는다.
6. API key 없이 소유 internal network/공개port0·전용 MySQL IP:3306만 허용한다.
   socket connect/connect_ex/create_connection 및 SDK/HTTP send 경계의 fail-closed negative controls가 필요하다.
   실제 coarse prompt/base64/guard를 통과한 뒤 SDK parse 진입 sentinel을 필수로 관측한다.
   guard PASS·SDK body 직렬화·HTTP wire·provider 성공은 별도 상태다. sentinel 정상 반환을 성공으로 세지 않는다.
7. commit한 행을 rollback으로 지웠다고 표현하지 않는다. 별도 미commit 신규ref의 정상 rollback과
   동일 물리 연결·invalidated=false·Aborted_clients delta0을 검사한다. 정상 committed 행은 소유 DB 정리로 제거한다.
   stream close 후 temp FD/디스크·pool·자식 process 정리와 supervisor Docker timeout 예외도 controls로 검증한다.
8. phase/sample/driver JSONL은 즉시 flush한다. runner/DB/ffmpeg/ffprobe RSS·CPU·cgroup·temp/disk를
   구분하고 unlink된 TemporaryFile은 directory listing만으로 크기0이라고 판정하지 않는다.
   sampled max와 HWM/cgroup peak를 구분하고 짧은 peak/도구 생존 구간 누락을 UNKNOWN으로 표시한다.

기존 helper controls `tests/runtime/test_capacity_probe.py`를 현재 checkout에서 직접 실행해
**8 PASS (0.17초)**를 확인했다. pytest cache 쓰기 권한 경고1건이 있었고 assertion 실패는 없었다.
실패 전파·비민감 진단·sentinel 필수·driver hook 복원·stat mismatch·stop marker·frame gap·journal의
기존 단위 대조다. 새 harness의 새 연결/commit/detached stream/egress 통합 controls 성공으로 확대하지 않는다.

## 단계별 결과와 다음 결정

| 항목 | 이번 상태 | 해석 |
| --- | --- | --- |
| branch/merge 포함·보호 입력 확인 | PASS | 현재 HEAD와 원본 identity 확인 |
| 시작 RAM gate | FAIL / RESOURCE_BUDGET_STOP | 시작 기준 미달. OOM/DB disconnect를 유발한 실패가 아님 |
| 기존 helper controls | PASS / 8개 | 새 통합 harness validation은 아님 |
| 통합 focused harness 구현·controls | NOT_RUN | 위 변경점 식별까지만 수행 |
| 작은 실제10초 Recording encode/DB commit/read/Search | NOT_RUN | 자원 gate에서 실행 자체를 시작하지 않음 |
| 100초·240초 재검증 | NOT_RUN | 앞 단계 실측과 예산 미충족 |
| 실행 내 encode·concat·strict decode·PTS/duration·provenance | NOT_REACHED | 새 관측값 없음 |
| DB command/청크 행/저장·새 물리 연결 길이/hash/rollback·연결 안정성 | NOT_REACHED | 새 관측값 없음 |
| Search source copy/재encode/base64/guard/sentinel | NOT_REACHED | 새 관측값 없음 |
| SDK body·HTTP·provider·Case/Web·20분·AWS·배포·운영 migration | NOT_RUN | 요청 범위 밖 |
| 이번 실영상 저장 개선·제품 다음 최초 병목 | UNKNOWN | #546의 합성38.36MB PASS를 실영상 성공으로 바꾸지 않음 |

과거 #537의 실제 저장 실패, packet128 OOM/감독 UNKNOWN, #538의 VFR 첫span PASS,
#546의 합성38.36MB 저장/새 연결 PASS는 각각 보존한다. 이번 결과로 어느 실패도 덮어쓰지 않는다.
현재 source는 VFR·청크 저장 수정이 포함됐으므로 과거와 **동일 제품 코드 조건은 아니다**.
100초의 입력·placement/profile·packet을 맞출 수 있어도 새 최종 bytes/시간·성공 여부를 예상값으로 고정하지 않는다.

20분 확장 전에는 먼저 RAM 여유·통합 controls·8.1 binary identity·작은 실제 경계 성공을 확보하고,
100초에서 storage 개선과 materializer/Search 전체bytes working set·시간을 직접 측정해야 한다.
240초 typed byte-limit 거부도 유효한 결과로 보존한다. 한도·strict 검증·Case timeout을 완화하지 않는다.
현재 결과만으로 cap 상향·시간 분할 탐색·운영값 승격이나 지원 길이를 결정할 수 없다.

## 종료·리뷰

종료01:46:06 KST 검사도 **원본15/15 SHA-256·size·mtime 불변**이다.
시작/종료의 보호 manifest hash·현재 source 경로+내용 hash·기존 tracked runner hash가 각각 일치한다.
최종 RAM 부족분303,779,840B는 **289.70703125MiB (계산)**다. 이후 가용량을 보장하지 않는다.
01:46:02 KST Docker 컨테이너 전체0, network는 기존 bridge/host/none뿐이며,
기존 보존 volume3개의 이름/owner label이 시작과 일치했다.

상대 문서 링크6개 누락0·민감 패턴 검사·7개 관련 Python AST parse·예산 산술 대조를 통과했다.
제품/runner/test 변경이 없어 Runtime quality·boundary·Contract·전체 pytest·전체 mandatory MySQL은
재실행하지 않았다. `git diff --check`와 staging 비어 있음을 확인했다.
구현 대화 이력을 전달하지 않은 fresh read-only reviewer가 harness/제품 경계·과거 JSON·보호 metadata·
새 감사 evidence·이 문서를 독립 대조했다. RAM 산술·10/100/240초 placement/config·과거 RSS 값·
시작/종료 입력/source/manifest/runner identity 구분에서 미해결 actionable 지적은 없었다.
reviewer의 기존 helper controls 최초 실행은 개인 basetemp 상위 폴더 미생성으로
**5 PASS / 3 setup ERROR**였고, 상위 폴더만 만든 별도 실행은 **8 PASS (0.11초)**였다.
초기 setup 실패를 제품 실패로 분류하거나 후속 성공으로 삭제하지 않는다.
reviewer는 cache disabled·개인 scratch로 단위 controls를 직접 실행했으며,
새 통합 harness·원본 영상·DB·Docker·provider는 재실행하지 않았다.
성공 중간 영상은 생성하지 않았고 새 DB/container/volume/network도 만들지 않았다.
기존 실패·복원 volume3개는 이름/owner label 목록만 확인했으며 mount/read/start/reuse/delete하지 않았다.
원본·기존 evidence는 수정하지 않았고 새 감사 JSON만 ignored scratch에 보존했다.
최종 branch/HEAD는 위와 같고 신규 이 문서1개만 untracked/unstaged다. index는 비어 있다.
commit·staging·push·PR·외부 댓글·CI 재실행은 하지 않았다.


## 자원 확보 후 재개 — 02:05–02:26 KST

사용자가 RAM 확보 후 새 통합 harness·controls 및10초→100초 실행을 요청했다.
앞선 RESOURCE_BUDGET_STOP과 과거 #537/#538/#546 결과는 보존한다.
branch/HEAD는 동일하고 당시 미커밋 문서도 보존했다.

### 현재 자원·단계 예산·환경

- 재개 최초 직접 조회: Windows available5,868,112KiB, C free13,134,606,336B,
  Docker 컨테이너0, WSL available7,180,427,264B/swap사용0. VM/Windows RAM은 합산하지 않는다.
- 원본 재검사02:05:38 KST: RAM6,211,743,744B/C12,933,591,040B.
  DB/각 단계 직전에도 host/DB gate를 다시 확인했다.
- runner CPU1.5/affinity0,1/RAM1280MiB, DB CPU0.5/RAM512MiB, 각각 swap 추가 없음.
  start gate3004MiB = hard cap1280+512 + 기존 host reserve700 + collector/daemon 여유512MiB.
  마지막512MiB는 **보수적 추정 예산**이며 실측 peak 보장이 아니다. 기존2100MiB 기준보다 강하고,
  DB 대조의 runner512MiB만으로 encode/Search를 충족한다고 가정하지 않았다.
- C 시작6GiB/reserve4GiB·성장2GiB, DB data1GiB·DB cgroup440MiB soft stop,
  runner cgroup1100MiB·temp512MiB soft stop을 유지했다. runner 표본200ms,
  host는1초 대기+Docker 호출 시간이다. 짧은 peak/관측 지연/overshoot 가능성이 있다.
- Recording 도구당120초, Search 준비/guard150초, runner900초/host930초,
  소유 process stop5초·DB stop10초와 후속 상태 재확인, 정리60초 후보 예산을 적용했다.
  실제 정리 명령은6.45초에 exit0이었다. 감독 Docker 호출은 유한 timeout을 사용했다.
- 새 owner의 DB/data·work volume/internal network만 생성했다. 공개port0, source/원본/manifest ro,
  root filesystem ro인 runner, API key 없음, 전용 DB IP:3306만 socket connect/connect_ex 허용,
  sync/async HTTP send 차단, SDK parse sentinel을 적용했다. Docker internal network와 Python fence는 별도 경계다.
- 실제 MySQL8.4.13, session packet67,108,864B. buffer pool32MiB/redo16MiB/connections12,
  performance/binary/general/slow log OFF. Analysis480/veryfast/CRF23·240000ms/50331648B,
  Search source/media/request512/40/56MiB를 유지했다. 운영 baseline과 cap override는 없다.
- immutable runtime image는 앞 절의 동일 ID이고 현재 checkout source를 ro mount했다.
  실제 import 위치가 `/repo/src/`인지 검사하고 media-preflight exit0 및 두 도구8.1을 확인했다.
  FFmpeg binary SHA-256 `19e0073f42f3cc0c1880ac9a4a91fc6c42d511bec9497db03872cc527791c91a`,
  ffprobe `ec4bde78f8b08c56109d68fffb16e9972ae7543ed62253fd90e699dda4a0f975`다.
  현재 제품 source를 오래된 이미지 내장 코드로 대체하지 않았다.

입력 ID·placement·profile은 최초 복원 표와 같다. 물리적 촬영 연속성은 여전히 사용자 설명이며
새 seam 독립 검증은 아니다. CPU affinity2개는 과거 #537 실행과 다른 조건이다.
같은 profile이어도 자동 thread 선택과 bytes/시간이 달라질 수 있으므로 과거와 완전히 같은 실행이라고 쓰지 않는다.

### 새 harness와 사전 controls

신규 `scripts/recording_real_media_recheck.py`는 기존 runner의 진단 helper만 사용한다.
기존 run()/legacy content SELECT/전체 stream.read()/BytesIO 우회는 호출하지 않는다.

실제 register→resolution→materializer→repository publish→**commit** 후 writer service/connection을 닫고
engine.dispose로 pool을 비웠다. 재조회는 TransactionalRecordingRepository와 새 service를 사용했다.
writer와 다른 CONNECTION_ID·callback 종료 후 checkout0·service 종료 후 stream 유효성을 검사했다.
bounded64KiB hash/길이 검증 후 seek0하여 **같은 detached stream**을 실제 Search MediaInput에 전달했다.
전체 stream bytes를 새로 합치지 않았다. 정상 prepared-media rollback은 별도 신규ref로 검사했다.
commit한 본문을 rollback으로 삭제했다고 표현하지 않는다.

실제 PyMySQL command(+command byte)·result packet payload 길이만 수집하고 SQL/BLOB/request를 로그에 넣지 않았다.
Search source copy와 reencode를 분리 계측했고, 실제 prompt/base64/JSON guard 후 SDK 진입 sentinel1회를 요구했다.
계측기가 base64 전체문자열을 split하거나 guard JSON을 다시 encode해 복제하던 부분은 reviewer 지적 후
비복사 길이 계산으로 바꿨다. 제품 자체의 전체media read/base64/guard bytes 할당은 그대로 관측 범위다.

| 직접 controls | 결과·범위 |
| --- | --- |
| Windows 새14+기존8 helper | 최종22 PASS, 2.15초 |
| Linux 동일22 | 22 PASS, 3.27초. network none, 원본/DB 없음 |
| Linux manifest 누락/손상 | 각각 의도된 FAIL final JSON·sampler/temp 정리 확인. DB/Search NOT_REACHED |
| 소유 감독기 fake | 최종6 PASS, 0.31초. start timeout/host stop/inspect timeout/daemon 오류/다른 owner/예상 밖 이름 |
| 기존 chunked 단위+초기 감독기5 | 작성자23 PASS, 1.43초. 실제 DB 재현 대체 아님 |
| 마지막 tracked harness focused | 새14+기존8 =22 PASS, 2.38초. publish_model 진단 추가본도 포함하며 미디어 재실행은 하지 않음 |

초기 missing-runner RED8 FAIL, Windows resource import8 FAIL/기존8 PASS,
추가 controls의 kwargs 오타·비동기 loop/close·오류 타입 import 실패는 ignored 로그로 보존한다.
loop 준비가 지연된 실행은 정확한 작업 소유 pytest PID만 확인해 종료했다. 다른 작업은 종료하지 않았다.
이 초기 harness/control 실패를 제품 실패로 분류하거나 최종 PASS로 삭제하지 않았다.

독립 reviewer는 감독기의 start가 예외 경계 밖인 점·owner label만으로 정리하던 점·inspect 비zero를
부재로 오인하던 점을 지적했다. 생성 전 pending exact-name 등록, 최상위 guarded cleanup,
owner+허용 이름 검증·stop 후 state 확인, 관측 실패 UNKNOWN·최초 오류 별도 보존을 반영했다.

### 실제10초와100초

시간은 직접 관측 monotonic seconds다. 아래 phase는 중첩되므로 합산하지 않는다.
Recording 준비 시간은 publish 시도까지 포함한다. 실제 API/Worker/Case 전체 시간을 뜻하지 않는다.

| 관측 | 10-a | 100-a |
| --- | ---: | ---: |
| 요청/선택 | input-02, 0–10초/1span | input-02→03, 0–100초/2span |
| 개별 encode 시간 | 5.381초 | 40.252 / 6.158초 |
| 개별 part bytes | 4,246,998 | 33,347,841 / 5,015,985 |
| 개별 materialize 시간 | 37.361초 | 76.987 / 34.263초 |
| chain 전체/concat mux | 해당 없음 | 129.298 / 0.111초 |
| 최종 media bytes | 4,246,998 | 38,363,450 |
| Recording 준비 총시간 | 39.402초 PASS | 136.508초 FAIL — publish 포함 |
| 출력 frame coverage | 300frame, gap0 | parts2657/343, final3000frame, gap0 |
| PTS/clock | strict increase, 1/30000 | strict increase, 1/30000 |
| strict decode | 아래 추가검사 PASS | native final decode4.896초 PASS |
| DB publish/commit | 0.579 / 0.108초 PASS | 0.144초 metadata 비교 FAIL, commit NOT_REACHED |
| 청크 | 17행, 합4,246,998B, 최대262,144B | INSERT NOT_REACHED, 이후 별도 조회0행 |
| 실제 command/row packet 최대 | 524,466 / 262,155B | 1,921 / 785B — 청크 전 실패 |
| 다른 물리 연결 stream/hash | 1.039초 PASS | NOT_REACHED |
| Search source copy/reencode | 0.035 / 1.022초 | NOT_REACHED |
| Search media/base64/guard JSON | 904,589 / 1,206,120 / 1,209,783B | NOT_REACHED |
| SDK 진입 sentinel | 1회, STOP_BEFORE_SEND | NOT_REACHED |

10초의 writer ID10·reader ID11, checkedout0, 같은 stream의 길이/SHA-256 일치,
신규ref prepared rollback 후 동일 writer 연결, Aborted_clients0→0을 확인했다.
서비스가 보유한 전체 prepared content4,246,998B도 별도 기록했다.
Search 준비 context 전체1.914초는 request 계측을 포함하며, base640.0195초/guard dumps0.0190초는
제품 전체 SDK body 직렬화 시간이나 HTTP body 크기가 아니다.
API key·인증 SDK·HTTP·provider·탐색 응답은 NOT_RUN이다.

일반 single-span 경로는 별도 final strict decode를 항상 호출하지 않으므로10-a 이후 저장된 영상을
새 detached stream으로 열어 제품 `_strict_decode`를 추가 실행했다(0.571초 PASS).
첫 추가 harness는 존재하지 않는 storage_root 선행조건으로 FAIL이었다. 실패 JSON/code/log를 보존하고
유효한 root를 사용하는 별도 read/decode만 실행했다. 원본 재encode로10-a를 반복하지 않았다.

100초는 원본과 출력의 실제 PTS/duration·frame 수 및 chain packet/format·strict decode가
기존 제품 검증을 통과한 뒤 `MySQLRecordingRepository.add_prepared_media`의 신규metadata INSERT와
locking read 이후 `type(media).model_validate(stored['payload']) != media`에서 ValueError로 거부됐다.
packet이나 전체영상 전송 전의 실패다. 허용폭·기대값·실패 skip은 바꾸지 않았다.
outer rollback/connection close/temp cleanup은 예외 없이 끝났고, 별도 새 연결의 확인에서
analysis_source/prepared_content 행0·chunk 행0이었다. 당시 후속 CONNECTION_ID/Aborted_clients는
실패 경로에서 계측하지 못했으므로100초 연결 안정성 전체와 Aborted delta는 UNKNOWN이다.
10초 성공이나 나중 정상 ping으로 이 공백을 채우지 않는다.

### 작은 제품 재현과 인과의 한계

100초 재encode는 반복하지 않았다. 별도1,545B 합성 MP4·새ref를 실제 같은 소유 MySQL schema에
`add_prepared_media`로 전달했다. 원본 파일/영상을 사용하지 않은 metadata 대조다.

| end_sec 입력 | DB 왕복 값 | 실제 repository 결과 |
| --- | --- | --- |
| 100.0 | 100.0 | PASS |
| 100.00000033333333 | 100.00000033333332 | FAIL — 신규행인데 immutable conflict ValueError |
| 88.566667 | 동일 | PASS |
| 11.433333333333334 | 동일 | PASS |

실패 대조에서 달라진 필드는 timeline_range뿐이고 float hex의 최하위1bit 차이(1ULP)를 직접 확인했다.
모든 작은 대조는 rollback했고 prepared/chunk 행은 전후0이다.
독립 CLI의 상수-only `CAST(... AS JSON)`/`JSON_EXTRACT`도 fraction값을
`100.00000033333332`로 반환했다. 정확한 query를 구성하는 ignored 진단 코드·hash·CLI exit0·
MySQL8.4.13/packet을 함께 보존했다. 서버 JSON 변환/표시 경계의 관측이며 내부 변환 알고리즘 원인은 미확정이다.

**확인:** 작은 신규 AnalysisSource도 JSON 왕복 후 metadata 동등성 검사에서 거부될 수 있다.
**추론:** 실제100초 실패의 유력 원인도 이1ULP 문제다. 다만100-a 당시 publish 모델 전체를 기록하지 않아
해당 end_sec가 실제 실패값이었다고 직접 확정할 수 없다. 후속 runner에는 publish_model 진단을 추가했지만
그 마지막 보완본으로 실제 영상을 다시 실행하지 않았다. 실제 실행별 runner snapshot/hash를 보존했다.
IncidentClip도 같은 비교 분기를 쓰므로 영향 가능성은 있으나 이번 직접 재현은 AnalysisSource만이다.

metadata 보조검사의 첫 두 시도는 테스트 seed import의 pytest/fixture mount 선행조건 오류로
DB 대조에 진입하지 못했다. raw 원문은 ignored scratch만 보존했다.
세 번째는 모듈 import 없이 seed 상수를 추출하고 최소모델을 직접 구성했다.
이 준비 오류 둘과 제품의1ULP 실패는 별개다.

### 자원 관측·중단 결정

아래는 bytes 단위 sampled maxima다. HWM과 kernel cgroup peak는 별도 열이다.

| 실행 | runner RSS 표본 | ffmpeg RSS 표본 | ffprobe RSS 표본 | runner cgroup 표본 / kernel peak | temp 표본 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10-a | 102,965,248 | 106,921,984 | 25,473,024 | 233,230,336 / 233,492,480 | 9,398,585 |
| 100-a | 163,475,456 | 107,585,536 | 26,263,552 | 250,429,440 / 250,429,440 | 76,727,379 |

runner ru_maxrss는10-a100,200KiB/100-a159,500KiB다. RSS 표본과 단위·정의가 달라
동일 값이나 driver별 allocation peak로 표현하지 않는다. DB의 단계별 RSS 표본 최대는
10-a230,888KiB/100-a221,996KiB, 단계별 cgroup 표본343,183,360/298,729,472B다.
DB kernel peak 표시는10-a345,931,776/100-a298,754,048B였다.
아래 수동 stop/start 때문에 cgroup 세대가 달라 이 둘을 같은 누적 peak로 비교하지 않는다.

전 세션 host 표본에서 Windows RAM 최소4,659,449,856B/C free최소12,639,084,544B였고,
DB data 관측 최대139,415,599B였다. 이는 관측 범위의 최댓값/최솟값이지 물리적 전체 peak 보장이 아니다.
CPU 누적은 runner·살아있는 child별로 JSONL에 기록했다. 종료된 짧은 child·샘플 사이 peak는 누락 가능하다.
익명/unlink된 stream은 `/proc/self/fd` inode와 named 파일을 중복 제거해 temp 논리bytes에 포함했다.
Windows/WSL monotonic epoch는 별개이며 교차 phase 정밀정렬을 측정했다고 주장하지 않는다.

소유 DB는 harness/100초 실패 시 감독 정책으로 정상 stop됐다. 추가 진단 전 같은 작업 소유 DB만
TCP final-server readiness로 수동 재개했다(총4회). 자동 RestartCount0과 **수동 재개0회는 다른 말**이다.
OOMKilled는 모든 소유 컨테이너에서 false였다. 마지막 server Aborted_clients0은 마지막 재개 이후 값이며
100초 실패 시점의 누락된 delta를 대신하지 않는다. 기존 보존 volume3개는 어떤 재개에도 연결하지 않았다.

240초는 자원 부족 때문이 아니라100초의 선행 제품 실패 때문에 **NOT_RUN**으로 결정했다.
100초의 청크 저장·새 조회·Search도 **NOT_REACHED**다. 같은 실패를 큰 입력으로 반복하지 않았다.

### 판정·후속·검증·정리

| 질문 | 최종 판정 |
| --- | --- |
| 작은 실제 입력의 새 저장/조회/Search 준비 | PASS —10초, provider 전송 전까지 |
| 기존100초 실패 입력의 개선 | 준비·strict decode는 PASS, storage는 metadata 단계 FAIL. 청크 저장 개선을 같은 실영상 크기에서 확인하지 못함 |
| 이번 다음 최초 제품 병목 | DB metadata 동등성 검사, 작은1ULP 재현 확보 |
| 과거 packet64 실패 해결 여부 | #546 합성 PASS와 이번10초 PASS만 확인. 원래38MB 실영상의 청크 저장/새조회/Search 성공은 미검증 |
| 240초/20분 확장 | NOT_RUN. metadata 표현 보존·ref fingerprint·불변성 대조의 일관성 검토/좁은 회귀 후100초 재검증이 선행 |

원본 timeline/PTS를 반올림하거나 비교 tolerance를 늘려 이번 실패를 성공으로 바꾸지 않는다.
이 측정에 제품 설계 변경·Search cap·시간 분할 탐색·Case timeout 변경을 섞지 않았다.
Case/Web·Package READY·20분 E2E·지원 길이·처리량·운영값 승격을 선언하지 않는다.

Runtime quality(Ruff + Linux/Windows mypy 각87 source), boundary,
Contract 구조62/JSON26/의미104, 새 Python 파일 Ruff를 통과했다.
전체 pytest·전체 mandatory MySQL·CI 재실행은 하지 않았다.
독립 fresh reviewer가 controls/감독기·실행 identity·실제 결과·최소 재현을 읽어 대조했다.
최종 문서·정리 증거 재검토에서 미해결 P1/P2 지적은 없었다.
직접 재실행은 offline controls뿐이며 실제 DB/원본/FFmpeg/provider는 실행하지 않았다.
reviewer의45개 묶음은44 PASS/기존 chunked temp 열거1 FAIL였고 단독 후속1 PASS였다.
Windows delete-pending 열거 지연 가능성이 높다는 **추론**으로 남기며 초기 실패를 보존했다.
마지막 감독기 fake6은 reviewer도6 PASS(0.27초)였다.

정리 전 소유 컨테이너11개 snapshot의 OOM0/자동 restart0, DB8.4.13/packet64MiB/internal network를 확인했고,
이후 읽기 전용 work-audit 소유 컨테이너1개로 files0/bytes0을 확인했다.
정확한 이름 allowlist+owner+idle 확인 후 총12개 소유 컨테이너와 이번 data/work volume·internal network를 정리했다.
성공 중간 영상·100초 준비 영상은 남기지 않았다. 필요한 실패 JSON/code snapshot·작은 재현·controls·표본만 ignored scratch에 보존했다.

종료02:26:16 KST 원본15/15 SHA-256·size·mtime 불변. Windows available5,579,571,200B,
C free13,233,516,544B는 종료 순간값이다. 최종 source/기존 runner·보존 volume·Docker 목록은 종료 검사에 함께 보존한다.
공개 변경은 이 문서+신규 harness1개+test1개(총3파일)뿐이며 미커밋·미스테이징으로 마친다.
commit/push/PR/외부 댓글/provider/AWS/배포/운영 migration·큰 backup/restore는 실행하지 않았다.
