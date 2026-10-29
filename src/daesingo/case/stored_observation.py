"""저장된 관찰 결과로 CaseView 입력을 만든다 — 8-6 2단계, `docs/modules/case/decisions/observation-storage.md`.

`StoredObservationAdapter`는 요청마다 만드는 무상태 `ModuleAdapter`다(§4-3). 관찰 job은 발주 때 고정한 입력
(`observation_inputs` — 후보 · 세대 · clip ref)으로 고르고(`incident-clip-observation-input.md` §4-7), 결과 내용은
read port의 `produced` → `ProducedReader`로, recording 사실은 `RecordingFacts` port로 읽어 evidence를 매번
조립한다(§4-2). 원본 asset은 case가 등록받은 `sources`의 ref로 recording에 묻는다(고도화 8-13 — local path를 쓰지 않는다).

## 여기 없는 것

- 객체의 뜻 · 모양. `payload`는 각 모듈 계약 객체 그대로다.
- 실행 상태 · 실패 notice. 객체가 없는 실행(`FAILED`)은 view가 read port로 계산한다(`jobexecution-read-port.md`).
- composition 주입. API · Worker의 `CaseStore(adapter_factory=stored_adapter_factory(...))`는 composition root(Runtime) 몫이다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from daesingo import search as search_module
from daesingo.case import real_e2e
from daesingo.case.domain import CaseAggregate
from daesingo.case.jobs import OBSERVATION_KINDS
from daesingo.case.observation import current_generation_job_id
from daesingo.evidence import NOT_ASSEMBLED, classify_visual_evidence

if TYPE_CHECKING:
    from daesingo.case.reflection import ProducedReader
    from daesingo.case.store import AdapterFactory, ExecutionReader


@dataclass(frozen=True)
class StoredObservation:
    """결과 저장소에서 읽은 관찰 객체 하나 — 그것을 만든 job과 kind를 함께 든다."""

    job_id: str
    kind: str
    payload: dict[str, Any]


def select_current_observations(case: CaseAggregate, observations: list[StoredObservation]) -> dict[str, StoredObservation]:
    """kind → CaseView에 쓸 관찰 객체(§4-4). 선택 후보가 없으면 빈 dict다.

    - 현재 후보 목록 세대의 job만 본다: 가장 나중 `REFLECTED` `COARSE_SEARCH`보다 뒤에 append된 JobRecord.
      재탐색 뒤 같은 `candidate_id`가 다시 나와도 이전 세대 관찰은 쓰지 않는다. 실패로 정산된 탐색도 `REFLECTED`지만
      그때는 후보 목록이 비어 있어(`SEARCHING`) 고를 것이 없다.
    - 그 안에서 객체의 `candidate_id`가 선택 후보와 같은 것만, kind마다 가장 나중 job의 것을 쓴다. 같은 세대 안
      A→B→A면 A의 관찰을 다시 쓰고, 이전 후보의 늦은 결과는 투영되지 않는다(6.6순위 조건 2).

    이 case가 발주하지 않은 job의 객체는 배선 오류(`ValueError`)다."""
    order = {r["job_id"]: i for i, r in enumerate(case.job_records)}
    for observation in observations:
        if observation.job_id not in order:
            raise ValueError(f"이 case가 발주하지 않은 job_id의 관찰: {observation.job_id!r}")
    selected = next((c.candidate_id for c in case.candidates if c.selected), None)
    if selected is None:
        return {}
    searches = [
        order[r["job_id"]]
        for r in case.job_records
        if r["kind"] == "COARSE_SEARCH" and case.settled_jobs.get(r["job_id"]) == "REFLECTED"
    ]
    generation_start = max(searches, default=-1)
    current: dict[str, StoredObservation] = {}
    for observation in sorted(observations, key=lambda o: order[o.job_id]):
        if order[observation.job_id] > generation_start and observation.payload.get("candidate_id") == selected:
            current[observation.kind] = observation
    return current


class RecordingFacts(Protocol):
    """recording 공개 조회 중 CaseView 조립에 쓰는 것 — composition root가 `RecordingService`로 꽂는다. 모양은 각
    recording 계약 객체의 JSON(`IncidentClip` · `TimeSourceCandidate` · `AssetFacts`)이다."""

    def get_incident_clip(self, incident_clip_ref: str) -> dict[str, Any]: ...

    def get_time_source_candidates(self, source_asset_ref: str) -> list[dict[str, Any]]: ...

    def list_case_asset_facts(self, case_id: str) -> list[dict[str, Any]]: ...


def stored_adapter_factory(
    *, reader: ProducedReader, executions: ExecutionReader, recording: RecordingFacts, export_max_byte_size=None
) -> AdapterFactory:
    """`CaseStore(adapter_factory=…)`에 꽂는 factory — 요청마다 호출자 transaction의 `conn`으로 adapter를 만든다."""

    def factory(case: CaseAggregate, conn: Any) -> StoredObservationAdapter:
        return StoredObservationAdapter(case, conn, reader=reader, executions=executions, recording=recording, export_max_byte_size=export_max_byte_size)

    return factory


class StoredObservationAdapter:
    """저장된 관찰 결과 → CaseView 입력. 상태는 이번 요청의 조립 결과 하나뿐이다.

    - 선택 후보 · 현재 세대의 관찰 job만 쓴다(입력의 `candidate_id` · `generation_job_id`). kind마다 가장 나중 job이
      대표다(A§10-7) — Fine은 가장 나중 성공 job, 판독은 가장 나중 정산된 job.
    - Fine이 없거나 `VisualEvidence` 없이 끝났으면 보일 것이 없다. `NOT_OBSERVED`면 조립하지 않는다(recording을 읽지 않는다).
    - 그 밖이면 같은 clip의 `PLATE_READ` · `OVERLAY_TIME_READ`가 둘 다 정산된 뒤에만 조립한다 — 판독 중에 번호판 ·
      시각이 빠진 evidence를 먼저 보이지 않는다. 판독 실패는 결과 없이 `plate_read_outcome=FAILED`로 넘긴다.
    """

    def __init__(
        self,
        case: CaseAggregate,
        conn: Any,
        *,
        reader: ProducedReader,
        executions: ExecutionReader,
        recording: RecordingFacts,
        export_max_byte_size=None,
    ) -> None:
        self._case = case
        self._conn = conn
        self._reader = reader
        self._executions = executions
        self._recording = recording
        self._export_max_byte_size = export_max_byte_size
        self._export_requests = {}
        self._built = False
        self._bundle: real_e2e.EvidenceBundle | None = None

    # ── 조립 ────────────────────────────────────────────────────────────
    def _evidence_bundle(self) -> real_e2e.EvidenceBundle | None:
        if not self._built:
            self._bundle = self._build()
            self._built = True
        return self._bundle

    def _build(self) -> real_e2e.EvidenceBundle | None:
        case = self._case
        selected = next((c.candidate_id for c in case.candidates if c.selected), None)
        generation = current_generation_job_id(case)
        if selected is None or generation is None:
            return None
        jobs = [
            r
            for r in case.job_records
            if r["kind"] in OBSERVATION_KINDS
            and (source := case.observation_inputs.get(r["job_id"])) is not None
            and source["candidate_id"] == selected
            and source["generation_job_id"] == generation
        ]
        executions = self._representatives([generation, *(r["job_id"] for r in jobs)])

        fine = next(
            (r for r in reversed(jobs) if r["kind"] == "FINE_VERIFY" and self._succeeded(executions, r["job_id"])),
            None,
        )
        if fine is None:
            return None
        fine_content = self._read(executions, fine)
        visual_evidence = fine_content["visual_evidence"]
        if visual_evidence is None:
            return None
        disposition = classify_visual_evidence(visual_evidence)
        observations = real_e2e.ObservationBundle(
            candidate=self._candidate_event(executions, generation, selected),
            visual_evidence=visual_evidence,
            fine_run=fine_content["analysis_run"],
            disposition=disposition,
        )
        if disposition.decision != NOT_ASSEMBLED:
            readouts = self._settled_readouts(jobs)
            if readouts is None:
                return None
            observations = self._with_clip_and_readouts(observations, executions, *readouts)
        return real_e2e.assemble_evidence_bundle(
            observations,
            case_id=case.case_id,
            selection_rev=case.selection_rev,
            correction_records=case.correction_records,
            location_hint=case.hints.get("location"),
            situation_response=case.situation_response,
        )

    def _representatives(self, job_ids: list[str]) -> dict[str, dict[str, Any]]:
        """job → 대표 execution(`attempt` 최댓값, A§10-6)."""
        representative: dict[str, dict[str, Any]] = {}
        for execution in self._executions(self._conn, job_ids):
            current = representative.get(execution["job_id"])
            if current is None or execution["attempt"] > current["attempt"]:
                representative[execution["job_id"]] = execution
        return representative

    @staticmethod
    def _succeeded(executions: dict[str, dict[str, Any]], job_id: str) -> bool:
        return executions.get(job_id, {}).get("status") == "SUCCEEDED"

    def _read(self, executions: dict[str, dict[str, Any]], job: dict[str, Any]) -> dict[str, Any]:
        produced = tuple(executions[job["job_id"]]["produced"])
        return self._reader(self._conn, job["kind"], produced)

    def _candidate_event(
        self, executions: dict[str, dict[str, Any]], generation: str, candidate_id: str
    ) -> search_module.CandidateEvent:
        search = next(r for r in self._case.job_records if r["job_id"] == generation)
        events = self._read(executions, search)["candidate_events"]
        event = next((e for e in events if e["candidate_id"] == candidate_id), None)
        if event is None:
            raise ValueError(f"현재 세대 탐색 결과에 선택 후보가 없다: {candidate_id!r} (job_id={generation!r})")
        return search_module.CandidateEvent.model_validate(event)

    def _settled_readouts(self, jobs: list[dict[str, Any]]) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
        """가장 나중 `PLATE_READ`의 clip에 대해 정산된 가장 나중 판독 두 개. 하나라도 아직이면 `None`."""
        latest_plate = next((r for r in reversed(jobs) if r["kind"] == "PLATE_READ"), None)
        if latest_plate is None:
            return None
        clip_ref = self._case.observation_inputs[latest_plate["job_id"]]["incident_clip_ref"]

        def settled(kind: str) -> dict[str, Any] | None:
            return next(
                (
                    r
                    for r in reversed(jobs)
                    if r["kind"] == kind
                    and self._case.observation_inputs[r["job_id"]]["incident_clip_ref"] == clip_ref
                    and self._case.settled_jobs.get(r["job_id"]) == "REFLECTED"
                ),
                None,
            )

        plate, overlay = settled("PLATE_READ"), settled("OVERLAY_TIME_READ")
        if plate is None or overlay is None:
            return None
        return clip_ref, plate, overlay

    def _with_clip_and_readouts(
        self,
        observations: real_e2e.ObservationBundle,
        executions: dict[str, dict[str, Any]],
        clip_ref: str,
        plate_job: dict[str, Any],
        overlay_job: dict[str, Any],
    ) -> real_e2e.ObservationBundle:
        plate_readout, plate_outcome = None, "FAILED"
        if self._succeeded(executions, plate_job["job_id"]):
            content = self._read(executions, plate_job)
            plate_readout, plate_outcome = content["plate_readout"], content["readout_run"]["outcome"]
        overlay_readout = None
        if self._succeeded(executions, overlay_job["job_id"]):
            overlay_readout = self._read(executions, overlay_job)["overlay_time_readout"]
        clip = self._recording.get_incident_clip(clip_ref)
        # 8-13: clip이 걸친 원본 중 case가 등록받은 source asset만, 그 ref로 recording에 묻는다.
        known = {s["source_asset_ref"] for s in self._case.sources}
        spans = clip["source_provenance"]["asset_spans"]
        source_refs = list(dict.fromkeys(s["source_asset_ref"] for s in spans if s["source_asset_ref"] in known))
        time_source_candidates = [c for ref in source_refs for c in self._recording.get_time_source_candidates(ref)]
        asset_facts = real_e2e.select_case_assets(clip_ref, self._recording.list_case_asset_facts(self._case.case_id))
        observation_facts = None
        if self._export_max_byte_size is not None:
            from daesingo.case.exports import build_export_requests, EXPORT_KINDS
            from daesingo.evidence import resolve_time
            resolution = resolve_time(time_source_candidates=time_source_candidates, overlay_time_readout=overlay_readout,
                candidate_event=observations.candidate.model_dump(mode="json"), correction_records=self._case.correction_records,
                case_id=self._case.case_id, selection_rev=self._case.selection_rev,
                resolution_id=f"tr_{self._case.case_id}_001")
            self._export_requests = build_export_requests(clip_ref, plate_readout, resolution, self._export_max_byte_size)
            export_jobs = [r for r in self._case.job_records if r["kind"] in EXPORT_KINDS
                and self._case.export_inputs.get(r["job_id"]) == self._export_requests.get(r["kind"])
                and r["job_id"] in self._case.export_inputs
                and self._case.settled_jobs.get(r["job_id"]) == "REFLECTED"]
            export_executions = self._representatives([r["job_id"] for r in export_jobs])
            chosen = {}
            for job in reversed(export_jobs):
                if job["kind"] not in chosen and self._succeeded(export_executions, job["job_id"]):
                    chosen[job["kind"]] = self._read(export_executions, job)["derived_asset_ref"]
            selected_refs = set(chosen.values())
            asset_facts = [f for f in asset_facts if f.get("derived_role") is None or f["asset_ref"]["ref"] in selected_refs]
            report_ref = chosen.get("REPORT_VIDEO_EXPORT")
            if report_ref:
                report = next((f for f in asset_facts if f["asset_ref"]["ref"] == report_ref), None)
                if report is not None:
                    asset = self._recording.get_derived_asset(report_ref)
                    transform = self._recording.get_export_transform(asset["transform_ref"])
                    if transform["input"] != self._export_requests["REPORT_VIDEO_EXPORT"]:
                        raise ValueError("report transform input mismatch")
                    applied = any(op.get("post_stamp_applied") is True for op in transform["operations"])
                    observation_facts = {"post_stamp_applied": {"value": applied, "subject_refs": [report["asset_ref"]]}}

        return real_e2e.ObservationBundle(
            candidate=observations.candidate,
            visual_evidence=observations.visual_evidence,
            fine_run=observations.fine_run,
            disposition=observations.disposition,
            incident_clip=clip,
            plate_readout=plate_readout,
            overlay_readout=overlay_readout,
            time_source_candidates=time_source_candidates,
            asset_facts=asset_facts,
            observation_facts=observation_facts,
            plate_read_outcome=plate_outcome,
        )

    def get_export_requests(self):
        import copy
        self._evidence_bundle()
        return copy.deepcopy(self._export_requests)

    # ── ModuleAdapter ───────────────────────────────────────────────────
    # 탐색 결과는 Worker T2가 case에 들여오므로(`reflection`) 비동기 경로의 view는 탐색 getter를 쓰지 않는다.
    def get_candidate_events(self) -> list[dict[str, Any]]:
        return []

    def get_candidate_search_outcome(self) -> str | None:
        return None

    def get_analysis_scopes(self) -> list[dict[str, Any]]:
        return list(self._case.analysis_scopes.values())

    def get_evidence_record(self) -> dict[str, Any] | None:
        bundle = self._evidence_bundle()
        return bundle.evidence_record if bundle else None

    def get_evidence_records(self) -> list[dict[str, Any]]:
        record = self.get_evidence_record()
        return [record] if record is not None else []

    def get_requirement_report(self, scope: str) -> dict[str, Any] | None:
        if scope not in ("EVIDENCE", "FINAL_PACKAGE"):
            raise ValueError(f"알 수 없는 requirement scope: {scope!r}")
        bundle = self._evidence_bundle()
        if bundle is None:
            return None
        return bundle.requirement_report_evidence if scope == "EVIDENCE" else bundle.requirement_report_package

    def get_requirement_reports(self, scope: str) -> list[dict[str, Any]]:
        report = self.get_requirement_report(scope)
        return [report] if report is not None else []

    def get_evidence_needs(self) -> list[dict[str, Any]]:
        bundle = self._evidence_bundle()
        return [bundle.evidence_needs] if bundle and bundle.evidence_needs is not None else []

    def get_report_package(self) -> dict[str, Any] | None:
        bundle = self._evidence_bundle()
        return bundle.report_package if bundle else None

    def get_plate_readouts(self) -> list[dict[str, Any]]:
        bundle = self._evidence_bundle()
        return [bundle.plate_readout] if bundle and bundle.plate_readout else []

    def get_overlay_time_readouts(self) -> list[dict[str, Any]]:
        bundle = self._evidence_bundle()
        return [bundle.overlay_readout] if bundle and bundle.overlay_readout else []

    def get_plate_read_status(self) -> str | None:
        bundle = self._evidence_bundle()
        return "FAILED" if bundle and bundle.plate_read_outcome == "FAILED" else None

    def get_visual_evidence_decision(self) -> str | None:
        bundle = self._evidence_bundle()
        return bundle.disposition.decision if bundle else None

    def get_independent_facts(self) -> dict[str, Any] | None:
        bundle = self._evidence_bundle()
        return bundle.independent_facts if bundle else None

    def get_job_executions(self) -> list[dict[str, Any]]:
        # 실행 상태는 view가 `CaseStore.read_executions`(read port)로 읽는다(8-10).
        return []
