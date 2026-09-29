"""PR #146 멘토 리뷰(r4084810910) 후속 — 실영상 번호판·시각 판독은 **IncidentClip 구간 프레임**을 본다.

예전엔 `LocalVideoFrameSource(원본 경로)`로 원본 파일 전체 길이의 30/50/70% 지점을 읽어, 위반 구간
밖의 프레임을 볼 수 있었다. readout의 `RecordingFrameSource`(#138)가 recording 공개 경로
(`get_incident_clip()` → `resolve_frame()` → `read_frame()`)로 clip 구간 안의 프레임과
recording이 발급한 `frame_ref`를 넘겨 주므로 그 경로로 바꾼다. 샘플링 간격·장수는 readout이 정한다.
"""
from __future__ import annotations

from types import SimpleNamespace

from daesingo.case import real_e2e
from daesingo.readout import paddle_provider


def test_real_video_ocr_reads_incident_clip_frames_through_recording():
    rec_service = object()
    context = SimpleNamespace(rec_service=rec_service, local_video_path="unused.mp4")

    provider = real_e2e._build_ocr_provider(context)

    assert isinstance(provider, paddle_provider.PaddleOcrProvider)
    assert isinstance(provider._source, paddle_provider.RecordingFrameSource)
    assert provider._source._recording is rec_service
