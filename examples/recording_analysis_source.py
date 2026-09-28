"""명시적인 VIDEO 구간을 Baseline 시험 profile로 준비하고 공개 binary stream을 읽는다."""

import argparse
import hashlib
import json
from uuid import uuid4

from daesingo.recording import AnalysisProfile, LocalAnalysisMaterializer, RecordingCapabilityError, RecordingService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("--video-index", type=int, required=True, help="VIDEO만 센 0 기반 순번")
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    args = parser.parse_args()
    profile_ref = f"prof_{uuid4().hex}"
    candidate = LocalAnalysisMaterializer({profile_ref: AnalysisProfile(height=480, preset="veryfast", crf=23)})
    try:
        with RecordingService(analysis_materializer=candidate) as service:
            registered = service.register_local_source(args.video)
            videos = [s for s in registered.media_streams if s.media_type == "VIDEO"]
            if not 0 <= args.video_index < len(videos):
                raise ValueError("명시적 VIDEO 순번이 필요합니다")
            timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
            ref = {"timeline_id": timeline.timeline_id, "revision": timeline.revision}
            result = service.resolve_span(ref, {"start_sec": args.start, "end_sec": args.end},
                                          media_stream_ref=videos[args.video_index].media_stream_ref)
            if result.status != "COMPLETE" or len(result.spans) != 1:
                raise ValueError("완전히 해소된 단일 span이 필요합니다")
            span = result.spans[0]
            source = service.prepare_analysis_source(span, profile_ref, timeline_ref=ref)
            reused = service.prepare_analysis_source(span, profile_ref, timeline_ref=ref)
            opened = service.open_analysis_source(source.analysis_source_ref)
            with opened.stream:
                digest = hashlib.file_digest(opened.stream, "sha256").hexdigest()
            print(json.dumps({"requested_span": span.model_dump(mode="json"),
                "analysis_source": source.model_dump(mode="json"), "content_type": opened.content_type,
                "byte_size": opened.byte_size, "sha256": digest, "reused": reused == source},
                ensure_ascii=False, indent=2))
    except (ValueError, RecordingCapabilityError) as error:
        print(json.dumps({"error_code": getattr(error, "code", "INVALID_INPUT")}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
