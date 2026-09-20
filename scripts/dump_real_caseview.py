#!/usr/bin/env python3
"""실제 `case.get_view()` 산출물을 web이 읽을 수 있는 자리에 떨어뜨린다 (이슈 #102).

`apps/web`의 로더는 저장소의 JSON을 glob으로 읽는다. 그런데 real 경로의 `CaseView`는
`tests/case/test_real_e2e.py` 안에서만 만들어지고 파일로 남지 않아서, **화면은 mock
스냅샷밖에 못 본다.** 이 스크립트가 그 한 hop을 잇는다 — 새 배선이 아니라 이미 도는
체인의 출력을 파일로 쓰는 것뿐이다.

체인은 `test_real_e2e.py`와 같다(recording→search→후보 선택→readout→evidence→CaseView).
값을 여기서 만들지 않는다 — `service.build_view_from_adapter()`가 준 dict를 그대로 쓴다.

사용:
    python scripts/dump_real_caseview.py
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
from daesingo.case.adapters import MockFixtureAdapter, RealAdapter  # noqa: E402
from daesingo.case.domain import CaseAggregate  # noqa: E402

MOCK_ROOT = Path(ROOT) / "data" / "mock"
DEFAULT_OUT = os.path.join(ROOT, "data", "real", "case", "real_e2e_happy_001.json")
CASE_ID = "case_h001_real_e2e"
SCENARIO_ID = "real_e2e_happy_001"


def build_view():
    """`test_real_e2e.py::test_real_e2e_happy_path_reaches_ready_caseview`와 같은 순서."""
    mock = MockFixtureAdapter(MOCK_ROOT, "happy_001")
    scope = mock.get_analysis_scopes()[0]
    real = RealAdapter(case_id=CASE_ID, search_scope=scope, mock_root=MOCK_ROOT)

    # 이슈 #103 — hints={}로 고정하면 후보 화면의 「기억 단서와 대조」가 그릴 값이 없다.
    case = CaseAggregate.intake(case_id=CASE_ID, hints=mock.get_hints(), manifest_summary={})
    case.start_search()
    jobs.issue_coarse_search(case, scope_ref="scope_h001",
                             input_fingerprint="sha1:h001-coarse-search")

    candidates = service.receive_search_candidates(case, real)
    case.select_candidate(candidates[0].candidate_id)

    jobs.issue_plate_read(case, input_fingerprint="sha1:h001-plate-read-clip_h001")
    jobs.issue_overlay_time_read(case, input_fingerprint="sha1:h001-overlay-read-clip_h001")
    jobs.issue_fine_verify(case, input_fingerprint="sha1:h001-fine-verify-as_h001_fine")
    jobs.issue_report_video_export(case, input_fingerprint="sha1:h001-report-video-export")
    case.mark_ready()

    return service.build_view_from_adapter(case, real)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    view = build_view()
    payload = {
        "scenario_id": SCENARIO_ID,
        "module": "case",
        # mock pack과 구분되는 유일한 표시다. 화면 탭에 그대로 뜨고, 아래 시각으로
        # 「언제 돌린 산출물인가」가 보인다 — 오래된 스냅샷을 실시간으로 착각하지 않게.
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "generated_by": "scripts/dump_real_caseview.py",
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
