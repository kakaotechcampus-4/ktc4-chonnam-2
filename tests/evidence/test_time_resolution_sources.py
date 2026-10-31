"""TimeResolution의 base-plus-offset이 사건 대표 순간이 담긴 원본 하나의 시계만 쓰는지 검사한다.

PR #458 리뷰(stored_observation.py 243-247): 원본 A(12:00:00, timeline 0~60초)와 B(12:01:00, 60~120초)를
이어 붙였을 때 사건이 timeline 65초면 B 안 5초 = 12:01:05여야 한다. timeline 위치를 B 시각에 그대로 더하면
12:02:05가 된다.
"""
from __future__ import annotations

import unittest

from daesingo.evidence import ContractInputError, resolve_time, validate_contract

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


def _resolve(candidates, representative_ms, clip):
    return resolve_time(
        time_source_candidates=candidates,
        overlay_time_readout=None,
        candidate_event=_event(representative_ms),
        case_id="case_multi",
        selection_rev=1,
        resolution_id="tr_multi",
        incident_clip=clip,
    )


def _reasons(result):
    return {item["input_ref"]["ref"]: item.get("reason_code") for item in result["considered"]}


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


if __name__ == "__main__":
    unittest.main()
