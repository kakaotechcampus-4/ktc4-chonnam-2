import json
import os
from eval import manifests_io, run, score, paths
from eval.scorers import candidate, classification, cost


def test_score_cli_writes_results_with_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
              "--stage", "candidate", "--run-id", "run_cli_001"])
    rc = score.main(["--prediction", "run_cli_001"])
    assert rc == 0
    gt_version = manifests_io.load_gt("b_youtube", "candidate")["meta"]["gt_version"]
    out = os.path.join(str(tmp_path), score.result_filename(
        "run_cli_001", {"gt_version": gt_version,
                        "scorer_version": candidate.SCORER_VERSION,
                        "cost_scorer_version": cost.SCORER_VERSION}))
    with open(out, encoding="utf-8") as f:
        res = json.load(f)
    assert res["candidate"]["recall_at"]["3"] == 1.0
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
    out = next(p for p in os.listdir(str(tmp_path)) if p.startswith(run_id + ".g1."))
    with open(os.path.join(str(tmp_path), out), encoding="utf-8") as f:
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
    gt_version = manifests_io.load_gt("b_youtube", "candidate")["meta"]["gt_version"]
    path = os.path.join(str(tmp_path), score.result_filename(
        "run_cli_notrun", {"gt_version": gt_version,
                           "scorer_version": candidate.SCORER_VERSION,
                           "cost_scorer_version": cost.SCORER_VERSION}))
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

    result = json.loads(next((tmp_path / "results").glob("t_pin.mp1.*.json"))
                        .read_text(encoding="utf-8"))
    assert result["meta"]["scorer_version"] == "s3"
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

    result = json.loads(next((tmp_path / "results").glob("t_cost_wiring.mp1.*.json"))
                        .read_text(encoding="utf-8"))
    assert result["cost"]["currency"] == "KRW"
    assert result["cost"]["total"] == 3570.0
    assert result["cost"]["cost_per_case"]["case_h001"] == 938.0


def test_plate_stage_with_no_gt_completes_and_reports_why(tmp_path, monkeypatch):
    """A tier 처럼 plate 정답지가 없는 manifest 로 --stage plate 를 돌리면

    FileNotFoundError 로 죽지 않고, 결과 파일이 plate 정답지가 없다는
    사실을 null + 사유로 남긴다 (FIX7 — NO_GT 를 CLI 에서 실제로 밟는다).
    """
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))
    # b_youtube 에는 gt/gt_plate.json 이 없다. mock_pack:contracts 는 manifest
    # 이름과 무관하게 data/mock/readout 을 읽으므로 예측 자체는 만들어진다.
    assert run.main(["--impl", "mock_pack:contracts", "--manifest", "b_youtube",
                     "--stage", "plate", "--run-id", "t_plate_no_gt"]) == 0
    rc = score.main(["--prediction", "t_plate_no_gt"])
    assert rc == 0

    results_dir = tmp_path / "results"
    out = next(results_dir.glob("t_plate_no_gt.*.json"))
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["plate"]["n"] is None
    assert result["plate"]["exact_accuracy"] is None
    assert "NO_PLATE_GT" in result["plate"]["coverage"]


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


def test_classification_result_pins_its_own_scorer_version(tmp_path, monkeypatch):
    """stage 마다 자기 버전을 적는다 — candidate 의 값을 빌려 쓰지 않는다.

    classification 결과에 candidate 의 버전이 실리면 그 파일이 candidate 의
    지표 정의("IoU -> onset point error", "1:1 배정")를 자기 것인 양 말한다.
    """
    from eval.scorers import candidate as candidate_scorer
    from eval.scorers import classification as classification_scorer

    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))
    assert run.main(["--impl", "fake:always_correct", "--manifest", "ab_mixed",
                     "--stage", "classification", "--run-id", "t_cls"]) == 0
    assert score.main(["--prediction", "t_cls"]) == 0

    result = json.loads(next((tmp_path / "results").glob("t_cls.ag1.*.json"))
                        .read_text(encoding="utf-8"))
    assert result["meta"]["scorer_version"] == classification_scorer.SCORER_VERSION
    assert result["meta"]["scorer_version"] != candidate_scorer.SCORER_VERSION


def test_prediction_ref_sha_matches_the_file_as_committed(tmp_path, monkeypatch):
    """결과에 적힌 지문이 실제 예측 파일의 지문이어야 한다.

    산출물을 텍스트 모드로 쓰면 Windows 에서 \n 이 \r\n 으로 바뀌는데
    .gitattributes 는 eol=lf 라, 기록된 sha 가 **커밋된 파일의 sha 가
    아니게 된다.** 클론한 사람은 전원 불일치를 본다 — prediction_ref 가
    「이 결과는 이 예측을 채점했다」를 증명하지 못한다.
    """
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "predictions"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "results"))
    assert run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
                     "--stage", "candidate", "--run-id", "t_sha"]) == 0
    assert score.main(["--prediction", "t_sha"]) == 0

    pred = tmp_path / "predictions" / "t_sha.json"
    assert b"\r\n" not in pred.read_bytes(), "산출물에 CRLF 가 섞였다"

    gt_version = manifests_io.load_gt("b_youtube", "candidate")["meta"]["gt_version"]
    result = json.loads(
        next((tmp_path / "results").glob("t_sha.%s.*.json" % gt_version))
        .read_text(encoding="utf-8"))
    assert result["meta"]["prediction_ref"]["sha256"] == manifests_io.sha256_file(str(pred))


def test_committed_results_point_at_the_committed_predictions():
    """커밋된 산출물끼리도 지문이 맞아야 한다 — 위 테스트는 tmp 안에서만 본다."""
    import glob
    from eval import paths as p
    checked = 0
    for path in sorted(glob.glob(os.path.join(p.results_dir(), "*.json"))):
        with open(path, encoding="utf-8") as f:
            result = json.load(f)
        ref = result.get("meta", {}).get("prediction_ref")
        if not ref:
            continue
        target = os.path.join(p.REPO_ROOT, ref["path"])
        assert manifests_io.sha256_file(target) == ref["sha256"], path
        checked += 1
    assert checked >= 6


# --- 채점 결과 보존 (멘토 피드백 2026-09-20) ---
#
# 「채점 결과도 덮어쓰지 말고 각각 저장해두시길 바랍니다. 채점 프로세스도
# 바뀔 수 있으니까요.」
#
# 실제로 한 번 잃었다 — s2 -> s3 때 파일명이 {run_id}.{gt_version}.json
# 이라 s2 결과가 전부 사라졌다. 예측은 run.py 가 덮어쓰기를 막는데
# 채점 결과는 안 막고 있었다.


def _score_once(tmp_path, monkeypatch, run_id, stage="candidate",
                manifest="b_youtube", impl="fake:always_correct"):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path / "p"))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path / "r"))
    assert run.main(["--impl", impl, "--manifest", manifest,
                     "--stage", stage, "--run-id", run_id]) == 0
    return score.main(["--prediction", run_id])


def test_result_filename_carries_every_version_that_made_the_numbers(tmp_path, monkeypatch):
    """파일명만 보고 어느 채점기가 낸 숫자인지 알 수 있어야 한다."""
    assert _score_once(tmp_path, monkeypatch, "t_name") == 0

    gt_version = manifests_io.load_gt("b_youtube", "candidate")["meta"]["gt_version"]
    expected = "t_name.%s.%s-%s.json" % (
        gt_version, candidate.SCORER_VERSION, cost.SCORER_VERSION)
    assert (tmp_path / "r" / expected).exists()


def test_rescoring_the_same_thing_refuses_instead_of_overwriting(tmp_path, monkeypatch):
    """예측과 같은 규율이다 (run.py rc 3)."""
    assert _score_once(tmp_path, monkeypatch, "t_twice") == 0
    out = next((tmp_path / "r").glob("t_twice.*.json"))
    before = out.read_text(encoding="utf-8")

    assert score.main(["--prediction", "t_twice"]) == 3
    assert out.read_text(encoding="utf-8") == before


def test_a_scorer_version_bump_lands_beside_the_old_result(tmp_path, monkeypatch):
    """채점 프로세스가 바뀌면 두 결과가 나란히 남아야 비교할 수 있다."""
    assert _score_once(tmp_path, monkeypatch, "t_bump") == 0
    old = next((tmp_path / "r").glob("t_bump.*.json"))

    monkeypatch.setattr(candidate, "SCORER_VERSION", "s99")
    assert score.main(["--prediction", "t_bump"]) == 0

    both = sorted(p.name for p in (tmp_path / "r").glob("t_bump.*.json"))
    assert len(both) == 2, both
    assert old.exists()
    assert any(".s99-" in n for n in both)


def test_the_result_records_the_same_version_its_filename_claims(tmp_path, monkeypatch):
    """파일명과 내용이 어긋나면 파일명을 믿을 수 없다."""
    monkeypatch.setattr(candidate, "SCORER_VERSION", "s99")
    assert _score_once(tmp_path, monkeypatch, "t_agree") == 0

    out = next((tmp_path / "r").glob("t_agree.*.json"))
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["meta"]["scorer_version"] == "s99"
    assert ".s99-" in out.name
