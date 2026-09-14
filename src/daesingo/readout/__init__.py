"""readout — 번호판·화면값 판독.

공개 함수는 둘이다 — `read_plate` · `read_overlay_time`. 다른 모듈은 이 둘만 부른다.
경계와 「알면 안 되는 것」은 README와 docs/architecture/module-architecture.md §4-모듈3이 소유한다.

실제 OCR은 아직 없다. 판정 로직은 전부 실제이고, 프레임을 글자로 바꾸는 부분만
`providers.py`의 Stub이 대신한다 — 교체 지점은 그 파일 하나다.
"""
from .api import (  # noqa: F401
    OverlayTimeReadResult,
    PlateReadResult,
    ReadRequest,
    TargetHint,
    read_overlay_time,
    read_plate,
)
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
from .providers import OcrProvider, ProviderError  # noqa: F401
