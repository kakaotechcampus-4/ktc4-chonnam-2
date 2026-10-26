import collections
import json
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


# --- 대상 객체를 위반유형별로 좁힌다 (F10) ------------------------------

def test_target_objects_are_mapped_per_violation_type():
    """유형마다 자기 대상 객체 이름이 하나씩 있다."""
    assert sorted(sample_aihub.TARGET_OBJECTS_BY_TYPE) == sorted(VIOLATION_TYPES)
    for vtype, names in sample_aihub.TARGET_OBJECTS_BY_TYPE.items():
        assert names, vtype


def test_target_object_names_do_not_overlap_between_types():
    """한 이름이 두 유형의 대상이면 좁힌 의미가 없다."""
    seen = set()
    for names in sample_aihub.TARGET_OBJECTS_BY_TYPE.values():
        assert not (seen & set(names))
        seen |= set(names)


def test_target_bbox_ignores_another_types_object():
    """신호위반 시퀀스에서 중앙선침범용 대상 객체를 가져가지 않는다 (F10).

    좁히기 전에는 TARGET_OBJECTS 가 전역 목록이라 프레임에 다른 유형의
    대상 객체가 어노테이션돼 있으면 그 bbox 를 정답으로 삼았다.
    """
    anns = [{"Object Name": "중앙선침범 위반 차량(이륜차 포함)",
             "Bbox Cordinate": [1, 2, 3, 4]}]
    assert sample_aihub.pick_target_bbox(anns, "SIGNAL") is None
    assert sample_aihub.pick_target_bbox(anns, "CENTER_LINE_CROSSING") == [1, 2, 3, 4]


def test_target_bbox_requires_the_coordinate_field():
    anns = [{"Object Name": "신호 위반 차량(이륜차 포함)"}]
    assert sample_aihub.pick_target_bbox(anns, "SIGNAL") is None


# --- 잠근 평가셋: 이미 쓴 시퀀스를 빼고 뽑는다 (W12 E1) ------------------

def _fake_label_zip(path, per_type):
    """유형마다 시퀀스 per_type 개, 시퀀스마다 프레임 1장짜리 라벨 zip."""
    import zipfile
    label = json.dumps({
        "condition": {"Weather": "맑음", "DayNights": "주간", "roadType": "일반도로"},
        "Annotation": {"annotations": []},
    })
    with zipfile.ZipFile(path, "w") as zf:
        for top in sample_aihub.TYPE_MAP:
            for i in range(per_type):
                seq = "%s_%04d" % (top, i)
                zf.writestr("%s/sub/%s/%s_001.json" % (top, seq, seq), label)
    return str(path)


def test_excluded_sequences_are_never_picked(tmp_path):
    z = _fake_label_zip(tmp_path / "VL.zip", per_type=4)
    first, _ = sample_aihub.sample(z, per_type=2, seed=1)
    used = {s["sequence_id"] for s in first["sequences"]}

    second, gt = sample_aihub.sample(z, per_type=2, seed=1, exclude_ids=used)
    picked = {s["sequence_id"] for s in second["sequences"]}

    assert not (used & picked)
    assert len(picked) == 2 * len(VIOLATION_TYPES)
    assert {i["sequence_id"] for i in gt["items"]} == picked


def test_split_and_versions_are_recorded(tmp_path):
    z = _fake_label_zip(tmp_path / "VL.zip", per_type=2)
    seqs, gt = sample_aihub.sample(
        z, per_type=1, seed=1, exclude_ids={"x"}, excluded_manifests=["a_aihub"],
        split="LOCKED", manifest_version="lm1", gt_version="lg1")

    assert {s["split"] for s in seqs["sequences"]} == {"LOCKED"}
    assert seqs["meta"]["manifest_version"] == "lm1"
    assert gt["meta"]["gt_version"] == "lg1"
    assert seqs["meta"]["sampling"]["excluded_manifests"] == ["a_aihub"]
    assert seqs["meta"]["sampling"]["excluded_count"] == 1


def test_committed_locked_a_tier_does_not_overlap_dev():
    """잠근 A tier 는 DEV(a_aihub)와 시퀀스 하나도 겹치지 않는다."""
    dev = {s["sequence_id"] for s in manifests_io.load_sequences("a_aihub")["sequences"]}
    locked = manifests_io.load_sequences("a_aihub_locked")
    ids = [s["sequence_id"] for s in locked["sequences"]]

    assert len(set(ids)) == len(ids), "sequence_id 중복"
    assert not (dev & set(ids))
    assert {s["split"] for s in locked["sequences"]} == {"LOCKED"}
    assert "a_aihub" in locked["meta"]["sampling"]["excluded_manifests"]

    gt = manifests_io.load_gt("a_aihub_locked", "classification")
    assert {i["sequence_id"] for i in gt["items"]} == set(ids)
