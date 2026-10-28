"""One immutable registry for available public module capabilities."""
from daesingo.worker.search_composition import compose_search_registry
from daesingo.worker.incident_clip_composition import compose_incident_clip_registry
from daesingo.worker.readout_composition import compose_readout_registry


def compose_registry(*, engine, startup, readout_provider_factory=None):
    return compose_search_registry(engine=engine, startup=startup).merged(
        compose_incident_clip_registry(engine=engine, startup=startup)).merged(
        compose_readout_registry(engine=engine, startup=startup, provider_factory=readout_provider_factory))
