"""실제 로컬 원본 등록 후 현재 AssetFacts를 조회한다. 파일을 쓰지 않는다."""

import argparse
import json

from daesingo.recording import RecordingCapabilityError, RecordingService


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="비공개 로컬 원본 경로")
    args = parser.parse_args()
    service = RecordingService()
    try:
        source = service.register_local_source(args.video).source_asset
        facts = service.lookup_asset_facts({"kind": "source_asset", "ref": source.source_asset_ref})
    except (RecordingCapabilityError, ValueError) as error:
        print(json.dumps({"error_code": getattr(error, "code", "INVALID_INPUT")}))
        return 1
    print(facts.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
