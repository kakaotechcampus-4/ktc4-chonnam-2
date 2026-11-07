"""Exact prepared metadata through real MySQL, including unequal replay refusal."""

from copy import deepcopy
import hashlib
import math
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest

from daesingo.recording import load_recording_fixture, RecordingService, ContractRef
from daesingo.recording.mysql_repository import MySQLRecordingRepository, entries, _key
from test_ownership_reads import MP4

pytestmark = pytest.mark.mysql


def kinds(prefix):
    return [
        pytest.param(
            kind,
            marks=pytest.mark.mysql_check(
                "recording", "chunked_media", parameter=prefix + "_" + kind
            ),
        )
        for kind in ("analysis_source", "incident_clip")
    ]


@pytest.fixture
def db(mysql_engine, tmp_path):
    cfg = Config(str(Path(__file__).parents[2] / "migrations/recording/alembic.ini"))
    with mysql_engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")
    return mysql_engine, tmp_path


def media(kind, end=100.00000033333333):
    f = load_recording_fixture("scenario_happy_001")
    original = (f.analysis_sources if kind == "analysis_source" else f.incident_clips)[
        0
    ]
    payload = original.model_dump(mode="json")
    payload.update(
        byte_size=len(MP4),
        availability="AVAILABLE",
        duration_sec=end,
        timeline_range={"start_sec": 0.0, "end_sec": end},
    )
    if kind == "incident_clip":
        provenance = payload["source_provenance"]
        provenance["requested_range"] = dict(payload["timeline_range"])
        provenance["asset_spans"] = provenance["asset_spans"][:1]
        provenance["asset_spans"][0].update(
            sequence=0,
            timeline_range=dict(payload["timeline_range"]),
            source_range=dict(payload["timeline_range"]),
        )
    return type(original).model_validate(payload)


def repo(conn, root):
    return MySQLRecordingRepository(conn, storage_root=root, temp_root=root,
                                    prepared_write_format="chunked")


def snapshot(conn):
    return (
        conn.exec_driver_sql(
            "SELECT kind,entry_key,CAST(payload AS CHAR),SHA2(content,256) FROM recording_entry ORDER BY kind,entry_key"
        ).all(),
        conn.exec_driver_sql(
            "SELECT kind,entry_key,chunk_index,SHA2(content,256) FROM recording_media_chunk ORDER BY kind,entry_key,chunk_index"
        ).all(),
    )


@pytest.mark.parametrize("kind", kinds("exact"))
def test_exact_numbers_commit_fresh_read_and_unequal_replays(db, kind):
    engine, root = db
    item = media(kind)
    ref = getattr(item, kind + "_ref")
    with engine.begin() as conn:
        repo(conn, root).add_prepared_media(item, MP4, case_id="owner")
        writer = conn.exec_driver_sql("SELECT CONNECTION_ID()").scalar_one()
    engine.dispose()
    with engine.begin() as conn:
        assert conn.exec_driver_sql("SELECT CONNECTION_ID()").scalar_one() != writer
        repository = repo(conn, root)
        restored = getattr(repository, "get_" + kind)(ref)
        assert restored == item and restored.model_dump() == item.model_dump()
        assert restored.duration_sec.hex() == item.duration_sec.hex()
        assert (
            restored.timeline_range.end_sec.hex() == item.timeline_range.end_sec.hex()
        )
        assert repository._models(kind, type(item)) == [item]
        facts = RecordingService(repository).list_case_asset_facts("owner")[0]
        assert facts.duration_sec.hex() == item.duration_sec.hex()
        stream, _ = repository.open_prepared_stream(ContractRef(kind=kind, ref=ref))
    with stream:
        assert (
            hashlib.file_digest(stream, "sha256").digest()
            == hashlib.sha256(MP4).digest()
        )
    with engine.begin() as conn:
        repository = repo(conn, root)
        repository.add_prepared_media(item, MP4, case_id="equal")
        before = snapshot(conn)
        for field in ("end", "duration", "stream", "revision", "provenance"):
            payload = deepcopy(item.model_dump(mode="json"))
            if field == "end":
                payload["timeline_range"]["end_sec"] = math.nextafter(
                    item.timeline_range.end_sec, 0
                )
            elif field == "duration":
                payload["duration_sec"] = math.nextafter(item.duration_sec, math.inf)
            elif field == "stream":
                payload["media_stream_refs"].append("different-stream")
            elif field == "revision":
                payload["timeline_ref"]["revision"] += 1
                if kind == "incident_clip":
                    payload["source_provenance"]["timeline_ref"]["revision"] += 1
            elif kind == "analysis_source":
                payload["source_refs"][0]["ref"] = "different-source"
            else:
                payload["source_provenance"]["asset_spans"][0]["source_asset_ref"] = (
                    "different-source"
                )
            different = type(item).model_validate(payload)
            with pytest.raises(ValueError, match="immutable identity"):
                repository.add_prepared_media(
                    different, MP4, case_id="conflict-" + field
                )
            assert snapshot(conn) == before
            assert repository.get_case_assets("conflict-" + field) == []
        assert getattr(repository, "get_" + kind)(ref) == item


@pytest.mark.parametrize("kind", kinds("exact_attach"))
def test_metadata_only_then_content_preserves_exact_values(db, kind):
    engine, root = db
    item = media(kind)
    ref = getattr(item, kind + "_ref")
    with engine.begin() as conn:
        getattr(repo(conn, root), "add_" + kind)(item)
    engine.dispose()
    with engine.begin() as conn:
        repository = repo(conn, root)
        assert getattr(repository, "get_" + kind)(ref) == item
        repository.add_prepared_media(item, MP4, case_id="attached")
    with engine.connect() as conn:
        assert getattr(repo(conn, root), "get_" + kind)(ref) == item


@pytest.mark.parametrize("kind", kinds("exact_legacy"))
def test_legacy_equal_replay_never_rewrites_old_native_payload(db, kind):
    engine, root = db
    item = media(kind, 100.0)
    ref = getattr(item, kind + "_ref")
    with engine.begin() as conn:
        conn.execute(
            entries.insert().values(
                kind=kind, entry_key=_key(ref), payload=item.model_dump(mode="json")
            )
        )
        before = conn.exec_driver_sql(
            "SELECT CAST(payload AS CHAR) FROM recording_entry"
        ).scalar_one()
        repository = repo(conn, root)
        repository.add_prepared_media(item, MP4)
        after = conn.exec_driver_sql(
            "SELECT CAST(payload AS CHAR) FROM recording_entry WHERE kind=%s", (kind,)
        ).scalar_one()
        assert after == before and getattr(repository, "get_" + kind)(ref) == item


@pytest.mark.parametrize("kind", kinds("exact_corrupt"))
def test_outer_metadata_mutation_is_not_hidden_by_internal_encoding(db, kind):
    engine, root = db
    item = media(kind)
    with engine.begin() as conn:
        repo(conn, root).add_prepared_media(item, MP4)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "UPDATE recording_entry SET payload=JSON_SET(payload,'$.availability','UNAVAILABLE') WHERE kind=%s",
            (kind,),
        )
    with engine.connect() as conn:
        with pytest.raises(ValueError):
            getattr(repo(conn, root), "get_" + kind)(getattr(item, kind + "_ref"))
