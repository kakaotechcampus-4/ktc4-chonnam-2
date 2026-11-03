# 후보 영상 실제 통합 테스트 계획

> **For agentic workers:** 실행 시 superpowers:executing-plans를 적용한다. 이 문서는 실행 계획이며, 아래 체크박스는 아직 실행한 결과가 아니다.

**Goal:** 사용자가 실제 화면에서 후보 영상을 요청하고, 별도 API/Worker 프로세스와 MySQL에 생성 결과가 저장되며, 새 프로세스와 브라우저에서도 선택 변경 없이 재생되는 것을 확인한다.

**Architecture:** Linux의 전용 MySQL 8.4·media volume에서 실제 Case/Worker/Recording 조립을 사용한다. 후보 수와 장애를 고정하는 통합 테스트는 외부 AI HTTP 응답만 통제하고, 마지막에는 실제 영상과 live provider를 거치는 사용자 흐름을 별도로 확인한다.

**Tech Stack:** 기존 pytest/MySQL harness·SQLAlchemy fault proxy·FFmpeg·API/Worker CLI, 빌드된 Web·Caddy·Playwright 브라우저 도구.

**Spec:** `docs/modules/case/decisions/candidate-video-preview.md`

**현재 증거:** `docs/runtime/candidate-video-preview.md`. 기존 브라우저 검증은 메모리 저장소를 썼다. 이번 계획의 MySQL·재시작·TCP 검증을 대신하지 않는다.

## Global Constraints

- rank 1~3만 영상 대상이다. 후보 0/1/2/3/5개, 빈 카드 없음, 무효 후보를 4위로 채우지 않음을 확인한다. 후보가 5개면 카드 5개를 유지하고 영상 대상만 최대 3개다.
- 영상 요청만으로 선택 후보·selection_rev·상황 응답·사용자 보정·신고자료가 변경되거나 Fine/OCR/export가 새로 발주되면 실패다.
- MySQL, Case 저장소, enqueue/claim, preview handler, Recording/FFmpeg, T1/T2, 영상 loader를 대역으로 교체하지 않는다. 관측·fault injection은 원래 호출을 감싼다.
- 통합 단계의 외부 AI 고정 응답과 실제 AI 검증을 별도 결과로 기록한다. 고정 응답으로 실제 AI 정확도를 검증했다고 하지 않는다.
- API는 실제 TCP listener다. 기존 `tests/e2e_runtime/production_processes.py::api_peer`는 TestClient를 쓰므로 이번 TCP 증거로 그대로 재사용하지 않는다.
- 필수 시나리오의 skip/xfail/미수집/timeout은 통과가 아니다. MySQL이 없으면 환경 미준비로 기록한다.
- 운영 DB·운영 media를 사용하지 않는다. 격리한 테스트 자원만 정리하고 기존 Compose 프로젝트/volume은 건드리지 않는다.

## Review Focus

1. **단일 후보의 재생 입구:** `ResultScreen.tsx`의 비교 버튼, `NotObservedScreen.tsx`·`FailedScreen.tsx`의 후보 영역이 현재 `others > 0` 조건이다. 후보 1개일 때 실제 사용자가 영상에 도달할 수 있는지 최우선으로 재현한다. 단독 컴포넌트에서 카드가 렌더된다는 사실로 대체하지 않는다.
2. **생성 재사용과 인코딩 횟수:** ref/파일 개수가 같아도 재인코딩이 있었을 수 있다. handler 호출과 실제 incident encode 호출을 함께 계수한다.
3. **재시작 시점별 복구:** T1 전 중단과 T1 후/T2 전 중단을 구분한다. T1 전 재인코딩은 허용되지만 T1 receipt replay/T2 재전달은 추가 인코딩 0회여야 한다.
4. **이전 세대와 소유권:** 이전 job이 끝날 수 있다는 현재 정책을 유지하되, 이전 ref/다른 Case ref로 새 화면이나 HTTP bytes를 받을 수 없어야 한다.
5. **실제 프로세스와 연결 수명:** 인코딩 중 Worker pool checkout 0, API 저장 stream 종료·DB 반환 후 HTTP body 전송을 관측한다. 정상 화면만 보고 통과시키지 않는다.

## 실행 순서와 산출물

### 1. 환경과 소스 고정

**사용할 기존 파일:** `compose.yaml`, `docker/runtime.py`, `deploy/Caddyfile`, `docs/runtime/local-runtime-environment.md`, `tests/mysql_harness.py`.

**추가할 파일:** `tests/deploy/candidate_video.compose.yaml` (테스트 전용 DB/port/volume override), `tests/e2e_runtime/candidate_video_process.py` (실제 TCP API와 Worker 실행·종료·관측).

- [ ] Docker가 가능한 Linux host/CI를 주 실행 환경으로 정한다. Windows의 기존 symlink/각인 문제와 기능 결함을 혼합하지 않는다.
- [ ] 실행 ID, base SHA, 변경·미추적 소스까지 포함한 파일 해시 manifest, image ID/digest, Python/FFmpeg/ffprobe/MySQL/Web 빌드 버전을 기록한다. 현재 코드는 미커밋이므로 `git rev-parse HEAD` 하나만으로 변경 내용을 식별하지 않는다.
- [ ] 고유 Compose project와 테스트 DB/media/temp를 만든다. `DAESINGO_MYSQL_URL`은 `test`가 포함된 폐기 가능한 DB를 가리키며, 기존 harness의 per-test schema 생성 권한을 충족한다. 서비스 URL인 `DAESINGO_RUNTIME_DB_URL`과 구분한다.
- [ ] credential은 보호 파일/환경에서 읽고 argv·보고서에 출력하지 않는다. 테스트 실행에 필요한 값이 없으면 해당 단계는 미실행으로 남긴다.
- [ ] MySQL healthy → migration exit 0 → media/readout preflight → API/Worker 시작 순서를 따른다. 기본 production Worker의 실제 OCR 초기화도 확인한다.
- [ ] `CANDIDATE_VIDEO_PREVIEW`를 포함한 실제 registry 9종을 확인한다. 기존 실행환경 문서의 ‘8종’ 표기는 현재 코드의 `worker/deployment_status.py::EXPECTED`와 다르므로 실행 증거는 현재 registry 기준으로 남긴다.
- [ ] `npm run build --workspace=daesingo-web` 산출물을 테스트용 Caddy에서 서비스한다. `deploy/Caddyfile`의 `/cases*` reverse proxy와 정적 Web 구성을 유지하고 테스트 host/port/root만 바꾼다. Range가 proxy를 통과하는지 확인한다.

**통과 기준:** 실제 listener PID/주소, 준비 상태, DB/media 식별, 9종 registry, 소스 manifest가 모두 기록된다. 메모리 QA 서버와 개발 Web만 띄운 상태는 이 단계 통과가 아니다.

### 2. MySQL에서 후보 수·요청·자료 보존 확인

**추가할 파일:** `tests/worker/test_candidate_video_mysql.py`, `tests/e2e_runtime/candidate_video_support.py`.

**재사용할 접점:** `tests/worker/test_worker_mysql.py::queue`, `tests/worker/test_incident_clip_mysql.py`의 실제 영상·T1/T2 계수 방식, `worker/composition_root.py::compose_registry`, `worker/case_composition.py::StoredCaseReflector`.

**입력:** 시간 위치를 판별할 수 있는 12초 합성 MP4, 한글 파일명 AVI, 앞/뒤 파일 경계를 넘는 연속 구간. 원본 SHA와 후보 구간을 고정한다. 공개 업로드/분석 경로를 이용하고 후보 0/1/2/3/5개는 외부 provider HTTP 응답 경계에서 만든다.

| ID | 조작 | 필수 단언 |
| --- | --- | --- |
| DB-01 | 후보 0/1/2/3/5개 생성 후 view 조회 | 카드 수는 입력 수 그대로, 영상 허용 대상은 각각 0/1/2/3/3 |
| DB-02 | rank 1~3 각각 영상 요청 | 해당 preview job만 발주되고 DB의 고정 입력에 후보·세대·span·stream이 일치 |
| DB-03 | rank 4/5, stale, span 없음, 다른 Case 후보 요청 | 거부, 새 job/encode 없음, 다른 카드 유지, 4위 보충 없음 |
| DB-04 | 같은 후보 동시 요청·연타 | 동일 revision 경합의 409는 현재 view 반영 후 판단. 진행 중에는 유효 job 1개, 성공 후 새 revision으로 재요청해도 job/encode 증가 없음 |
| DB-05 | 후보 2/3 동시 요청 | 둘 다 완료하며 서로 supersede하지 않음 |
| DB-06 | 준비 전/준비 중/성공 후 새 DB connection으로 조회 | PREPARING→READY, produced와 Case 반영·clip metadata/bytes가 일치 |
| DB-07 | 준비된 신고자료가 있는 Case에서 재생만 요청 | before/after의 선택·selection_rev·상황 응답·보정 값·evidence/package 내용 동일. preview용 case_rev·running_jobs 변경은 허용 |
| DB-08 | 선택 후보의 관찰과 preview 병행 | preview 대기로 Fine 발주/재선택이 추가 차단되지 않으며 preview T2에서 OCR/export 후속 발주 0개 |
| DB-09 | 단일 원본과 연속 파일 경계 구간 생성 | 실제 MP4 decode 성공, 요청 후보의 원본 구간/lineage 일치, 다른 후보 장면과 혼동 없음 |

**초기 상태 구분:** NOT_OBSERVED Case와 자료가 준비된 Case를 각각 둔다. 후자는 실제 공개 command로 상황 응답·필요한 값 보정을 완료한 상태를 사용한다. 재현 가능한 자료 fixture seed를 보조 테스트에 쓰면 그 결과를 전체 사용자 흐름 검증과 구분한다.

**통과 기준:** 모든 필수 ID가 실제 MySQL에서 실행되고 job/produced/Case/Recording 연결이 일치한다. encode 중 pool checkout은 0이다.

### 3. 재시작·장애·이전 세대 격리

**추가/확장할 파일:** `tests/worker/test_candidate_video_mysql.py`, `tests/e2e_runtime/test_candidate_video_process_mysql.py`, `tests/e2e_runtime/candidate_video_process.py`.

**재사용:** `tests/mysql_fault_proxy.py::CommitResponseProxy`, `common/jobs/redelivery.py::redeliver_once`, 기존 incident clip의 rollback/receipt 검증 방식.

| ID | 중단/장애 시점 | 통과 기준 |
| --- | --- | --- |
| RC-01 | 성공 후 API/Worker를 완전히 종료하고 새 PID로 시작 | 기존 CaseView/ref/bytes hash 동일, 재생 가능, 추가 인코딩 0회 |
| RC-02 | 인코딩 완료 후 T1 receipt commit 전 Worker 강제 종료 | lease/STALE 정책으로 복구. 새 attempt의 재인코딩 가능, 성공 receipt/ref 연결은 일관적이며 Case 후속 발주 없음 |
| RC-03 | T1 rollback·COMMIT 응답 손실 | 실제 fault 발생 증거와 복구 receipt 확인. 확정된 동일 receipt를 재생성/중복 반영하지 않음 |
| RC-04 | T1 성공 후 T2 직전 중단, T2 rollback·redelivery | 최종 READY, 추가 handler/encode 0회, 반영 1회 |
| RC-05 | 후보 2의 생성 실패 뒤 후보 3 재생·후보 2 재요청 | 실패는 해당 카드만. 명시적 재요청은 새 job으로 성공할 수 있고 기존 신고자료 유지 |
| RC-06 | preview 실행 중 새 탐색 세대 또는 span 변경, 이후 이전 결과 도착 | 이전 job은 끝나도 새 view에 ref가 섞이지 않고 이전 ref 조회 404. 새 후보 요청은 정상 동작 |
| RC-07 | 원본 소실·저장 clip bytes 소실/손상·일시 DB 단절 | 정해진 404/503과 복구 동작, 가짜 READY/무한 준비 없음. 사용자 요청 없는 자동 생성 없음 |

인코딩 계수는 테스트 관측 wrapper/child report로 남기며 실제 materializer를 대체하지 않는다. 프로세스 내 monkeypatch만으로 검증한 항목은 별도 프로세스 crash 증거라고 표기하지 않는다.

### 4. TCP HTTP·브라우저 사용자 흐름

**추가할 파일:** `tests/api/test_candidate_videos_mysql.py`, `tests/e2e_runtime/test_candidate_video_process_mysql.py`.

**참고:** `tests/api/test_assets_mysql.py`의 소유권·다른 connection·저장 stream/transaction 종료 검증. 기존 `/assets` 다운로드 의미는 유지한다.

| ID | 실제 요청/동작 | 통과 기준 |
| --- | --- | --- |
| HTTP-01 | API 직접 GET과 Caddy 경유 GET | 같은 저장 MP4 bytes/hash, video/mp4·inline·private/no-store·Accept-Ranges |
| HTTP-02 | closed/open/suffix Range, 범위 초과, malformed/multipart, If-Range | 계약대로 206·정확한 Content-Range/길이, 416, 또는 전체 200. proxy 경유도 같음 |
| HTTP-03 | 다른 Case·unknown·이전 세대·소유 원본 불일치 ref | 404, bytes/내부 경로/예외 정보 노출 없음 |
| HTTP-04 | 반복 GET·Range·새로고침, 전송 중 취소/프로세스 종료 | GET으로 encode 증가 없음. stream/DB 반환 확인, 다음 재생 가능 |
| UI-01 | 후보 0/1/2/3/5개로 실제 결과/미관찰/실패 화면 진입 | 0개는 빈 결과, 1개도 사용자가 재생 가능한 입구 존재, 나머지는 있는 카드만. rank 4/5가 영상 대상이 되지 않음 |
| UI-02 | 영상 보기 → 준비 중 → native 재생/일시정지/중간 탐색 | 실제 currentTime 증가·seek 완료, 화면이 신고자료 진행 화면으로 바뀌지 않음 |
| UI-03 | 후보 2 재생 중 후보 3 재생, 키보드 조작 | 후보 2 정지, 후보 3만 재생, 선택은 별도 버튼을 눌렀을 때만 변경 |
| UI-04 | 생성 실패·실제 media 요청 실패 → 재시도 | 해당 카드 오류/복구, 다른 카드/선택 버튼 정상, 브라우저 재조회만으로 재인코딩 없음 |
| UI-05 | 새로고침·새 브라우저 탭·서버 재시작 후 같은 Case 열기 | 저장된 READY 영상 재생, 추가 생성 없음 |
| UI-06 | 375/768/1280px | controls·버튼·한글 문구가 잘리지 않고 가로 넘침 없음 |

**단일 후보 보류 조건:** UI-01에서 재생 입구가 숨겨지면 기능 결함으로 처리하고 수정 후 해당 사용자 흐름을 다시 검증한다. 테스트 전용 페이지나 URL 강제 진입만으로 사용자 접근성 통과를 선언하지 않는다. 신고용 결과 영상 #519의 완료를 대신 요구하지는 않는다.

### 5. 실제 영상 최종 확인·CI·결과 봉합

- [ ] 사용 권한이 확인된 실제 블랙박스 영상 1건을 지정하고, 원본 hash·선택 구간·파일 크기만 증거로 남긴다. 아직 입력 파일이 정해지지 않았다면 실제 영상 항목은 미실행이다.
- [ ] 실제 provider credential과 기존 비용 상한이 준비된 환경에서 업로드→분석→결과→후보 영상→후보 선택까지 1회 수행한다. live AI 항목을 실행할 수 없으면 고정 응답 테스트 성공과 구분하여 기록한다.
- [ ] 번호판/시각처럼 사용자가 확인하는 값과 신고자료가 재생만으로 바뀌지 않는지 전후 대조한다. 실제 결과와 AI 정확도 평가는 구분한다.
- [ ] 필수 새 MySQL 시나리오 ID/parameter를 `scripts/check_mysql_test_report.py`의 REQUIRED_CHECKS/REQUIRED_PARAMETERS와 독립 기대 목록인 `tests/common/db/integration/test_migration_gate.py`에 등록한다. 기존 MySQL harness/orchestrator를 사용하고 별도 느슨한 ‘초록’ 집계기를 만들지 않는다.
- [ ] Linux CI의 quality/regression/mysql/필수 종합 결과와 새 브라우저 증거를 같은 소스 manifest에 묶는다. 이 문서에서는 workflow dispatch·commit·push·배포를 실행하지 않는다.
- [ ] 실패를 수정했다면 영향을 받는 시나리오와 관련 회귀를 재실행한다. 한 번의 실행 결과와 여러 번의 최종 결과를 합산하여 전체 suite 성공이라고 쓰지 않는다.

## 실행 명령과 증거

아래 MySQL 전용 파일은 **이 계획의 실행 단계에서 만들 파일**이다. 보호된 테스트 DB 설정을 준비하고 저장소 루트에서 실행한다. URL/password는 명령 인자로 넣지 않는다.

```sh
# Linux: 기존 잠금 의존성과 실제 미디어 도구 준비 후
uv sync --locked --extra test --extra eval-gemini --extra quality
PYTHONUTF8=1 DAESINGO_REQUIRE_MYSQL=1 uv run --no-sync pytest \
  -p tests.mysql_harness \
  tests/worker/test_candidate_video_mysql.py \
  tests/api/test_candidate_videos_mysql.py \
  tests/e2e_runtime/test_candidate_video_process_mysql.py \
  --mysql-report=.omo/evidence/candidate-video-real/focused-mysql.json \
  --junitxml=.omo/evidence/candidate-video-real/focused-mysql.xml

npm run test:web
npm run build --workspace=daesingo-web
PYTHONUTF8=1 uv run --no-sync python scripts/check_runtime_quality.py
PYTHONUTF8=1 uv run --no-sync python scripts/check_boundaries.py

# 정식 전체 CI와 같은 분할/증거 검증. MySQL gate를 bare pytest로 따로 부르지 않는다.
uv run --no-sync python -m tests.ci_orchestration regression .omo/evidence/candidate-video-real/regression.xml
uv run --no-sync python -m tests.ci_orchestration mysql .omo/evidence/candidate-video-real/canonical-mysql
```

실행마다 고유 run directory를 만들고 명령의 예시 경로를 그 위치로 바꾼다. 디렉터리는 테스트 전 생성한다. full MySQL의 strict 검사에는 focused 결과를 넣지 않는다.

보관할 증거: 소스/image manifest, PID와 재시작 전후 기록, 테스트 이름별 PASS/FAIL/NOT_RUN, JUnit/MySQL 보고서, 최소 DB 전후 snapshot, clip hash·encode 계수·pool 관측, TCP/curl 헤더, 브라우저 trace/스크린샷·console, 정리한 테스트 자원 목록. 원본 영상·보호 설정·raw provider payload는 공유 증거에 포함하지 않는다.

## 최종 통과·중단 기준

- 환경·DB-01~09·RC-01~07·HTTP-01~04·UI-01~06을 모두 실행하고 통과해야 실제 통합 완료다. 중요 실패를 알려진 기존 실패 목록에 끼워 넣지 않는다.
- 실제 영상/live provider 확인은 별도 결과를 남긴다. 미실행이면 ‘실제 사용자 영상 전체 흐름까지 완료’라고 하지 않는다.
- 현재 Windows에서 관찰한 24건의 기존 실패와 업로드 disconnect 간헐 실패는 Linux에서 다시 확인한다. 동일 환경에서 baseline과 비교하기 전에는 새 실패를 환경 탓으로 분류하지 않는다.
- 동결한 코드의 필수 검증이 끝나기 전에는 배포 준비 완료로 표시하지 않는다. 테스트 종료 뒤 이번 실행이 만든 PID/schema/container/media/temp만 정리하고 결과를 남긴다.

## 계획 자체 검토

- 기존 파일·접점·MySQL 금지/필수 조건과 실제 TCP가 아닌 기존 peer를 확인했다.
- 수량·재생 입구·선택 독립·중복·내구성·소유권·범위 응답·실패 복구의 검증 항목을 모두 배치했다.
- 아직 필요한 입력은 테스트 Linux/MySQL 환경, 보호된 설정, 실제 영상 1건과 live provider 실행 환경이다. 이번 작업은 계획 작성까지이며 제품 코드와 테스트는 실행/수정하지 않았다.
