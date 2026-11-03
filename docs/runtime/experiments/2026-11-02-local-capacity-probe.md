# #452 로컬 격리 capacity probe — 2026-11-02

상태: 로컬 subset 측정 종료 — 예상 거부/Recording 검증 실패/DB packet 실패 확인,
packet 대조 중 감독 실패·전용 MySQL OOM으로 추가 부하 중단. 운영값 승격·20분 지원·제품 acceptance 완료가 아니다.
담당: 정철원(Runtime/Recording). 사용자 승인 범위의 로컬 실험이며 provider 호출은 차단했다.

## 근거와 실행 경계

- 제품 checkout: `codex/issue452-capacity-probe`, HEAD
  `ea2bc5e3d6be67b308b25073c7d36c29510bd135`. 시작 working tree/staging은 비어 있었다.
- [Issue #452](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/452)의 본문/9개 댓글과
  [PR #530](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/pull/530)의 본문/최신 댓글을 읽었다.
  #530은 미병합이며 계획·감사 문서는 원격 HEAD
  `fdcccfa966af2c82db4d6f68c81c42706ed456a2`로 고정해 읽었다.
  [계획](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/fdcccfa966af2c82db4d6f68c81c42706ed456a2/docs/runtime/experiments/elice-runtime-capacity-smoke-plan.md),
  [감사](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/blob/fdcccfa966af2c82db4d6f68c81c42706ed456a2/docs/runtime/reviews/runtime-p2-plan-audit-2026-11-02.md).
  타인의 계획과 #527 브랜치는 변경하거나 가져오지 않았다.
- [설정 명세](../../management/environment-and-deployment-config.md#3-recording-초기-배포-baseline-v1)와
  [AnalysisSource 한도](../../modules/recording/analysis-source-limits.md)를 실행 입력으로 사용했다.
  Analysis `480/veryfast/CRF23`, `50331648 bytes/240000 ms`를 **로컬에서 명시**했다.
  Incident `720/veryfast/CRF20`은 기존 운영자 보고이며 이번에 실행하지 않았다.
  운영 서버/config/credential/AWS를 조회하지 않았다.
- 원본 15개는 기존 비공개 manifest를 재사용했다. 합계 `1,771,439,266 bytes`, metadata 길이 합계
  `1,584.173332초`. H.264/1080p, VIDEO index 0, time base `1/30000`.
  파일명 순서는 잠정이며 같은 전방 카메라/연속 주행은 사용자 확인이다.
  **실제 촬영 seam/gap 독립 검증은 NOT_RUN**이다. metadata 길이를 누적한 명시적 placement는
  capacity 후보 입력이며 물리적 연속성의 검증 결과가 아니다. 반복 영상/길이 올림은 사용하지 않았다.
- 기존 8.1 decode 성공/진단 기록을 재사용했다. decode 성공을 Recording coverage/concat 성공으로 바꾸지 않았다.

## 코드·도구·격리

재사용 image ID는 `sha256:f76274a9b66b8fcdde51d88d34cfb221c7667e756ac237daaa21ff3cabcd140f`다.
image의 revision 표시는 `local`이며 정확한 내장 git SHA는 확인할 수 없다.
내장 코드와 현재 코드에는 Recording/Search를 포함한 차이가 있으므로 **현재 checkout의 `src`를
read-only mount하고 `PYTHONPATH`로 우선 사용**했다. 이미지 내장 코드를 현재 HEAD라고 간주하지 않았다.
현재 source 202개 Python 파일의 경로+내용 hash 집계는
`3d91fb6120bab2ce4e0ea650cd8ff98d9d4fa8a9b06858bc0af9920a694ce1a0`다.

FFmpeg/ffprobe는 둘 다 **8.1**, 동일 이미지의 `media-preflight`도 exit 0이다.
Windows 9.0.1을 대체 증거로 사용하지 않았다.
실제 image 라이브러리는 PyMySQL `1.2.3`, SQLAlchemy `2.1.3`, psutil `7.2.2`,
OpenAI SDK `2.54.0`, pydantic `2.13.5`다.

| 경계 | 실제 방식 |
|---|---|
| Recording | 실제 `register_local_source`, 명시 placement, `resolve_span`, `build_recording_service`, `prepare_analysis_source_from_resolution` |
| phase | 기존 `capture_materialization()` + runner의 개별 materialize/chain/tool/publish observer. 반환값·검증 기준·FFmpeg 옵션은 유지 |
| 저장 | 실제 `MySQLRecordingRepository.add_prepared_media`; arbitrary BLOB 삽입 대체 없음. 새 service로 DB content 읽기 + SQL SHA2/길이 대조 + caller rollback |
| Search | DB에서 읽은 실제 content의 `MediaInput` → 실제 `MediaPreparer.prepare_coarse` → 실제 `GeminiProvider.search_coarse`/prompt/base64/JSON guard |
| 전송 중단 | 인증 SDK를 만들지 않고 SDK `parse` 진입에 sentinel을 주입. sentinel을 관측해야 PASS. SDK JSON/schema 직렬화·HTTP/wire·provider는 NOT_RUN |
| DB bytes | PyMySQL `_execute_command`와 `_write_bytes`의 실제 인자 길이만 관측. SQL/영상/base64/request payload를 저장하지 않음. write buffer bytes는 TCP wire/driver allocation 측정이 아님 |
| network | 소유 label의 internal Docker network, 공개 port 없음. 원본/manifest/source ro. 추가 socket allowlist는 전용 DB IP:3306만 허용. API key/운영 secret 없음 |
| 범위 밖 | 실제 API ingest, ProductionMediaFactory 전체, Search resolver/coarse orchestration/Run 저장, Worker queue·heartbeat·T1/T2·Case/Web·OCR·탐색 품질은 NOT_RUN |

Search source/media/request cap은 `512/40/56 MiB`, 준비 budget은 `150초`로 유지했다.
provider request는 Coarse prompt를 사용하는 module probe이며 실제 Case의 intent/event_types를 재현한 요청이 아니다.
guard JSON 크기는 SDK가 schema 등을 추가한 실제 HTTP body 크기와 구분한다.

## 자원 예산과 관측 한계

시작 호스트 RAM: total `16,281,024 KiB`, available `3,018,404 KiB`.
C free `8,590,028,800 bytes`. Docker limit `8,072,286,208 bytes/18 CPU`, 기존 컨테이너/volume 0개였다.
운영 EC2 동등 환경이나 API/Worker/OCR/MySQL 동시 구성이 아니다.

| 항목 | 로컬 안전값·근거 |
|---|---|
| 동시 실행 | probe 1개, CPU 1.5/RAM 1280 MiB; DB CPU 0.5/RAM 512 MiB, swap 추가 허용 없음. 합계 1.75 GiB는 시작 가용 RAM보다 약 1.1 GiB 작음 |
| DB | 소유 volume, buffer pool 64 MiB, redo 32 MiB, connections 5, binary/general/slow log OFF, 공개 port 없음 |
| 중단 | C reserve 4 GiB, run 중 disk 증가 2 GiB, DB data 1 GiB, host available RAM 700 MiB, 전체 900초. 신규 run은 C 6 GiB/RAM 2100 MiB 미만이면 시작하지 않음 |
| 도구 | Recording 도구당 120초, Search 준비/guard 150초 |
| soft stop | probe cgroup 1100 MiB 또는 temp 512 MiB에서 marker/checkpoint. host 감독기가 다음 polling에서 소유 worker만 중단. 감지·Docker 호출·5초 stop 유예 중 overshoot 가능. 하드 디스크 quota 아님 |
| 표본 | Linux `time.monotonic` seconds, 200ms Python/자식 RSS·자식 CPU 누적·cgroup memory.current·temp. host는 별도 monotonic/2초 대기+Docker 호출 시간, C/RAM/Docker stats/DB data |

RSS는 공유 페이지 등을 포함하며 cgroup와 정의가 다르다. 표의 최대값은 sampled max이고 실제 HWM이 아니다.
짧은 peak·짧게 생존한 자식·sampling 지연은 누락 가능하다. DB driver allocation/OS wire bytes는 NOT_RUN.
focused controls는 helper/marker/journal을 동적으로 검증했다. 감독기의 timeout/stop 실패·실제 process kill은
추가 동적 재검증하지 않았고 예외 경로를 독립 읽기 리뷰로 확인했다. OOM/ENOSPC를 목표로 부하를 만들지 않았다.
`docker stop` 자체가 daemon 장애로 실패하면 Docker CLI 종료만으로 컨테이너 중단을 보장할 수 없다.
그 경우 실제 container state 확인이 필요하다. 이번 probe의 실제 종료와 최종 소유 컨테이너0은 별도로 확인했다.

## 실행 결과

실행별 runner hash·config hash·input ID·image/tool·monotonic phase·단위·표본은 비공개 evidence에 묶었다.
원본 filename/path·영상·SQL/request 원문·credential은 이 문서에 넣지 않았다.
실패한 run을 이후 설정/runner 변경의 성공으로 재분류하지 않았다.

| evidence ID | 입력/설정 | 실제 결과 |
|---|---|---|
| short01 | input-02의 10초, baseline | harness FAIL: 새 temp volume root 소유/UID10001 쓰기 불가. source probe 뒤 encode 미도달. volume root의 소유권만 수정 |
| short02 | 같은 10초 | runner FAIL: fingerprint property를 함수 호출. Recording 4,247,576 B 저장/새 service hash/rollback은 PASS, Search NOT_REACHED |
| short03 | 같은 10초 | 준비 PASS, SDK 직전 중단. Recording 4,247,576 B, Search 904,476 B, base64 1,205,968 B, guard JSON 1,209,631 B |
| baseline-over | input-01~03, 240.001초 | resolve COMPLETE/3 span; 예상 `ANALYSIS_SOURCE_SIZE_LIMIT_EXCEEDED`, encode/concat/BLOB/Search NOT_REACHED |
| baseline-exact | input-01~03, 240초 | FAIL: 첫 구간 encode 25,865,650 B 뒤 output_validate의 `_FrameCoverageError/UNSUPPORTED_MEDIA`. 준비 80.095초. concat/BLOB/Search NOT_REACHED |
| baseline-multi | input-02→03, 100초, 64 MiB packet | parts 33,340,577 + 5,019,442 B; concat·3000 frame 검증·decode PASS; 최종 38,359,627 B. 실제 publish `OperationalError`; driver command 76,721,052 B > packet 67,108,864 B; Aborted_clients 0→1. Search NOT_REACHED |
| experimental-packet | 같은 100초, Recording 한도 불변, DB만 128 MiB packet | FAIL/미검증: 감독 Docker 조회 `TimeoutExpired` 뒤 소유 probe 중단(exit137/OOMKilled=false). 전용 MySQL도 이후 exit137/OOMKilled=true. 최종 runner 결과 없음. 저장/재조회/rollback/Search 도달 여부 UNKNOWN |

실제 8분/10분/20분 duration override와 byte=1 encode negative control은 **NOT_RUN**이다.
앞 단계의 검증 실패와 예상 밖 OOM/감독 실패 뒤 중단했으며 처음부터 26분을 변환하지 않았다.
이유가 확인되지 않은 실패를 지우거나 RAM/packet을 더 늘려 진행하지 않았다.

baseline-multi는 준비 137.65초, publish 실패 0.51초다. 48 MiB보다 작은 최종 영상을 DB가 저장하지 못했다.
PyMySQL 1.2.3의 실제 `escape_bytes`는 `_binary X'…'` 안에 `value.hex()`를 넣는다.
**관측 command byte가 BLOB의 약 2배**라는 결과와 일치한다. SQL 문자열·packet buffer 할당량이나 TCP 전송량을
이 비율로 측정했다고 주장하지 않는다. 이 run의 driver errno는 계측되지 않았으므로 2006으로 단정하지 않는다.
rollback 뒤 prepared 행 0/ping 1은 확인했지만, Aborted 증가 뒤의 ping은 재연결 가능성을 포함하며 원래 연결 유지 증거가 아니다.

실패 뒤 신규 부하를 멈추고 driver/packet 원인을 확인했다. 전용 DB만 `64→128 MiB`로 바꾸고
새 연결의 global/session `134,217,728 bytes`를 확인했다. 이는 관측 command 약 76.7 MB에 대한 유한한 대조이며,
Recording 48 MiB/4분·Search cap은 유지한다. baseline 실패를 덮어쓰지 않는다.

## 판정·잔여·종료

### 최초 병목과 다음 판단

| 관측 범위 | 판정 |
|---|---|
| 현재 4분 정책 | 240.001초는 준비 0.00161초에 typed 거부. 실제 22개 fixture의 Runtime/Case notice regression 전체를 수행한 것은 아님 |
| 확보 원본 prefix | 첫 구간의 encode 뒤 output coverage 검증이 가장 먼저 실패. decode exit0/같은 time base만으로 연결 가능을 판단할 수 없음. encoder clock/원본 frame의 세부 원인은 아직 미확정이며 별도 최소 재현 후속 |
| 검증을 통과한 다른 100초 chain | 최종 38.36 MB < 48 MiB인데 실제 driver command 약76.72 MB > DB64 MiB. 저장이 최초 실패 지점. BLOB 한도+고정 margin만으로 전송 여유를 증명하지 못함 |
| packet128 MiB 대조 | 안전한 성공 후보로 승격 불가. 감독 timeout과 DB OOM, 최종 phase 증거 부족을 먼저 해결해야 함. DB OOM이 probe 중단을 먼저 유발했다고 단정하지 않음 |
| 20분 | **미달/미검증**. duration 확장 media probe는 앞 단계 실패/자원 사건 뒤 미실행. Search40/56MiB cap에 실제 긴 prepared media를 넣은 결과도 없음 |

다음 단계는 **운영 설정 후보 승격이 아니라 Recording timing 최소 재현과 Runtime·Recording·DB의
저장/driver working set·감독 관측 보완 검토**다. 장시간은 Search request·Case 대기와 함께
cross-module 설계 검토로 연결해야 한다. bounded/chunked processing·storage 분리 등 방식은 아직 채택하지 않았다.
이번 표본만으로 구조 전체의 20분 성공/불가능이나 운영 packet/RAM 최적값을 확정할 수 없다.

### 자원 표본과 정리 증거

아래는 모두 bytes 단위의 sampled max다. CPU 누적/개별 표본은 보호 evidence에 남겼다.

| run | probe Python RSS | ffmpeg RSS | ffprobe RSS | probe cgroup | temp |
|---|---:|---:|---:|---:|---:|
| short03 | 102,064,128 | 257,232,896 | 25,755,648 | 301,760,512 | 5,152,052 |
| baseline-exact | 73,535,488 | 263,352,320 | 25,939,968 | 330,440,704 | 25,865,650 |
| baseline-multi | 344,473,600 | 260,608,000 | 25,829,376 | 338,685,952 | 76,719,749 |

short03의 DB publish/read는 `0.13606/0.09696초`, Search 준비 `1.56222초`,
base64 `0.00119초`, JSON serialization `0.00208초`였다.
baseline-multi의 가장 큰 command에 대해 실제 `_write_bytes` 인자 합계는 `76,721,073 bytes/5 calls`였다.
이는 Python driver의 쓰기 buffer 길이 관측이며 wire bytes가 아니다.

최종 report가 있는 6개 run은 모두 unwind 뒤 temp0/자식0/rollback prepared 행0이다.
baseline-multi의 Aborted 증가와 연결 손실은 별도 실패로 남겼다.
experimental-packet은 마지막 저장된 host 표본에서 probe `170.8 MiB`, MySQL `253.7 MiB`였고
그 뒤 Docker 조회가 timeout됐다. 이 마지막 표본을 MySQL peak나 OOM 직전 RSS라고 쓰지 않는다.
최종 report/phase가 없으므로 이 run의 rollback·정리 성공을 추정하지 않는다.
종료 후 독립 read-only volume 점검에서 work files0/bytes0은 확인했다.

종료 순서는 Docker state를 KST로 변환하면 probe `2026-11-02 19:14:55.065790709`,
MySQL `2026-11-02 19:15:07.956040677`이다. 정확한 MySQL OOM 내부 phase와
어느 Docker 조회가 timeout됐는지는 UNKNOWN이다.

이 관측 공백 때문에 runner에 **phase/sample/driver byte JSONL의 즉시 flush**를 추가했다.
감독기가 post-run DB 조회 실패에도 이미 수집한 host evidence를 보존하도록 보완했다.
이 마지막 보완본은 focused tests로 검증했으며 **실영상/DB 재실행은 하지 않았다**.
따라서 앞선 run의 runner hash를 마지막 보완본 실행 증거로 사용하지 않는다.

최종 원본 전체 15개의 SHA-256/size/mtime을 manifest와 한 번 대조해 **15/15 불변**을 확인했다.
원본 mount는 모든 probe에서 ro였고 대량 사본을 만들지 않았다.

### 변경 파일·검증

- 신규 [측정 runner](../../../scripts/recording_capacity_probe.py)
- 신규 [focused controls](../../../tests/runtime/test_capacity_probe.py)
- 신규 이 측정 결과 문서
- ignored scratch: 실행 ledger, 로컬 host 감독기, code/source audit·집계 도구,
  run별 private 결과/host 표본/실패 로그/postmortem/단위검증 산출물. 원본/manifest는 기존 위치 보존.

직접 focused controls **8 PASS**, 해당 두 Python 파일의 Ruff와 `git diff --check` PASS.
실패 전파·진단 비노출·sentinel 정상 반환 오인 거부·driver hook 복원·원본 stat 불일치·
soft-stop marker·frame gap 집계·실패 journal 보존을 negative control로 확인했다.
전체 pytest/mandatory MySQL suite는 수행하지 않았다. 제품 source·운영 config 변경은 없다.

독립 reviewer는 read-only로 runner/감독기/실행 결과를 검토했고 초기 4개→6개 control을 직접 재실행했다.
sentinel 필수 판정, Search soft-stop 감시, context cleanup, 감독 예외 시 소유 process 중단을 지적해 반영했다.
최종 reviewer가 별도 temp에서 8개 control을 직접 재실행해 **8 PASS**를 확인했고,
runner/감독기/결과 문서와 byte·실패·종료 순서를 추가 읽기 검토했다.
실영상·원본·DB·Docker·provider는 reviewer가 재실행하지 않았다.

### 종료 확인

작업 소유 컨테이너 8개, internal network, 비어 있는 work volume을 owner label/idle/잔여0 확인 뒤 정리했다.
소유 컨테이너는 0개 남았고 공유 Docker/WSL 재시작·prune·기존 image/cache 삭제는 하지 않았다.
실패한 전용 DB volume은 재시작/파기하지 않고 보호 evidence로 보존한다.
read-only file stat 기준 `108,019,857 bytes`이며 논리 파일 크기와 Docker disk allocation은 다를 수 있다.
남은 volume은 `issue452-capacity-db`이고 owner label은 `issue452-capacity-probe`다.
종료 확인(2026-11-02 19:35 KST)에서 C free `8,652,570,624 bytes`,
host available RAM `1,921,360 KiB`였다. 이는 순간 관측이며 이후 가용량을 보장하지 않는다.
브랜치/HEAD는 시작과 같고 신규 공개 파일 3개만 untracked/unstaged다. staging은 비어 있다.
commit/push/PR/외부 댓글/merge는 하지 않았다.

20분 이상 실제 처리 성공은 아직 없고 최소 20분 목표는 **미달/미검증**이다.
전체 26분 변환, 실제 22개 이슈 fixture 재현, 촬영 seam/gap 검증도 미실행이다.
현재 자료를 N분 지원 길이, Search 탐색 품질, Case/Web E2E 성공으로 확대하지 않는다.

후속: [2026-11-03 #544 이후 재검증](2026-11-03-chunked-capacity-recheck.md)은
disk/RAM 부족으로 두 차례 시작 전 중단한 뒤, 자원 확보 후 합성38,359,627B의 저장·분할 조회·rollback 대조를 통과했다.
실영상 재encode/decode·20분 탐색·큰 복원 검증은 아니다. 이 문서의 실패·UNKNOWN은 보존한다.
