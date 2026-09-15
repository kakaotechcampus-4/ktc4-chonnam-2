"""eval/manifests/mock_pack/gt/*.json 이 data/mock/expected/ 라벨과 갈라지지 않았는지 본다.

test_expected_labels.py 는 data/mock/expected/ 가 pack(fixture)과 스스로
앞뒤가 맞는지만 본다. 그러나 scorer 가 실제로 읽는 파일은
eval/manifests/mock_pack/gt/gt_candidate.json · gt_plate.json 이고, 이 둘은
그 라벨에서 손으로 옮겨 적은 사본이다. 옮기다 t_onset_sec 하나만 움직여도
recall 이 흔들리는데 그것을 잡는 테스트가 없었다 — 여기서 막는다.
"""
import json
import os

from eval import manifests_io, paths

MANIFEST = "mock_pack"
EXPECTED_DIR = os.path.join(paths.REPO_ROOT, "data", "mock", "expected")


def _all_expected_docs():
    for fname in sorted(os.listdir(EXPECTED_DIR)):
        if not fname.endswith(".expected.json"):
            continue
        with open(os.path.join(EXPECTED_DIR, fname), encoding="utf-8") as f:
            yield json.load(f)


def _candidate_onset_targets_by_scenario():
    """scenario_id -> candidate_onset metric_targets 목록."""
    return {doc["scenario_id"]: [t for t in doc["metric_targets"]
                                  if t["metric"] == "candidate_onset"]
            for doc in _all_expected_docs()}


def _plate_labels_by_readout_id():
    """readout_id(ref.ref) -> plate_readout label."""
    out = {}
    for doc in _all_expected_docs():
        for t in doc["metric_targets"]:
            if t["metric"] == "plate_readout":
                out[t["ref"]["ref"]] = t
    return out


def test_gt_candidate_agrees_with_the_expected_label_it_was_derived_from():
    gt = manifests_io.load_gt(MANIFEST, "candidate")
    labels_by_scenario = _candidate_onset_targets_by_scenario()

    for item in gt["items"]:
        clip_id = item["clip_id"]
        targets = item["targets"]
        labels = labels_by_scenario.get(clip_id, [])
        assert len(targets) == len(labels), (
            "%s: gt targets=%d개인데 expected label=%d개" % (clip_id, len(targets), len(labels))
        )
        for t, label in zip(targets, labels):
            assert t["t_onset_sec"] == label["onset_ms"] / 1000, (
                "%s: t_onset_sec 이 라벨의 onset_ms 와 갈라졌다" % clip_id
            )
            assert t["violation_type"] == label["violation_type"], (
                "%s: violation_type 이 라벨과 갈라졌다" % clip_id
            )
            assert t["scoring"] == label["scoring"], (
                "%s: scoring 이 라벨과 갈라졌다" % clip_id
            )


def test_gt_candidate_and_expected_labels_cover_the_same_scenarios():
    """한쪽에만 추가된 항목은 여기서 잡는다."""
    gt = manifests_io.load_gt(MANIFEST, "candidate")
    gt_scenarios = {item["clip_id"] for item in gt["items"]}
    labels_by_scenario = _candidate_onset_targets_by_scenario()
    assert gt_scenarios == set(labels_by_scenario)


def test_gt_plate_agrees_with_the_expected_label_it_was_derived_from():
    gt = manifests_io.load_gt(MANIFEST, "plate")
    labels = _plate_labels_by_readout_id()

    for item in gt["items"]:
        rid = item["readout_id"]
        assert rid in labels, "%s: expected 라벨에 없는 readout_id" % rid
        label = labels[rid]
        assert item["legibility"] == label["legibility"], (
            "%s: legibility 가 라벨과 갈라졌다" % rid
        )
        if item["legibility"] == "READABLE":
            assert item["true_text"] == label["true_text"], (
                "%s: true_text 가 라벨과 갈라졌다" % rid
            )


def test_gt_plate_and_expected_labels_cover_the_same_readout_ids():
    """한쪽에만 추가된 판독은 여기서 잡는다."""
    gt = manifests_io.load_gt(MANIFEST, "plate")
    gt_ids = {item["readout_id"] for item in gt["items"]}
    label_ids = set(_plate_labels_by_readout_id())
    assert gt_ids == label_ids
