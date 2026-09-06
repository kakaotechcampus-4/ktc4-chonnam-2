import collections
import os

import pytest

from eval import manifests_io, paths
from eval.enums import VIOLATION_TYPES
from eval.tools import sample_aihub

VL = os.path.join(paths.REPO_ROOT, "eval", "manifests", "02.라벨링데이터", "VL.zip")
needs_archive = pytest.mark.skipif(not os.path.exists(VL), reason="VL.zip 없음 (로컬 전용)")


def test_type_map_covers_exactly_the_four_baseline_types():
    assert sorted(sample_aihub.TYPE_MAP.values()) == sorted(VIOLATION_TYPES)


@needs_archive
def test_sample_is_deterministic_for_same_seed():
    a, _ = sample_aihub.sample(VL, per_type=3, seed=42)
    b, _ = sample_aihub.sample(VL, per_type=3, seed=42)
    ids_a = [s["sequence_id"] for s in a["sequences"]]
    ids_b = [s["sequence_id"] for s in b["sequences"]]
    assert ids_a == ids_b


@needs_archive
def test_sample_balances_by_type():
    seqs, _ = sample_aihub.sample(VL, per_type=3, seed=42)
    counts = {}
    for s in seqs["sequences"]:
        counts[s["violation_type"]] = counts.get(s["violation_type"], 0) + 1
    assert set(counts) == set(VIOLATION_TYPES)
    assert all(v == 3 for v in counts.values())


@needs_archive
def test_sampling_rule_is_recorded_in_meta():
    seqs, _ = sample_aihub.sample(VL, per_type=3, seed=42)
    s = seqs["meta"]["sampling"]
    assert s["seed"] == 42
    assert s["per_type"] == 3
    assert s["rule_version"]


@needs_archive
def test_gt_labels_are_baseline_enum_and_carry_source_tier():
    _, gt = sample_aihub.sample(VL, per_type=3, seed=42)
    assert gt["meta"]["stage"] == "classification"
    for item in gt["items"]:
        assert item["label"] in VIOLATION_TYPES
        assert item["source_tier"] == "A"


def test_committed_a_tier_gt_is_self_consistent():
    """커밋된 A tier GT 의 불변식. 247MB 아카이브 없이 돈다.

    B tier 는 check_invariants 가 7가지를 강제하는데 A tier 는 아무것도
    강제되지 않았다. GT 는 커밋돼 있고 그것으로 채점까지 하므로, 아카이브가
    없는 clone 에서도 정답지가 스스로 모순되지 않는지는 확인돼야 한다.
    """
    gt = manifests_io.load_gt("a_aihub", "classification")
    seqs = manifests_io.load_sequences("a_aihub")
    items = gt["items"]

    assert len(items) == 120
    per_type = collections.Counter(i["label"] for i in items)
    assert set(per_type) == set(VIOLATION_TYPES)
    assert set(per_type.values()) == {30}

    gt_ids = [i["sequence_id"] for i in items]
    seq_ids = [s["sequence_id"] for s in seqs["sequences"]]
    assert len(set(gt_ids)) == len(gt_ids), "sequence_id 중복"
    assert set(gt_ids) == set(seq_ids), "GT 와 sequences.json 이 1:1 이 아니다"

    cov = gt["meta"]["coverage"]
    assert cov["sequences_total"] == len(items)
    assert cov["items_with_target_bbox"] == 115

    n_with_box = 0
    for item in items:
        assert item["label"] in VIOLATION_TYPES
        box = item["target_bbox"]
        if box is None:
            # bbox 가 없으면 그 bbox 에 딸린 사실도 전부 null 이어야 한다 —
            # 하나만 남으면 「무엇을 모르는지」가 흐려진다.
            assert item["target_frame"] is None
            assert item["distractor_count"] is None
        else:
            n_with_box += 1
            assert len(box) == 4
    assert n_with_box == cov["items_with_target_bbox"]
