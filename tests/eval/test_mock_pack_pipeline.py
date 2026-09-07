"""팀 목데이터가 eval 파이프라인을 끝까지 통과하는지 확인한다.

W4 의 목표는 "실제 기능이 없어도 공용 Mock 기준 E2E 가 끝까지 연결되는 상태"고,
Merge 가이드 §16 은 eval 에 "정상 Fixture 로 기대 Metric 이 나오는지"를 요구한다.
숫자가 훌륭한지가 아니라 **나오는지**를 본다.

입력은 남이 만든 것이다 — 서어진(search)의 candidate_events fixture 를 읽어
내 registry → run → normalize → score → 결과 파일까지 태운다.

**여기서 나오는 숫자는 성능이 아니다.** 시나리오 1건이라 recall 은 0 아니면 1이고,
negative clip 이 없어 fp_per_clip 은 null 이다. 지표가 맞다는 증거는 실제 데이터
(B tier 55클립 · A tier 120시퀀스)에서 가짜 구현 2종의 대비로 나온다.
"""
import json
import os

from eval import manifests_io, paths, run, score
from eval.runners import registry

MANIFEST = "mock_pack"
SCENARIO = "scenario_happy_001"


def test_mock_pack_impl_is_registered_without_the_fake_prefix():
    """`fake:` 는 정답지를 몰래 읽는 치트의 표시다.

    mock_pack impl 은 정답지를 보지 않고 팀 산출물을 읽으므로 그 접두어를
    쓰지 않는다. 구분이 흐려지면 치트를 실제 구현으로 착각할 수 있다.
    """
    assert "mock_pack:contracts" in registry.names()
    assert not any(n.startswith("fake:") and "mock_pack" in n
                   for n in registry.names())


def test_impl_reads_team_fixture_and_keeps_the_contract_span():
    """impl 이 서어진의 fixture 를 읽고 계약의 구간을 살려 오는지 확인한다.

    납작한 eval fixture(prediction_*.json)에는 구간이 없지만 계약 산출물인
    candidate_events 에는 있다(690000~708000ms). 그래서 IoU 매칭이 성립한다.
    """
    impl = registry.get("mock_pack:contracts")
    raw = impl({"manifest": MANIFEST, "stage": "candidate"})

    assert len(raw) == 1
    item = raw[0]
    assert item["clip_id"] == SCENARIO
    c = item["candidates"][0]
    assert c["t_start_sec"] == 690.0
    assert c["t_end_sec"] == 708.0
    assert c["event_type"] == "SOLID_LINE_LANE_CHANGE"


def test_gt_declares_that_it_is_derived_not_independent():
    """이 manifest 의 정답지는 팀 fixture 에서 유도한 것이다.

    독립적인 정답지가 아니므로 「예측이 맞다」의 근거가 될 수 없다. 파일이
    스스로 그 사실을 말해야 다음 사람이 이 숫자를 성능으로 읽지 않는다.
    """
    gt = manifests_io.load_gt(MANIFEST, "candidate")
    cov = gt["meta"]["coverage"]
    assert cov["derived_from_mock_pack"] is True
    assert cov["independent_ground_truth"] is False
    assert cov["purpose"]  # 무엇을 확인하는 정답지인지 적혀 있다


def test_pipeline_runs_end_to_end_and_writes_a_result(tmp_path, monkeypatch):
    """run -> score 가 끝까지 돌아 결과 파일이 나오는지 확인한다.

    이것이 오늘 확인할 핵심이다. 숫자의 크기가 아니라 연결이 목적이다.
    실제 저장소를 더럽히지 않도록 출력 경로만 tmp 로 돌린다.
    """
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))

    rc = run.main(["--impl", "mock_pack:contracts", "--manifest", MANIFEST,
                   "--stage", "candidate", "--run-id", "t_mock_e2e"])
    assert rc == 0

    rc = score.main(["--prediction", "t_mock_e2e"])
    assert rc == 0

    gt = manifests_io.load_gt(MANIFEST, "candidate")
    out = tmp_path / "results" / ("t_mock_e2e.%s.json" % gt["meta"]["gt_version"])
    result = json.loads(out.read_text(encoding="utf-8"))

    assert result["meta"]["manifest"] == MANIFEST
    assert result["meta"]["impl"] == "mock_pack:contracts"

    cand = result["candidate"]
    # 맞힌 예측이므로 적중한다 — 표본 1건이라 0 아니면 1이다
    assert cand["recall_at"]["1"] == 1.0
    assert cand["n_events"] == 1
    # negative clip 이 없으므로 0.0 이 아니라 null 이어야 한다
    assert cand["fp_per_clip"] is None
    assert "NO_NEGATIVE_CLIPS" in cand["coverage"]


def test_result_keeps_provenance_of_the_team_fixture():
    """결과에 어느 목데이터를 태운 것인지가 남는지 확인한다.

    manifest 이름만으로는 어느 시나리오였는지 알 수 없다. 정답지 meta 가
    시나리오를 적고 있어야 결과를 나중에 읽는 사람이 추적할 수 있다.
    """
    gt = manifests_io.load_gt(MANIFEST, "candidate")
    assert gt["meta"]["coverage"]["scenario_id"] == SCENARIO
