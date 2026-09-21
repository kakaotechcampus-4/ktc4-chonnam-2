# 로컬 단일 원본 AnalysisSource — 첫 구현 단위

이 구현은 기존 `recording` 공개 계약을 유지하면서 실제 로컬 영상의 일부를 MP4
`AnalysisSource`로 준비한다. `LocalAnalysisProfile`은 Python adapter 설정이며 Canonical
profile schema나 최종 운영값이 아니다. Elice/Google provider 호출은 이 경계에 없다.

## 지원 범위

- `register_local_source(path)`로 등록한 원본 1개
- `create_relative_timeline(source_ref)`로 만든 gap 없는 상대 Timeline
- `resolve_span(..., media_stream_ref=video_ref)`에서 명시적으로 선택된 VIDEO의 단일 usable span
- 명시적으로 등록한 `profile_ref`에 대한 H.264/yuv420p MP4 transcode
- 선택적인 첫 번째 audio stream의 AAC 포함
- `open_analysis_source(ref)`로 실제 bytes stream 열기
- 동일 span + timeline revision + profile의 서비스 생존 기간 내 재사용
- `lookup_asset_facts()`로 실제 byte size/duration/lineage 조회

구간 계산 자체는 `local-span-resolution.md`의 COMPLETE/PARTIAL/FAILED 규칙을
그대로 따른다. 이 adapter는 그 결과에서 단일 usable VIDEO span을 전달받을 때만
materialize한다. 다중 원본, 다중 usable span, video stream duration 미확인,
stream copy의 keyframe cut 정책은 지원하지 않는다.

## 호출 예

```python
from daesingo.recording import (
    LocalAnalysisProfile, RecordingService,
)

with RecordingService(analysis_profiles={
    "experiment-480p-noaudio": LocalAnalysisProfile(height=480),
}) as service:
    registered = service.register_local_source(local_path)
    timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
    video_ref = next(
        stream.media_stream_ref for stream in registered.media_streams
        if stream.media_type == "VIDEO"
    )
    resolved = service.resolve_span(
        {"timeline_id": timeline.timeline_id, "revision": timeline.revision},
        {"start_sec": 3.7, "end_sec": 18.4},
        media_stream_ref=video_ref,
    )
    source = service.prepare_analysis_source(
        resolved.spans[0], "experiment-480p-noaudio",
    )
    opened = service.open_analysis_source(source.analysis_source_ref)
    with opened.stream as stream:
        consume(stream, opened.content_type, opened.byte_size)
```

`ffmpeg`와 `ffprobe`가 PATH에 없으면 `LocalAnalysisMaterializer`와
`FfprobeMediaProbe`에 실행 파일 경로를 주입한다. 생성된 MP4는 서비스 내부 임시
디렉터리에만 존재한다. Consumer가 stream을 닫고 `RecordingService.close()` 또는
context manager를 종료하면 디렉터리가 삭제된다. 서비스 종료 뒤 open/prepare는
`UNAVAILABLE`이다. Source 원본은 복사·변경·삭제하지 않는다.

## 실패·검증

- 원본은 materialize 전후 크기·mtime·SHA-256을 재검증한다.
- 동일 요청의 재사용 전에도 원본 fingerprint를 재검증하며 변경된 원본의 stale cache를 반환하지 않는다.
- ffmpeg 실행이 실패하거나 timeout되면 부분 출력 파일을 삭제한다.
- 생성 MP4를 ffprobe로 다시 읽고 실제 duration과 byte size를 Canonical 객체에 기록한다.
- 요청과 실파일 duration 차이가 0.15초보다 크면 실패로 처리한다.
- audio 포함 profile은 출력에도 audio stream이 있어야 성공한다.
- 0.15초 기준은 첫 단계의 frame-boundary 허용치로, 제품의 최종 정확도 정책이 아니다.
- in-memory repository와 temp media는 프로세스 간 공유되지 않는다. EC2/worker
  영속성, eviction, 다중 worker 동시성은 후속 범위다.

## 재현

```powershell
$env:PYTHONPATH = "src"
python tests/recording/test_local_analysis_materialization.py -v
```

테스트는 실제 사용자 영상을 요구하지 않는다. `ffmpeg`/`ffprobe`가 없으면 미디어
테스트는 skip되고 fixture 회귀 테스트만 실행된다. 실행 파일 경로를 명시하려면
`DAESINGO_FFMPEG`, `DAESINGO_FFPROBE` 환경변수를 사용한다.
