import os

import pytest

from eval import manifests_io
from eval import paths as eval_paths

# B tier 클립 123개는 .gitignore 대상이라 clone 만으로는 없다. 미디어가 필요한
# 검사(file_path 존재 · sha256 대조)는 있을 때만 돈다 — 없는데 실패로 적으면
# 「데이터가 없다」가 「정답지가 틀렸다」로 오독된다.
B_CLIPS_DIR = os.path.join(eval_paths.datasets_dir(), "youtube", "clips")
needs_b_media = pytest.mark.skipif(
    not os.path.isdir(B_CLIPS_DIR), reason="B tier 미디어 없음 (로컬 전용)"
)


def test_load_clips_returns_123_entries():
    data = manifests_io.load_clips("b_youtube")
    assert data["meta"]["tier"] == "B"
    assert len(data["clips"]) == 123


def test_load_gt_candidate_has_coverage_block():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    cov = gt["meta"]["coverage"]
    assert cov["clips_total"] == 123
    assert cov["clips_reviewed"] == 123
    assert cov["negatives_confirmed"] is True


@needs_b_media
def test_real_b_youtube_data_has_no_invariant_violations():
    problems = manifests_io.check_invariants("b_youtube", "candidate", verify_hashes=3)
    assert problems == [], "위반: " + "; ".join(problems)


def test_bad_violation_type_is_reported(tmp_path, monkeypatch):
    # baseline 밖의 이름이 들어오면 잡아낸다.
    gt = {
        "meta": {"gt_version": "gx", "tier": "B", "stage": "candidate",
                 "coverage": {"clips_total": 1, "clips_reviewed": 1,
                              "clips_with_events": 1, "negatives_confirmed": True}},
        "items": [{"clip_id": "C0", "source_video_id": "V0",
                   "targets": [{"event_id": "E0", "violation_type": "LANE_CHANGE",
                                "t_start_sec": 1.0, "t_end_sec": 2.0,
                                "t_onset_sec": 1.5, "scoring": "INCLUDED"}]}],
    }
    clips = {"meta": {"tier": "B"},
             "clips": [{"clip_id": "C0", "duration_sec": 60,
                        "file_path": __file__, "sha256": "", "split": "DEV",
                        "source_video_id": "V0"}]}
    problems = manifests_io.validate(clips, gt, verify_hashes=0)
    assert any("LANE_CHANGE" in p for p in problems)


def test_span_outside_clip_is_reported():
    gt = {
        "meta": {"coverage": {"clips_total": 1, "clips_reviewed": 1,
                              "clips_with_events": 1, "negatives_confirmed": True}},
        "items": [{"clip_id": "C0", "source_video_id": "V0",
                   "targets": [{"event_id": "E0", "violation_type": "SIGNAL",
                                "t_start_sec": 55.0, "t_end_sec": 70.0,
                                "t_onset_sec": 60.0, "scoring": "INCLUDED"}]}],
    }
    clips = {"meta": {"tier": "B"},
             "clips": [{"clip_id": "C0", "duration_sec": 60,
                        "file_path": __file__, "sha256": "", "split": "DEV",
                        "source_video_id": "V0"}]}
    problems = manifests_io.validate(clips, gt, verify_hashes=0)
    assert any("클립 길이" in p for p in problems)


def test_coverage_clips_total_mismatch_is_reported():
    # items 수와 meta.coverage.clips_total 이 어긋나면 잡아낸다 (다른 지표는 일치시켜 격리한다).
    gt = {
        "meta": {"coverage": {"clips_total": 2, "clips_reviewed": 2,
                              "clips_with_events": 0, "negatives_confirmed": True}},
        "items": [{"clip_id": "C0", "source_video_id": "V0", "targets": []}],
    }
    clips = {"meta": {"tier": "B"},
             "clips": [{"clip_id": "C0", "duration_sec": 60,
                        "file_path": __file__, "sha256": "", "split": "DEV",
                        "source_video_id": "V0"}]}
    problems = manifests_io.validate(clips, gt, verify_hashes=0)
    assert any("clips_total=2" in p and "items=1" in p for p in problems)


def test_coverage_clips_with_events_mismatch_is_reported():
    # targets 있는 item 수와 meta.coverage.clips_with_events 가 어긋나면 잡아낸다.
    gt = {
        "meta": {"coverage": {"clips_total": 1, "clips_reviewed": 1,
                              "clips_with_events": 1, "negatives_confirmed": True}},
        "items": [{"clip_id": "C0", "source_video_id": "V0", "targets": []}],
    }
    clips = {"meta": {"tier": "B"},
             "clips": [{"clip_id": "C0", "duration_sec": 60,
                        "file_path": __file__, "sha256": "", "split": "DEV",
                        "source_video_id": "V0"}]}
    problems = manifests_io.validate(clips, gt, verify_hashes=0)
    assert any("clips_with_events=1" in p and "실제=0" in p for p in problems)


def test_target_start_after_end_is_reported():
    # t_start_sec >= t_end_sec 이면 잡아낸다 (span은 클립 길이 안이라 다른 지표는 안 건드림).
    gt = {
        "meta": {"coverage": {"clips_total": 1, "clips_reviewed": 1,
                              "clips_with_events": 1, "negatives_confirmed": True}},
        "items": [{"clip_id": "C0", "source_video_id": "V0",
                   "targets": [{"event_id": "E0", "violation_type": "SIGNAL",
                                "t_start_sec": 5.0, "t_end_sec": 3.0,
                                "t_onset_sec": 4.0, "scoring": "INCLUDED"}]}],
    }
    clips = {"meta": {"tier": "B"},
             "clips": [{"clip_id": "C0", "duration_sec": 60,
                        "file_path": __file__, "sha256": "", "split": "DEV",
                        "source_video_id": "V0"}]}
    problems = manifests_io.validate(clips, gt, verify_hashes=0)
    assert any("t_start_sec >= t_end_sec" in p for p in problems)


def test_missing_file_path_is_reported(tmp_path, monkeypatch):
    # clips[].file_path 가 실제로 없으면 잡아낸다. 진짜 dataset 은 건드리지 않는다 —
    # REPO_ROOT 를 임시 디렉터리로 monkeypatch 하고, 그 안에 만들지 않은 파일을 가리킨다.
    monkeypatch.setattr(eval_paths, "REPO_ROOT", str(tmp_path))
    gt = {
        "meta": {"coverage": {"clips_total": 1, "clips_reviewed": 1,
                              "clips_with_events": 0, "negatives_confirmed": True}},
        "items": [{"clip_id": "C0", "source_video_id": "V0", "targets": []}],
    }
    clips = {"meta": {"tier": "B"},
             "clips": [{"clip_id": "C0", "duration_sec": 60,
                        "file_path": "no_such_clip.mp4", "sha256": "", "split": "DEV",
                        "source_video_id": "V0"}]}
    problems = manifests_io.validate(clips, gt, verify_hashes=0)
    assert any("file_path 가 존재하지 않는다" in p for p in problems)


def test_sha256_mismatch_is_reported(tmp_path, monkeypatch):
    # verify_hashes 로 켠 sha256 대조가 실제로 불일치를 잡아내는지 확인한다.
    # 진짜 dataset 은 건드리지 않는다 — REPO_ROOT 를 임시 디렉터리로 monkeypatch 하고
    # 그 안에 가짜 내용의 파일을 만들어 기록된 해시와 다르게 만든다.
    monkeypatch.setattr(eval_paths, "REPO_ROOT", str(tmp_path))
    (tmp_path / "clip.mp4").write_bytes(b"not the expected content")
    gt = {
        "meta": {"coverage": {"clips_total": 1, "clips_reviewed": 1,
                              "clips_with_events": 0, "negatives_confirmed": True}},
        "items": [{"clip_id": "C0", "source_video_id": "V0", "targets": []}],
    }
    clips = {"meta": {"tier": "B"},
             "clips": [{"clip_id": "C0", "duration_sec": 60,
                        "file_path": "clip.mp4", "sha256": "0" * 64, "split": "DEV",
                        "source_video_id": "V0"}]}
    problems = manifests_io.validate(clips, gt, verify_hashes=1)
    assert any("sha256 불일치" in p for p in problems)


# --- 시퀀스 manifest 불변식 (F13) ---------------------------------------
#
# clips.json 을 전제하는 validate() 는 A tier·ab_mixed 에서 돌지 않는다.
# 시퀀스 manifest 는 clip 도 span 도 없기 때문이다.

def _seqs(*ids):
    return {"meta": {"manifest_version": "m1", "tier": "A"},
            "sequences": [{"sequence_id": i, "source_tier": "A"} for i in ids]}


def _seq_gt(items, total=None):
    return {"meta": {"gt_version": "g1", "tier": "A", "stage": "classification",
                     "coverage": {"sequences_total": len(items) if total is None else total}},
            "items": items}


def _item(sid, label="SIGNAL", box=None, frame=None, distractors=None, tier="A"):
    return {"sequence_id": sid, "label": label, "target_bbox": box,
            "target_frame": frame, "distractor_count": distractors,
            "condition": None, "source_tier": tier}


def test_sequence_gt_and_manifest_must_be_one_to_one():
    problems = manifests_io.validate_sequences(_seqs("S1"), _seq_gt([_item("S1"), _item("S2")]))
    assert any("S2" in p for p in problems)


def test_sequence_manifest_entry_without_gt_is_reported():
    """채점되지 않는 시퀀스가 manifest 에 남아 있으면 분모를 오해하게 된다."""
    problems = manifests_io.validate_sequences(_seqs("S1", "S2"), _seq_gt([_item("S1")]))
    assert any("S2" in p for p in problems)


def test_duplicate_sequence_id_is_reported():
    problems = manifests_io.validate_sequences(
        _seqs("S1", "S1"), _seq_gt([_item("S1"), _item("S1")]))
    assert any("중복" in p for p in problems)


def test_label_outside_the_five_class_space_is_reported():
    problems = manifests_io.validate_sequences(_seqs("S1"), _seq_gt([_item("S1", label="JAYWALK")]))
    assert any("JAYWALK" in p for p in problems)


def test_none_label_is_accepted():
    """NONE 은 5클래스 공간 안이다 — ab_mixed 가 이걸로 선다."""
    assert manifests_io.validate_sequences(
        _seqs("S1"), _seq_gt([_item("S1", label="NONE", tier="B")])) == []


def test_malformed_target_bbox_is_reported():
    problems = manifests_io.validate_sequences(
        _seqs("S1"), _seq_gt([_item("S1", box=[0, 0, 10])]))
    assert any("bbox" in p for p in problems)


def test_inverted_target_bbox_is_reported():
    """x1 >= x2 면 넓이가 0 이하라 IoU 가 영원히 0 이다 — 조용히 오답이 된다."""
    problems = manifests_io.validate_sequences(
        _seqs("S1"), _seq_gt([_item("S1", box=[10, 0, 10, 20], frame="f.jpg", distractors=0)]))
    assert any("bbox" in p for p in problems)


def test_bbox_absent_but_its_companions_present_is_reported():
    """bbox 가 없으면 딸린 사실도 전부 null 이어야 한다 — 하나만 남으면
    「무엇을 모르는지」가 흐려진다."""
    problems = manifests_io.validate_sequences(
        _seqs("S1"), _seq_gt([_item("S1", box=None, frame="f.jpg")]))
    assert any("target_frame" in p for p in problems)


def test_coverage_sequences_total_mismatch_is_reported():
    problems = manifests_io.validate_sequences(_seqs("S1"), _seq_gt([_item("S1")], total=9))
    assert any("sequences_total" in p for p in problems)


def test_unknown_source_tier_is_reported():
    problems = manifests_io.validate_sequences(
        _seqs("S1"), _seq_gt([_item("S1", tier="Z")]))
    assert any("source_tier" in p for p in problems)


def test_committed_sequence_manifests_have_no_invariant_violations():
    """a_aihub 와 ab_mixed 둘 다 검사에 건다. 지금까지 ab_mixed 는 무검사였다."""
    for name in ("a_aihub", "ab_mixed"):
        assert manifests_io.check_sequence_invariants(name) == [], name


def test_violation_type_drifting_from_gt_label_is_reported():
    """A tier 는 위반유형을 두 파일에 중복 저장한다 — 드리프트가 가능한 유일한 지점이다."""
    seqs = {"meta": {"manifest_version": "m1", "tier": "A"},
            "sequences": [{"sequence_id": "S1", "source_tier": "A",
                           "violation_type": "SIGNAL"}]}
    problems = manifests_io.validate_sequences(
        seqs, _seq_gt([_item("S1", label="CENTER_LINE_CROSSING")]))
    assert any("violation_type" in p for p in problems)


def test_null_violation_type_does_not_conflict_with_a_none_label():
    """B tier 항목은 violation_type 이 없고 라벨이 NONE 이다 — 오탐이면 안 된다."""
    seqs = {"meta": {"manifest_version": "am1", "tier": "AB"},
            "sequences": [{"sequence_id": "YT_A", "source_tier": "B",
                           "violation_type": None}]}
    assert manifests_io.validate_sequences(
        seqs, _seq_gt([_item("YT_A", label="NONE", tier="B")])) == []
