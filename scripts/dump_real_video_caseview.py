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


def build_view(video_path: str, target_event_types: list[str] | None = None):
    case = CaseAggregate.intake(case_id=CASE_ID, hints={}, manifest_summary={})
    real = RealVideoAdapter(
        case_id=CASE_ID,
        case=case,
        local_video_path=video_path,
        scope_id=SCOPE_ID,
        target_event_types=target_event_types,
    )
    try:
        case.start_search()
        jobs.issue_coarse_search(
            case, scope_ref=SCOPE_ID, input_fingerprint=f"sha1:{SCOPE_ID}-coarse-search"
        )

        candidates = service.receive_search_candidates(case, real)
        raw_candidate = real._candidates_by_id[candidates[0].candidate_id]
        print(
            "  coarse span: start_ms=%s end_ms=%s representative_ms=%s"
            % (
                raw_candidate.span.start_ms,
                raw_candidate.span.end_ms,
                raw_candidate.span.representative_ms,
            )
        )
        case.select_candidate(candidates[0].candidate_id)

        jobs.issue_plate_read(case, input_fingerprint=f"sha1:{SCOPE_ID}-plate-read")
        jobs.issue_overlay_time_read(case, input_fingerprint=f"sha1:{SCOPE_ID}-overlay-read")
        case.mark_ready()

        view = service.build_view_from_adapter(case, real)
        # `_build_evidence_bundle()`가 위 build_view_from_adapter() 호출 중에 이미
        # 캐시해 둔 값 — Fine을 다시 부르지 않고 그대로 읽는다. real-e2e-protocol.md
        # §5/§10이 요구하는 "OCR 실패 시 UNKNOWN인지"·disposition 사유를 실행 결과에
        # 남기기 위한 진단용 (evidence가 null일 때 "왜"인지 CaseView만 봐서는 알 수
        # 없다 — 2026-09-23 real_e2e_yt0002 실행에서 필요성 확인).
        bundle = real._evidence_bundle
        disposition = {
            "decision": bundle.disposition.decision if bundle else None,
            "verification": bundle.disposition.verification if bundle else None,
            "reason_code": bundle.disposition.reason_code if bundle else None,
            "uncertainties": bundle.visual_evidence.get("uncertainties") if bundle else None,
            "visual_evidence": bundle.visual_evidence if bundle else None,
        }
        return view, disposition
    finally:
        real.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default=DEFAULT_VIDEO)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument(
        "--target-event-types",
        default=None,
        help="쉼표로 구분한 v4 baseline enum 목록(예: CENTER_LINE_CROSSING). "
        "생략하면 real_e2e._MONDAY_TARGET_EVENT_TYPES로 fallback한다 — scope.py의 "
        "정의대로 case에 아직 intake UI가 없어 호출자가 공급해야 하는 값이다.",
    )
    args = parser.parse_args()
    target_event_types = (
        [t.strip() for t in args.target_event_types.split(",") if t.strip()]
        if args.target_event_types
        else None
    )

    view, disposition = build_view(args.video, target_event_types)
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
    print("  fine disposition: decision=%s verification=%s reason_code=%s"
          % (disposition["decision"], disposition["verification"], disposition["reason_code"]))
    if disposition["uncertainties"]:
        print("  fine uncertainties: " + json.dumps(disposition["uncertainties"], ensure_ascii=False))
    if disposition["decision"] == "NOT_ASSEMBLED":
        print("  fine visual_evidence (full, diagnostic): "
              + json.dumps(disposition.get("visual_evidence"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
