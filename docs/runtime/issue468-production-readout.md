# 기본 Worker production OCR 조립

**IN_PROGRESS · Refs #468 · Related #460**

2026-10-30. 이 문서는 로컬 변경·검증 기록이며 Issue 댓글을 수정하지 않는다.
이전 실행 기록은 [RT-10(b)](./rt10b-readout-handlers.md)에 보존한다.

## 근거와 조립 경계 (#468 기록 초안)

- 시작 시 현재 branch `codex/issue468-default-worker-readout`, HEAD와 fetch한
  `origin/develop` 모두 `b9c74d5e1f2b48c95254f6178e4ce9b9b5fb73b5`.
  최초 working tree/index는 비어 있었다. PR #473의 merge를 포함한다.
- [Issue #468](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/468),
  [#460](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/460),
  [Readout Owner 확정 답변](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/468#issuecomment-6501179946)을 직접 읽었다.
- 이전 `worker.__main__.main()`은 factory 없이 `compose_registry()`를 호출했다.
  `readout_registry(provider_factory=None)`는 의도적으로 빈 registry를 반환했다.
  따라서 운영 기본 진입점에서 두 kind가 등록되지 않았다.
- 기본 `main()`은 이제 `production_readout_factory()`를 명시적으로 호출한다.
  이 함수는 startup에서 dependency/cache 검증과 엔진 로드·예열을 완료한 뒤
  `recording_ocr_factory()`를 반환한다. 각 execution은 별도 RecordingService,
  `RecordingFrameSource`, `PaddleOcrProvider`와 결과 cache를 가진다.
  단일 Worker의 직렬 실행에서 예열한 엔진만 공유한다.
- `compose_registry(..., readout_provider_factory=...)`와
  `main(readout_provider_factory=...)`는 명시적 테스트 injection 경계다.
  낮은 조립 계층의 `None`은 이전 의미를 유지한다. production `main()`의
  `None`은 production 조립을 선택하며 `FixtureOcrProvider`를 사용하지 않는다.
- 일반 import/pytest collection은 Paddle을 import하지 않는다. 실제 production
  main 및 이미지 `readout-preflight`에서만 production dependency/cache가 필수다.
- dependency 누락/버전 불일치, 모델 누락/변조/읽기 권한 오류, 엔진 로드·예열
  실패는 Worker loop/claim 전에 종료한다. 기존 `runtime.worker.failed`와 exit 1,
  이미지 어댑터의 `container: operation_failed` 경계를 사용한다. 새로운 오류
  taxonomy code는 만들지 않는다. 원래 예외/traceback/cache·모델 경로는 출력하지 않는다.

## 실행환경 (#460 기록 초안)

| 항목 | 확정 구성 |
| --- | --- |
| Provider | `PaddleOcrProvider` |
| 설치 extra | `readout-paddle` (`uv sync --locked --no-dev --extra eval-gemini --extra readout-paddle`) |
| dependency | `paddleocr==3.7.0`, `paddlepaddle==3.3.1`, `opencv-contrib-python==4.10.0.84` |
| 사전학습 모델 | `PP-OCRv5_mobile_det`, `korean_PP-OCRv5_mobile_rec` |
| 실행 | CPU, `enable_mkldnn=False`, 화면 시각 기본 `+09:00` |
| 이미지 model cache | `/opt/daesingo/paddlex/official_models/<model>/` |
| 무결성 | build 생성 `models.json`, 모델별 inference JSON/parameters/YAML SHA-256을 startup에서 검증 |
| 사용자 | UID/GID `10001:10001`; 모델 파일 `0444`, 모델 디렉터리 `0555` |
| 라이브러리 cache root | `PADDLE_PDX_CACHE_HOME=/opt/daesingo/paddlex`; root는 UID10001 쓰기 가능하여 PaddleX 자체 임시/lock cache 생성 허용 |
| 설치 시스템 라이브러리 | 기존 media 라이브러리 + `libgl1`, `libglib2.0-0`, `libgomp1` |
| 다운로드 | `readout-build` stage에서 두 모델만 사전 다운로드; runtime에는 inference 파일과 manifest만 복사 |
| runtime 모델 선택 | 추가 env key 없음. 고정된 이름과 명시적 local model directory 사용 |
| runtime 사전 검사 | `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True`, 네트워크 없는 image build preflight |

기본 PaddleX 홈 cache에 의존하지 않고 build와 runtime이 같은 cache 위치를 사용한다.
모델 checksum은 이 이미지가 받은 파일의 무결성을 검증한다. 별도 외부 서명 검증을
추가한 것은 아니다. FFmpeg/ffprobe 8.1의 기존 source/hash/base/snapshot 및 동일
build binary preflight는 유지한다.

```sh
docker build --tag daesingo-readout:local .
docker run --rm --network none daesingo-readout:local python /app/docker/runtime.py media-preflight
docker run --rm --network none daesingo-readout:local python /app/docker/runtime.py readout-preflight
# 기존 Compose의 외부 runtime env/secret 파일 설정 후:
docker compose up --build
# 이미지의 Worker 실행 어댑터:
python /app/docker/runtime.py worker
# 동일 image 안에서 직접 실행하는 기본 진입점:
python -m daesingo.worker
```

credential은 기존 외부 env/secret 파일로 공급한다. 실제 값이나 개인 로컬 절대경로는
이 문서에 기록하지 않는다. API/Worker/Recording 필수 설정은 기존
[Compose Notes](./rt13a-docker-compose.md)를 따른다.

## 검증 기록

- 기본 `main()` 두 kind 미등록 RED 확인 후 GREEN. 실제 registry dispatch가
  Recording factory와 Paddle provider를 통과하여 두 공개 판독 결과를 만드는 unit 검증.
  이 unit의 OCR 엔진은 테스트 대역이며 실제 Paddle 성공으로 집계하지 않는다.
- 일반 Windows 환경에 Paddle 미설치 확인. 작성자 focused 383 PASS (77.75초),
  production preflight focused 12 PASS. 기본 임시 디렉터리 권한 실패는 task 전용
  pytest basetemp로 재실행했다.
- 최초 Docker build 중 C: free 0, Docker read-only filesystem/EOF로 실패.
  같은 시점의 확장 테스트 setup 오류 및 MySQL 연결 preflight 실패를 성공으로
  집계하지 않는다. 이후 여유 공간과 Docker 응답 회복을 확인하여 재실행했다.
- 작성자 production image build PASS. UID10001의 `RUN --network=none ... readout-preflight`
  PASS. 실제 이미지 media acceptance는 MP4/AVI/MKV/MP4 chain 네 그룹 PASS.
- 실제 기본 Worker의 dependency/cache/permission 음성 acceptance는 각각 exit1과
  안전한 로그를 확인했다. 최초 테스트 helper의 overlay filesystem rename(EXDEV)은
  disposable container에서 metadata를 제거하는 방법으로 수정 후 통과했다.
- 실제 synthetic OCR 및 별도 API/Worker T1/T2, 최종 image 검사와 fresh review 결과는
  아래에 실행 완료 후 추가한다. 이 줄 시점에서 완료로 집계하지 않는다.

## 범위와 제출 경계

DB schema/migration/inventory는 변경하지 않는다. 전체 로컬 pytest·전체 mandatory
MySQL은 중복 실행하지 않는다. 최종 regression·MySQL strict gate·aggregator는
향후 사용자가 push한 뒤 원격 CI 조건이다. 30분/timeout/skip/xfail/strict gate
정책을 완화하지 않는다. 일반 regression/MySQL job에 Paddle을 설치하지 않는다.
실제 Paddle은 production image acceptance에서 검증한다.

commit/push/PR/외부 Issue 변경은 하지 않는다. 위 #468/#460 내용은 게시용 로컬
기록 초안이다. `.codex-scratch`, credential/env, RAW/JUnit, 모델 다운로드 cache
임시 사본, Docker export는 PR 제외다. 자원 정리와 최종 파일 목록은 후속 기록에 추가한다.


## 실제 판독에서 발견한 추가 결함과 검증

실제 3초 synthetic MP4를 Paddle로 읽는 과정에서 `3.0 * 0.2`가 `0.6000000000000001`을 만들어 Recording의 엄격한 실제 PTS 검사에 실패했다. 샘플 비율 곱셈과 clip→source 시각 덧셈 두 RED를 확인하고 decimal 표현 기반 계산으로 GREEN 전환했다. Recording의 시각/ffmpeg 검증 기준은 변경하지 않았다. 이전 실패 Run은 성공으로 집계하지 않는다.

실제 기본 Worker가 두 OCR job을 완료한 뒤 SIGTERM에서 exit -15로 끝나는 두 번째 결함도 발견했다. Paddle native 초기화가 먼저 설치한 OS signal handler를 바꿀 수 있으므로, production factory 초기화 후 Worker가 자신의 handler를 다시 등록한다. 해당 signal ownership RED→GREEN, 진입점/production focused31PASS. 원래 signal 복원과 engine cleanup은 유지한다.

작성자 image37f9d9의 실제 synthetic 번호판 `12가3456`/화면시각 PASS, `--network none` 및 socket audit 연결 시도0, 모델 artifact hash 불변, UID/GID10001. 최종 진입점만 mount하여 별도 API peer/MySQL과 실행한 기본 Worker도 실제 Paddle 두 판독·T1 produced/usage 저장·T2 Case 반영·SIGTERM exit0 PASS. 이 중간 source-mount 결과는 최종 무-mount 이미지 결과와 구분한다. API peer는 별도 OS process 안에서 실제 HTTP app/TestClient를 사용하며, 선행 Search 응답만 offline 대역이다. Readout Worker에는 provider injection/patch가 없다.

작성자 MySQL8.4.13 focused55PASS (476.91초): Readout durable receipt/usage, T1 interruption/replay, 별도 API/Worker6 modes 및 sweep/entrypoint. JSON selected55/collection_errors0 및 JUnit55/skip0/failure0/error0을 대조했다. 이 검사는 실제 Paddle OCR 검사와 별개인 기존 offline-provider 회귀다.

fresh read-only reviewer는 구현 이력을 상속하지 않았고 현재 소스의 P1/P2/P3 지적 없음으로 판정했다. reviewer 직접 실행은 focused52PASS (23.59초), 새 process의 Worker import 시 paddle/paddleocr 미import 확인, diff check PASS. reviewer 첫 실행20setupERROR는 reviewer basetemp 상위 디렉터리 미생성 문제로 수정하여 재실행했다. 실제 Docker/OCR/MySQL 수치는 작성자 실행이다. 최종 image/evidence/docs 재검토를 같은 reviewer에게 요청한다.


## 전체 변경 파일 (20개)

- `.dockerignore`
- `.github/workflows/python-tests.yml`
- `Dockerfile`
- `README.md`
- `docker/runtime.py`
- `docker/readout_cache.py`
- `docs/runtime/runtime-implementation-log.md`
- `docs/runtime/issue468-production-readout.md`
- `src/daesingo/readout/paddle_provider.py`
- `src/daesingo/readout/providers.py`
- `src/daesingo/worker/__main__.py`
- `src/daesingo/worker/readout_composition.py`
- `src/daesingo/worker/readout_runtime.py`
- `tests/readout/test_recording_frame_source.py`
- `tests/worker/test_entrypoint.py`
- `tests/worker/test_sweep_worker_mysql.py`
- `tests/worker/test_production_readout.py`
- `tests/deploy/readout_acceptance.py`
- `tests/deploy/readout_process_acceptance.py`
- `tests/deploy/readout_startup_acceptance.py`

최종 소스 작성자 일반 focused 명령: `python -B -X utf8 -m pytest tests/readout tests/worker tests/deploy tests/test_ci_orchestration.py -m "not mysql" -q -p no:cacheprovider --basetemp=<ignored task temp>` → **664PASS / 338 deselected**, 66.04초. 338건은 이 실행에서 제외한 MySQL 표식이며 skip으로 대체하지 않았다. 기존 Starlette/httpx deprecation warning1건이 있다. 작성자 actionlint/경계/Contract fixture/Compose 구조/diff 검사 PASS. 전체 mandatory MySQL 실행을 뜻하지 않는다.


### 최종 이미지 고정 및 글꼴 검사 이력

최종 source mount 없는 production image는 `sha256:51c214dba2d1fee50c1092e68c6f09e74e2cc1759a30ded0275c551314c5c0de`다. 작성자/같은 fresh reviewer가 모두 offline media/readout preflight exit0을 확인했다. 작성자 최종 이미지의 media helper 네 그룹, 기본 Worker의 dependency/cache/권한 누락 exit1 세 그룹, UID10001 모델6파일 읽기·정확한 dependency·application test data/credential 파일·build tool/cache 부재 검사를 통과했다. source/data allowlist 검사와 credential 변수 없는 image config도 확인 대상으로 삼는다.

최종 CI 글꼴(NanumGothicBold) 첫 시도에서는 OCR이 날짜/시각 사이 공백을 지워 `2026-06-2014:19:56`을 반환했다. 기존 parser가 UNKNOWN으로 처리하여 두 acceptance가 FAIL했다. 이 결과는 성공으로 집계하지 않으며 parser/모델/판정 threshold를 변경하지 않았다. Korean plate에는 Nanum, 숫자 timestamp에는 이미지에 이미 포함된 DejaVuSans-Bold를 쓰는 synthetic generator로 재검사했다. 글꼴 변경은 테스트 입력 구성만의 변경이다. 검증한 synthetic 가독성이 실제 블랙박스 전반의 OCR 정확도를 보장하지 않는다.

이 generator의 최종 이미지 standalone OCR은 plate/overlay PASS, socket audit network_attempts0, cache_unchanged=true, UID10001이다. CI와 같은 공개 Nanum font package checksum을 확인한 임시 font를 사용했고 이미지에는 font/test helper/fixture를 추가하지 않았다. 최종 별도 process 검사는 완료 후 아래에 추가한다.


### 최종 완료한 로컬 검증과 정리

위 최종 image51c214에서 production source mount 없이 실행한 작성자 최종 별도 process acceptance는 **PASS**다. 실제 `python -m daesingo.worker`, 실제 Paddle, 별도 API process, 번호판/시각 각각 T1 produced·usage 저장과 T2 Case 반영, 두 관찰 status OK, Worker SIGTERM exit0을 확인했다. 모델/handler 실패나 UNKNOWN을 성공으로 오인하지 않도록 각 terminal·run·observation·usage·Case 적용 상태를 검사한다. Docker internal network로 외부 egress를 제한했고, 별도 standalone 검사는 `--network none`과 socket audit에서 시도0을 확인했다.

동일 fresh reviewer가 최종 image의 media/readout offline preflight exit0과 실제 standalone OCR을 직접 실행했다: plate/overlay PASS, UID10001, network attempts0, cache hash 불변. reviewer 직접 focused52PASS 및 이 Docker 직접 실행과, 작성자664/55/process/media/음성 검사 결과는 구분한다. reviewer는 최신 helper의 글꼴 변경·실패 이력·20파일 manifest·원본 Log byte prefix·HEAD/index를 재검토했으며 P1/P2/P3 지적이 없다.

정리 전 전용 MySQL audit: test schema0, 다른 client0, 남은 transaction0, data lock0. 전용 container와 식별한 anonymous volume, internal network, 작업 tag 및 중간 image를 제거한 뒤 부재를 재조회했다. 이번 작업 생성 시각과 설명으로 식별한 비공유 build cache를 정확한 ID별로 정리했다(최종24 records). 공유 image/cache/daemon에는 blanket prune/restart를 하지 않았다. 작업 전용 pytest env/media/model-test temp 및 checksum 검증용 임시 font를 삭제했다. 실제 production model cache의 host 임시 사본이나 Docker export는 만들지 않았다. 실패/중간/최종 RAW, 소형 audit script, JSON/JUnit은 ignored scratch에 남기며 위20파일 manifest와 Docker build context에서 제외한다.

최종 image config/history에서는 credential env/key 전달이 없음을 확인했고, application 파일 allowlist 검사에서 credential 파일·private-key marker·test fixture/data가 없었다. runtime에 UV/compiler/curl/build cache가 없음을 확인했다. 기존 production fixture adapter 소스 모듈은 패키지 일부이며, 테스트 fixture 데이터를 이미지에 복사하거나 production provider로 사용한 것은 아니다.

남은 범위: 전체 로컬 pytest와 전체 mandatory MySQL/strict gate/aggregator는 실행하지 않았다. DB schema/migration/inventory 변경이 없으며 이들은 향후 사용자 push 뒤 원격 CI 조건이다. Windows/native Paddle 및 비-amd64 image, 사용자 실제 영상 전반의 OCR 정확도는 검증하지 않았다. 기존 deprecation warning은 남아 있다. runtime model download와 첫 모델 로드/예열을 job 실행 이전으로 옮긴 검증이며, 실제 inference 처리시간이 0이라는 의미는 아니다.

**IN_PROGRESS · Refs #468 · Related #460**. 현재 브랜치에서 미커밋·미스테이징으로 남겼으며 commit/push/PR/Issue/Notion 변경은 하지 않았다. #468/#460 게시 내용은 이 문서의 로컬 기록 초안으로 제공한다.


최종 cache 정리 후속 확인: 첫24개 ID만 선택한 검사에서는 preflight/permission 하위 참조가 남아 부재 assertion이 실패했다. 이 작업에서 생성된 비공유 root11개를 추가로 식별하고 child→parent 순서로 정확한35개 ID를 정리한 뒤 잔여0을 확인했다. 공유/이전 cache를 범용 prune하지 않았다. 이 검사는 container/volume/network/image 부재와 별도의 build cache 정리 검증이다.
