"""readout — 번호판·화면값 판독.

지금 있는 것은 계약 타입과 fixture 로더뿐이다. 공개 함수(`read_plate`·`read_overlay_time`)는
다음 단계에서 이 패키지에 추가한다 — 경계와 「알면 안 되는 것」은 README와
docs/architecture/module-architecture.md §4-모듈3이 소유한다.
"""
from .contracts import (  # noqa: F401
    AssociatedRegion,
    AssociationEvidence,
    BestFrame,
    Consensus,
    ContractRef,
    Failure,
    FrameResult,
    InputRef,
    Observation,
    ObservationReason,
    OverlaySample,
    OverlayTimeReadout,
    OverlayValidation,
    PlateReadout,
    ProducedBy,
    ReadoutFixture,
    ReadoutRun,
    TargetAssociation,
    UnknownFieldError,
)
