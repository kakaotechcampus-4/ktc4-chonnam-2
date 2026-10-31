"""RT-12(b) approved distribution semantics, independent of any DB adapter."""
from importlib import import_module, util

import pytest


def metrics():
    assert util.find_spec('daesingo.common.jobs.metrics'), 'RT-12(b) metrics missing'
    return import_module('daesingo.common.jobs.metrics')


def test_query_requires_caller_transaction_before_any_io():
    class Connection:
        def in_transaction(self): return False
        def execute(self, *args): raise AssertionError('unexpected I/O')
    with pytest.raises(ValueError, match='transaction'):
        metrics().read_metrics(Connection())


@pytest.mark.parametrize('cap', [-1, True, 1.5, '1'])
def test_invalid_retry_cap_cannot_silently_change_counts(cap):
    with pytest.raises(ValueError, match='retry'):
        metrics().read_metrics(None, retry_max=cap)
