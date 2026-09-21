"""명시적 시간대 설정으로 원본 시각을 관찰하고 수동 확인 입력에 따라 anchor를 적용한다."""

import argparse
import json

from daesingo.recording import LocalTimeSourceObserver, RecordingCapabilityError, RecordingService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("--filename-offset", required=True, help="실행자가 지정한 ±HH:MM")
    parser.add_argument("--mdr-century", type=int)
    parser.add_argument("--overlay-match", choices=["match", "mismatch", "unconfirmed"], default="unconfirmed")
    parser.add_argument("--trusted", action="store_true")
    args = parser.parse_args()
    try:
        observer = LocalTimeSourceObserver(filename_offset=args.filename_offset, mdr_century=args.mdr_century)
        with RecordingService(time_source_observer=observer) as service:
            source = service.register_local_source(args.video).source_asset
            timeline = service.create_relative_timeline(source.source_asset_ref)
            observed = service.observe_time_sources(source.source_asset_ref)
            filename_candidates = [c for c in observed.candidates if c.source_kind == "FILENAME"]
            candidate = filename_candidates[0] if len(filename_candidates) == 1 else None
            result = service.apply_filename_anchor(
                {"timeline_id": timeline.timeline_id, "revision": timeline.revision},
                candidate.candidate_id if candidate else None,
                overlay_matches={"match": True, "mismatch": False, "unconfirmed": None}[args.overlay_match],
                trusted=args.trusted,
            )
            print(json.dumps({
                "configured_filename_offset": args.filename_offset,
                "candidates": [c.model_dump(mode="json") for c in observed.candidates],
                "checks": [c.model_dump(mode="json") for c in observed.checks],
                "manual_input": {"overlay_matches": result.overlay_matches, "trusted": result.trusted},
                "anchor_applied": result.applied,
                "timeline": result.timeline.model_dump(mode="json"),
            }, ensure_ascii=False, indent=2))
    except (ValueError, RecordingCapabilityError) as error:
        print(json.dumps({"error_code": getattr(error, "code", "INVALID_INPUT")}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
