# W7 Python CI와 Recording 합성 media smoke

`.github/workflows/python-tests.yml`은 develop/main 대상 PR, develop push 및 수동 실행에서
root Python 3.12 환경으로 pytest를 실행한다. 기존 boundary-check는 변경하지 않는다.
권한은 contents: read, job timeout은 20분이며 checkout 인증정보를 유지하지 않는다.

## 의존성과 실행 명령

root pyproject.toml과 uv.lock이 정본이다. setuptools build backend를 유지한다.
[uv 공식 Actions 안내](https://docs.astral.sh/uv/guides/integration/github/)의 setup-uv와
locked sync 방식을 사용하며 uv는 0.11.15로 고정한다.

```sh
uv sync --locked --extra test --extra eval-gemini
sudo apt-get update
sudo apt-get install --no-install-recommends -y ffmpeg
ffmpeg -version
ffprobe -version
uv run --no-sync python --version
uv run --no-sync python -m pytest tests/recording/test_ci_media_smoke.py -q -p no:cacheprovider --junitxml="$RUNNER_TEMP/recording-smoke.xml"
uv run --no-sync python -m pytest -q -p no:cacheprovider
```

- test extra: pytest, NumPy, OpenCV. 현재 Readout target crop 회귀가 NumPy 배열과
  OpenCV resize를 사용하므로 필요하다. OpenCV 버전은 기존 readout-paddle 선언과 맞춘다.
- eval-gemini extra: 기존 Search provider 생성 경로의 오프라인 spy 테스트에 필요한
  openai 및 SDK 의존성을 root에 선언된 묶음으로 설치한다. API 호출이나 인증정보는 사용하지 않는다.
- readout-paddle extra / --all-extras는 사용하지 않는다. PaddleOCR·PaddlePaddle·모델 다운로드는 없다.
- sync 후 --no-sync로 실행하여 테스트 실행 중 extras가 제거되지 않게 한다.

## FFmpeg 실행 조건

ubuntu-24.04 배포 패키지를 설치하고 ffmpeg/ffprobe 버전을 CI 로그에 남긴다.
설치된 도구의 `-fps_mode`와 libx264 encoder 가용성을 검사한다.
FFmpeg 4.3.1은 현재 엔진의 `-fps_mode passthrough`를 지원하지 않는다.
전체 지원 최소 버전을 임의로 확정하지 않으며, 옵션 검사에 더해 실제 생성·변환·검증이
모두 통과해야 해당 CI 환경에서 성공으로 판단한다.
자세한 배경은 [FFmpeg 실행 환경](../local-analysis-source.md#ffmpeg-실행-환경)을 참고한다.

## 필수 smoke 경로

테스트는 pytest 임시 공간에 2초·10fps·160×90 VIDEO 1개와 AUDIO 1개를 가진 영상을 생성한다.
기존 Recording 검사 helper를 재사용하며 media 처리 엔진은 복제하지 않는다.

1. register_local_source로 등록하고 실제 크기를 확인한다.
2. relative Timeline을 만들고 USABLE_RELATIVE_ONLY를 확인한다.
3. VIDEO가 정확히 하나임을 확인하고 그 media_stream_ref를 명시적으로 전달한다.
4. 같은 revision에서 analysis 0–2초, incident 0.5–1.5초를 각각 resolve_span으로 COMPLETE 해소한다.
5. prepare_analysis_source와 open_analysis_source를 통해 독립 stream·크기·duration·범위를 검사한다.
   공개 bytes를 ffprobe로 재검사하여 H.264/480p/yuv420p/MP4·VIDEO 단독 구성을 확인하고 decode한다.
6. build_incident_clip과 get_incident_clip으로 AVAILABLE·실측 byte_size·duration·범위·provenance를 검사한다.
   새 clip bytes 공개 API나 내부 저장소 접근을 추가하지 않는다.
7. clip provenance에서 STREAM_POSITION을 얻어 resolve_frame → read_frame으로 PNG를 읽고 decode한다.
8. 원본 SHA-256·크기·mtime 불변과 materialization 임시 파일 cleanup을 확인한다.

도구 부재는 assert 실패, 생성 실패는 subprocess 오류로 처리한다. 이 smoke에는 skip 경로가 없다.
workflow는 JUnit에서 정확히 1개 testcase가 실행됐고 skipped/failure/error가 없는지도 확인한다.
전체 pytest의 실제 영상·외부 dataset opt-in skip은 필수 합성 smoke 성공과 별도로 표시된다.

## Real Recording Benchmark와의 차이

이 CI는 짧은 합성 영상의 공개 경로와 회귀를 검증한다. 실제 블랙박스 영상, raw benchmark JSON,
외부 AI API, 비밀정보를 입력으로 받지 않으며 media나 JSON artifact를 업로드하지 않는다.
[Real Benchmark](w7-benchmark-runner.md)와 [Baseline](w7-baseline-bundle.md)의
익명 dataset 측정·반복 동결·성능 전후 비교를 대체하지 않는다. CI 실행시간에 성능 합격선을 두지 않는다.

Ubuntu runner 실행 결과는 GitHub Actions에서 별도로 확인해야 한다. 로컬 Windows 검증만으로
Linux에서의 통과나 모든 FFmpeg 버전 호환성을 주장하지 않는다. 배포 패키지의 patch 버전은
고정하지 않으므로 실제 로그의 버전과 smoke 결과를 함께 확인한다.
