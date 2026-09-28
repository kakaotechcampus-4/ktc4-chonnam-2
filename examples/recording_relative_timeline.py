"""단일 로컬 영상 등록 → 상대 Timeline 생성 → 공개 조회 재현 예제."""

import argparse
import json

from daesingo.recording import FfprobeMediaProbe, RecordingCapabilityError, RecordingService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="비공개 로컬 영상 파일 경로 한 개")
    parser.add_argument("--ffprobe", default="ffprobe")
    args = parser.parse_args()
    service = RecordingService(media_probe=FfprobeMediaProbe(args.ffprobe))
    try:
        registered = service.register_local_source(args.video)
        timeline = service.create_relative_timeline(registered.source_asset.source_asset_ref)
        stored = service.get_timeline(timeline.timeline_id, timeline.revision)
        latest = service.get_latest_timeline(timeline.timeline_id)
        if stored != timeline or latest != timeline:
            raise ValueError("생성 결과와 저장된 Timeline이 일치하지 않습니다")
    except (RecordingCapabilityError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({
        "source_asset": registered.source_asset.model_dump(mode="json"),
        "media_streams": [stream.model_dump(mode="json") for stream in registered.media_streams],
        "recording_timeline": stored.model_dump(mode="json"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
