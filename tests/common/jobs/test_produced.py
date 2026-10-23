"""Opaque payload preparation; no module-specific interpretation."""

from importlib import import_module
import math

import pytest


def storage():
    return import_module("daesingo.common.jobs.produced")


def test_stable_refs_and_detached_json_snapshot():
    m = storage()
    payload = {"candidate_id": "후보", "nested": [1, None, True, {"value": "é"}]}
    obj = m.ProducedObject(kind="unknown/v1", payload=payload)
    first = m.prepare_objects("exec_1", (obj, obj))
    payload["nested"].append("mutated")
    assert [r.reference.ref for r in first] == ["runtime:exec_1:0", "runtime:exec_1:1"]
    assert first == m.prepare_objects("exec_1", (obj, obj))
    assert first[0].payload == {"candidate_id": "후보", "nested": [1, None, True, {"value": "é"}]}
    assert first[0].reference.ref != m.prepare_objects("exec_2", (obj,))[0].reference.ref


def test_explicit_ref_is_not_inferred_from_payload_and_payload_is_not_modified():
    m = storage()
    payload = {"id": "module-id", "status": "whatever", "contract": "unknown"}
    obj = m.ProducedObject(kind="kind", ref="module-id", payload=payload)
    item, = m.prepare_objects("exec_1", (obj,))
    assert item.reference.model_dump() == {"kind": "kind", "ref": "module-id"}
    assert item.payload == payload
    assert m.prepare_objects("exec_1", (m.ProducedObject(kind="kind", payload=payload),))[0].reference.ref == "runtime:exec_1:0"


@pytest.mark.parametrize("payload", [None, [], {"x": math.nan}, {"x": math.inf}, {"x": (1, 2)}, {1: "value"}, {"x": object()}])
def test_non_json_payload_rejected_without_echo(payload):
    m = storage()
    with pytest.raises(ValueError, match="invalid produced"):
        m.ProducedObject(kind="kind", payload=payload)


def test_handler_snapshot_retains_payloads_and_rejects_tampering():
    from daesingo.common.jobs.execution import HandlerResult, validated_terminal
    m = storage()
    result = HandlerResult(objects=(m.ProducedObject(kind="kind", payload={"x": [1]}),))
    snapshot = validated_terminal(result)
    result.objects[0].payload["x"].append(2)
    assert snapshot.objects[0].payload == {"x": [1]}
    invalid = snapshot.model_copy(update={"objects": (object(),)})
    with pytest.raises(ValueError, match="invalid handler"):
        validated_terminal(invalid)


@pytest.mark.parametrize("mode", ["missing_ref", "extra", "list", "subclass"])
def test_nested_object_corruption_cannot_silently_change_terminal_identity(mode):
    from daesingo.common.jobs.execution import HandlerResult, validated_terminal
    m = storage()
    obj = m.ProducedObject(kind="kind", ref="module-id", payload={"v": 1})
    if mode == "subclass":
        class ExtraObject(m.ProducedObject):
            extra: str = "value"
        obj = ExtraObject(kind="kind", ref="module-id", payload={"v": 1})
    result = HandlerResult(objects=(obj,))
    if mode == "missing_ref":
        del obj.__dict__["ref"]
    elif mode == "extra":
        obj.__dict__["claim_token"] = "secret"
    elif mode == "list":
        result = result.model_copy(update={"objects": [obj]})
    with pytest.raises(ValueError, match="invalid handler terminal result"):
        validated_terminal(result, execution_id="exec")
