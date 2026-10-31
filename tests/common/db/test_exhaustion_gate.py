"""New outbox boundaries must be mandatory, including metadata evidence."""
from copy import deepcopy
import pytest
from exhaustion_acceptance import EXHAUSTION_CHECKS, EXHAUSTION_PARAMETERS
from tests.common.db.test_mysql_gate import checker, good_report


@pytest.mark.parametrize('identity', EXHAUSTION_PARAMETERS)
@pytest.mark.parametrize('mutation', ('role','scenario','parameter','all_metadata','skip','xfail'))
def test_exhaustion_evidence_is_mandatory(identity, mutation):
    report = good_report()
    target = dict(zip(('role','scenario','parameter'),identity))
    item, = (n for n in report['collected'] if target in n.get('checks',[]))
    if mutation in ('skip','xfail'):
        phase, = (p for p in report['reports'] if p['nodeid']==item['nodeid'] and p['when']=='call')
        if mutation=='skip': phase['outcome']='skipped'
        else: phase['xfail']=True
    elif mutation=='all_metadata':
        item['checks']=[]
    else:
        for c in item['checks']:
            c.pop(mutation,None)
    with pytest.raises(ValueError):
        checker().validate_report(report)


@pytest.mark.parametrize('role,scenario', EXHAUSTION_CHECKS)
def test_exhaustion_family_cannot_be_omitted(role, scenario):
    report = good_report()
    for node in report['collected']:
        node['checks'] = [c for c in node.get('checks',[]) if (c['role'],c['scenario']) != (role,scenario)]
    with pytest.raises(ValueError):
        checker().validate_report(report)
