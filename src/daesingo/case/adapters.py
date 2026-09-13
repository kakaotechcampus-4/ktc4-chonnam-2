"""Mock Fixture 기반 upstream adapter — recording/search/readout/evidence가 아직 코드가
없는 상태에서 case를 독립적으로 실행·테스트하기 위한 stand-in이다.

`data/mock/<module>/scenario_<id>.json`을 Canonical Contract 모양 그대로 읽어서 돌려준다.
여기서 하는 일은 오직 "파일을 읽어서 그대로 넘기는 것"뿐 — evidence의 판정 로직이나
readout의 OCR 판단을 이 어댑터가 재구현하지 않는다(그건 각 모듈 Owner의 책임).

나중에 실제 모듈이 구현되면, 이 클래스와 같은 메서드 시그니처를 갖는 실제 HTTP/함수
호출 어댑터로 교체하면 된다 — case의 domain/view 코드는 이 인터페이스에만 의존한다.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MockFixtureAdapter:
    def __init__(self, mock_root: Path, scenario_id: str) -> None:
        self.mock_root = Path(mock_root)
        self.scenario_id = scenario_id
        self._cache: dict[str, dict[str, Any]] = {}

    def _load(self, module: str) -> dict[str, Any]:
        if module not in self._cache:
            path = self.mock_root / module / f"scenario_{self.scenario_id}.json"
            with open(path, encoding="utf-8") as fh:
                self._cache[module] = json.load(fh)
        return self._cache[module]

    # ── search ──────────────────────────────────────────────────────────
    def get_candidate_events(self) -> list[dict[str, Any]]:
        """`AnalysisRun.operation == CANDIDATE_SEARCH`가 만든 `CandidateEvent`만 반환한다
        (`VISUAL_VERIFY`/Fine run은 후보를 만들지 않는다 — module-architecture.md §4-모듈2)."""
        search = self._load("search")
        candidates: list[dict[str, Any]] = []
        for entry in search.get("analysis_run_candidate_events", []):
            if entry["analysis_run"]["operation"] == "CANDIDATE_SEARCH":
                candidates.extend(entry.get("candidates", []))
        return candidates

    # ── evidence ────────────────────────────────────────────────────────
    def get_evidence_record(self) -> dict[str, Any] | None:
        records = self._load("evidence").get("evidence_records", [])
        return records[0] if records else None

    def get_requirement_report(self, scope: str) -> dict[str, Any] | None:
        reports = self._load("evidence").get("requirement_reports", [])
        return next((r for r in reports if r["scope"] == scope), None)

    def get_report_package(self) -> dict[str, Any] | None:
        packages = self._load("evidence").get("report_packages", [])
        return packages[0] if packages else None
