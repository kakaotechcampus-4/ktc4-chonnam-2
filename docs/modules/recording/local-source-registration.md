# 실제 로컬 영상 등록 — 첫 번째 기능 단위

`RecordingService.register_local_source(path: str | Path) -> RegisteredSource`는
기존 `SourceAsset`과 `MediaStream` tuple을 반환한다. `RegisteredSource`는 Python
반환 묶음이며 새 Canonical Contract가 아니다. 기존 계약 모델·버전은 유지한다.

## 입력과 처리

- 신뢰된 로컬 실행기의 파일 경로를 입력으로 받는다. HTTP 업로드 API가 아니다.
- ffprobe는 PATH에서 찾는다. 필요하면 `FfprobeMediaProbe(executable=...)`를
  `RecordingService(media_probe=...)`에 주입한다. 기본 probe timeout은 30초다.
- 일반 파일을 읽기 전용으로 열고 실제 크기와 SHA-256을 측정한다. probe 전후
  해시·파일 identity·크기·mtime을 비교하며 달라지면 등록하지 않는다.
- ffprobe의 format duration과 각 video/audio stream의 duration을 각각 사용한다.
  누락/`N/A`는 `null`이며 container duration으로 stream duration을 채우지 않는다.
- 카메라 역할은 추정하지 않는다: VIDEO는 `UNKNOWN`, AUDIO는 `null`.
- subtitle/data/첨부 표지는 MediaStream으로 등록하지 않는다. video stream 없는
  입력은 이 진입점에서 거부한다. 빈 stream 목록의 Canonical 의미는 정하지 않는다.
- 파일 읽기를 확인한 SourceAsset은 `AVAILABLE`. stream decode는 검사하지 않으므로
  MediaStream은 `UNKNOWN`이다. probe 성공을 전체 decode 성공으로 주장하지 않는다.
- 외부 시스템에서 받은 원본 ref가 없으므로 `external_source_ref=null`이다.
  source/stream마다 새 opaque ref를 발급한다. 중복 파일 재사용은 하지 않는다.

## 내부와 공개 값

파일 경로·SHA-256·mtime·ffprobe stream index는 in-memory repository에만 보관한다.
공개 결과에는 기존 Canonical 필드만 담는다. 원본은 복사·변환·이동·삭제하지 않는다.
source 등록을 case의 삭제 대상에 연결하지 않는다. hash 계산은 파일을 두 번 읽으므로
대용량 최적화는 후속 작업이다. OS가 갱신하는 access time은 무변형 검증 대상이 아니다.

## 실패

- 파일/도구 접근 실패, probe 비정상 종료·timeout, 원본 변경 감지:
  기존 `RecordingCapabilityError(code="TEMPORARY_FAILURE")`.
- 일반 파일이 아님, video 없음, 잘못된 JSON·index·duration: `ValueError`.
- 실패 메시지에는 path와 ffprobe stderr/argv를 포함하지 않는다.
- 검증이 끝나기 전에는 ref/자산을 등록하지 않는다. fixture fallback은 없다.
- 등록 전용 canonical failure code나 JobExecution 매핑을 신설하지 않는다.

## 재현 (현재 브랜치, root PowerShell / Python 3.12)

환경 PR #82 미병합 상태의 root `.venv`를 사용하며 환경 파일을 재생성하지 않는다.
ffmpeg와 ffprobe가 PATH에 있어야 생성 영상 smoke가 실행된다.

```powershell
$env:PYTHONPATH = "src"
.venv/Scripts/python.exe -m examples.recording_register_local "D:\videos\sample.mp4"
.venv/Scripts/python.exe -m pytest tests/recording/test_local_source_registration.py -q

# 실제 영상 검증은 입력을 명시한 경우에만 실행한다.
$env:DAESINGO_RECORDING_VIDEO = "D:\videos\sample.mp4"
.venv/Scripts/python.exe -m pytest tests/recording/test_local_source_registration.py -k opt_in -q
```

예제 경로는 사용자가 실제 경로로 바꾼다. 미디어·경로를 Git에 넣지 않는다.
자동 smoke는 임시 폴더에 1초짜리 2 video + 1 audio 영상을 생성해 실제 ffprobe를
호출한다. 도구가 없으면 명시적으로 skip한다. 사용자 영상 입력이 없을 때의 opt-in
skip과 생성 영상 성공을 실제 도로 영상 E2E 성공으로 해석하지 않는다.

현재 한계: metadata 등록만 수행한다. `lookup_asset_facts` 연결, decoder 검증,
Timeline, AnalysisSource/D1·D2, clip/frame 생성, JobExecution 배선, 영속화는 포함하지 않는다.
등록 후 외부 프로세스가 파일을 변경하는 것을 차단하지 않으며 후속 읽기 시 재검증이 필요하다.
