from eval import manifests_io


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
