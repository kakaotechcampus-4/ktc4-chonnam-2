from datetime import datetime, timezone
import pytest

from daesingo.recording.mysql_repository import _key
from daesingo.recording.purge import plan_rows, PurgeBlocked


def row(number, kind, identity, payload):
    return {"ordinal": number, "kind": kind, "entry_key": _key(identity), "payload": payload}


def graph():
    return [row(1, "case_asset", ["case_1", "source_asset", "sa_1"],
                {"case_id": "case_1", "asset_ref": {"kind": "source_asset", "ref": "sa_1"}}),
        row(2, "source_asset", "sa_1", {"source_asset_ref": "sa_1", "media_stream_refs": ["ms_1"]}),
        row(3, "local_source", "sa_1", {"locator": "source/" + "a" * 32, "sha256": "b" * 64, "byte_size": 10}),
        row(4, "media_stream", "ms_1", {"media_stream_ref": "ms_1", "source_asset_ref": "sa_1"}),
        row(5, "stream_index", "ms_1", {"index": 0}),
        row(6, "frame", "fr_1", {"frame_ref": "fr_1", "media_stream_ref": "ms_1"}),
        row(7, "frame_position", ["ms_1", "0"], {"frame_ref": "fr_1"}),
        row(8, "timeline", ["tl_1", 1], {"timeline_id": "tl_1", "source_placements": [{"source_asset_ref": "sa_1"}]}),
        row(9, "analysis_source", "as_1", {"analysis_source_ref": "as_1", "timeline_ref": {"timeline_id": "tl_1"}}),
        row(10, "prepared_content", ["analysis_source", "as_1"], {"version": 1, "chunk_count": 1}),
        row(11, "derived_asset", "da_1", {"derived_asset_ref": "da_1", "source_refs": [{"kind": "analysis_source", "ref": "as_1"}]}),
        row(12, "derived_content", "da_1", {"content_type": "video/mp4", "byte_size": 20})]


def test_exclusive_case_graph_includes_frames_prepared_metadata_and_descriptors():
    plan = plan_rows(graph(), "case_1", datetime.now(timezone.utc))
    assert {x["ordinal"] for x in plan["entries"]} == set(range(1, 13))
    assert plan["files"] == [{"locator": "source/" + "a" * 32, "sha256": "b" * 64, "byte_size": 10}]


def test_other_case_reference_preserves_entire_shared_graph_and_canonical_file():
    rows = graph() + [row(13, "case_asset", ["case_2", "source_asset", "sa_1"],
        {"case_id": "case_2", "asset_ref": {"kind": "source_asset", "ref": "sa_1"}})]
    plan = plan_rows(rows, "case_1", datetime.now(timezone.utc))
    assert [x["ordinal"] for x in plan["entries"]] == [1]
    assert plan["files"] == [] and plan["shared_entries"] == 11


def test_expired_provider_reference_is_not_guessed_deleted():
    rows = graph() + [row(13, "remote_copy", "remote_1", {"remote_copy_ref": "remote_1",
        "analysis_source_ref": "as_1", "expires_at": None})]
    with pytest.raises(PurgeBlocked) as error:
        plan_rows(rows, "case_1", datetime.now(timezone.utc))
    assert error.value.code == "PENDING_EXPIRY"


def test_unknown_connected_metadata_or_private_locator_never_expands_deletion():
    for extra in (row(13, "future_kind", "something", {"source_asset_ref": "sa_1"}),
                  row(13, "local_source", "as_1", {"locator": "../protected-original", "byte_size": 10, "sha256": "x"})):
        with pytest.raises(PurgeBlocked):
            plan_rows(graph() + [extra], "case_1", datetime.now(timezone.utc))


def test_normal_preparation_time_observation_is_purged_with_its_source():
    from daesingo.recording.time_sources import ObservedTimeSources, TimeSourceCheck
    from daesingo.recording.durable import observation_payload
    observed = ObservedTimeSources(candidates=(), checks=(TimeSourceCheck(source_asset_ref="sa_1",
        source_kind="FILE_METADATA", source_detail="creation_time", status="NOT_FOUND"),))
    rows = graph() + [row(13, "time_observation", "sa_1", observation_payload(observed))]
    assert len(plan_rows(rows, "case_1", datetime.now(timezone.utc))["entries"]) == 13
