"""readout — 번호판·화면값 판독.

공개 함수는 둘이다 — `read_plate` · `read_overlay_time`. 다른 모듈은 이 둘만 부른다.
경계와 「알면 안 되는 것」은 README와 docs/architecture/module-architecture.md §4-모듈3이 소유한다.

판정은 `api.py`가 하고, 프레임을 글자로 바꾸는 부분은 provider가 한다. 운영 OCR은
`paddle_provider.PaddleOcrProvider`(PaddleOCR)다. provider를 넘기지 않으면 테스트용
`providers.FixtureOcrProvider`가 기본값이다.
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
