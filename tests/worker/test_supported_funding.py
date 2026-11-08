"""Match supported calls to the actual immutable Worker provider configuration."""
from dataclasses import replace

from pydantic import SecretStr
import pytest

from daesingo.common.public_runtime.policy import PublicDenied
from daesingo.search.config import GeminiSearchConfig
from daesingo.worker.bootstrap import SearchSettings, require_supported_elice


@pytest.mark.parametrize("operation,module", [("HINT_EXTRACT", "intent"), ("SEARCH_COARSE", "search"),
                                              ("SEARCH_FINE", "search")])
def test_actual_supported_provider_configuration_is_required(operation, module):
    config = GeminiSearchConfig(model="test-model")
    snapshot = {"operation": operation, "provider_label": "elice:test-model"}
    def modules(value):
        return {module: SearchSettings(SecretStr("test-only"), value) if module == "search" else value}
    require_supported_elice(modules(config), snapshot)
    for actual, call in (({}, snapshot),
                         (modules(replace(config, base_url="https://generativelanguage.googleapis.com/v1")), snapshot),
                         (modules(config), dict(snapshot, provider_label="elice:other")),
                         (modules(config), dict(snapshot, operation="OTHER"))):
        with pytest.raises(PublicDenied) as error:
            require_supported_elice(actual, call)
        assert error.value.code == "UNSUPPORTED"


def test_internal_untagged_usage_is_not_subject_to_supported_public_scope(tmp_path, monkeypatch):
    from io import StringIO
    from threading import Event
    from types import SimpleNamespace
    import sqlalchemy as sa
    from a1_support import supported_policy_values
    from daesingo.common.bootstrap import Startup
    from daesingo.common.config import RuntimeConfig
    from daesingo.common.jobs.execution import ExecutionContext
    from daesingo.common.logging import configure_logging
    from daesingo.common.public_runtime.policy import PublicPolicy
    from daesingo.worker.composition import compose_worker
    from daesingo.worker.registry import KindRegistry
    import daesingo.worker.composition as composition
    policy = PublicPolicy.model_validate(supported_policy_values(tmp_path))
    media, temp = tmp_path / "media", tmp_path / "temp"
    media.mkdir()
    temp.mkdir()
    config = RuntimeConfig.from_mapping("worker", {
        "DAESINGO_RUNTIME_DB_URL": "mysql+pymysql://test:test@localhost/test",
        "DAESINGO_RUNTIME_MEDIA_ROOT": str(media), "DAESINGO_RUNTIME_WORKER_TEMP_ROOT": str(temp),
        "DAESINGO_RUNTIME_PUBLIC_MODE": "internal"})
    monkeypatch.setattr(composition, "load_policy", lambda *a, **k: policy)
    scoped = [False]
    monkeypatch.setattr(composition.PublicStore, "reserve", lambda *a: scoped[0])
    monkeypatch.setattr(composition, "DurableUsageSink", lambda **k: SimpleNamespace(before_begin=k["before_begin"]))
    engine = sa.create_engine("sqlite://")
    try:
        loop = compose_worker(engine=engine, startup=Startup(config, {}, configure_logging("worker", stream=StringIO())),
            registry=KindRegistry({}), stop=Event())
        context = ExecutionContext("exec", "job", "case", "TEST", 1, "trace")
        gate = loop.usage_sink_factory(context).before_begin
        snapshot = {"operation": "READOUT_PLATE", "provider_label": "local:test"}
        gate(None, snapshot)
        # An internal misconfiguration still cannot bypass a tagged public Case.
        scoped[0] = True
        with pytest.raises(PublicDenied):
            gate(None, snapshot)
    finally:
        engine.dispose()
