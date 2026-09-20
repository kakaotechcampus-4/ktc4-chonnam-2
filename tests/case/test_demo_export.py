"""이슈 #108 — real E2E `CaseView`를 web(`fixtures.ts`)이 읽을 수 있는 JSON으로
export하는 최소 경로. `apps/web/src/contracts/fixtures.ts`가 기대하는 `ScenarioFile`
모양(`{scenario_id, module, case_views: CaseView[]}`)을 그대로 맞춘다 — `data/mock/case/`
와 같은 파일 모양이어야 web이 별도 파싱 로직 없이 읽을 수 있다.
"""
import json

from daesingo.case.demo_happy_001 import export_view_snapshot


def test_export_view_snapshot_writes_fixtures_ts_shape(tmp_path):
    view = {"stage": "READY", "hints": {"vehicle": "흰색 SUV"}}

    output_path = export_view_snapshot(view, scenario_id="happy_001", output_root=tmp_path)

    assert output_path == tmp_path / "scenario_happy_001.json"
    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written == {
        "scenario_id": "happy_001",
        "module": "case",
        "case_views": [view],
    }
