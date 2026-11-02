"""Lossless prepared-model JSON within MySQL's native JSON column.

Only the repository's two prepared-media kinds use this internal representation.
The inner JSON string keeps the original numeric spelling out of MySQL's numeric
parser; public models and immutable model comparisons continue to use numbers.
"""
import json
import math

_MARKER = '__recording_prepared_metadata__'


def encode_prepared_payload(payload):
    return {_MARKER: {'version': 1, 'json': json.dumps(payload, separators=(',', ':'), allow_nan=False)}}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _number(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError
    return value


def _non_json_constant(_text):
    raise ValueError


def decode_prepared_payload(payload):
    if isinstance(payload, dict) and _MARKER not in payload:
        return payload  # Legacy native JSON, with no repair or rewriting.
    try:
        if not isinstance(payload, dict) or set(payload) != {_MARKER}:
            raise ValueError
        body = payload[_MARKER]
        if (not isinstance(body, dict) or set(body) != {'version', 'json'}
                or type(body['version']) is not int or body['version'] != 1
                or not isinstance(body['json'], str)):
            raise ValueError
        restored = json.loads(body['json'], object_pairs_hook=_object,
                              parse_float=_number, parse_constant=_non_json_constant)
        if not isinstance(restored, dict):
            raise ValueError
        return restored
    except (ValueError, TypeError, RecursionError):
        raise ValueError('invalid recording prepared metadata') from None
