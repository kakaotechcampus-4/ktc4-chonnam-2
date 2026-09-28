"""실제 IncidentClip을 생성한 뒤 provenance에서 원본 frame을 읽는 공개 경로 예제."""

import argparse
import hashlib
import json

from daesingo.recording import (
    IncidentClipEncoding, LocalIncidentMaterializer, RecordingCapabilityError, RecordingService,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("--video-index", type=int, required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    args = parser.parse_args()
    # 실행 조립용 생성 조건이다. Readout source_profile 또는 AnalysisSource ref가 아니다.
    materializer = LocalIncidentMaterializer(IncidentClipEncoding(height=480, preset="veryfast", crf=23))
    try:
        with RecordingService(incident_materializer=materializer) as service:
            registered = service.register_local_source(args.video)
            videos = [s for s in registered.media_streams if s.media_type == "VIDEO"]
            if not 0 <= args.video_index < len(videos):
                raise ValueError("명시적 VIDEO 순번이 필요합니다")
            timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
            result = service.resolve_span({"timeline_id": timeline.timeline_id, "revision": timeline.revision},
                {"start_sec": args.start, "end_sec": args.end}, media_stream_ref=videos[args.video_index].media_stream_ref)
            clip = service.build_incident_clip(result)
            stored = service.get_incident_clip(clip.incident_clip_ref)
            span, = stored.source_provenance.asset_spans
            frame = service.resolve_frame({"kind": "STREAM_POSITION", "media_stream_ref": span.media_stream_ref,
                                           "source_offset_sec": span.source_range.start_sec})
            image = service.read_frame(frame.frame_ref)
            print(json.dumps({"incident_clip": stored.model_dump(mode="json"),
                "frame": frame.model_dump(mode="json"), "frame_byte_size": len(image),
                "frame_sha256": hashlib.sha256(image).hexdigest()}, ensure_ascii=False, indent=2))
    except (ValueError, RecordingCapabilityError) as error:
        print(json.dumps({"error_code": getattr(error, "code", "INVALID_INPUT")}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
