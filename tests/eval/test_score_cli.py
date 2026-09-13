import json
import os
from eval import run, score, paths
from eval.scorers import classification


def test_score_cli_writes_results_with_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
              "--stage", "candidate", "--run-id", "run_cli_001"])
    rc = score.main(["--prediction", "run_cli_001"])
    assert rc == 0
    out = os.path.join(str(tmp_path), "run_cli_001.g1.json")
    with open(out, encoding="utf-8") as f:
        res = json.load(f)
    assert res["candidate"]["recall_at"]["1"] == 1.0
    assert res["plate"]["exact_accuracy"] is None
    assert res["meta"]["impl"] == "fake:always_correct"


def test_score_cli_returns_rc2_when_gt_missing_not_a_traceback(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
              "--stage", "candidate", "--run-id", "run_missing_gt"])
    # prediction이 가리키는 manifest를 GT가 없는 이름으로 바꿔치기한다.
    p = os.path.join(str(tmp_path), "run_missing_gt.json")
    with open(p, encoding="utf-8") as f:
        env = json.load(f)
    env["meta"]["manifest"] = "does_not_exist"
    with open(p, "w", encoding="utf-8") as f:
        json.dump(env, f)
    rc = score.main(["--prediction", "run_missing_gt"])
    assert rc == 2


def _score_classification(run_id, impl, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    assert run.main(["--impl", impl, "--manifest", "a_aihub",
                     "--stage", "classification", "--run-id", run_id]) == 0
    assert score.main(["--prediction", run_id]) == 0
    with open(os.path.join(str(tmp_path), run_id + ".g1.json"), encoding="utf-8") as f:
        return json.load(f)


def test_classification_runs_end_to_end_and_fakes_contrast(tmp_path, monkeypatch):
    """치트 두 개의 점수 차이가 classification 지표 계산의 검증이다 (§6)."""
    ok = _score_classification("run_cls_ok", "fake:always_correct", tmp_path, monkeypatch)
    ng = _score_classification("run_cls_ng", "fake:always_wrong", tmp_path, monkeypatch)

    assert ok["classification"]["recall_macro"] == 1.0
    assert ok["classification"]["precision_macro"] == 1.0
    assert ok["classification"]["target_correctness"] == 1.0
    assert ng["classification"]["recall_macro"] == 0.0
    assert ng["classification"]["target_correctness"] == 0.0
    assert ok["classification"]["n"] == 120


def test_not_run_classification_block_keeps_every_metric_key(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
              "--stage", "candidate", "--run-id", "run_cli_notrun"])
    assert score.main(["--prediction", "run_cli_notrun"]) == 0
    path = os.path.join(str(tmp_path), "run_cli_notrun.g1.json")
    with open(path, encoding="utf-8") as f:
        text = f.read()
    res = json.loads(text)
    blank = res["classification"]
    assert blank["recall_macro"] is None and blank["confusion"] is None
    assert blank["coverage"].startswith("NOT_RUN")
    # 채점된 블록과 키 집합이 같아야 한다 (plate 무데이터 블록과 같은 규칙).
    assert set(blank) == set(classification.not_run("x"))
    # 결과 파일은 개행으로 끝난다 — 텍스트 도구로 이어 붙이기 위해서다.
    assert text.endswith("}\n")


def test_result_pins_the_scorer_version_and_the_prediction_it_scored(tmp_path, monkeypatch):
    """어느 지표 정의로 어느 예측을 채점했는지가 결과에 남아야 한다.

    run_id 문자열이 같다는 것만으로 이어져 있으면, 예측 파일을 덮어써도
    결과가 그 사실을 모른다.
    """
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))
    assert run.main(["--impl", "mock_pack:contracts", "--manifest", "mock_pack",
                     "--stage", "candidate", "--run-id", "t_pin"]) == 0
    assert score.main(["--prediction", "t_pin"]) == 0

    result = json.loads((tmp_path / "results" / "t_pin.mp1.json").read_text(encoding="utf-8"))
    assert result["meta"]["scorer_version"] == "s2"
    ref = result["meta"]["prediction_ref"]
    assert ref["path"].endswith("t_pin.json")
    assert len(ref["sha256"]) == 64


def test_cost_block_is_wired_end_to_end_and_keyed_by_case_id(tmp_path, monkeypatch):
    """단위 테스트는 cost.score() 만 본다 — build_result 가 실제로 그 값을
    result["cost"] 로 옮겨 쓰는지는 여기서 pin 한다."""
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))
    assert run.main(["--impl", "mock_pack:contracts", "--manifest", "mock_pack",
                     "--stage", "candidate", "--run-id", "t_cost_wiring"]) == 0
    assert score.main(["--prediction", "t_cost_wiring"]) == 0

    result = json.loads((tmp_path / "results" / "t_cost_wiring.mp1.json").read_text(encoding="utf-8"))
    assert result["cost"]["currency"] == "KRW"
    assert result["cost"]["total"] == 3570.0
    assert result["cost"]["cost_per_case"]["case_h001"] == 938.0


def test_score_refuses_when_the_contract_version_does_not_match(tmp_path, monkeypatch):
    """버전이 다르면 비교를 거부한다 (module-architecture v4 §9-2 규칙 5)."""
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))
    assert run.main(["--impl", "mock_pack:contracts", "--manifest", "mock_pack",
                     "--stage", "candidate", "--run-id", "t_mismatch"]) == 0

    path = tmp_path / "predictions" / "t_mismatch.json"
    env = json.loads(path.read_text(encoding="utf-8"))
    env["meta"]["contract_version"] = "analysis-run-candidate-event/v9.9"
    path.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")

    assert score.main(["--prediction", "t_mismatch"]) == 4


def test_score_proceeds_when_only_the_ground_truth_declares_a_contract_version(tmp_path, monkeypatch):
    """한쪽만 null 이면 불일치가 아니다 — 훅 없는 impl 을 거부하면 안 된다.

    `fake:always_correct` 는 mock_pack 의 GT 모양(t_onset_sec 만 있고
    t_start_sec/t_end_sec 가 없다)을 읽지 못하고 KeyError 로 죽는다 —
    b_youtube 용으로 만들어진 치트라 mock_pack 계약 산출물을 모른다.
    그래서 실제 CLI 호출 대신, 진짜 실행으로 얻은 envelope 의
    contract_version 만 null 로 덮어써 같은 상황(정답지는 버전을 선언,
    예측은 훅이 없어 null)을 만든다 — 위 불일치 테스트와 같은 패턴이다.
    """
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))
    assert run.main(["--impl", "mock_pack:contracts", "--manifest", "mock_pack",
                     "--stage", "candidate", "--run-id", "t_null_env_contract"]) == 0

    path = tmp_path / "predictions" / "t_null_env_contract.json"
    env = json.loads(path.read_text(encoding="utf-8"))
    assert env["meta"]["contract_version"] is not None  # 정답지가 버전을 선언하는 쪽
    env["meta"]["contract_version"] = None  # 예측 쪽은 훅이 없다고 가정한다
    path.write_text(json.dumps(env, ensure_ascii=False), encoding="utf-8")

    assert score.main(["--prediction", "t_null_env_contract"]) == 0
    reread = json.loads(path.read_text(encoding="utf-8"))
    assert reread["meta"]["contract_version"] is None
