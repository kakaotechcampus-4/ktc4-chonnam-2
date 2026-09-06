import os
import pytest
from eval import paths
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
