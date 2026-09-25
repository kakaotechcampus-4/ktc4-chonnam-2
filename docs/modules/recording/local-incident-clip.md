# 실제 단일 VIDEO IncidentClip과 Readout 경계

Owner: 정철원. Readout 신유민과의 월요일 합의에 따라 Readout은 clip bytes/경로를 받지 않는다.
`incident_clip_ref`로 metadata를 조회하고 `source_provenance.asset_spans[]`에서 원본 VIDEO ref와
source-local 위치를 얻어 기존 `resolve_frame(STREAM_POSITION)` → `read_frame()`을 사용한다.
`open_incident_clip`은 추가하지 않는다. Canonical Contract 및 다른 Owner 코드는 변경하지 않는다.

## 공개 사용

```python
materializer = LocalIncidentMaterializer(
    IncidentClipEncoding(height=480, preset="veryfast", crf=23),
)
with RecordingService(incident_materializer=materializer) as recording:
    clip = recording.build_incident_clip(resolution)
    metadata = recording.get_incident_clip(clip.incident_clip_ref)
    span, = metadata.source_provenance.asset_spans
    frame = recording.resolve_frame({
        "kind": "STREAM_POSITION",
        "media_stream_ref": span.media_stream_ref,
        "source_offset_sec": span.source_range.start_sec,
    })
    png = recording.read_frame(frame.frame_ref)
```

`build_incident_clip(resolution, options=None)`와 `get_incident_clip(ref)`의 기존 시그니처를 유지한다.
options schema는 확정하지 않으며 비어 있지 않은 options는 기존처럼 입력 오류다.
생성 설정은 실행 조립 시 별도 주입한다. 위 480p 설정은 재현 예제의 시험 조건이며 최종 신고 품질을 뜻하지 않는다.
이 설정과 Readout 판독 라벨 `source_profile`, AnalysisSource의 opaque `profile_ref`는 별개다.
공유 변환 엔진은 재사용하지만 AnalysisSource를 만들거나 그 ref를 clip에 연결하지 않는다.

```powershell
uv run --locked python -m examples.recording_incident_clip <로컬영상> --video-index 0 --start 3.7 --end 8.7
```

예제는 공개 계약과 PNG 크기/hash만 출력하고 파일을 저장하지 않는다. frame은 clip의 축소 영상이 아니라
원본에서 읽는다. root Python 3.12, ffmpeg/ffprobe가 필요하다. IncidentClip도 AnalysisSource와
같은 변환 엔진을 사용하므로 [FFmpeg 실행 환경과 4.3.1 제한](local-analysis-source.md#ffmpeg-실행-환경)이
동일하게 적용된다.

## 생성·provenance·identity

- 로컬 단일 VIDEO의 usable span 한 개만 지원한다. 입력 resolution을 같은 timeline/revision/request와
  명시적 VIDEO ref로 다시 해소해 일치 여부를 확인한다. 바뀐 원본·잘못된 매핑은 발행 전에 거부한다.
- `source_provenance.timeline_ref`, `requested_range`, `asset_spans`는 입력의 canonical 값을 그대로 보존한다.
  경계 밖 누락을 포함한 PARTIAL도 usable span이 한 개이고 재검증과 일치하면 그 부분을 materialize한다.
- 실제 MP4를 재검사한 duration, 실제 bytes 길이, 선택한 frame들의 실제 Timeline coverage로 metadata를 만든다.
  요청 길이·원본 파일 크기를 복사하거나 추정하지 않는다. 검증 완료 후에만 AVAILABLE을 발행한다.
- 출력은 H.264 MP4·yuv420p·audio/subtitle off·faststart다. frame 경계 때문에 실제 timeline_range는
  requested_range 또는 asset_span의 경계와 다를 수 있다. 입력 provenance를 그 값으로 덮어쓰지 않는다.
  허용 범위의 Evidence 판정은 여기서 하지 않는다.
- 매 build는 실제 bytes를 다시 생성·검증한다. provenance 전체, 생성 설정/version, SHA-256,
  실제 duration/range가 모두 같으면 기존 ref를 반환한다. 어느 값이 달라져도 새 UUID 기반 opaque ref를 발급한다.
  내부 비교 key는 공개 identity가 아니며 ref에 timeline/offset/sequence를 인코딩하지 않는다.
- 반환값·조회값은 deep copy다. 반환 객체의 nested list를 수정해도 기존 clip/provenance는 바뀌지 않는다.
- fixture 기반 생성·조회는 유지한다. malformed 계약 입력은 validation 오류, 로컬 생성·검증·timeout·
  지원 범위 밖의 실패는 기존 INCIDENT_CLIP_BUILD_FAILED로 표현한다. 새 failure taxonomy를 추가하지 않는다.

## 보관·cleanup과 한계

임시 출력은 공유 materializer의 전용 TemporaryDirectory 안에서 생성·probe 후 제거한다.
성공 bytes는 서비스 메모리에 보관하며 `close()`/context 종료 시 해제한다. 종료 후 해당 ref 조회는 UNAVAILABLE이다.
원본은 읽기만 하며 hash/크기/mtime을 검증한다. 공개 오류에 경로·도구 stderr를 노출하지 않는다.

현재 재사용은 ref 동일성 확인이며 재인코딩 비용을 생략하는 성능 cache가 아니다. 영속 저장·TTL·동시 요청
중복 방지·강제 종료 복구·case purge/AssetFacts 배선은 미구현이다. 여러 원본 stitching, 일반 복수 VIDEO,
복수 usable span은 후속이다. 입력 단일 span의 원본 stream 선택은 기존 명시적 VIDEO 합의를 따른다.
Readout 모델 호출·판독 품질·최종 ReportPackage는 이번 검증 범위가 아니다.

## 테스트

`tests/recording/test_local_incident_clip.py`는 합성 영상의 실제 MP4 metadata, provenance 보존,
ref 재사용/변경, 경계 PARTIAL, 원본 변경·소실, 생성 실패·timeout cleanup, fixture 호환을 검증한다.
소비 경로는 공개 `get_incident_clip`→`resolve_frame`→`read_frame`만 사용한다. 별도의 테스트 내부 검사만
보관 bytes를 임시 파일로 써 독립 ffprobe 후 제거한다. 이것은 Readout 공개 capability가 아니다.
`DAESINGO_RECORDING_VIDEO` opt-in은 실제 대표 AVI에서 생성·재사용·원본 frame decode·fingerprint 보존을 검증한다.
