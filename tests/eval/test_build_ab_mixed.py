"""ab_mixed manifest 빌더 (F12).

5×5 confusion 의 NONE 행·열은 A tier 만으로는 채울 수 없다 — 전 시퀀스가
4종 중 하나다. 이 빌더가 B tier 의 negative 클립을 NONE 으로 들여온다.
"""
import pytest

from eval.tools import build_ab_mixed

A_SEQ = {"meta": {"manifest_version": "m1", "tier": "A", "source": "aihub"},
         "sequences": [
             {"sequence_id": "SEQ_SIG", "violation_type": "SIGNAL", "frame_count": 40,
              "condition": {"weather": "맑음", "day_night": "주간", "road_type": "일반도로"},
              "archive": "VS.zip", "archive_path": "x/y", "split": "DEV"},
             {"sequence_id": "SEQ_CTR", "violation_type": "CENTER_LINE_CROSSING",
              "frame_count": 40,
              "condition": {"weather": "흐림", "day_night": "야간", "road_type": "일반도로"},
              "archive": "VS.zip", "archive_path": "x/z", "split": "DEV"},
         ]}

A_GT = {"meta": {"gt_version": "g1", "tier": "A", "stage": "classification",
                 "coverage": {"sequences_total": 2}},
        "items": [
            {"sequence_id": "SEQ_SIG", "label": "SIGNAL", "target_bbox": [0, 0, 10, 10],
             "target_frame": "f.jpg", "distractor_count": 1,
             "condition": {"weather": "맑음", "day_night": "주간", "road_type": "일반도로"},
             "source_tier": "A"},
            {"sequence_id": "SEQ_CTR", "label": "CENTER_LINE_CROSSING", "target_bbox": None,
             "target_frame": None, "distractor_count": None,
             "condition": {"weather": "흐림", "day_night": "야간", "road_type": "일반도로"},
             "source_tier": "A"},
        ]}

B_CLIPS = {"meta": {"manifest_version": "m3", "clip_rule_version": "c1", "tier": "B",
                    "source": "youtube"},
           "clips": [
               {"clip_id": "YT_A", "source_video_id": "YT_0001", "duration_sec": 60.0,
                "file_path": "eval/datasets/youtube/clips/YT_A.mp4", "sha256": "a" * 64,
                "split": "DEV"},
               {"clip_id": "YT_B", "source_video_id": "YT_0001", "duration_sec": 60.0,
                "file_path": "eval/datasets/youtube/clips/YT_B.mp4", "sha256": "b" * 64,
                "split": "DEV"},
               {"clip_id": "YT_C", "source_video_id": "YT_0001", "duration_sec": 60.0,
                "file_path": "eval/datasets/youtube/clips/YT_C.mp4", "sha256": "c" * 64,
                "split": "DEV"},
               {"clip_id": "YT_HAS_EVENT", "source_video_id": "YT_0001", "duration_sec": 60.0,
                "file_path": "eval/datasets/youtube/clips/YT_HAS_EVENT.mp4",
                "sha256": "d" * 64, "split": "DEV"},
           ]}

B_GT = {"meta": {"gt_version": "g3", "tier": "B", "stage": "candidate",
                 "coverage": {"clips_total": 4, "clips_reviewed": 4, "clips_with_events": 1,
                              "negatives_confirmed": True}},
        "items": [
            {"clip_id": "YT_A", "source_video_id": "YT_0001", "targets": []},
            {"clip_id": "YT_B", "source_video_id": "YT_0001", "targets": []},
            {"clip_id": "YT_C", "source_video_id": "YT_0001", "targets": []},
            {"clip_id": "YT_HAS_EVENT", "source_video_id": "YT_0001", "targets": [
                {"event_id": "E1", "scoring": "INCLUDED", "violation_type": "SIGNAL",
                 "t_onset_sec": 10}]},
        ]}


def _build(n_none=2, seed=1):
    return build_ab_mixed.build(A_SEQ, A_GT, B_CLIPS, B_GT, n_none=n_none, seed=seed)


def test_none_items_come_only_from_reviewed_negative_clips():
    """사건이 있는 클립은 NONE 이 아니다 — 들어오면 정답이 거짓이 된다."""
    _, gt = _build(n_none=3)
    none_ids = {i["sequence_id"] for i in gt["items"] if i["label"] == "NONE"}
    assert none_ids == {"YT_A", "YT_B", "YT_C"}
    assert "YT_HAS_EVENT" not in none_ids


def test_every_item_declares_its_source_tier():
    """A tier 는 AI-Hub 원본 프레임, B tier 는 YouTube 재인코딩 영상이다.

    해상도·압축 특성이 달라서 결과가 그 차이를 스스로 말해야 한다.
    """
    seqs, gt = _build()
    assert {s["source_tier"] for s in seqs["sequences"]} == {"A", "B"}
    assert all(i.get("source_tier") in ("A", "B") for i in gt["items"])


def test_labels_stay_inside_the_five_class_space():
    from eval.enums import CLASS_LABELS
    _, gt = _build()
    assert {i["label"] for i in gt["items"]} <= set(CLASS_LABELS)
    assert "NONE" in {i["label"] for i in gt["items"]}


def _wide_b(n=20):
    """negative 클립이 넉넉한 B tier. 3개 중 2개를 뽑으면 seed 가 달라도
    같은 집합이 나오기 쉬워 seed 의 효과를 볼 수 없다."""
    clips = [{"clip_id": "YT_%02d" % i, "source_video_id": "YT_0001",
              "duration_sec": 60.0, "file_path": "eval/datasets/youtube/clips/YT_%02d.mp4" % i,
              "sha256": "0" * 64, "split": "DEV"} for i in range(n)]
    items = [{"clip_id": c["clip_id"], "source_video_id": "YT_0001", "targets": []}
             for c in clips]
    return ({"meta": dict(B_CLIPS["meta"]), "clips": clips},
            {"meta": {"gt_version": "g3", "tier": "B", "stage": "candidate",
                      "coverage": {"clips_total": n, "clips_reviewed": n,
                                   "clips_with_events": 0, "negatives_confirmed": True}},
             "items": items})


def test_same_seed_selects_the_same_negative_clips():
    """샘플링이 GT 의 일부다 — 재현되지 않으면 정답지가 아니다."""
    clips, gt = _wide_b()

    def pick(seed):
        _, out = build_ab_mixed.build(A_SEQ, A_GT, clips, gt, n_none=10, seed=seed)
        return {i["sequence_id"] for i in out["items"] if i["label"] == "NONE"}

    assert pick(7) == pick(7)
    assert pick(7) != pick(8)


def test_sequence_ids_do_not_collide_between_tiers():
    seqs, gt = _build(n_none=3)
    ids = [s["sequence_id"] for s in seqs["sequences"]]
    assert len(ids) == len(set(ids))
    assert len(ids) == len(gt["items"])


def test_b_tier_items_carry_no_invented_labels():
    """B tier 에는 bbox·촬영조건 라벨이 없다. 없는 값을 지어내지 않는다."""
    _, gt = _build()
    b_items = [i for i in gt["items"] if i["source_tier"] == "B"]
    assert b_items
    for i in b_items:
        assert i["target_bbox"] is None
        assert i["condition"] is None


def test_coverage_records_how_the_mix_was_made():
    """무엇을 얼마나 어떤 규칙으로 섞었는지가 정답지에 남아야 한다."""
    _, gt = _build(n_none=2, seed=7)
    cov = gt["meta"]["coverage"]
    assert cov["a_tier_sequences"] == 2
    assert cov["b_tier_negative_clips"] == 2
    assert cov["negatives_available"] == 3
    assert cov["sampling"]["seed"] == 7
    assert cov["sampling"]["rule_version"]
    assert cov["source_gt_versions"] == {"a_aihub": "g1", "b_youtube": "g3"}


def test_asking_for_more_negatives_than_exist_is_refused():
    """분모를 조용히 줄이지 않는다 — 모자라면 말한다."""
    with pytest.raises(ValueError, match="negative"):
        _build(n_none=99)


def test_unreviewed_b_tier_gt_is_refused():
    """검토 안 된 클립을 「사건 없음」 정답으로 쓸 수 없다."""
    bad = {"meta": {"gt_version": "g3", "tier": "B", "stage": "candidate",
                    "coverage": {"clips_total": 4, "clips_reviewed": 2,
                                 "clips_with_events": 1, "negatives_confirmed": False}},
           "items": B_GT["items"]}
    with pytest.raises(ValueError, match="검토"):
        build_ab_mixed.build(A_SEQ, A_GT, B_CLIPS, bad, n_none=2, seed=1)


def test_committed_ab_mixed_fills_the_none_row_and_column():
    """커밋된 ab_mixed 로 채점하면 5×5 가 실제로 5×5 다 (F12 회귀 가드).

    A tier 만으로 채점하면 NONE 행·열이 전부 0이라 「5×5 라고 부르는 4×4」가
    된다. 이 테스트가 깨지면 NONE 데이터 경로가 다시 끊긴 것이다.
    """
    from eval import manifests_io
    from eval.runners import normalize, registry
    from eval.scorers import classification

    gt = manifests_io.load_gt("ab_mixed", "classification")
    raw = registry.get("fake:always_correct")(
        {"manifest": "ab_mixed", "stage": "classification"})
    r = classification.score(normalize.normalize_classification(raw), gt)

    assert sum(r["confusion"]["NONE"].values()) > 0, "NONE 행이 비었다"
    assert sum(row["NONE"] for row in r["confusion"].values()) > 0, "NONE 열이 비었다"
    assert r["recall_by_label"]["NONE"] is not None
