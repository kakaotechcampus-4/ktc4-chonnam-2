"""원본 등록 → 명시한 video stream의 실제 FrameRef/PNG 조회. 파일을 쓰지 않는다."""

import argparse
import hashlib
import json

from daesingo.recording import RecordingCapabilityError, RecordingService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="비공개 로컬 영상 경로")
    parser.add_argument("--video-index", type=int, required=True, help="video만 센 0 기반 순번")
    parser.add_argument("--offset", type=float, required=True, help="stream local 초")
    args = parser.parse_args()
    service = RecordingService()
    try:
        registered = service.register_local_source(args.video)
        videos = [s for s in registered.media_streams if s.media_type == "VIDEO"]
        if not 0 <= args.video_index < len(videos):
            raise ValueError("등록된 video stream 순번이 필요합니다")
        stream = videos[args.video_index]
        frame = service.resolve_frame({"kind": "STREAM_POSITION",
            "media_stream_ref": stream.media_stream_ref, "source_offset_sec": args.offset})
        content = service.read_frame(frame.frame_ref)
    except (RecordingCapabilityError, ValueError) as error:
        # ValidationError의 원래 입력 값도 출력하지 않는다.
        print(json.dumps({"error_code": getattr(error, "code", "INVALID_INPUT")}, ensure_ascii=False))
        return 1
    print(json.dumps({"media_stream": stream.model_dump(mode="json"),
        "frame": frame.model_dump(mode="json"), "content_type": "image/png",
        "png_byte_size": len(content), "png_sha256": hashlib.sha256(content).hexdigest(),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
