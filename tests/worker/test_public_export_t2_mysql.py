"""Mandatory actual Case/receipt/enqueue MySQL regression; no provider."""
import pytest
from public_export_t2_support import scenario
from test_public_mysql import public_db  # noqa: F401

pytestmark = pytest.mark.mysql


@pytest.mark.mysql_check('public_a1', 'export_deferral')
@pytest.mark.parametrize('mode', [pytest.param(mode, marks=pytest.mark.mysql_check('public_a1', 'export_deferral', parameter=mode))
    for mode in ('capacity', 'repeat', 'stop')])
def test_terminal_settlement_and_refused_exports_are_separate(public_db, tmp_path, monkeypatch, mode):  # noqa: F811
    engine, _ = public_db
    scenario(engine, tmp_path, monkeypatch, mode)
