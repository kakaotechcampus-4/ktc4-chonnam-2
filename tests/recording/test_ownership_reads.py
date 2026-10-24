"""Catch ownership leaks, fabricated legacy reads and non-atomic media writes."""
import base64
import struct

import pytest

from daesingo.recording import RecordingService, RecordingCapabilityError, ContractRef, load_recording_fixture
from daesingo.recording.repository import InMemoryRecordingRepository

MP4 = base64.b64decode(
    'AAAAIGZ0eXBpc29tAAACAGlzb21pc28yYXZjMW1wNDEAAAAIZnJlZQAAAs1tZGF0AAACrQYF//+p3EXpvebZSLeWLNgg2SPu73gy'
    'NjQgLSBjb3JlIDE2NSByMzIyMyAwNDgwY2IwIC0gSC4yNjQvTVBFRy00IEFWQyBjb2RlYyAtIENvcHlsZWZ0IDIwMDMtMjAyNSAt'
    'IGh0dHA6Ly93d3cudmlkZW9sYW4ub3JnL3gyNjQuaHRtbCAtIG9wdGlvbnM6IGNhYmFjPTEgcmVmPTMgZGVibG9jaz0xOjA6MCBh'
    'bmFseXNlPTB4MzoweDExMyBtZT1oZXggc3VibWU9NyBwc3k9MSBwc3lfcmQ9MS4wMDowLjAwIG1peGVkX3JlZj0xIG1lX3Jhbmdl'
    'PTE2IGNocm9tYV9tZT0xIHRyZWxsaXM9MSA4eDhkY3Q9MSBjcW09MCBkZWFkem9uZT0yMSwxMSBmYXN0X3Bza2lwPTEgY2hyb21h'
    'X3FwX29mZnNldD0tMiB0aHJlYWRzPTEgbG9va2FoZWFkX3RocmVhZHM9MSBzbGljZWRfdGhyZWFkcz0wIG5yPTAgZGVjaW1hdGU9'
    'MSBpbnRlcmxhY2VkPTAgYmx1cmF5X2NvbXBhdD0wIGNvbnN0cmFpbmVkX2ludHJhPTAgYmZyYW1lcz0zIGJfcHlyYW1pZD0yIGJf'
    'YWRhcHQ9MSBiX2JpYXM9MCBkaXJlY3Q9MSB3ZWlnaHRiPTEgb3Blbl9nb3A9MCB3ZWlnaHRwPTIga2V5aW50PTI1MCBrZXlpbnRf'
    'bWluPTEgc2NlbmVjdXQ9NDAgaW50cmFfcmVmcmVzaD0wIHJjX2xvb2thaGVhZD00MCByYz1jcmYgbWJ0cmVlPTEgY3JmPTIzLjAg'
    'cWNvbXA9MC42MCBxcG1pbj0wIHFwbWF4PTY5IHFwc3RlcD00IGlwX3JhdGlvPTEuNDAgYXE9MToxLjAwAIAAAAAQZYiEABX//vfJ'
    '78Cm69vfgQAAAxRtb292AAAAbG12aGQAAAAAAAAAAAAAAAAAAAPoAAAD6AABAAABAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAA'
    'AAEAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAACP3RyYWsAAABcdGtoZAAAAAMAAAAAAAAA'
    'AAAAAAEAAAAAAAAD6AAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAEAAAAAAAAAAAAAAAAAAEAAAAAAEAAAABAAAAAA'
    'ACRlZHRzAAAAHGVsc3QAAAAAAAAAAQAAA+gAAAAAAAEAAAAAAbdtZGlhAAAAIG1kaGQAAAAAAAAAAAAAAAAAAEAAAABAAFXEAAAA'
    'AAAtaGRscgAAAAAAAAAAdmlkZQAAAAAAAAAAAAAAAFZpZGVvSGFuZGxlcgAAAAFibWluZgAAABR2bWhkAAAAAQAAAAAAAAAAAAAA'
    'JGRpbmYAAAAcZHJlZgAAAAAAAAABAAAADHVybCAAAAABAAABInN0YmwAAAC+c3RzZAAAAAAAAAABAAAArmF2YzEAAAAAAAAAAQAA'
    'AAAAAAAAAAAAAAAAAAAAEAAQAEgAAABIAAAAAAAAAAEUTGF2YzYzLjEuMTAxIGxpYngyNjQAAAAAAAAAAAAAAAAY//8AAAA0YXZj'
    'QwFkAAr/4QAXZ2QACqzZXsBEAAADAAQAAAMACDxIllgBAAZo6+PLIsD9+PgAAAAAEHBhc3AAAAABAAAAAQAAABRidHJ0AAAAAAAA'
    'FigAAAAAAAAAGHN0dHMAAAAAAAAAAQAAAAEAAEAAAAAAHHN0c2MAAAAAAAAAAQAAAAEAAAABAAAAAQAAABRzdHN6AAAAAAAAAsUA'
    'AAABAAAAFHN0Y28AAAAAAAAAAQAAADAAAABhdWR0YQAAAFltZXRhAAAAAAAAACFoZGxyAAAAAAAAAABtZGlyYXBwbAAAAAAAAAAA'
    'AAAAACxpbHN0AAAAJKl0b28AAAAcZGF0YQAAAAEAAAAATGF2ZjYzLjEuMTAx'
)
OTHER_MP4 = MP4[:-1] + b"2"


def padded_mp4(size):
    padding = max(8, size-len(MP4))
    return MP4 + struct.pack(">I4s", padding, b"free") + bytes(padding-8)


PNG = b"\x89PNG\r\n\x1a\n" + b"stored-image" + b"\x00\x00\x00\x00IEND\xaeB`\x82"


def asset(size=None, **changes):
    original = load_recording_fixture("scenario_happy_001").derived_assets[0]
    return original.model_copy(update={"byte_size": len(MP4) if size is None else size, **changes})


def seed(repo):
    f = load_recording_fixture("scenario_happy_001")
    for a in f.source_assets:
        repo.add_source_asset(a)
        repo.associate_case_asset("case-a", ContractRef(kind="source_asset", ref=a.source_asset_ref))
    for s in f.media_streams:
        repo.add_media_stream(s)
    repo.add_frame(f.frame_refs[0], content=PNG)
    return f.frame_refs[0], f.source_assets[0]


@pytest.fixture
def repo():
    return InMemoryRecordingRepository()


def test_ownership_follows_source_and_never_direct_frame_link(repo):
    frame, source = seed(repo)
    service = RecordingService(repo)
    repo.associate_case_asset("case-b", ContractRef(kind="frame", ref=frame.frame_ref))
    assert service.owns_frame("case-a", frame.frame_ref) is True
    assert service.owns_frame("case-b", frame.frame_ref) is False
    assert service.owns_frame("case-b", "missing") is False
    assert service.owns_asset("case-a", ContractRef(kind="source_asset", ref=source.source_asset_ref)) is True
    assert service.owns_asset("case-b", ContractRef(kind="source_asset", ref=source.source_asset_ref)) is False


def test_persistent_read_projection_and_same_case_derived(repo):
    service = RecordingService(repo)
    service.register_derived_asset(asset(), content=MP4, content_type="video/mp4", case_id="case-a")
    new = RecordingService(repo)
    opened = new.open_derived_asset(asset().derived_asset_ref)
    with opened.stream as stream:
        assert stream.read() == MP4
    assert opened.content_type == "video/mp4" and opened.byte_size == len(MP4)
    assert not hasattr(opened, "locator") and not hasattr(opened, "payload")
    ref = ContractRef(kind="derived_asset", ref=asset().derived_asset_ref)
    assert new.owns_asset("case-a", ref) is True
    assert new.owns_asset("case-b", ref) is False
    assert new.owns_asset("case-b", ContractRef(kind="derived_asset", ref="missing")) is False


def test_frame_format_comes_from_stored_png_without_regeneration(repo):
    frame, _ = seed(repo)
    image = RecordingService(repo).read_frame_image(frame.frame_ref)
    assert image.content == PNG
    assert image.content_type == "image/png" and image.image_format == "png"
    assert RecordingService(repo).read_frame(frame.frame_ref) == PNG


@pytest.mark.parametrize("content", [None, b"legacy-stub", b""])
def test_legacy_unknown_images_are_unavailable_without_fabrication(repo, content):
    frame = load_recording_fixture("scenario_happy_001").frame_refs[0]
    repo.add_frame(frame, content=content)
    with pytest.raises(RecordingCapabilityError) as e:
        RecordingService(repo).read_frame_image(frame.frame_ref)
    assert e.value.code == "FRAME_NOT_FOUND"


def test_legacy_metadata_only_derived_is_unavailable(repo):
    service = RecordingService(repo)
    service.register_derived_asset(asset())
    assert service.get_derived_asset(asset().derived_asset_ref) == asset()
    with pytest.raises(RecordingCapabilityError) as e:
        service.open_derived_asset(asset().derived_asset_ref)
    assert e.value.code == "UNAVAILABLE"
    with pytest.raises(RecordingCapabilityError) as e:
        service.open_derived_asset("missing")
    assert e.value.code == "UNKNOWN_REF"
    with pytest.raises(RecordingCapabilityError) as e:
        service.get_derived_asset("missing")
    assert e.value.code == "NOT_FOUND"  # Existing metadata API compatibility.


@pytest.mark.parametrize("bad", ["", None, 42, "\ud800"])
def test_invalid_case_and_ref_do_not_echo_input(repo, bad):
    service = RecordingService(repo)
    for invoke in (lambda: service.owns_frame(bad, "missing"),
                   lambda: service.owns_frame("case-a", bad),
                   lambda: service.open_derived_asset(bad)):
        with pytest.raises(ValueError):
            invoke()


@pytest.mark.parametrize("kind", ["frame", "analysis_source", "incident_clip", "external_source", "remote_copy"])
def test_wrong_asset_family_is_machine_readable(repo, kind):
    with pytest.raises(RecordingCapabilityError) as e:
        RecordingService(repo).owns_asset("case-a", {"kind": kind, "ref": "secret"})
    assert e.value.code == "INVALID_REF_KIND" and "secret" not in str(e.value)


@pytest.mark.parametrize("ct", ["", "text", "video/mp4\r\nsecret: value", "video/mp4;secret=x", 1])
def test_invalid_content_type_is_rejected_before_any_write(repo, ct):
    with pytest.raises(ValueError) as e:
        RecordingService(repo).register_derived_asset(asset(), content=MP4, content_type=ct, case_id="case-a")
    assert repo.get_derived_asset(asset().derived_asset_ref) is None
    assert repo.get_case_assets("case-a") == [] and "secret" not in str(e.value)


@pytest.mark.parametrize("size,content,ct", [(2,MP4,"video/mp4"), (3,MP4,None), (3,None,"video/mp4"), (3,bytearray(MP4),"video/mp4")])
def test_inconsistent_bytes_metadata_is_rejected_atomically(repo, size, content, ct):
    with pytest.raises(ValueError):
        RecordingService(repo).register_derived_asset(asset(size), content=content, content_type=ct, case_id="case-a")
    assert repo.get_derived_asset(asset().derived_asset_ref) is None


@pytest.mark.parametrize("content", [MP4, padded_mp4(1024*1024)], ids=["small", "one_mib"])
def test_zero_and_large_payload_round_trip(repo, content):
    service = RecordingService(repo)
    value = asset(len(content))
    service.register_derived_asset(value, content=content, content_type="video/mp4")
    assert service.open_derived_asset(value.derived_asset_ref).stream.read() == content


def test_conflicting_duplicate_does_not_add_case_link_or_change_bytes(repo):
    service = RecordingService(repo)
    service.register_derived_asset(asset(), content=MP4, content_type="video/mp4", case_id="case-a")
    service.register_derived_asset(asset(), content=MP4, content_type="video/mp4", case_id="case-a")
    with pytest.raises(ValueError):
        service.register_derived_asset(asset(), content=OTHER_MP4, content_type="video/mp4", case_id="case-b")
    assert service.open_derived_asset(asset().derived_asset_ref).stream.read() == MP4
    assert repo.get_case_assets("case-b") == []


@pytest.mark.parametrize("fmt", ["jpeg", "", "png\r\nsecret", 42])
def test_frame_image_format_rejection_leaves_no_frame(repo, fmt):
    frame = load_recording_fixture("scenario_happy_001").frame_refs[0]
    with pytest.raises(ValueError):
        repo.add_frame(frame, content=PNG, image_format=fmt)
    assert repo.get_frame(frame.frame_ref) is None


def test_frame_identity_conflict_keeps_original_bytes(repo):
    frame, _ = seed(repo)
    with pytest.raises(ValueError):
        repo.add_frame(frame, content=PNG.replace(b"stored", b"mutate"))
    assert repo.get_frame_content(frame.frame_ref) == PNG


@pytest.mark.parametrize("fault", ["content_type", "metadata", "size"])
def test_duplicate_metadata_conflicts_cannot_attach_another_case(repo, fault):
    service = RecordingService(repo)
    service.register_derived_asset(asset(), content=MP4, content_type="video/mp4", case_id="case-a")
    value, content, ct = asset(), MP4, "video/mp4"
    if fault == "content_type":
        ct = "image/png"
    elif fault == "metadata":
        value = asset(transform_ref="secret")
    else:
        value, content = asset(len(MP4)+8), MP4 + b"\0\0\0\x08free"
    with pytest.raises(ValueError):
        service.register_derived_asset(value, content=content, content_type=ct, case_id="case-b")
    assert repo.get_case_assets("case-b") == []
    assert service.get_derived_asset(asset().derived_asset_ref) == asset()


@pytest.mark.parametrize("payload", [{"secret": "path"}, asset().model_dump(mode="json") | {"derived_asset_ref": ""}])
def test_invalid_derived_payload_never_echoes_raw_fields(repo, payload):
    with pytest.raises(ValueError) as e:
        RecordingService(repo).register_derived_asset(payload)
    assert "secret" not in str(e.value) and "input_value" not in str(e.value)


@pytest.mark.parametrize("content,ct", [(PNG,"video/mp4"), (b"unidentified","video/mp4"), (b"","video/mp4")], ids=["mismatch","unidentified","empty"])
def test_derived_actual_format_must_match_content_type(repo, content, ct):
    with pytest.raises(ValueError):
        RecordingService(repo).register_derived_asset(asset(len(content)), content=content, content_type=ct)
    assert repo.get_derived_asset(asset().derived_asset_ref) is None
