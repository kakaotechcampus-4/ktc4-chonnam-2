"""공용 Mock Pack의 readout fixture 로더.

fixture는 `data/mock/readout/<scenario_id>.json` 5개다. 소유는 유소연(Mock Pack)이고
readout은 읽기만 한다 — 이 모듈은 고치지 않는다.
"""
from __future__ import annotations

import json
from pathlib import Path

from .contracts import ReadoutFixture

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = REPO_ROOT / "data" / "mock" / "readout"


def fixture_paths() -> list:
    return sorted(FIXTURE_DIR.glob("*.json"))


def load_raw(path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load(scenario_id: str) -> ReadoutFixture:
    return ReadoutFixture.from_dict(load_raw(FIXTURE_DIR / f"{scenario_id}.json"))


def load_all() -> dict:
    out = {}
    for path in fixture_paths():
        fixture = ReadoutFixture.from_dict(load_raw(path))
        out[fixture.scenario_id] = fixture
    return out
