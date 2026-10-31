"""Public P-6 result must never turn uncertainty or failure into absence."""
import pytest
import daesingo.recording as recording


def test_public_surface_distinguishes_all_three_verdicts_and_propagates_errors():
    assert hasattr(recording, 'PublishRegistration'), 'P-6 public verdict missing'
    status = recording.PublishRegistration
    class Repo:
        result = status.REGISTERED
        def read_publish_registration(self, locator):
            assert locator == 'source/' + 'a' * 32
            if isinstance(self.result, Exception):
                raise self.result
            return self.result
    repo = Repo()
    service = recording.RecordingService(repo)
    for result in (status.REGISTERED, status.UNREGISTERED, status.UNKNOWN):
        repo.result = result
        assert service.read_publish_registration('source/' + 'a' * 32) is result
    repo.result = RuntimeError('private')
    with pytest.raises(RuntimeError):
        service.read_publish_registration('source/' + 'a' * 32)
    repo.result = False
    assert service.read_publish_registration('source/' + 'a' * 32) is status.UNKNOWN


@pytest.mark.parametrize('locator', ['', '../source/' + 'a'*32, '/source/' + 'a'*32,
    'source\\' + 'a'*32, 'source/' + 'A'*32, 'source/short~1', None])
def test_invalid_locator_never_reaches_repository(locator):
    assert hasattr(recording, 'PublishRegistration'), 'P-6 public verdict missing'
    class Repo:
        def read_publish_registration(self, locator):
            pytest.fail('ambiguous locator queried')
    assert recording.RecordingService(Repo()).read_publish_registration(locator) is recording.PublishRegistration.UNKNOWN
