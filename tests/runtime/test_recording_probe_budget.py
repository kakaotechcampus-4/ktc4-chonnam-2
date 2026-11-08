"""긴 실험의 byte/RAM/temp/DB/disk/감독 예산을 함께 검증한다."""
import importlib.util
from pathlib import Path

import pytest


def budget_module():
    path = Path(__file__).parents[2] / 'scripts/recording_probe_budget.py'
    spec = importlib.util.spec_from_file_location('probe_budget', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extended_profile_accounts_for_all_overlapping_resources():
    b = budget_module().ProbeBudget.from_profile('coarse-1200-384m')
    b.validate_experiment(402653184, 1200000, 3000)
    required = b.requirements(402653184, 67108864)
    assert required['temp_candidate_bytes'] == 872415232  # 2*384+64 MiB
    assert required['runner_candidate_bytes'] == 1862270976  # 4*384+240 MiB
    assert required['db_growth_candidate_bytes'] == 1207959552
    assert required['disk_growth_candidate_bytes'] == 2147483648  # 3N+2N+64+64 MiB
    assert b.host_start_bytes == 4089446400  # 2176+512+700+512 MiB
    assert b.host_timeout_sec(3000) == 3030
    value = b.preflight(available_ram=5000000000, c_free=17000000000,
        disk_growth_used=0, db_data=127267169, output_cap=402653184, search_candidate=67108864)
    assert value['status'] == 'PASS'


@pytest.mark.parametrize('changes,code', [
    ({'available_ram': 4089446399}, 'HOST_RAM'),
    ({'c_free': 8589934591}, 'HOST_DISK'),
    ({'disk_growth_used': 1073741825}, 'DISK_GROWTH'),
    ({'db_data': 939524096}, 'DB_DATA'),
    ({'search_candidate': 134217729}, 'TEMP'),
])
def test_preflight_refuses_insufficient_budget_without_reducing_reserves(changes, code):
    b = budget_module().ProbeBudget.from_profile('coarse-1200-384m')
    args = dict(available_ram=5000000000, c_free=17000000000, disk_growth_used=0,
        db_data=127267169, output_cap=402653184, search_candidate=67108864)
    with pytest.raises(ValueError, match=code):
        b.preflight(**{**args, **changes})


@pytest.mark.parametrize('profile,values', [
    ('legacy', (402653184, 1200000, 3000)),
    ('coarse-1200-384m', (402653183, 1200000, 3000)),
    ('coarse-1200-384m', (402653184, 1200000, 1800)),
    ('coarse-1200-384m', (402653184, 720000, 3000)),
])
def test_output_limit_cannot_be_raised_independently_of_coordinated_profile(profile, values):
    with pytest.raises(ValueError, match='BUDGET'):
        budget_module().ProbeBudget.from_profile(profile).validate_experiment(*values)


@pytest.mark.parametrize('value', ['unknown', None, True, {}, float('inf')])
def test_unknown_resource_profile_is_rejected(value):
    with pytest.raises(ValueError, match='BUDGET'):
        budget_module().ProbeBudget.from_profile(value)
