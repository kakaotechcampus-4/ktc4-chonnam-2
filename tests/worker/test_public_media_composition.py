"""Exercise the MediaRoot constructed by each production registry, without AI/DB."""
from importlib import import_module
from io import StringIO
from types import MappingProxyType

import pytest

from daesingo.common.bootstrap import Startup
from daesingo.common.config import RuntimeConfig
from daesingo.common.logging import configure_logging
from daesingo.common.public_runtime.temporary import case_temp_scope, public_temp_root
from daesingo.common.storage._filesystem import UnsafePath
from daesingo.recording.factory import RecordingSettings
from daesingo.worker.registry import KindRegistry
from tests.recording.test_factory_config import clip_mapping, mapping


@pytest.fixture(params=[
    ("search_composition", "compose_search_registry", "search_registry"),
    ("incident_clip_composition", "compose_incident_clip_registry", "incident_clip_registry"),
    ("export_composition", "compose_export_registry", "export_registry"),
], ids=["search", "incident-and-preview", "export"])
def production_media(request, monkeypatch, tmp_path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    work = media_root / "worker-temp"
    work.mkdir()
    (media_root / "source").mkdir()
    config = RuntimeConfig.from_mapping("worker", {
        "DAESINGO_RUNTIME_PUBLIC_MODE": "a1",
        "DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://fixture@127.0.0.1:1/no_connection",
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(media_root),
        "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(work),
    })
    settings = RecordingSettings.from_mapping(mapping() | clip_mapping())
    startup = Startup(config, MappingProxyType({"recording": settings, "search": object()}),
                      configure_logging("worker", stream=StringIO()))
    module_name, compose_name, registry_name = request.param
    module = import_module("daesingo.worker." + module_name)
    captured = {}

    def capture(**kwargs):
        captured.update(kwargs)
        return KindRegistry({})

    # Keep the real registry composition, configured cleanup and MediaRoot.
    # Only defer handler execution, which would require production DB/media/AI.
    monkeypatch.setattr(module, registry_name, capture)
    getattr(module, compose_name)(engine=object(), startup=startup)
    factory = captured["service_factory"]
    assert factory is not None and factory.media is not None
    return factory.media, media_root, work


def test_production_registry_accepts_its_owned_public_case_temp(production_media):
    media, root, _ = production_media
    public = public_temp_root(root)
    with case_temp_scope(public, "a" * 32) as owned:
        with media.detached_temp() as actual:
            assert actual.samefile(owned)
            assert actual.parent.samefile(public)


def test_production_registry_keeps_internal_temp_without_public_scope(production_media):
    media, _, work = production_media
    with media.detached_temp() as actual:
        assert actual.samefile(work)


def test_production_registry_rejects_a_different_public_root(production_media):
    media, root, _ = production_media
    public_temp_root(root)  # The real dispatch creates the approved parent before binding a Case.
    foreign = root / "different-public-root"
    foreign.mkdir()
    with case_temp_scope(foreign, "b" * 32):
        with pytest.raises(UnsafePath):
            with media.detached_temp():
                pytest.fail("A token-shaped directory outside the approved root was accepted")
