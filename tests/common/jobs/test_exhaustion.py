"""Runtime port validation and minimal surface; no domain taxonomy leakage."""
from dataclasses import fields
from datetime import datetime, timezone
import pytest

from daesingo.common.jobs.exhaustion import JobExhaustionNotice, ExhaustionResult, validated_notice


def notice(**changes):
    return JobExhaustionNotice(**(dict(notice_id='notice', job_id='job', case_id='case',
        kind='HINT_EXTRACT', final_execution_id='exec', attempt=2, exhausted_at=datetime(2026,1,1)) | changes))


@pytest.mark.parametrize('key,value', [
    ('kind','PLATE_READ'), ('terminal_status','FAILED'), ('reason','secret provider response'),
    ('attempt',0), ('attempt',True), ('attempt',1.5),
    ('exhausted_at',None), ('exhausted_at',datetime(2026,1,1,tzinfo=timezone.utc)),
    ('notice_id',''), ('case_id','한글'), ('job_id','j'*192), ('final_execution_id',None),
])
def test_invalid_notice_facts_fail_with_safe_error(key, value):
    with pytest.raises(ValueError, match='^invalid exhaustion notice$'):
        notice(**{key:value})


@pytest.mark.parametrize('changes', [
    {'status':'OTHER'}, {'status':'NO_CHANGE','appended_job_records':[{'job_id':'x','case_id':'case','kind':'COARSE_SEARCH'}]},
    {'status':'APPLIED'}, {'status':'APPLIED','appended_job_records':[{'job_id':'x','case_id':'case','kind':'FINE_VERIFY'}]},
    {'status':'APPLIED','appended_job_records':[{'job_id':'x'}]},
])
def test_invalid_receiver_results_cannot_reach_enqueue(changes):
    with pytest.raises(ValueError, match='^invalid exhaustion result$'):
        ExhaustionResult(**changes)


def test_minimal_surface_excludes_case_reason_and_projects_enqueue_facts():
    assert {f.name for f in fields(ExhaustionResult)} == {'status','appended_job_records'}
    assert {f.name for f in fields(JobExhaustionNotice)} == {
        'notice_id','job_id','case_id','kind','final_execution_id','attempt','terminal_status','reason','exhausted_at'}
    raw = {'job_id':'followup','case_id':'case','kind':'COARSE_SEARCH','input_fingerprint':'private payload'}
    result = ExhaustionResult('APPLIED',[raw])
    raw['job_id']='mutated'
    assert result.appended_job_records == [{'job_id':'followup','case_id':'case','kind':'COARSE_SEARCH'}]
    n=notice()
    object.__setattr__(n,'kind','unsupported')
    with pytest.raises(ValueError):
        validated_notice(n)
