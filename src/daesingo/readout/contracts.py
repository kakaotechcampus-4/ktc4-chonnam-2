"""readout Producer 계약 3종의 도메인 타입 — ReadoutRun · PlateReadout · OverlayTimeReadout.

스키마 원문은 계약 문서가 소유한다. 이 파일은 옮겨 적은 것이고 규칙을 새로 만들지 않는다.
  - docs/architecture/contracts/contract-readout-run.md
  - docs/architecture/contracts/contract-plate-overlay-readout.md
  - docs/architecture/contracts/contract-observation.md  (Observation<T> v1 envelope)

## 이 모듈이 지키는 두 가지

**1. 키가 없는 것과 값이 null인 것은 다르다.** `contract`·`contract_version`·`observation.reason`은
   fixture에서 「키 자체가 없는」 형태로 나타나고 명시적 null로 쓰인 적이 없다. 그래서 이 셋만
   `None = 키 없음`으로 두고 직렬화에서 생략한다. 나머지 nullable 필드(`failure`·`abstain_reason`·
   `validation.format_ok` 등)는 키를 항상 쓰고 값만 null이 된다.

**2. 모르는 키는 조용히 버리지 않는다.** readout은 이 세 계약의 Producer라서, fixture에 내가 모르는
   키가 있으면 계약이 움직였거나 내 타입이 뒤처진 것이다. 파싱에서 UnknownFieldError로 세운다.

값 공간 검사는 여기서 하지 않는다 — `registry.py`가 목록을 갖고, 검사는 테스트가 한다.
파싱 시점에 등재값을 강제하면 남이 등재한 새 값을 읽지 못하고 죽는다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


class UnknownFieldError(ValueError):
    """계약 타입이 모르는 키가 payload에 있다."""


def _take(data: dict, *names: str) -> list:
    """알려진 키를 순서대로 꺼내고, 남은 키가 있으면 세운다."""
    rest = set(data) - set(names)
    if rest:
        raise UnknownFieldError(f"모르는 키: {sorted(rest)}")
    return [data.get(n) for n in names]


# ── 공용 조각 ─────────────────────────────────────────────────

@dataclass
class ContractRef:
    kind: str
    ref: str

    @classmethod
    def from_dict(cls, d: dict) -> "ContractRef":
        return cls(*_take(d, "kind", "ref"))

    def to_dict(self) -> dict:
        return {"kind": self.kind, "ref": self.ref}


@dataclass
class Failure:
    kind: str
    code: str

    @classmethod
    def from_dict(cls, d: dict) -> "Failure":
        return cls(*_take(d, "kind", "code"))

    def to_dict(self) -> dict:
        return {"kind": self.kind, "code": self.code}


@dataclass
class ObservationReason:
    code: str
    note: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "ObservationReason":
        return cls(*_take(d, "code", "note"))

    def to_dict(self) -> dict:
        return {"code": self.code, "note": self.note}


@dataclass
class ProducedBy:
    module: str
    run_ref: ContractRef

    @classmethod
    def from_dict(cls, d: dict) -> "ProducedBy":
        module, run_ref = _take(d, "module", "run_ref")
        return cls(module, ContractRef.from_dict(run_ref))

    def to_dict(self) -> dict:
        return {"module": self.module, "run_ref": self.run_ref.to_dict()}


@dataclass
class Observation:
    """공용 Observation<T> v1 envelope. `value`의 타입은 소비처가 안다.

    `support_refs`는 readout에서 항상 빈 배열이다 — 근거 ref는 best_frame·frame_results가 갖는다
    (contract-plate-overlay-readout.md §3).
    """
    contract_version: str
    value: Any
    status: str
    source: dict
    support_refs: list
    produced_by: ProducedBy
    reason: Optional[ObservationReason] = None  # 키 없음 = None

    @classmethod
    def from_dict(cls, d: dict) -> "Observation":
        ver, value, status, reason, source, support_refs, produced_by = _take(
            d, "contract_version", "value", "status", "reason",
            "source", "support_refs", "produced_by",
        )
        return cls(
            contract_version=ver,
            value=value,
            status=status,
            source=source,
            support_refs=list(support_refs),
            produced_by=ProducedBy.from_dict(produced_by),
            reason=ObservationReason.from_dict(reason) if reason is not None else None,
        )

    def to_dict(self) -> dict:
        out: dict = {
            "contract_version": self.contract_version,
            "value": self.value,
            "status": self.status,
        }
        if self.reason is not None:
            out["reason"] = self.reason.to_dict()
        out["source"] = dict(self.source)
        out["support_refs"] = list(self.support_refs)
        out["produced_by"] = self.produced_by.to_dict()
        return out


@dataclass
class InputRef:
    incident_clip_ref: str
    source_profile: str
    provenance: str

    @classmethod
    def from_dict(cls, d: dict) -> "InputRef":
        return cls(*_take(d, "incident_clip_ref", "source_profile", "provenance"))

    def to_dict(self) -> dict:
        return {
            "incident_clip_ref": self.incident_clip_ref,
            "source_profile": self.source_profile,
            "provenance": self.provenance,
        }


# ── ReadoutRun ───────────────────────────────────────────────

@dataclass
class ReadoutRun:
    run_id: str
    operation: str
    outcome: str
    failure: Optional[Failure]
    usage_refs: list
    started_at: str
    ended_at: str
    contract: Optional[str] = None
    contract_version: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "ReadoutRun":
        (contract, ver, run_id, operation, outcome, failure,
         usage_refs, started_at, ended_at) = _take(
            d, "contract", "contract_version", "run_id", "operation", "outcome",
            "failure", "usage_refs", "started_at", "ended_at",
        )
        return cls(
            run_id=run_id, operation=operation, outcome=outcome,
            failure=Failure.from_dict(failure) if failure is not None else None,
            usage_refs=list(usage_refs), started_at=started_at, ended_at=ended_at,
            contract=contract, contract_version=ver,
        )

    def to_dict(self) -> dict:
        out: dict = {}
        if self.contract is not None:
            out["contract"] = self.contract
        if self.contract_version is not None:
            out["contract_version"] = self.contract_version
        out["run_id"] = self.run_id
        out["operation"] = self.operation
        out["outcome"] = self.outcome
        out["failure"] = self.failure.to_dict() if self.failure else None
        out["usage_refs"] = list(self.usage_refs)
        out["started_at"] = self.started_at
        out["ended_at"] = self.ended_at
        return out


# ── PlateReadout ─────────────────────────────────────────────

@dataclass
class AssociatedRegion:
    frame_ref: str
    bbox_xywh: list

    @classmethod
    def from_dict(cls, d: dict) -> "AssociatedRegion":
        frame_ref, bbox = _take(d, "frame_ref", "bbox_xywh")
        return cls(frame_ref, list(bbox))

    def to_dict(self) -> dict:
        return {"frame_ref": self.frame_ref, "bbox_xywh": list(self.bbox_xywh)}


@dataclass
class AssociationEvidence:
    kind: str
    detail: str

    @classmethod
    def from_dict(cls, d: dict) -> "AssociationEvidence":
        return cls(*_take(d, "kind", "detail"))

    def to_dict(self) -> dict:
        return {"kind": self.kind, "detail": self.detail}


@dataclass
class TargetAssociation:
    status: str
    target_hint_used: bool
    track_ref: Optional[str]
    association_method: str
    associated_region: Optional[AssociatedRegion]
    evidence: list

    @classmethod
    def from_dict(cls, d: dict) -> "TargetAssociation":
        status, hint_used, track_ref, method, region, evidence = _take(
            d, "status", "target_hint_used", "track_ref",
            "association_method", "associated_region", "evidence",
        )
        return cls(
            status=status, target_hint_used=hint_used, track_ref=track_ref,
            association_method=method,
            associated_region=AssociatedRegion.from_dict(region) if region is not None else None,
            evidence=[AssociationEvidence.from_dict(e) for e in evidence],
        )

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "target_hint_used": self.target_hint_used,
            "track_ref": self.track_ref,
            "association_method": self.association_method,
            "associated_region": self.associated_region.to_dict() if self.associated_region else None,
            "evidence": [e.to_dict() for e in self.evidence],
        }


@dataclass
class Consensus:
    """`disagree_positions`는 observation.value의 `?` 위치와 일치해야 한다(불변조건, 6단계에서 코드화)."""
    text: str
    disagree_positions: list
    method: str

    @classmethod
    def from_dict(cls, d: dict) -> "Consensus":
        text, positions, method = _take(d, "text", "disagree_positions", "method")
        return cls(text, list(positions), method)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "disagree_positions": list(self.disagree_positions),
            "method": self.method,
        }


@dataclass
class BestFrame:
    frame_ref: str
    crop_ref: str
    quality: dict

    @classmethod
    def from_dict(cls, d: dict) -> "BestFrame":
        frame_ref, crop_ref, quality = _take(d, "frame_ref", "crop_ref", "quality")
        return cls(frame_ref, crop_ref, dict(quality))

    def to_dict(self) -> dict:
        return {
            "frame_ref": self.frame_ref,
            "crop_ref": self.crop_ref,
            "quality": dict(self.quality),
        }


@dataclass
class FrameResult:
    frame_ref: str
    crop_ref: str
    text: Optional[str]
    confidence: Optional[float]

    @classmethod
    def from_dict(cls, d: dict) -> "FrameResult":
        return cls(*_take(d, "frame_ref", "crop_ref", "text", "confidence"))

    def to_dict(self) -> dict:
        return {
            "frame_ref": self.frame_ref,
            "crop_ref": self.crop_ref,
            "text": self.text,
            "confidence": self.confidence,
        }


@dataclass
class PlateReadout:
    readout_id: str
    run_ref: ContractRef
    case_id: str
    candidate_id: str
    input_ref: InputRef
    target_association: TargetAssociation
    observation: Observation
    consensus: Consensus
    abstained: bool
    abstain_reason: Optional[str]
    best_frame: Optional[BestFrame]
    frame_results: list
    contract: Optional[str] = None
    contract_version: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "PlateReadout":
        (contract, ver, readout_id, run_ref, case_id, candidate_id, input_ref,
         target_association, observation, consensus, abstained, abstain_reason,
         best_frame, frame_results) = _take(
            d, "contract", "contract_version", "readout_id", "run_ref", "case_id",
            "candidate_id", "input_ref", "target_association", "observation",
            "consensus", "abstained", "abstain_reason", "best_frame", "frame_results",
        )
        return cls(
            readout_id=readout_id,
            run_ref=ContractRef.from_dict(run_ref),
            case_id=case_id,
            candidate_id=candidate_id,
            input_ref=InputRef.from_dict(input_ref),
            target_association=TargetAssociation.from_dict(target_association),
            observation=Observation.from_dict(observation),
            consensus=Consensus.from_dict(consensus),
            abstained=abstained,
            abstain_reason=abstain_reason,
            best_frame=BestFrame.from_dict(best_frame) if best_frame is not None else None,
            frame_results=[FrameResult.from_dict(f) for f in frame_results],
            contract=contract,
            contract_version=ver,
        )

    def to_dict(self) -> dict:
        out: dict = {}
        if self.contract is not None:
            out["contract"] = self.contract
        if self.contract_version is not None:
            out["contract_version"] = self.contract_version
        out["readout_id"] = self.readout_id
        out["run_ref"] = self.run_ref.to_dict()
        out["case_id"] = self.case_id
        out["candidate_id"] = self.candidate_id
        out["input_ref"] = self.input_ref.to_dict()
        out["target_association"] = self.target_association.to_dict()
        out["observation"] = self.observation.to_dict()
        out["consensus"] = self.consensus.to_dict()
        out["abstained"] = self.abstained
        out["abstain_reason"] = self.abstain_reason
        out["best_frame"] = self.best_frame.to_dict() if self.best_frame else None
        out["frame_results"] = [f.to_dict() for f in self.frame_results]
        return out


# ── OverlayTimeReadout ───────────────────────────────────────

@dataclass
class OverlayValidation:
    """「검증 안 함」은 false가 아니라 null이다(contract-plate-overlay-readout.md §7)."""
    format_ok: Optional[bool]
    monotonic_ok: Optional[bool]
    duration_match_ok: Optional[bool]
    sample_count: int

    @classmethod
    def from_dict(cls, d: dict) -> "OverlayValidation":
        return cls(*_take(d, "format_ok", "monotonic_ok", "duration_match_ok", "sample_count"))

    def to_dict(self) -> dict:
        return {
            "format_ok": self.format_ok,
            "monotonic_ok": self.monotonic_ok,
            "duration_match_ok": self.duration_match_ok,
            "sample_count": self.sample_count,
        }


@dataclass
class OverlaySample:
    frame_ref: str
    offset_sec: float
    raw_text: str
    parsed_at: Optional[str]

    @classmethod
    def from_dict(cls, d: dict) -> "OverlaySample":
        return cls(*_take(d, "frame_ref", "offset_sec", "raw_text", "parsed_at"))

    def to_dict(self) -> dict:
        return {
            "frame_ref": self.frame_ref,
            "offset_sec": self.offset_sec,
            "raw_text": self.raw_text,
            "parsed_at": self.parsed_at,
        }


@dataclass
class OverlayTimeReadout:
    readout_id: str
    run_ref: ContractRef
    case_id: str
    candidate_id: str
    input_ref: InputRef
    observation: Observation
    validation: OverlayValidation
    samples: list
    contract: Optional[str] = None
    contract_version: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "OverlayTimeReadout":
        (contract, ver, readout_id, run_ref, case_id, candidate_id,
         input_ref, observation, validation, samples) = _take(
            d, "contract", "contract_version", "readout_id", "run_ref", "case_id",
            "candidate_id", "input_ref", "observation", "validation", "samples",
        )
        return cls(
            readout_id=readout_id,
            run_ref=ContractRef.from_dict(run_ref),
            case_id=case_id,
            candidate_id=candidate_id,
            input_ref=InputRef.from_dict(input_ref),
            observation=Observation.from_dict(observation),
            validation=OverlayValidation.from_dict(validation),
            samples=[OverlaySample.from_dict(s) for s in samples],
            contract=contract,
            contract_version=ver,
        )

    def to_dict(self) -> dict:
        out: dict = {}
        if self.contract is not None:
            out["contract"] = self.contract
        if self.contract_version is not None:
            out["contract_version"] = self.contract_version
        out["readout_id"] = self.readout_id
        out["run_ref"] = self.run_ref.to_dict()
        out["case_id"] = self.case_id
        out["candidate_id"] = self.candidate_id
        out["input_ref"] = self.input_ref.to_dict()
        out["observation"] = self.observation.to_dict()
        out["validation"] = self.validation.to_dict()
        out["samples"] = [s.to_dict() for s in self.samples]
        return out


# ── fixture 파일 단위 ────────────────────────────────────────

@dataclass
class ReadoutFixture:
    """data/mock/readout/<scenario>.json 한 파일. 계약 객체가 아니라 Mock 묶음이다."""
    scenario_id: str
    module: str
    readout_runs: list
    plate_readouts: list
    overlay_time_readouts: list

    @classmethod
    def from_dict(cls, d: dict) -> "ReadoutFixture":
        scenario_id, module, runs, plates, overlays = _take(
            d, "scenario_id", "module", "readout_runs",
            "plate_readouts", "overlay_time_readouts",
        )
        return cls(
            scenario_id=scenario_id,
            module=module,
            readout_runs=[ReadoutRun.from_dict(r) for r in runs],
            plate_readouts=[PlateReadout.from_dict(p) for p in plates],
            overlay_time_readouts=[OverlayTimeReadout.from_dict(o) for o in overlays],
        )

    def to_dict(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "module": self.module,
            "readout_runs": [r.to_dict() for r in self.readout_runs],
            "plate_readouts": [p.to_dict() for p in self.plate_readouts],
            "overlay_time_readouts": [o.to_dict() for o in self.overlay_time_readouts],
        }
