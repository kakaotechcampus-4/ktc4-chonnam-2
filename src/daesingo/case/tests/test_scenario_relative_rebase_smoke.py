"""`scenario_relative_rebase_001`(absolute anchor가 없는 영상 — `TIMELINE_RELATIVE` 좌표만
있는 candidate가, timeline이 rebase된 뒤 stale로 표시됨) — §11 제외 범위였던 시나리오를
`build_case_view()` 공개 API로 두 revision 모두 fixture와 바이트 단위로 비교한다.

이 시나리오로 새로 확인/추가한 것:
  - `progress`가 `CANDIDATE_REVIEW`면 후보가 0개든 아니든(심지어 `selected:true`인 후보가
    있어도) `file_intake`/`coarse_search`/`candidate_review` 3개로 truncate된다 —
    `scenario_empty_001`(후보 0개)만의 특수 규칙이 아니라 `CANDIDATE_REVIEW` 단계 자체의
    일반 규칙이었다(2026-09-14 정정, `view.py::_build_progress()` 조건을 넓혔다). 이
    fixture는 `candidates[0].selected:true`인데도 `stage`가 `EVIDENCE_REVIEW`로 전이하지
    않는다 — `select_candidate()`(항상 stage를 전이시킨다)를 호출하지 않고
    `Candidate(selected=True, ...)`를 직접 `receive_candidates()`에 넘겨서 재현한다(화면에
    "이 후보가 선택돼 보인다"는 것과 "stage 전이가 실제로 일어났다"는 건 별개).
  - `candidates[].stale_revision`/`stale_revision_label_key`는 candidate 생성 시점에 고정된
    값이 아니라 매 투영 시점에 다시 계산하는 파생값이다(`candidate-stale-revision-
    display.md` 결정문) — `view.py::_build_candidates_view()`가 새 `current_timeline_revision`
    파라미터로 `candidate.timeline_revision`과 비교해서 계산하도록 고쳤다. rev1(rebase 전,
    `current_timeline_revision=1`)은 `stale_revision:false`, rev2(rebase 후,
    `current_timeline_revision=2`)는 `stale_revision:true`+
    `stale_revision_label_key:"candidate.stale_timeline_revision"`.
  - `case_rev`가 job 발주·correction·mark_reviewed 없이 오르는 지점(rev1→rev2)이 하나 더
    있다: recording이 timeline을 rebase했다는 소식(추가 파일 합류로 `manifest_summary`가
    바뀐 것과 동시)이 case에 보고되는 것도 `bump_revision()`의 일반 정의 안에 들어간다 —
    `scenario_infra_failure_001`의 job 실패 보고와 같은 패턴.

⚠️ 이 fixture도 `scenario_infra_failure_001`처럼 search 단계의 case_rev 흐름을 2026-09-14
정정(`receive_candidates()`는 빈 배열이어도 항상 bump)대로 온전히 재생하면 뒤가 안 맞는다 —
`job_records`에 `COARSE_SEARCH` 1건(`case_rev:1`)만 있고 rev1의 `case_rev`도 1인데,
`receive_candidates()`를 실제로 호출하면 그 시점에 이미 2로 오른다. 그래서 이 테스트도
domain 메서드로 재생하지 않고 fixture가 전제하는 시작 상태(CANDIDATE_REVIEW, case_rev:1,
candidate 1개 `selected:true`)를 `CaseAggregate`에 직접 구성한다 — case가 만든 게 아닌
사전조건 격차로 보고 여기서 다시 만들지 않는다.
"""
import json
from pathlib import Path

from daesingo.case.domain import Candidate, CaseAggregate
from daesingo.case.view import build_case_view

MOCK_ROOT = Path(__file__).resolve().parents[4] / "data" / "mock"
SCENARIO_ID = "relative_rebase_001"


def _load_case_fixture() -> dict:
    path = MOCK_ROOT / "case" / f"scenario_{SCENARIO_ID}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_relative_rebase_two_revisions_match_fixture():
    fixture = _load_case_fixture()
    rev1, rev2 = fixture["case_views"]
    assert rev1["stage"] == rev2["stage"] == "CANDIDATE_REVIEW"

    raw = rev1["candidates"][0]
    candidate = Candidate(
        candidate_id=raw["candidate_id"],
        at=raw["at"],
        at_provenance=raw["at_provenance"],
        observed=raw["observed"],
        thumb_ref=raw["thumb_ref"],
        selected=raw["selected"],  # select_candidate()를 호출하지 않고 그대로 선택 상태로 구성
        timeline_revision=raw["timeline_revision"],
    )
    # fixture가 전제하는 search 단계 이후 상태를 직접 구성한다(모듈 docstring 참고).
    case = CaseAggregate(
        case_id="case_rb001",
        case_rev=1,
        stage="CANDIDATE_REVIEW",
        hints=rev1["hints"],
        manifest_summary=rev1["manifest_summary"],
        candidates=[candidate],
    )
    assert case.case_rev == rev1["case_rev"] == 1

    view1 = build_case_view(case, current_timeline_revision=1)
    assert view1["stage"] == rev1["stage"]
    assert view1["case_rev"] == rev1["case_rev"]
    assert view1["progress"] == rev1["progress"]
    assert view1["manifest_summary"] == rev1["manifest_summary"]
    assert view1["candidates"] == rev1["candidates"]
    assert view1["evidence"] is None
    assert view1["running_jobs"] == []
    assert view1["notices"] == rev1["notices"]

    # ── rebase 소식이 case에 보고된다(추가 파일 합류로 manifest_summary도 바뀐다) ──
    case.manifest_summary = rev2["manifest_summary"]
    case.bump_revision()
    assert case.case_rev == rev2["case_rev"] == 2

    view2 = build_case_view(case, current_timeline_revision=2)
    assert view2["stage"] == rev2["stage"]
    assert view2["case_rev"] == rev2["case_rev"]
    assert view2["progress"] == rev2["progress"]
    assert view2["manifest_summary"] == rev2["manifest_summary"]
    assert view2["candidates"] == rev2["candidates"]
    assert view2["candidates"][0]["stale_revision"] is True
    assert view2["candidates"][0]["stale_revision_label_key"] == "candidate.stale_timeline_revision"
    assert view2["evidence"] is None
    assert view2["running_jobs"] == []
    assert view2["notices"] == rev2["notices"]
