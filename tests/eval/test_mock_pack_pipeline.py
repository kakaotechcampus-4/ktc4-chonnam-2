"""팀 목데이터가 eval 파이프라인을 끝까지 통과하는지 확인한다.

W4 의 목표는 "실제 기능이 없어도 공용 Mock 기준 E2E 가 끝까지 연결되는 상태"고,
Merge 가이드 §16 은 eval 에 "정상 Fixture 로 기대 Metric 이 나오는지"를 요구한다.
숫자가 훌륭한지가 아니라 **나오는지**를 본다.

입력은 남이 만든 것이다 — 서어진(search)의 계약 산출물을 읽어 내 registry
→ run → normalize → score → 결과 파일까지 태운다.

**여기서 나오는 숫자는 성능이 아니다.** 정답지가 예측과 같은 fixture
(span.representative_ms)에서 나왔으므로 recall·onset_error 는 순환적이다.
지표가 맞다는 증거는 실제 데이터(B tier 55클립 · A tier 120시퀀스)에서
가짜 구현 2종의 대비로 나온다.
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


def test_impl_reads_team_fixture_and_keeps_the_coarse_window():
    """impl 이 서어진의 계약 산출물을 읽고 coarse 창을 살려 오는지 확인한다.

    span 은 「이 근처를 보라」는 창이지 사건의 외연이 아니다. 창은 보조
    신호(containment)로만 쓰고 매칭은 representative_ms 로 한다.
    """
    impl = registry.get("mock_pack:contracts")
    raw = impl({"manifest": MANIFEST, "stage": "candidate"})

    happy = next(i for i in raw if i["clip_id"] == SCENARIO)
    c = happy["candidates"][0]
    assert c["t_start_sec"] == 300.0
    assert c["t_end_sec"] == 420.0
    assert c["t_start_sec"] <= c["representative_sec"] <= c["t_end_sec"]


def test_impl_covers_every_scenario_that_has_a_search_fixture():
    """search fixture 가 없는 시나리오는 「후보 없음」이 아니라 「대상 아님」이다.

    둘을 뭉개면 infra_failure_001 이 음성 클립으로 분모에 들어가
    fp_per_clip 이 조용히 희석된다.
    """
    impl = registry.get("mock_pack:contracts")
    raw = impl({"manifest": MANIFEST, "stage": "candidate"})

    clip_ids = {item["clip_id"] for item in raw}
    assert "scenario_infra_failure_001" not in clip_ids
    assert len(raw) == 6
    # empty_001 은 fixture 가 있고 후보가 0건이다 — 이쪽은 진짜 음성이다
    empty = next(i for i in raw if i["clip_id"] == "scenario_empty_001")
    assert empty["candidates"] == []


def test_impl_carries_representative_ms_for_point_error_matching():
    """점 오차 매처가 쓸 값이 예측에 실려 오는지 본다.

    계약의 span 은 coarse 후보 창이고 사건 외연이 아니다
    (contract-analysis-run-candidate-event v1.1 §4-1). 매칭은
    representative_ms 로 한다.
    """
    impl = registry.get("mock_pack:contracts")
    raw = impl({"manifest": MANIFEST, "stage": "candidate"})

    happy = next(i for i in raw if i["clip_id"] == "scenario_happy_001")
    c = happy["candidates"][0]
    assert c["representative_sec"] == 312.48
    assert c["timeline_revision"] == 1
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


def test_gt_has_one_item_per_scenario_and_keeps_the_circularity_warning():
    gt = manifests_io.load_gt(MANIFEST, "candidate")
    cov = gt["meta"]["coverage"]

    assert len(gt["items"]) == 7
    assert cov["clips_total"] == 7
    assert cov["clips_with_events"] == 5
    assert cov["derived_from_mock_pack"] is True
    assert cov["independent_ground_truth"] is False
    assert "순환" in cov["warning"]
    # 죽은 경로를 가리키지 않는다
    for p in cov["derived_from"]:
        assert os.path.exists(os.path.join(paths.REPO_ROOT, p.split(" ")[0])), p


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
    # scenario_happy_001 은 맞힌 예측이므로 그 사건은 적중한다
    assert cand["recall_at"]["1"] == 1.0


def test_empty_scenario_makes_fp_per_clip_a_real_number(tmp_path, monkeypatch):
    """empty_001 이 pack 최초 음성 케이스다.

    fp_per_clip 이 null(NO_NEGATIVE_CLIPS)에서 처음으로 실제 값이 된다.
    """
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))

    assert run.main(["--impl", "mock_pack:contracts", "--manifest", MANIFEST,
                     "--stage", "candidate", "--run-id", "t_seven"]) == 0
    assert score.main(["--prediction", "t_seven"]) == 0

    gt = manifests_io.load_gt(MANIFEST, "candidate")
    out = tmp_path / "results" / ("t_seven.%s.json" % gt["meta"]["gt_version"])
    cand = json.loads(out.read_text(encoding="utf-8"))["candidate"]

    assert cand["fp_per_clip"] == 0.0
    assert cand["n_negative_clips"] == 1
    assert cand["excluded_by_reason"] == {"EXCLUDED": 1}


def test_result_keeps_provenance_of_the_team_fixture():
    """결과를 나중에 읽는 사람이 어느 팀 산출물에서 유도됐는지 추적할 수
    있는지 확인한다. 시나리오가 7개로 늘어 단일 scenario_id 는 의미가
    없어졌고, 정답지 meta 의 derived_from 이 그 자리를 대신한다.
    """
    gt = manifests_io.load_gt(MANIFEST, "candidate")
    cov = gt["meta"]["coverage"]
    assert cov["derived_from"]
    for p in cov["derived_from"]:
        assert os.path.exists(os.path.join(paths.REPO_ROOT, p.split(" ")[0])), p


def test_plate_stage_pipeline_runs_end_to_end_and_writes_a_result(tmp_path, monkeypatch):
    """--stage plate 를 실제로 태우는 유일한 테스트다.

    이게 없으면 _run_plate 가 판독 하나를 조용히 빠뜨려도(예: abstain
    처리된 readout_p001_plate 를 빼먹어도) exact_accuracy 는 그대로 1.0 이고
    abstention_recall 만 조용히 null 이 돼 아무것도 실패하지 않는다.
    """
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))

    rc = run.main(["--impl", "mock_pack:contracts", "--manifest", MANIFEST,
                   "--stage", "plate", "--run-id", "t_mock_plate"])
    assert rc == 0

    rc = score.main(["--prediction", "t_mock_plate"])
    assert rc == 0

    gt = manifests_io.load_gt(MANIFEST, "plate")
    out = tmp_path / "results" / ("t_mock_plate.%s.json" % gt["meta"]["gt_version"])
    result = json.loads(out.read_text(encoding="utf-8"))

    plate = result["plate"]
    assert plate["n"] == 5
    assert plate["exact_accuracy"] == 1.0
    assert plate["abstention_recall"] == 1.0
    assert plate["wrong_accept_rate"] == 0.0
    assert "순환" in plate["coverage"]
    assert "분자" in plate["coverage"]


def test_gt_states_the_clip_id_convention_in_the_file():
    """규약이 코드 주석이 아니라 결과에서 읽히는 자리에 있어야 한다.

    B tier 는 clip_id 가 실재하고 mock tier 는 시나리오다. 같은 scorer 를
    타므로 결과 파일만 보고 어느 쪽인지 말할 수 있어야 한다.
    """
    for stage in ("candidate", "plate"):
        meta = manifests_io.load_gt(MANIFEST, stage)["meta"]
        assert meta.get("contract_version")
    cand_meta = manifests_io.load_gt(MANIFEST, "candidate")["meta"]
    assert "scenario_id" in cand_meta["clip_id_convention"]
    assert "clip_id" in cand_meta["clip_id_convention"]
