# recording

**Owner:** 정철원

Recording은 원본 영상을 읽어 파일과 영상 스트림을 등록하고, 시간축과 분석·신고에 필요한 미디어를 준비한다.
공개 함수는 [Recording 코드 README](../../../src/daesingo/recording/README.md), 모듈 경계는
[아키텍처](../../architecture/module-architecture.md)를 참고한다.

| 입력 | 출력 |
| --- | --- |
| 신뢰된 로컬 원본 경로 | `SourceAsset`과 등록된 `MediaStream` 목록 |
| 원본 배치와 선택한 영상 스트림, 요청 시각 또는 구간 | `RecordingTimeline`, 구간 해소 결과 `SpanResolution`, 프레임 참조 `FrameRef` |
| 해소한 구간과 용도별 인코딩 설정 | 분석용 `AnalysisSource`, 사건 영상 `IncidentClip`과 조회 가능한 미디어 |

## 예제와 테스트

저장소 루트에서 실행한다. 합성 영상 테스트에는 `ffmpeg`와 `ffprobe`가 PATH에 있어야 한다.

```sh
uv sync --locked --extra test
uv run --no-sync python -m examples.recording_consumer
uv run --no-sync pytest tests/recording/test_local_source_registration.py tests/recording/test_ci_media_smoke.py -q
```

실제 MySQL 테스트에는 별도 테스트 DB가 필요하다. [CI 실행 구조](../../runtime/ci-test-partitions.md)를 참고한다.
로컬 실측에 사용한 버전과 배포 이미지가 요구하는 버전은 [FFmpeg 실행 환경](local-analysis-source.md#ffmpeg-실행-환경)에 구분해 적었다.

## 다루는 범위

- 원본 파일과 시간축
- 파일 경계 해결
- 파일이 주는 시각 후보
- GPS 좌표
- 분석용/외부/신고용 사본과 보관·삭제

## 다루지 않는 범위

- 교통위반 의미 판단
- 신고요건
- AI 모델·프롬프트
- 어느 시각 출처가 최종적으로 맞는지 판정
## 문서 운영

- `research/`: 조사·비교·Spike
- `experiments/`: 실제 설정/입력/결과/learning
- `decisions/`: 조사·실험 후 확정한 module 내부 결정
- `contracts/`: 이 모듈이 생산/소비하는 계약의 초안·검토 메모. cross-module 최종 계약은 `architecture/contracts/`로 승격

## 초기 구현 기록

- [recording 1차 Mock E2E Tech Spec](decisions/first-integration-tech-spec.md)

빈 spec을 미리 만들지 않는다. 필요해질 때 Owner가 생성한다.

## 실제 원본 capability

- [실제 영상 처리 Edge Case 목록](real-video-edge-cases.md)
- [로컬 원본의 실제 FrameRef·PNG 조회](local-frame-access.md)
- [등록 원본의 현재 AssetFacts 조회](local-asset-facts.md)
- [실제 단일 원본의 SpanResolution 계산](local-span-resolution.md)
- [실행별 로컬 AnalysisSource materialization](local-analysis-source.md)
- [AnalysisSource 크기·길이 한도와 초기 배포값](analysis-source-limits.md)
- [실제 단일 VIDEO IncidentClip과 Readout 경계](local-incident-clip.md)
