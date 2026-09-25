# 로컬 원본의 실제 FrameRef·PNG 조회

Owner: 정철원. `contract-source-asset-media-stream.md` §5.3–5.4의 기존 공개
`resolve_frame(STREAM_POSITION)` / `read_frame()`을 실제 등록 원본에 연결한다.
Canonical 모델과 함수의 입출력 형식은 변경하지 않는다.

## 사용

root Python 3.12 환경과 PATH의 ffprobe/ffmpeg가 필요하다.

```powershell
uv run --locked python -m examples.recording_local_frame <로컬영상> --video-index 0 --offset 1.01
```

예제의 video-index는 등록 결과 중 VIDEO만 센 0 기반 순번이며 FRONT/REAR를 뜻하지 않는다.
공개 capability에는 순번 대신 등록에서 받은 `media_stream_ref`를 전달한다.
예제는 계약 객체, PNG 크기와 SHA-256만 출력하며 원본이나 PNG 파일을 저장하지 않는다.

```python
service = RecordingService()
registered = service.register_local_source(path)
video = next(s for s in registered.media_streams if s.media_type == "VIDEO")
frame = service.resolve_frame({
    "kind": "STREAM_POSITION",
    "media_stream_ref": video.media_stream_ref,
    "source_offset_sec": 1.01,
})
png = service.read_frame(frame.frame_ref)
```

## Recording 내부 선택 규칙

- 원본의 지정 video stream을 decode한다. proxy나 AnalysisSource를 사용하지 않는다.
- 첫 decoded PTS를 stream-local 0으로 정규화하고 요청 시각 이상 첫 frame을 선택한다.
  예를 들어 10 fps 영상에서 0.11초와 0.19초는 모두 0.2초 frame을 가리킨다.
- FrameRef에는 요청 시각이 아닌 선택 frame의 정수 PTS × time base를 저장한다.
  표시용 pts_time의 반올림 값이나 fps 추정치를 사용하지 않는다.
- 같은 stream·실제 offset이면 기존 FrameRef를 반환한다. 재추출 bytes가 달라지면
  기존 ref를 덮어쓰지 않고 실패한다. PNG는 서비스 수명 동안 메모리에 보관된다.
- 영상의 회전 metadata에 따른 자동 회전을 끄고 원본 raster 크기로 PNG를 만든다.
- 등록 snapshot과 추출 전후 SHA-256·크기·수정 시각을 검사한다. 원본 변경 또는
  decode 실패 시 FrameRef를 발행하지 않는다. 이미 발행된 PNG는 원본이 사라져도 유지된다.
- 일부 frame의 decode 성공으로 MediaStream 전체 availability를 AVAILABLE로 바꾸지 않는다.
- fixture 기반 기존 경로는 유지한다. 실제 로컬 원본에 fixture bytes를 반환하지 않는다.

## 실패와 제한

| 조건 | 결과 |
| --- | --- |
| 음수·비유한 위치 | 입력 validation 오류 |
| 미등록 stream/frame ref | UNKNOWN_REF |
| 알려진 stream duration 이상 요청 | OUT_OF_RANGE |
| AUDIO 또는 요청 이후 decoded frame 없음 | FRAME_NOT_FOUND |
| 원본 변경·소실, decode 실패, 명시적 UNAVAILABLE | STREAM_UNAVAILABLE |
| 도구 부재·timeout·출력 시각 검증 실패 | TEMPORARY_FAILURE |

기존 RecordingCapabilityError의 code 경계를 사용한다. 공통 failure.kind taxonomy를
새로 확정하지 않으며 외부 도구의 argv·stderr·로컬 경로는 공개 오류에 넣지 않는다.

매 resolve 호출은 원본 hash 확인과 처음부터의 decode를 수행한다. 장시간 영상에서
기본 60초 timeout이 발생할 수 있으며 seek 최적화·용량 제한 cache·영속화는 미구현이다.
`FfmpegFrameExtractor(executable=..., timeout_sec=...)`를 서비스 생성자의
`frame_extractor`로 주입할 수 있다. ffmpeg showinfo 형식이 달라지면 성공으로 추측하지 않고 실패한다.
메모리는 조회 frame 수와 해상도에 비례해 증가하므로 월요일 로컬 실행용이다.

Timeline 위치에서의 새 frame 추출·다중 stream 선택, resolve_span의 실제 구간 매핑,
AnalysisSource/IncidentClip 생성 및 Readout 통합 배선은 이번 단위에 포함하지 않는다.
실제 영상 전 범위의 decode 가능성이나 번호판 가시성을 보증하지 않는다.

## 설계서의 D1·D2·D3 반영 범위

- D1: Elice 경로의 RemoteCopy 미사용을 유지한다.
- D2: profile 속성의 미확정 상태를 유지한다. 이번 PNG는 AnalysisSource가 아니며
  prepared video bytes·구간 정합성 검증은 후속 기능이다.
- D3: UsageRecord·추론 effort는 Search/runtime 범위이므로 변경하지 않는다.

## 검증

`tests/recording/test_local_frames.py`는 생성한 두 video+audio 영상으로 실제 PNG 픽셀,
stream 선택, PTS 정규화, 같은 frame의 identity, EOF, 변경된 원본 거부, 실패 미발행과
공개 예제를 검증한다. `DAESINGO_RECORDING_VIDEO`를 지정한 opt-in 테스트는
해당 실제 원본의 각 VIDEO에서 1.01초 이후 frame을 읽고 decode 및 원본 보존을 검사한다.
원본은 저장소에 복사하지 않는다.
