"""단일 로컬 원본의 상대 Timeline과 요청 구간으로 실제 SpanResolution을 계산한다."""

import argparse
import json

from daesingo.recording import RecordingCapabilityError, RecordingService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="비공개 로컬 원본 경로")
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--end", type=float, required=True)
    parser.add_argument("--video-index", type=int, required=True,
                        help="사용자가 명시하는 VIDEO 목록의 0 기반 순번. 기본 선택 없음")
    args = parser.parse_args()
    service = RecordingService()
    try:
        registered = service.register_local_source(args.video)
        source = registered.source_asset
        videos = [s for s in registered.media_streams if s.media_type == "VIDEO"]
        if not 0 <= args.video_index < len(videos):
            raise ValueError("등록된 VIDEO의 명시적 순번이 필요합니다")
        timeline = service.create_relative_timeline(source.source_asset_ref)
        result = service.resolve_span(
            {"timeline_id": timeline.timeline_id, "revision": timeline.revision},
            {"start_sec": args.start, "end_sec": args.end},
            media_stream_ref=videos[args.video_index].media_stream_ref,
        )
    except (ValueError, RecordingCapabilityError) as error:
        print(json.dumps({"error_code": getattr(error, "code", "INVALID_INPUT")}))
        return 1
    print(result.model_dump_json(indent=2))
    return 0  # FAILED도 유효한 domain 응답이며 예외와 구분한다.


if __name__ == "__main__":
    raise SystemExit(main())
