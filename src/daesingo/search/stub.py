"""search 공개 함수의 fixture 기반 가짜 구현(stub).

1차 Mock E2E 통합용이다. 실제 AI/Search 성능을 증명하지 않는다 — 목적은 case·eval이
search의 출력을 계약 형식대로 바로 연결할 수 있게 하는 것이다(`docs/modules/search/
first-integration-checklist.md` F/G절).

값은 코드가 아니라 `data/mock/search/`의 fixture가 소유한다. 함수는 입력을 보고 해당
fixture를 찾아 반환한다. fixture가 바뀌면 이 코드를 고치지 않아도 자동으로 따라간다.

실제 구현이 생기면 이 파일을 대체한다. `__init__`이 노출하는 공개 함수 이름·시그니처는
그대로 유지한다(Consumer는 내부가 fixture인지 실제 구현인지 몰라야 한다).
"""

import json
from pathlib import Path

# repo 루트 기준 fixture 디렉터리. stub.py → search → daesingo → src → repo 루트(parents[3]).
MOCK_DIR = Path(__file__).resolve().parents[3] / "data" / "mock" / "search"


def _load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _scenario_suffix(filename):
    # "analysis_run.happy_001.json" -> "happy_001"
    return filename.split(".", 1)[1].rsplit(".", 1)[0]


def search_candidates(scope, mock_dir=MOCK_DIR):
    """Candidate Search 공개 함수.

    입력: `AnalysisScope` (contract-analysis-scope.md) — dict.
    출력: `{"analysis_run": AnalysisRun, "candidates": CandidateEvent[]}`
          (contract-analysis-run-candidate-event.md §2 serialization) — dict.

    scope_id로 해당 시나리오의 AnalysisRun/CandidateEvent fixture를 찾아 합쳐 반환한다.
    """
    scope_id = scope["scope_id"]
    for run_path in sorted(Path(mock_dir).glob("analysis_run.*.json")):
        run = _load_json(run_path)
        if run.get("input_ref", {}).get("ref") == scope_id:
            suffix = _scenario_suffix(run_path.name)
            candidates = _load_json(Path(mock_dir) / f"candidate_events.{suffix}.json")
            return {"analysis_run": run, "candidates": candidates}
    raise ValueError(f"scope_id={scope_id!r}에 해당하는 AnalysisRun fixture가 없다")


def verify_visual(input_ref, target_hint=None, mock_dir=MOCK_DIR):
    """Fine / Classification visual verification 공개 함수.

    입력: `input_ref` (opaque str) — 실제 Fine 입력 참조. `target_hint`는 optional soft hint.
    출력: `VisualEvidence` (contract-visual-evidence.md §2) — dict.

    input_ref와 일치하는 VisualEvidence fixture를 찾아 반환한다. target_hint는 이 stub에서는
    사용하지 않는다(시그니처 유지용) — 실제 구현이 association 보조에 쓴다.
    """
    for ve_path in sorted(Path(mock_dir).glob("visual_evidence.*.json")):
        ve = _load_json(ve_path)
        if ve.get("input_ref") == input_ref:
            return ve
    raise ValueError(f"input_ref={input_ref!r}에 해당하는 VisualEvidence fixture가 없다")
