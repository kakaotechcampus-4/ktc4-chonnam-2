"""Schema validation is exercised against actual formatter/emitter output."""
from importlib import import_module, util
from io import StringIO
import json

import pytest

from daesingo.common.logging import configure_logging, log_event
from daesingo.common.jobs.heartbeat import Heartbeat, HeartbeatObservation, OwnershipFence


def catalog():
    assert util.find_spec('daesingo.common.logging.catalog'), 'RT-12(b) catalog missing'
    return import_module('daesingo.common.logging.catalog')


def test_real_heartbeat_emitter_schema_units_and_numeric_count_status():
    output = StringIO()
    heartbeat = Heartbeat(renew=lambda: 1, fence=OwnershipFence(), interval=10,
        logger=configure_logging('worker', stream=output))
    heartbeat._observe(HeartbeatObservation('RENEWED', 5, 2, 3, 0))
    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert {event['event'] for event in events} == {
        'runtime.heartbeat.attempt_ms', 'runtime.heartbeat.lag_ms',
        'runtime.heartbeat.skipped_tick_count', 'runtime.heartbeat.consecutive_failures'}
    for value in events:
        catalog().validate_event(value)
    assert events[0]['duration_ms'] == 5 and events[2]['status'] == '3'
    for field, value in [('status','PRIVATE'), ('duration_ms',-1)]:
        with pytest.raises(ValueError): catalog().validate_event(dict(events[0], **{field:value}))
    for name in ('status','duration_ms'):
        broken = dict(events[0]); broken.pop(name)
        with pytest.raises(ValueError): catalog().validate_event(broken)


PRIVATE = ('12가3456', '37.123456,127.123456 상세 위치', '/private/user/video.mp4',
           'PRIVATE_VIDEO_FRAME_BYTES', 'PRIVATE_AI_REQUEST_RESPONSE', 'PRIVATE_FREE_TEXT',
           'sk_PRIVATE_API_KEY', 'PRIVATE_ACCESS_TOKEN', 'PRIVATE_SECRET', 'PRIVATE_RAW_PROVIDER')


@pytest.mark.parametrize('payload', PRIVATE)
def test_structured_formatter_never_serializes_raw_message_args_extras_or_exception(payload):
    output = StringIO()
    logger = configure_logging('worker', stream=output)
    try:
        raise RuntimeError(payload)
    except RuntimeError:
        logger.error('%s', payload, exc_info=True, stack_info=True, extra={'private':payload})
    assert payload not in output.getvalue()
    value = json.loads(output.getvalue())
    assert value['event'] == 'log.unstructured'
    assert set(value) == {'timestamp','level','service','event'}


@pytest.mark.parametrize('name', ['plate','gps','video','frame','path','request','response',
                                'text','api_key','access_token','secret','raw_provider_payload'])
def test_event_api_rejects_private_field_names_before_emission(name):
    output = StringIO()
    logger = configure_logging('worker', stream=output)
    with pytest.raises(ValueError):
        log_event(logger, 'runtime.heartbeat.attempt_ms', **{name:PRIVATE})
    assert output.getvalue() == ''


def test_catalog_covers_every_baseline_log_metric_with_explicit_source():
    expected = {
        'runtime.heartbeat.lag_ms','runtime.heartbeat.attempt_ms',
        'runtime.heartbeat.skipped_tick_count','runtime.heartbeat.consecutive_failures',
        'runtime.stale.detect_latency_s','runtime.stale.false_count',
        'runtime.retry.after_case_stopped_count','runtime.cancel.observe_latency_ms',
        'runtime.db.claim_latency_ms','runtime.db.lock_wait_timeout_count',
        'runtime.db.deadlock_count','runtime.db.pool_timeout_count','runtime.db.error_count',
        'runtime.db.tx_retry_count','runtime.reflect.redelivery_count',
        'api.view.request_rate','api.view.latency_ms','api.request.latency_ms',
        'api.request.rejected_413_count','api.upload.bytes','api.upload.duration_ms',
        'api.upload.throughput_bps','api.upload.aborted_count','api.upload.rejected_413_count',
        'api.upload.failures','api.frame.latency_ms','api.frame.wait_ms','api.frame.request_rate',
        'api.asset.download_latency_ms','api.asset.bytes','api.ready.duration_ms','api.ready.unavailable_count'}
    assert set(catalog().METRICS) == expected
    for metric in catalog().METRICS.values():
        assert metric.events and metric.meaning
        assert all(catalog().EVENTS[name].source for name in metric.events)
