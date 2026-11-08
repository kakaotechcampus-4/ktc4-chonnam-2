"""Lossless internal metadata, without numeric tolerance or public Contract changes."""

import importlib
import json
import math

import pytest


def codec():
    return importlib.import_module("daesingo.recording.prepared_metadata")


@pytest.mark.parametrize(
    "number",
    [
        100.00000033333333,
        math.nextafter(100.00000033333333, 0),
        5e-324,
        1.7976931348623157e308,
        -0.0,
    ],
)
def test_numbers_survive_native_json_boundary_as_exact_original_float(number):
    module = codec()
    original = {
        "duration_sec": number,
        "nested": [{"end_sec": number}],
        "revision": 2,
        "text": "한글",
    }
    stored = json.loads(json.dumps(module.encode_prepared_payload(original)))
    restored = module.decode_prepared_payload(stored)
    assert restored == original
    assert restored["duration_sec"].hex() == number.hex()
    assert restored["nested"][0]["end_sec"].hex() == number.hex()
    assert restored["revision"] == 2 and type(restored["revision"]) is int
    assert restored["text"] == "한글"


def test_legacy_dictionary_is_read_without_numeric_repair_or_migration():
    original = {"duration_sec": 100.00000033333332}
    assert codec().decode_prepared_payload(original) is original


@pytest.mark.parametrize("number", [float("inf"), float("-inf"), float("nan")])
def test_non_json_numbers_are_still_refused(number):
    with pytest.raises(ValueError):
        codec().encode_prepared_payload({"duration_sec": number})


@pytest.mark.parametrize(
    "damage",
    [
        "version",
        "bool_version",
        "type",
        "extra_outer",
        "extra_inner",
        "invalid_json",
        "not_model",
        "infinite",
        "overflow",
        "duplicate",
    ],
)
def test_recognized_malformed_encoding_fails_closed(damage):
    module = codec()
    value = module.encode_prepared_payload({"duration_sec": 100.00000033333333})
    marker = next(iter(value))
    body = value[marker]
    if damage == "version":
        body["version"] = 2
    elif damage == "bool_version":
        body["version"] = True
    elif damage == "type":
        body["json"] = 123
    elif damage == "extra_outer":
        value["duration_sec"] = 7
    elif damage == "extra_inner":
        body["other"] = True
    elif damage == "invalid_json":
        body["json"] = "{"
    elif damage == "not_model":
        body["json"] = "[]"
    elif damage == "infinite":
        body["json"] = '{"duration_sec":Infinity}'
    elif damage == "overflow":
        body["json"] = '{"duration_sec":1e400}'
    elif damage == "duplicate":
        body["json"] = '{"duration_sec":1,"duration_sec":2}'
    with pytest.raises(ValueError, match="invalid recording prepared metadata"):
        module.decode_prepared_payload(value)
