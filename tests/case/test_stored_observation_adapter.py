"""`StoredObservationAdapter` — 저장된 관찰 결과로 CaseView 입력을 만든다(8-6 2단계 · 8-13,
`decisions/observation-storage.md` §3 · §4-3, `decisions/incident-clip-observation-input.md` §4-7).

동기 fixture 경로(`observe_fixture_candidate`, happy_001)가 만든 관찰 결과를 가짜 결과 저장소(`ProducedReader`) ·
가짜 recording에 넣고, stored adapter가 같은 관찰로 같은 evidence를 조립하는지 대조한다. 관찰 job은
`observation_inputs`(후보 · 세대 · clip ref)로 고르고, recording 사실은 case가 아는 source asset ref로 읽는다(8-13).
"""
from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from daesingo import search as search_module
from daesingo.case import jobs, observation, real_e2e, service
from daesingo.case.adapters import MockFixtureAdapter
from daesingo.case.domain import CaseAggregate
from daesingo.case.service import candidates_from_events
from daesingo.case.store import CaseStore
from daesingo.case.stored_observation import StoredObservationAdapter, stored_adapter_factory

MOCK_ROOT = Path(__file__).resolve().parents[2] / "data" / "mock"
CASE_ID = "case_stored"
CONN = object()


@pytest.fixture(scope="module")
def fixture_observation() -> tuple[dict[str, Any], real_e2e.ObservationBundle]:
    scope = search_module.AnalysisScope.model_validate(MockFixtureAdapter(MOCK_ROOT, "happy_001").get_analysis_scopes()[0])
    candidate = search_module.search_candidates(scope).candidates[0]
    obs = real_e2e.observe_fixture_candidate(case_id=CASE_ID, candidate=candidate, scope=scope, mock_root=MOCK_ROOT)
    return candidate.model_dump(mode="json"), obs


class FakeResults:
    """결과 저장소 + read port 대역 — job마다 실행 상태와 결과 내용을 둔다."""

    def __init__(self) -> None:
        self.status: dict[str, str] = {}
        self.content: dict[str, dict[str, Any]] = {}
        self.conns: list[Any] = []

    def put(self, job: dict[str, Any], content: dict[str, Any] | None, status: str = "SUCCEEDED") -> None:
        self.status[job["job_id"]] = status
        if content is not None:
            self.content[job["job_id"]] = content

    def executions(self, conn: Any, job_ids: list[str]) -> list[dict[str, Any]]:
        self.conns.append(conn)
        return [
            {
                "job_id": job_id,
                "attempt": 1,
                "status": self.status[job_id],
                "produced": [{"kind": "result", "ref": job_id}] if job_id in self.content else [],
            }
            for job_id in job_ids
            if job_id in self.status
        ]

    def reader(self, conn: Any, kind: str, produced: tuple) -> dict[str, Any]:
        self.conns.append(conn)
        (ref,) = produced
        return self.content[ref["ref"]]


class FakeRecording:
    def __init__(self, obs: real_e2e.ObservationBundle) -> None:
        self.obs = obs
        self.calls: list[tuple[str, Any]] = []

    def get_incident_clip(self, incident_clip_ref: str) -> dict[str, Any]:
        self.calls.append(("clip", incident_clip_ref))
        assert incident_clip_ref == self.obs.incident_clip["incident_clip_ref"]
        return self.obs.incident_clip

    def get_time_source_candidates(self, source_asset_ref: str) -> list[dict[str, Any]]:
        self.calls.append(("time", source_asset_ref))
        return self.obs.time_source_candidates

    def list_case_asset_facts(self, case_id: str) -> list[dict[str, Any]]:
        self.calls.append(("assets", case_id))
        # 다른 clip의 파생 asset은 lineage로 걸러져야 한다.
        other = {**self.obs.asset_facts[-1], "asset_ref": {"kind": "derived_asset", "ref": "da_other"},
                 "lineage": [{"kind": "incident_clip", "ref": "clip_other"}]}
        return [*self.obs.asset_facts, other]


class Chain:
    """case를 관찰 체인의 각 단계까지 진행시킨다 — 발주는 `observation` 함수, 정산은 T2와 같은 `settle_job`."""

    def __init__(self, candidate_event: dict[str, Any], obs: real_e2e.ObservationBundle) -> None:
        self.obs = obs
        self.results = FakeResults()
        self.case = CaseAggregate(case_id=CASE_ID, stage="SEARCHING")
        self.case.sources = [{"source_asset_ref": "sa_h001_front", "video_stream_ref": "ms_front", "duration_sec": 600.0},
                             {"source_asset_ref": "sa_unrelated", "video_stream_ref": "ms_x", "duration_sec": 10.0}]
        self.coarse = jobs.issue_coarse_search(self.case, scope_ref="scope_h001", input_fingerprint="sha256:coarse")
        other = {**candidate_event, "candidate_id": "candidate_other", "rank": 2}
        self.case.receive_candidates(candidates_from_events([candidate_event, other]), job_id=self.coarse["job_id"])
        self.results.put(self.coarse, {"outcome": "SUCCEEDED", "candidate_events": [candidate_event, other]})
        self.case.select_top_ranked()
        self.fine = observation.issue_fine_for_selected(self.case)
        self.clip = self.plate = self.overlay = None

    def fine_done(self, verification: str | None = None) -> "Chain":
        visual = dict(self.obs.visual_evidence)
        if verification is not None:
            # 계약: `visual_event_type`은 `OBSERVED`일 때만 있다.
            visual["verification"] = verification
            if verification != "OBSERVED":
                visual["visual_event_type"] = None
        self.case.settle_job(self.fine["job_id"], "REFLECTED")
        self.results.put(self.fine, {"analysis_run": self.obs.fine_run, "visual_evidence": visual})
        self.clip = observation.follow_fine(self.case, self.fine["job_id"], visual)
        return self

    def clip_done(self) -> "Chain":
        clip_ref = self.obs.incident_clip["incident_clip_ref"]
        self.case.settle_job(self.clip["job_id"], "REFLECTED")
        self.results.put(self.clip, {"incident_clip_ref": clip_ref})
        self.plate, self.overlay = observation.follow_clip(self.case, self.clip["job_id"], clip_ref)
        return self

    def readouts_done(self, *, plate_status: str = "SUCCEEDED") -> "Chain":
        for job in (self.plate, self.overlay):
            self.case.settle_job(job["job_id"], "REFLECTED")
        if plate_status == "SUCCEEDED":
            self.results.put(self.plate, {"readout_run": {"outcome": self.obs.plate_read_outcome},
                                          "plate_readout": self.obs.plate_readout})
        else:
            self.results.put(self.plate, None, status=plate_status)
        self.results.put(self.overlay, {"readout_run": {"outcome": "SUCCEEDED"},
                                        "overlay_time_readout": self.obs.overlay_readout})
        return self

    def adapter(self, recording: FakeRecording | None = None) -> StoredObservationAdapter:
        self.recording = recording or FakeRecording(self.obs)
        factory = stored_adapter_factory(reader=self.results.reader, executions=self.results.executions,
                                         recording=self.recording)
        return factory(self.case, CONN)


@pytest.fixture
def chain(fixture_observation) -> Chain:
    candidate_event, obs = fixture_observation
    return Chain(candidate_event, obs)


# ── 끝까지 관찰된 후보 ────────────────────────────────────────────────────


def test_completed_chain_assembles_the_same_evidence_as_the_sync_path(chain):
    adapter = chain.fine_done().clip_done().readouts_done().adapter()
    expected = real_e2e.assemble_evidence_bundle(chain.obs, case_id=CASE_ID, selection_rev=chain.case.selection_rev)

    assert adapter.get_visual_evidence_decision() == expected.disposition.decision
    assert adapter.get_evidence_record() == expected.evidence_record
    assert adapter.get_plate_readouts() == [chain.obs.plate_readout]
    assert adapter.get_overlay_time_readouts() == [chain.obs.overlay_readout]
    assert adapter.get_plate_read_status() is None
    assert adapter.get_evidence_needs() == [expected.evidence_needs]


def test_recording_facts_are_read_by_case_known_source_and_clip_lineage(chain):
    adapter = chain.fine_done().clip_done().readouts_done().adapter()
    adapter.get_evidence_record()

    # 8-13: time source는 clip이 걸친 원본 중 case가 등록한 source asset ref로 recording에서 읽는다.
    assert ("time", "sa_h001_front") in chain.recording.calls
    assert ("time", "sa_unrelated") not in chain.recording.calls
    assert ("clip", chain.obs.incident_clip["incident_clip_ref"]) in chain.recording.calls
    assert ("assets", CASE_ID) in chain.recording.calls


class PerSourceTimeRecording(FakeRecording):
    """원본마다 다른 시계를 돌려준다."""

    def __init__(self, obs: real_e2e.ObservationBundle, clocks: dict[str, list[dict[str, Any]]]) -> None:
        super().__init__(obs)
        self.clocks = clocks

    def get_time_source_candidates(self, source_asset_ref: str) -> list[dict[str, Any]]:
        self.calls.append(("time", source_asset_ref))
        return self.clocks[source_asset_ref]


def test_clip_across_sources_is_timed_by_the_source_holding_the_moment(fixture_observation):
    # PR #458 리뷰: 원본을 이어 붙이면 timeline 위치를 원본 시각에 그대로 더할 수 없다. 앞 원본(timeline 0~310초)
    # 뒤에 50초 끊긴 다음 원본(18:06:00 녹화 시작)을 이었고, 사건(timeline 312.48초)은 다음 원본 안 2.48초다.
    candidate_event, obs = fixture_observation
    front, nxt = obs.time_source_candidates[0], {
        **obs.time_source_candidates[0], "candidate_id": "tsc_h001_next_filename", "value": "2026-08-24T18:06:00+09:00",
        "applies_to": {"source_asset_ref": "sa_h001_next", "source_offset_sec": 0.0}}
    provenance = obs.incident_clip["source_provenance"]
    (whole,) = provenance["asset_spans"]
    clip = {**obs.incident_clip, "source_provenance": {**provenance, "asset_spans": [
        {**whole, "timeline_range": {"start_sec": 300.0, "end_sec": 310.0}, "source_range": {"start_sec": 300.0, "end_sec": 310.0}},
        {**whole, "sequence": 1, "source_asset_ref": "sa_h001_next", "media_stream_ref": "ms_h001_next_v",
         "timeline_range": {"start_sec": 310.0, "end_sec": 420.0}, "source_range": {"start_sec": 0.0, "end_sec": 110.0}},
    ]}}
    # 화면 시각이 없어야 원본 시각 + 위치로 계산한다.
    multi = dataclasses.replace(obs, incident_clip=clip, overlay_readout=None, time_source_candidates=[front, nxt])
    chain = Chain(candidate_event, multi)
    chain.case.sources.append({"source_asset_ref": "sa_h001_next", "video_stream_ref": "ms_h001_next_v", "duration_sec": 110.0})
    recording = PerSourceTimeRecording(multi, {"sa_h001_front": [front], "sa_h001_next": [nxt]})

    record = chain.fine_done().clip_done().readouts_done().adapter(recording).get_evidence_record()

    assert record["occurred_at"]["value"] == "2026-08-24T18:06:02.480000+09:00"
    assert record["occurred_at"]["resolution_status"] == "NEEDS_REVIEW"
    assert {("time", "sa_h001_front"), ("time", "sa_h001_next")} <= set(recording.calls)


def test_reader_and_read_port_share_the_callers_connection(chain):
    chain.fine_done().clip_done().readouts_done().adapter().get_evidence_record()

    assert chain.results.conns and all(conn is CONN for conn in chain.results.conns)


# ── 아직 끝나지 않은 체인 ─────────────────────────────────────────────────


def test_before_fine_result_there_is_nothing_to_show(chain):
    adapter = chain.adapter()

    assert adapter.get_visual_evidence_decision() is None
    assert adapter.get_evidence_record() is None
    assert chain.recording.calls == []


def test_not_observed_fine_is_not_assembled_and_reads_no_recording(chain):
    adapter = chain.fine_done("NOT_OBSERVED").adapter()

    assert adapter.get_visual_evidence_decision() == "NOT_ASSEMBLED"
    assert adapter.get_evidence_record() is None
    assert chain.recording.calls == []


def test_observed_fine_waits_for_both_readouts_before_assembling(chain):
    adapter = chain.fine_done().clip_done().adapter()

    # 판독 중에 번호판 · 시각이 빠진 evidence를 먼저 보이지 않는다.
    assert adapter.get_visual_evidence_decision() is None
    assert adapter.get_evidence_record() is None


def test_failed_plate_read_is_reported_and_evidence_is_assembled_without_plate(chain):
    adapter = chain.fine_done().clip_done().readouts_done(plate_status="FAILED").adapter()

    assert adapter.get_plate_read_status() == "FAILED"
    assert adapter.get_plate_readouts() == []
    assert adapter.get_evidence_record() is not None


# ── 선택 · 세대 ─────────────────────────────────────────────────────────


def test_other_selected_candidate_does_not_see_previous_candidates_observations(chain):
    chain.fine_done().clip_done().readouts_done()
    chain.case.stage = "EVIDENCE_REVIEW"
    chain.case.reselect_candidate("candidate_other")

    adapter = chain.adapter()

    assert adapter.get_visual_evidence_decision() is None
    assert adapter.get_evidence_record() is None


def test_no_selected_candidate_has_no_downstream_values(chain):
    for c in chain.case.candidates:
        c.selected = False

    adapter = chain.adapter()

    assert adapter.get_evidence_record() is None
    assert adapter.get_plate_readouts() == []


# ── 진입점에서 ───────────────────────────────────────────────────────────


def test_get_view_reads_through_the_stored_factory(chain):
    chain.fine_done().clip_done().readouts_done()
    chain.case.stage = "EVIDENCE_REVIEW"
    recording = FakeRecording(chain.obs)
    store = CaseStore(
        conn=CONN,
        executions=chain.results.executions,
        adapter_factory=stored_adapter_factory(reader=chain.results.reader, executions=chain.results.executions,
                                               recording=recording),
    )
    store.repository.insert(CONN, chain.case)

    view = service.get_view(CASE_ID, store=store)

    expected = real_e2e.assemble_evidence_bundle(chain.obs, case_id=CASE_ID, selection_rev=chain.case.selection_rev)
    assert view["evidence"]["record_id"] == expected.evidence_record["record_ref"]["ref"]
    assert view["evidence"]["plate_display"]["value"] is not None
    # Worker 경로에서도 번호판 확인 장면은 판독 근거 best frame이다 — 사건 썸네일(`preview_ref`)이 아니다(#47 · #446).
    assert view["evidence"]["plate_preview_ref"] == chain.obs.plate_readout["best_frame"]["frame_ref"]
    assert view["evidence"]["plate_preview_ref"] is not None
