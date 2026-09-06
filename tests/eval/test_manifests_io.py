import os

import pytest

from eval import manifests_io
from eval import paths as eval_paths

# B tier 클립 55개는 .gitignore 대상이라 clone 만으로는 없다. 미디어가 필요한
# 검사(file_path 존재 · sha256 대조)는 있을 때만 돈다 — 없는데 실패로 적으면
# 「데이터가 없다」가 「정답지가 틀렸다」로 오독된다.
B_CLIPS_DIR = os.path.join(eval_paths.datasets_dir(), "youtube", "clips")
needs_b_media = pytest.mark.skipif(
    not os.path.isdir(B_CLIPS_DIR), reason="B tier 미디어 없음 (로컬 전용)"
)


def test_load_clips_returns_55_entries():
    data = manifests_io.load_clips("b_youtube")
    assert data["meta"]["tier"] == "B"
    assert len(data["clips"]) == 55


def test_load_gt_candidate_has_coverage_block():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    cov = gt["meta"]["coverage"]
    assert cov["clips_total"] == 55
    assert cov["clips_reviewed"] == 55
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
