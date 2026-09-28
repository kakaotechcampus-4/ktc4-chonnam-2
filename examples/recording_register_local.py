"""Recording 공개 API로 실제 원본을 등록하고 경로 없는 계약 JSON을 출력한다."""

import argparse
import json

from daesingo.recording import FfprobeMediaProbe, RecordingCapabilityError, RecordingService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="비공개 로컬 영상 파일 경로")
    parser.add_argument("--ffprobe", default="ffprobe", help="ffprobe 실행 파일")
    args = parser.parse_args()
    service = RecordingService(media_probe=FfprobeMediaProbe(args.ffprobe))
    try:
        result = service.register_local_source(args.video)
    except (RecordingCapabilityError, ValueError) as error:
        # 원본 path, ffprobe argv/stderr를 출력하지 않는다.
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({
        "source_asset": result.source_asset.model_dump(mode="json"),
        "media_streams": [stream.model_dump(mode="json") for stream in result.media_streams],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
