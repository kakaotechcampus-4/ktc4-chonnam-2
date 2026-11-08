"""TimeResolution의 base-plus-offset이 사건 대표 순간이 담긴 원본 하나의 시계만 쓰는지 검사한다.

PR #458 리뷰(stored_observation.py 243-247): 원본 A(12:00:00, timeline 0~60초)와 B(12:01:00, 60~120초)를
이어 붙였을 때 사건이 timeline 65초면 B 안 5초 = 12:01:05여야 한다. timeline 위치를 B 시각에 그대로 더하면
12:02:05가 된다.
"""
from __future__ import annotations

import unittest
from datetime import datetime

import pytest

from daesingo.evidence import ContractInputError, resolve_time, validate_contract
from daesingo.recording import TimeSourceCandidate

TIMELINE = {"timeline_id": "tl_multi", "revision": 1}


def _candidate(candidate_id, asset, value, *, kind="FILENAME", applies_at_sec=0.0):
    return {
        "candidate_id": candidate_id,
        "source_kind": kind,
        "value": value,
        "applies_to": {"source_asset_ref": asset, "source_offset_sec": applies_at_sec},
        "observation_status": "OK",
    }


def _span(sequence, asset, timeline_range, source_range):
    return {
        "sequence": sequence,
        "timeline_range": {"start_sec": timeline_range[0], "end_sec": timeline_range[1]},
        "source_asset_ref": asset,
        "media_stream_ref": f"ms_{asset}",
        "source_range": {"start_sec": source_range[0], "end_sec": source_range[1]},
    }


def _clip(*spans, requested=None, timeline=TIMELINE):
    requested = requested or (spans[0]["timeline_range"]["start_sec"], spans[-1]["timeline_range"]["end_sec"])
    return {
        "incident_clip_ref": "clip_multi",
        "timeline_ref": dict(timeline),
        "timeline_range": {"start_sec": requested[0], "end_sec": requested[1]},
        "duration_sec": requested[1] - requested[0],
        "source_provenance": {
            "timeline_ref": dict(timeline),
            "requested_range": {"start_sec": requested[0], "end_sec": requested[1]},
            "asset_spans": list(spans),
        },
    }


def _event(representative_ms):
    return {"span": {"timeline_id": "tl_multi", "timeline_revision": 1, "representative_ms": representative_ms}}


A = _candidate("tsc_a", "sa_a", "2026-10-31T12:00:00+09:00")
B = _candidate("tsc_b", "sa_b", "2026-10-31T12:01:00+09:00")
ONLY_B = _clip(_span(0, "sa_b", (60.0, 75.0), (0.0, 15.0)))
A_AND_B = _clip(_span(0, "sa_a", (45.0, 60.0), (45.0, 60.0)), _span(1, "sa_b", (60.0, 75.0), (0.0, 15.0)))


def _resolve(candidates, representative_ms, clip, *, overlay=None, corrections=()):
    return resolve_time(
        time_source_candidates=candidates,
        overlay_time_readout=overlay,
        correction_records=corrections,
        candidate_event=_event(representative_ms),
        case_id="case_multi",
        selection_rev=1,
        resolution_id="tr_multi",
        incident_clip=clip,
    )


def _reasons(result):
    return {item["input_ref"]["ref"]: item.get("reason_code") for item in result["considered"]}


def _overlay(*points):
    return {
        "readout_id": "overlay_kind",
        "input_ref": {"incident_clip_ref": "clip_multi"},
        "observation": {"status": "OK", "value": f"2026-10-31T14:00:{points[0][1]}+09:00"},
        "validation": {"format_ok": True, "monotonic_ok": True, "duration_match_ok": True},
        "samples": [
            {
                "frame_ref": f"fr_{index}",
                "offset_sec": offset,
                "frame_offset_sec": offset,
                "parsed_at": f"2026-10-31T14:00:{seconds}+09:00" if seconds is not None else None,
            }
            for index, (offset, seconds) in enumerate(points)
        ],
    }


@pytest.mark.parametrize(("clip_start", "source_start"), [(0, 0), (45, 45), (60, 3)])
@pytest.mark.parametrize(("event_offset", "seconds", "delta_ms"), [(2, "12", 0), (9, "19", 2000), (12, "22", 0)])
def test_overlay_time_resolves_at_the_representative_position(clip_start, source_start, event_offset, seconds, delta_ms):
    clip = _clip(_span(0, "sa_a", (clip_start, clip_start + 15), (source_start, source_start + 15)))
    # The request may start before the actual materialized clip; OCR offsets use the latter.
    if clip_start:
        clip["source_provenance"]["requested_range"]["start_sec"] = clip_start - 1
    overlay = _overlay((2, "12"), (7, "17"), (12, "22"))
    result = _resolve([], (clip_start + event_offset) * 1000, clip, overlay=overlay)

    assert result["status"] == "OK"
    resolved = result["resolved"]
    assert resolved["value"] == f"2026-10-31T14:00:{seconds}+09:00"
    assert resolved["verification"] == "VERIFIED"
    assert resolved["source"]["input_ref"] == result["provenance"]["selected_input_ref"]
    considered = result["considered"][0]
    assert considered["used"]
    assert considered["value"] == f"2026-10-31T14:00:{'17' if delta_ms else seconds}+09:00"
    assert resolved["computation"]["mode"] == ("BASE_PLUS_OFFSET" if delta_ms else "DIRECT")
    if delta_ms:
        assert resolved["computation"]["base_input_ref"] == considered["input_ref"]
        assert resolved["computation"]["source_offset_ms"] == delta_ms
    assert result["post_stamp"]["needed"] is False
    assert validate_contract(result) == []


def test_overlay_time_does_not_borrow_a_sample_across_the_source_boundary():
    overlay = _overlay((14, "14"), (16, "16"), (20, "20"))
    boundary = _resolve([A, B], 60_000, A_AND_B, overlay=overlay)
    assert boundary["status"] == "NEEDS_REVIEW"
    assert boundary["resolved"]["value"] == "2026-10-31T12:01:00+09:00"
    assert _reasons(boundary)["overlay_kind"] == "time.overlay_event_not_covered"
    later = _resolve([A, B], 63_000, A_AND_B, overlay=overlay)
    assert later["status"] == "OK"
    assert later["resolved"]["value"] == "2026-10-31T14:00:18+09:00"


def test_overlay_time_does_not_resolve_a_timeline_gap():
    clip = _clip(_span(0, "sa_a", (45, 60), (45, 60)), _span(1, "sa_b", (70, 80), (0, 10)))
    overlay = _overlay((14, "14"), (19, "19"), (26, "26"))
    result = _resolve([A, B], 64_000, clip, overlay=overlay)
    assert result["status"] == "UNKNOWN"
    assert "resolved" not in result
    assert result["post_stamp"]["requires_user_notice"] is True
    assert _reasons(result)["overlay_kind"] == "time.overlay_event_not_covered"


@pytest.mark.parametrize(("points", "reason"), [
    ([(2, "12"), (7, "17"), (12, None)], "time.overlay_samples_unusable"),
    ([(2, "12"), (7, "10"), (12, "22")], "time.overlay_samples_unusable"),
    ([(2, "12"), (7, "20"), (12, "22")], "time.overlay_samples_unusable"),
    ([(2, "12"), (7, "17"), (16, "26")], "time.overlay_event_not_covered"),
    ([(2, "12"), (2, "12"), (12, "22")], "time.overlay_samples_unusable"),
    ([(2, "12"), (float("nan"), "17"), (12, "22")], "time.overlay_samples_unusable"),
    ([(2, "12"), (7, "17"), (8, "18")], "time.overlay_event_not_covered"),
])
def test_overlay_time_falls_back_when_samples_do_not_support_the_event(points, reason):
    result = _resolve([B], 69_000, ONLY_B, overlay=_overlay(*points))
    assert result["status"] == "NEEDS_REVIEW"
    assert result["resolved"]["value"] == "2026-10-31T12:01:09+09:00"
    assert result["post_stamp"]["needed"] is True
    assert _reasons(result)["overlay_kind"] == reason


def test_overlay_time_uses_decoded_frame_position_instead_of_requested_position():
    overlay = _overlay((2, "12"), (7, "17"), (12, "22"))
    overlay["samples"][1]["offset_sec"] = 6.5
    result = _resolve([], 69_000, ONLY_B, overlay=overlay)
    assert result["resolved"]["value"] == "2026-10-31T14:00:19+09:00"
    assert result["resolved"]["computation"]["source_offset_ms"] == 2000


def test_overlay_can_anchor_to_a_later_sample_with_a_negative_delta():
    overlay = _overlay((2, "12"), (7, "17"), (12, "22"))
    result = _resolve([], 71_000, ONLY_B, overlay=overlay)
    assert result["resolved"]["value"] == "2026-10-31T14:00:21+09:00"
    assert result["resolved"]["computation"]["source_offset_ms"] == -1000


def test_legacy_overlay_without_decoded_positions_needs_review():
    overlay = _overlay((2, "12"), (7, "17"), (12, "22"))
    for sample in overlay["samples"]:
        del sample["frame_offset_sec"]
    result = _resolve([B], 69_000, ONLY_B, overlay=overlay)
    assert result["status"] == "NEEDS_REVIEW"
    assert _reasons(result)["overlay_kind"] == "time.overlay_samples_unusable"


def test_overlay_time_rejects_samples_from_another_clip():
    overlay = _overlay((2, "12"), (7, "17"), (12, "22"))
    overlay["input_ref"]["incident_clip_ref"] = "clip_other"
    result = _resolve([], 69_000, ONLY_B, overlay=overlay)
    assert result["status"] == "UNKNOWN"
    assert _reasons(result)["overlay_kind"] == "time.overlay_event_not_covered"


class EventSourceTimeTests(unittest.TestCase):
    def assertResolved(self, result, value, base_ref, offset_ms):
        self.assertEqual("NEEDS_REVIEW", result["status"])
        self.assertEqual(value, result["resolved"]["value"])
        computation = result["resolved"]["computation"]
        self.assertEqual("BASE_PLUS_OFFSET", computation["mode"])
        self.assertEqual(base_ref, computation["base_input_ref"]["ref"])
        self.assertEqual(offset_ms, computation["source_offset_ms"])
        self.assertEqual([], validate_contract(result))

    def test_review_example_offsets_from_inside_the_event_source(self):
        self.assertResolved(_resolve([A, B], 65_000, ONLY_B), "2026-10-31T12:01:05+09:00", "tsc_b", 5_000)

    def test_clip_across_two_sources_uses_the_source_holding_the_moment(self):
        result = _resolve([A, B], 65_000, A_AND_B)
        self.assertResolved(result, "2026-10-31T12:01:05+09:00", "tsc_b", 5_000)
        self.assertEqual({"tsc_a": "time.other_source_asset", "tsc_b": None}, _reasons(result))

        earlier = _resolve([A, B], 52_000, A_AND_B)
        self.assertResolved(earlier, "2026-10-31T12:00:52+09:00", "tsc_a", 52_000)
        self.assertEqual({"tsc_a": None, "tsc_b": "time.other_source_asset"}, _reasons(earlier))

    def test_other_source_clocks_are_not_a_conflict(self):
        result = _resolve([A, B], 65_000, A_AND_B)
        self.assertEqual({"exists": False, "between_refs": [], "requires_user_notice": False}, result["conflict"])

    def test_disagreeing_clocks_of_the_same_source_still_conflict(self):
        b_meta = _candidate("tsc_b_meta", "sa_b", "2026-10-31T12:01:02+09:00", kind="FILE_METADATA")
        result = _resolve([A, B, b_meta], 65_000, A_AND_B)
        self.assertTrue(result["conflict"]["exists"])
        self.assertEqual({"tsc_b", "tsc_b_meta"}, {ref["ref"] for ref in result["conflict"]["between_refs"]})
        self.assertEqual("tsc_b", result["resolved"]["computation"]["base_input_ref"]["ref"])

    def test_boundary_moment_belongs_to_the_later_source_and_clip_end_to_the_last(self):
        self.assertResolved(_resolve([A, B], 60_000, A_AND_B), "2026-10-31T12:01:00+09:00", "tsc_b", 0)
        self.assertResolved(_resolve([A, B], 75_000, A_AND_B), "2026-10-31T12:01:15+09:00", "tsc_b", 15_000)

    def test_timeline_gap_does_not_shift_the_later_source(self):
        b_late = _candidate("tsc_b", "sa_b", "2026-10-31T12:05:00+09:00")
        gap_clip = _clip(_span(0, "sa_a", (55.0, 60.0), (55.0, 60.0)), _span(1, "sa_b", (70.0, 80.0), (0.0, 10.0)))
        self.assertResolved(_resolve([A, b_late], 75_000, gap_clip), "2026-10-31T12:05:05+09:00", "tsc_b", 5_000)

    def test_moment_in_a_gap_is_unknown_rather_than_borrowing_a_neighbor(self):
        gap_clip = _clip(_span(0, "sa_a", (55.0, 60.0), (55.0, 60.0)), _span(1, "sa_b", (70.0, 80.0), (0.0, 10.0)))
        result = _resolve([A, B], 65_000, gap_clip)
        self.assertEqual("UNKNOWN", result["status"])
        self.assertNotIn("resolved", result)
        self.assertEqual({"tsc_a": "time.other_source_asset", "tsc_b": "time.other_source_asset"}, _reasons(result))

    def test_event_source_without_a_clock_is_unknown(self):
        result = _resolve([A], 65_000, A_AND_B)
        self.assertEqual("UNKNOWN", result["status"])
        self.assertEqual({"tsc_a": "time.other_source_asset"}, _reasons(result))

    def test_value_applying_after_the_source_start_is_offset_from_that_point(self):
        b_at_10s = _candidate("tsc_b", "sa_b", "2026-10-31T12:01:10+09:00", applies_at_sec=10.0)
        self.assertResolved(_resolve([b_at_10s], 72_000, ONLY_B), "2026-10-31T12:01:12+09:00", "tsc_b", 2_000)

    def test_clip_from_another_timeline_is_a_contract_error(self):
        other = _clip(_span(0, "sa_b", (60.0, 75.0), (0.0, 15.0)), timeline={"timeline_id": "tl_multi", "revision": 2})
        with self.assertRaisesRegex(ContractInputError, "timeline revision mismatch"):
            _resolve([A, B], 65_000, other)

    def test_without_a_clip_the_timeline_position_is_added_as_before(self):
        result = _resolve([A], 65_000, None)
        self.assertResolved(result, "2026-10-31T12:01:05+09:00", "tsc_a", 65_000)


class TimeSourceKindTests(unittest.TestCase):
    def _candidate(self, kind="VENDOR_METADATA"):
        # Validate and serialize the producer's real contract, rather than a consumer-only mock enum.
        return TimeSourceCandidate.model_validate({
            **_candidate("tsc_kind", "sa_b", datetime.fromisoformat("2026-10-31T12:01:00+09:00"), kind=kind),
            "source_detail": "test.timestamp/v1",
            "producer_checks": {"parse_valid": True},
            "provenance": {"producer": "recording", "observed_from": "test-source.mp4"},
        }).model_dump(mode="json")

    def _overlay(self):
        return _overlay((5, "06"), (10, "11"))

    def _correction(self):
        return {
            "contract_version": "correction-record/v1.1",
            "correction_id": "corr_kind", "case_id": "case_multi", "selection_rev": 1,
            "kind": "EVENT_TIME_MANUAL", "target_field": "occurred_at",
            "previous_value": "2026-10-31T12:01:05+09:00",
            "new_value": "2026-10-31T12:02:00+09:00",
            "supersedes_ref": None, "corrected_at": "2026-10-31T13:00:00+09:00",
        }

    def test_canonical_recording_kinds_resolve_as_unverified_base_plus_offset(self):
        for kind, source in (
            ("FILENAME", "recording.filename_time"),
            ("FILE_METADATA", "recording.file_metadata_time"),
            ("VENDOR_METADATA", "recording.manufacturer_metadata_time"),
        ):
            with self.subTest(kind=kind):
                result = _resolve([self._candidate(kind)], 65_000, ONLY_B)
                self.assertEqual("NEEDS_REVIEW", result["status"])
                self.assertEqual("2026-10-31T12:01:05+09:00", result["resolved"]["value"])
                self.assertEqual(source, result["resolved"]["source"]["kind"])
                self.assertEqual("UNVERIFIED", result["resolved"]["verification"])
                self.assertEqual("BASE_PLUS_OFFSET", result["resolved"]["computation"]["mode"])
                self.assertEqual(5_000, result["resolved"]["computation"]["source_offset_ms"])
                self.assertEqual(result["resolved"]["source"]["input_ref"], result["provenance"]["selected_input_ref"])
                self.assertTrue(result["considered"][0]["used"])
                self.assertEqual([], validate_contract(result))

    def test_vendor_candidate_preserves_verified_overlay_priority_and_validation(self):
        overlay = self._overlay()
        result = _resolve([self._candidate()], 65_000, ONLY_B, overlay=overlay)
        self.assertEqual("OK", result["status"])
        self.assertEqual(overlay["observation"]["value"], result["resolved"]["value"])
        self.assertEqual("readout.overlay_ocr", result["resolved"]["source"]["kind"])
        self.assertEqual("VERIFIED", result["resolved"]["verification"])
        self.assertEqual("DIRECT", result["resolved"]["computation"]["mode"])
        self.assertFalse(result["resolved"]["user_corrected"])
        self.assertEqual("overlay_kind", result["provenance"]["selected_input_ref"]["ref"])
        self.assertEqual("time.superseded_by_verified_overlay", _reasons(result)["tsc_kind"])
        self.assertFalse(result["considered"][1]["used"])
        self.assertEqual([], validate_contract(result))

        overlay["validation"]["monotonic_ok"] = False
        fallback = _resolve([self._candidate()], 65_000, ONLY_B, overlay=overlay)
        self.assertEqual("NEEDS_REVIEW", fallback["status"])
        self.assertEqual("recording.manufacturer_metadata_time", fallback["resolved"]["source"]["kind"])
        self.assertEqual("time.overlay_not_verified", _reasons(fallback)["overlay_kind"])
        self.assertEqual([], validate_contract(fallback))

    def test_vendor_candidate_preserves_user_correction_priority_and_provenance(self):
        correction = self._correction()
        result = _resolve([self._candidate()], 65_000, ONLY_B, overlay=self._overlay(), corrections=[correction])
        self.assertEqual("OK", result["status"])
        self.assertEqual(correction["new_value"], result["resolved"]["value"])
        self.assertEqual("case.user_correction", result["resolved"]["source"]["kind"])
        self.assertEqual("AGREED", result["resolved"]["verification"])
        self.assertEqual("USER_OVERRIDE", result["resolved"]["computation"]["mode"])
        self.assertTrue(result["resolved"]["user_corrected"])
        selected = {"kind": "correction_record", "ref": "corr_kind"}
        self.assertEqual(selected, result["provenance"]["selected_input_ref"])
        self.assertEqual(selected, result["resolved"]["source"]["input_ref"])
        self.assertEqual("time.superseded_by_user_correction", _reasons(result)["tsc_kind"])
        self.assertFalse(result["considered"][1]["used"])
        self.assertEqual([], validate_contract(result))

    def test_unknown_and_noncanonical_kinds_still_fail_in_every_path(self):
        for kind in ("MANUFACTURER_METADATA", "UNKNOWN_KIND"):
            candidate = {**self._candidate(), "source_kind": kind}
            for path in ({}, {"overlay": self._overlay()}, {"corrections": [self._correction()]}):
                with self.subTest(kind=kind, path=path):
                    with self.assertRaisesRegex(ContractInputError, "unsupported TimeSourceCandidate.source_kind"):
                        _resolve([candidate], 65_000, ONLY_B, **path)


if __name__ == "__main__":
    unittest.main()
