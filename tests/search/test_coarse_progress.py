import pytest

from daesingo.search import search_candidates
from daesingo.search.schemas import CoarseResponse
from daesingo.search.runs import RunOutcome
from tests.search.test_coarse_boundaries import _scope, _service, _source


@pytest.mark.parametrize("failed", [False, True])
def test_real_boundaries_surround_provider_and_failure_never_announces_organizing(failed):
    phases = []
    service = _service(_source(), CoarseResponse(candidates=[]))
    original = service.provider
    class Provider:
        def search_coarse(self, request):
            assert phases == ["PREPARING", "SEARCHING"]
            if failed:
                raise TimeoutError()
            return original.search_coarse(request)
    service.provider = Provider()
    result = search_candidates(_scope(), service=service, on_progress=phases.append)
    assert phases == (["PREPARING", "SEARCHING"] if failed else ["PREPARING", "SEARCHING", "ORGANIZING"])
    assert (result.analysis_run.outcome == RunOutcome.FAILED) == failed
