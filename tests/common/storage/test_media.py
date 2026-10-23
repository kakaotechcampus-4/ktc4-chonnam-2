"""Existing materializer constructor injection and close/cancellation scope."""
from importlib import import_module
import os
from pathlib import Path
import tempfile

import pytest
from test_cleanup import NOW, scanner


@pytest.mark.parametrize('outcome', ['success', 'exception', 'cancel'])
def test_materializer_receives_explicit_root_and_live_lease_until_finally(tmp_path, outcome):
    try:
        module = import_module('daesingo.common.storage.media')
    except ModuleNotFoundError:
        pytest.fail('Runtime temp_root injection and active scope missing')
    cleaner = scanner(tmp_path, kind='temp')
    class Cancel(BaseException):
        pass
    class Producer:
        def __init__(self, *, temp_root):
            self.root = temp_root
        def materialize(self):
            assert self.root == tmp_path
            with tempfile.TemporaryDirectory(prefix='recording-analysis-', dir=self.root) as work:
                path = Path(work)/'partial'
                path.write_bytes(b'abc')
                for p in (path, Path(work)):
                    os.utime(p, (NOW-4000, NOW-4000))
                assert cleaner.scan().count == 0
                assert path.read_bytes() == b'abc'
                if outcome == 'exception':
                    raise ValueError('PRIVATE')
                if outcome == 'cancel':
                    raise Cancel()
                return b'abc'
    producer = module.MediaRoot(cleaner).materializer(Producer)
    if outcome == 'success':
        assert producer.materialize() == b'abc'
    else:
        with pytest.raises(ValueError if outcome == 'exception' else Cancel):
            producer.materialize()
    assert not list(tmp_path.glob('recording-*'))
    assert cleaner.scan().count == 0
