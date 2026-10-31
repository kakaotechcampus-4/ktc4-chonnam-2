"""API/Worker relay the public Evidence requirement into the existing Case port."""

import ast
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest

from daesingo.case.domain import CaseAggregate
from daesingo.case.exports import build_export_requests


@pytest.mark.parametrize("module_name", ["daesingo.api.composition", "daesingo.worker.case_composition"])
def test_composition_uses_public_constraint_and_relays_byte_limit(monkeypatch, tmp_path, module_name):
    module = import_module(module_name)
    calls = []
    limit = 123_457

    def constraint(role):
        calls.append(role)
        return {"max_byte_size": limit, "policy_ref": "policy/test-attachment/v2"}

    monkeypatch.setattr(module, "attachment_constraint", constraint)
    # Construct the real Case store/factory/adapter without opening a database.
    conn = object()
    if module_name == "daesingo.api.composition":
        composition = module.ApiComposition(
            startup=SimpleNamespace(config=SimpleNamespace(media_root=tmp_path)),
            engine=None, ready_engine=None, readiness=None,
        )
        store = composition._store(conn)
    else:
        store = module.stored_case_store(conn, storage_root=tmp_path)
    adapter = store.adapter_for(CaseAggregate.empty("case-constraint"))
    assert calls == ["PLATE_IMAGE"]
    assert adapter._export_max_byte_size == limit
    requests = build_export_requests(
        "clip", {"best_frame": {"frame_ref": "frame", "plate_bbox_xywh": [1, 2, 3, 4]}},
        {"post_stamp": {"needed": False}}, adapter._export_max_byte_size,
    )
    assert requests["PLATE_IMAGE_EXPORT"]["max_byte_size"] == limit


@pytest.mark.parametrize("consumer", ["api", "worker", "case"])
def test_consumers_do_not_import_evidence_policy_catalog(consumer):
    source = Path(__file__).resolve().parents[2] / "src" / "daesingo" / consumer
    for path in source.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert node.module != "daesingo.evidence.policy_catalog", path
                if node.module == "daesingo.evidence":
                    assert all(alias.name != "policy_catalog" for alias in node.names), path
            elif isinstance(node, ast.Import):
                assert all(alias.name != "daesingo.evidence.policy_catalog" for alias in node.names), path
