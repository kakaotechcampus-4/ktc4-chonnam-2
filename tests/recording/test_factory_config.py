from importlib import import_module

import pytest


def mapping():
    return {"DAESINGO_RECORDING_ANALYSIS_PROFILE_REF": "explicit-profile",
            "DAESINGO_RECORDING_ANALYSIS_HEIGHT": "240",
            "DAESINGO_RECORDING_ANALYSIS_PRESET": "veryfast",
            "DAESINGO_RECORDING_ANALYSIS_CRF": "23"}


def test_module_mapping_requires_explicit_media_profile_without_guessing_env(monkeypatch, tmp_path):
    module = import_module("daesingo.recording.factory")
    monkeypatch.setenv("DAESINGO_RECORDING_ANALYSIS_HEIGHT", "999")
    settings = module.RecordingSettings.from_mapping({})
    assert settings.profile_ref is None
    configured = module.RecordingSettings.from_mapping(mapping())
    assert configured.profile_ref == "explicit-profile" and configured.profile.height == 240
    from daesingo.recording.repository import InMemoryRecordingRepository
    with module.build_recording_service(InMemoryRecordingRepository(), configured, temp_root=tmp_path) as service:
        assert service.get_time_source_candidates("not-observed") == []


@pytest.mark.parametrize("key,value", [("DAESINGO_RECORDING_ANALYSIS_HEIGHT", "241"),
    ("DAESINGO_RECORDING_ANALYSIS_PRESET", "unknown"), ("DAESINGO_RECORDING_ANALYSIS_CRF", "52"),
    ("DAESINGO_RECORDING_FILENAME_OFFSET", "guess"), ("DAESINGO_RECORDING_ANALYSIS_PROFILE_REF", "")])
def test_bad_module_values_reject_before_any_media_invocation(key, value):
    module = import_module("daesingo.recording.factory")
    values = {**mapping(), key: value}
    with pytest.raises(ValueError): module.RecordingSettings.from_mapping(values)


def test_partially_configured_profile_rejects_instead_of_enabling_defaults():
    module = import_module("daesingo.recording.factory")
    with pytest.raises(ValueError): module.RecordingSettings.from_mapping({"DAESINGO_RECORDING_ANALYSIS_HEIGHT": "240"})
