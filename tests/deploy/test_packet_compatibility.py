"""Writer-aware startup packet policy, offline SQL boundary (not DB acceptance)."""
from contextlib import contextmanager
import struct
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
import pymysql

from daesingo.recording import mysql_repository as repository
from daesingo.recording import load_recording_fixture
from test_deployment_runtime import adapter


def packet_run(monkeypatch, *, write_format, maximum, packet, margin):
    runtime = adapter()
    monkeypatch.setattr(repository, "PREPARED_WRITE_FORMAT", write_format)
    monkeypatch.setattr(runtime, "deployment_config", lambda: (
        {"DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://packet-canary@mysql/daesingo"},
        SimpleNamespace(analysis_limits=SimpleNamespace(max_bytes=maximum))))
    calls = []

    def scalar(statement):
        assert str(statement) == "SELECT @@SESSION.max_allowed_packet"
        calls.append("query")
        return packet

    @contextmanager
    def connect():
        yield SimpleNamespace(scalar=scalar)

    engine = SimpleNamespace(connect=connect, dispose=lambda: calls.append("dispose"))
    monkeypatch.setattr(sa, "create_engine", lambda *args, **kwargs: engine)
    result = runtime.main(["deploy-packet", str(margin)])
    assert calls == ["query", "dispose"]
    return result


@pytest.mark.parametrize("write_format,maximum,packet,margin,expected", [
    # Overall media can exceed P only for the image's chunked writer.
    ("chunked", 256*1024*1024, 64*1024*1024, 8*1024*1024, 0),
    ("legacy", 256*1024*1024, 64*1024*1024, 8*1024*1024, 1),
    ("legacy", 48*1024*1024, 64*1024*1024, 8*1024*1024, 0),
    ("legacy", 56*1024*1024, 64*1024*1024, 8*1024*1024, 1),
    # P=1MiB -> budget=960KiB. Equality with policy reserve is forbidden.
    ("chunked", 256*1024*1024, 1024*1024, 64*1024-1, 0),
    ("chunked", 256*1024*1024, 1024*1024, 64*1024, 1),
    ("chunked", 256*1024*1024, 1024*1024, 64*1024+1, 1),
    # P=80KiB+1 -> budget=16KiB+1 -> no whole escaped payload byte.
    ("chunked", 256*1024*1024, 80*1024+1, 1, 1),
    ("chunked", 256*1024*1024, 80*1024+2, 1, 0),
    ("unknown", 1, 64*1024*1024, 1, 1),
])
def test_deploy_packet_uses_image_writer_policy(monkeypatch, capsys,
        write_format, maximum, packet, margin, expected):
    assert packet_run(monkeypatch, write_format=write_format, maximum=maximum,
                      packet=packet, margin=margin) == expected
    output = capsys.readouterr()
    assert "packet-canary" not in output.out + output.err


@pytest.mark.parametrize("field,value", [
    (field, value) for field in ("maximum", "packet") for value in (0, -1, True, 1.5, "100")
] + [("margin", 0), ("margin", -1), ("margin", "bad")])
def test_chunked_does_not_bypass_positive_limits(monkeypatch, field, value):
    values = dict(maximum=256*1024*1024, packet=64*1024*1024, margin=8*1024*1024)
    values[field] = value
    assert packet_run(monkeypatch, write_format="chunked", **values) == 1


@pytest.mark.parametrize("write_format,spoof,expected", [
    ("chunked", "legacy", 0), ("legacy", "chunked", 1), ("unknown", "chunked", 1),
])
def test_host_env_cannot_select_writer_format(monkeypatch, write_format, spoof, expected):
    monkeypatch.setenv("PREPARED_WRITE_FORMAT", spoof)
    monkeypatch.setenv("DAESINGO_RECORDING_PREPARED_WRITE_FORMAT", spoof)
    assert packet_run(monkeypatch, write_format=write_format, maximum=256*1024*1024,
                      packet=64*1024*1024, margin=8*1024*1024) == expected


@pytest.mark.parametrize("write_format,packet,cap,want", [
    ("chunked", 64*1024*1024, None, (1048576, 262144)),
    ("chunked", 1024*1024, None, (983040, 262144)),
    ("chunked", 128*1024, None, (65536, 24576)),
    ("chunked", 80*1024+2, None, (16386, 1)),
    ("chunked", 64*1024*1024, 64*1024, (65536, 24576)),
    ("legacy", 64*1024*1024, None, (67043328, 262144)),
    ("legacy", 128*1024, 1024*1024, (65536, 24576)),
])
def test_shared_writer_limits_have_hand_checked_budgets(write_format, packet, cap, want):
    calculate = getattr(repository, "prepared_command_limits", None)
    assert callable(calculate), "writer and deploy-packet need one shared calculation"
    assert calculate(packet, write_format=write_format, command_budget=cap) == want


@pytest.mark.parametrize("write_format,packet,cap", [
    ("unknown", 64*1024*1024, None),
    ("chunked", 0, None), ("chunked", True, None), ("chunked", "100000", None),
    ("chunked", 64*1024, None), ("chunked", 80*1024+1, None),
    ("legacy", 80*1024, None),
    ("chunked", 64*1024*1024, 0), ("chunked", 64*1024*1024, 16*1024),
    ("chunked", 64*1024*1024, True), ("chunked", 64*1024*1024, 20000.5),
])
def test_shared_limits_reject_unknown_or_unusable_inputs(write_format, packet, cap):
    calculate = getattr(repository, "prepared_command_limits", None)
    assert callable(calculate), "writer and deploy-packet need one shared calculation"
    with pytest.raises(ValueError):
        calculate(packet, write_format=write_format, command_budget=cap)


def test_actual_escaping_guard_still_rejects_oversized_rendered_sql():
    # Real PyMySQL rendering; neither a network connection nor a DB write.
    driver = pymysql.connections.Connection(defer_connect=True)
    driver.server_status = 0
    cursor = driver.cursor()
    engine = sa.create_engine("sqlite://")
    try:
        with engine.connect() as conn:
            repo = object.__new__(repository.MySQLRecordingRepository)
            repo._connection = conn
            with repo._prepared_commands(128):
                # Installed PyMySQL renders bytes as hex literals (~2x).
                # Both raw lengths fit128; only the smaller rendered SQL fits.
                for content, rejected in [(b"x"*40, False), (b"\0"*80, True)]:
                    def render():
                        conn.dispatch.before_cursor_execute(conn, cursor, "SELECT %s",
                                                            (content,), None, False)
                    if rejected:
                        with pytest.raises(ValueError, match="exceeds budget"):
                            render()
                    else:
                        render()
            assert not list(conn.dispatch.before_cursor_execute)
    finally:
        cursor.close()
        engine.dispose()


def test_writer_default_propagates_shared_policy_rejection_before_sql(tmp_path, monkeypatch):
    repo = repository.MySQLRecordingRepository(
        SimpleNamespace(dialect=SimpleNamespace(name="mysql"), closed=False), storage_root=tmp_path)
    assert repo._prepared_write_format == repository.PREPARED_WRITE_FORMAT
    # Container-signature fixture only, not decode/real-video acceptance.
    content = (struct.pack(">I4s4sI", 16, b"ftyp", b"isom", 0)
               + struct.pack(">I4s", 8, b"moov") + struct.pack(">I4s", 8, b"mdat"))
    media = load_recording_fixture("scenario_happy_001").analysis_sources[0].model_copy(
        update={"byte_size": len(content), "availability": "AVAILABLE"})

    def execute(statement):
        assert str(statement) == "SELECT @@session.max_allowed_packet", "must reject before DML"
        return SimpleNamespace(scalar_one=lambda: 1048576)

    def reject(packet, *, write_format, command_budget=None):
        assert packet == 1048576 and write_format == repo._prepared_write_format
        assert command_budget is None
        raise ValueError("shared policy rejection")

    monkeypatch.setattr(repo, "_execute", execute)
    # Fault injection pins consumption of the shared policy, not a copied formula.
    monkeypatch.setattr(repository, "prepared_command_limits", reject)
    with pytest.raises(ValueError, match="shared policy rejection"):
        repo.add_prepared_media(media, content)
