#!/usr/bin/env python3
"""실제 영상(`register_local_source`)으로 `case.get_view()` 산출물을 만들어
`data/real/case/`에 web이 읽을 수 있는 자리로 떨어뜨린다.

`dump_real_caseview.py`(fixture `scenario_happy_001`)와 짝이지만, 백엔드가
`RealVideoAdapter`(실제 로컬 영상 등록 → real Gemini/Elice service → 실제
PaddleOCR)라는 점이 다르다. 값을 여기서 만들지 않는다 —
`service.build_view_from_adapter()`가 준 dict를 그대로 쓴다.

Coarse/Fine은 real Elice/Gemini 유료 호출이다 — 이슈 #132(search 내부
coarse/fine 시간 정합성 검증)가 풀리기 전까지는 대부분 실패한다
(`docs/modules/case/experiments/real-e2e-20260922-monday-baseline.md` 참고).

사용:
    python scripts/dump_real_video_caseview.py --video doc/20260620_141956_EVT_1.avi
"""
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from daesingo.case import jobs, service  # noqa: E402
from daesingo.case.adapters import RealVideoAdapter  # noqa: E402
from daesingo.case.domain import CaseAggregate  # noqa: E402

DEFAULT_VIDEO = os.path.join(ROOT, "doc", "20260620_141956_EVT_1.avi")
DEFAULT_OUT = os.path.join(ROOT, "data", "real", "case", "real_e2e_monday_video.json")
CASE_ID = "case_monday_real_video"
SCOPE_ID = "scope_monday_real_video"
SCENARIO_ID = "real_e2e_monday_video"


def build_view(video_path: str):
    case = CaseAggregate.intake(case_id=CASE_ID, hints={}, manifest_summary={})
    real = RealVideoAdapter(
        case_id=CASE_ID, case=case, local_video_path=video_path, scope_id=SCOPE_ID
    )
    try:
        case.start_search()
        jobs.issue_coarse_search(
            case, scope_ref=SCOPE_ID, input_fingerprint=f"sha1:{SCOPE_ID}-coarse-search"
        )

        candidates = service.receive_search_candidates(case, real)
        case.select_candidate(candidates[0].candidate_id)

        jobs.issue_plate_read(case, input_fingerprint=f"sha1:{SCOPE_ID}-plate-read")
        jobs.issue_overlay_time_read(case, input_fingerprint=f"sha1:{SCOPE_ID}-overlay-read")
        case.mark_ready()

        return service.build_view_from_adapter(case, real)
    finally:
        real.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default=DEFAULT_VIDEO)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    view = build_view(args.video)
    payload = {
        "scenario_id": SCENARIO_ID,
        "module": "case",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_by": "scripts/dump_real_video_caseview.py",
        "source_video": os.path.basename(args.video),
        "case_views": [view],
    }

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print("생성: " + os.path.relpath(args.out, ROOT).replace(os.sep, "/"))
    print("  stage=%s · candidates=%d · package=%s"
          % (view["stage"], len(view["candidates"]), "있음" if view["package"] else "없음"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
