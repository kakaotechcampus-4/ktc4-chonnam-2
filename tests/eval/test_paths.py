import os
from eval import paths
from eval import enums


def test_manifest_dir_points_at_b_youtube():
    d = paths.manifest_dir("b_youtube")
    assert os.path.isdir(d)
    assert os.path.isfile(os.path.join(d, "clips.json"))


def test_violation_types_are_the_four_baseline_names():
    assert enums.VIOLATION_TYPES == (
        "SIGNAL",
        "CENTER_LINE_CROSSING",
        "SOLID_LINE_LANE_CHANGE",
        "MOTORCYCLE_HELMET_NON_USE",
    )


def test_class_labels_add_none_for_confusion_matrix():
    assert enums.CLASS_LABELS == enums.VIOLATION_TYPES + ("NONE",)
