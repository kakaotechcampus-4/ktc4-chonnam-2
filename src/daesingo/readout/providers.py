"""OCR provider 경계 — **실제 OCR이 들어올 자리는 이 파일 하나다.**

공개 함수(`api.py`)는 판정을 전부 직접 한다 — association 반영·consensus·abstain·overlay 4갈래·
validation·run 조립. provider가 하는 일은 그 앞단, 즉 **프레임을 떠서 픽셀을 글자로 바꾸는 것**뿐이다.
그래서 실제 OCR로 교체할 때 `api.py`는 손대지 않는다.

## 교체 지점

`OcrProvider`를 상속해 두 메서드를 채우고 공개 함수에 `provider=`로 넘긴다. 지금 기본값인
`FixtureOcrProvider`는 Mock Pack v5 fixture를 그대로 되읽는 Stub이고, 판정 로직을 태우기 위한
입력 공급자일 뿐이다 — 계약 객체를 만들지 않는다(만들면 파이프라인이 검사되지 않는다).

## provider가 **모르는** 것

`ReadoutRun`·`PlateReadout`·`OverlayTimeReadout`·`run_id`·`crop_ref`·abstain·계약 버전.
전부 공개 함수가 소유한다. provider는 프레임·글자·신뢰도·overlay 유무까지만 말한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .fixtures import load_all

# overlay 유무 판정 — provider가 말하는 세 가지. 계약의 observation.status가 아니다.
# 「없음(사실)」과 「있는지 못 봄(모름)」을 provider 층위에서부터 갈라 둔다
# (decisions/failure-taxonomy.md 「실패가 아닌 상태」).
PRESENT = "PRESENT"
NOT_PRESENT = "NOT_PRESENT"
UNDETERMINED = "UNDETERMINED"

PRESENCES = frozenset({PRESENT, NOT_PRESENT, UNDETERMINED})


class ProviderError(Exception):
    """판독 실행 자체가 실패했다 — 결과 객체를 만들 수 없는 완전 실패.

    `kind`·`code`는 `decisions/failure-taxonomy.md` 등재값이어야 한다. 실행 중 감지되는
    완전 실패는 `INFRA` 3종뿐이고, `OVERLAY_VALIDATION`은 여기로 오지 않는다 — 그것은
    값을 읽은 **뒤의** 검증 결과라 run 실패가 아니다(같은 문서 「kind와 outcome은 1:1이 아니다」).
    """

    def __init__(self, kind: str, code: str, detail: str = ""):
        super().__init__(f"{kind}/{code}" + (f" — {detail}" if detail else ""))
        self.kind = kind
        self.code = code
        self.detail = detail


# ── provider가 돌려주는 것 ────────────────────────────────────

@dataclass
class PlateFrameReading:
    """프레임 한 장에서 번호판 영역을 떠서 읽은 결과.

    `crop_ref`가 없다 — crop identity 발급은 readout 공개 함수의 몫이다
    (contract-plate-overlay-readout.md §3 「발급 주체는 readout이다」).
    """
    frame_ref: str
    bbox_xywh: list
    text: Optional[str]
    confidence: Optional[float]
    quality: dict = field(default_factory=dict)


@dataclass
class AssociationReading:
    """「어느 차량의 번호판을 읽었나」와 그 근거. status 값 공간은 계약 §5.

    `region`은 **대상 차량 영역**이고 번호판 박스가 아니다. 번호판 박스는 프레임마다
    `PlateFrameReading.bbox_xywh`가 갖는다 — 계약 §4 `best_frame.plate_bbox_xywh`(v1.3).
    둘을 한 값으로 쓰면 소비자가 번호판을 그리려고 association 근거를 읽게 된다.
    """
    status: str
    target_hint_used: bool
    track_ref: Optional[str]
    association_method: str
    evidence: list = field(default_factory=list)  # [(kind, detail), ...]
    region: Optional[tuple] = None                # (frame_ref, bbox_xywh) | None


@dataclass
class PlateReading:
    association: AssociationReading
    frames: list


@dataclass
class OverlaySampleReading:
    """sample 한 건의 OCR 원문. 파싱은 공개 함수가 한다 — `parsed_at`이 여기 없는 이유다."""
    frame_ref: str
    offset_sec: float
    raw_text: Optional[str]


@dataclass
class OverlayReading:
    presence: str
    samples: list = field(default_factory=list)
    tz_offset: str = "+09:00"
    """overlay 문자열에는 timezone이 없다. 실제 구현에서는 clip의 source 메타데이터에서 온다."""


class OcrProvider:
    """readout이 외부 OCR에 기대하는 전부. 실제 구현은 이 두 메서드만 채우면 된다."""

    label = "abstract"

    def read_plate(self, input_ref, target_hint) -> PlateReading:
        raise NotImplementedError

    def read_overlay_time(self, input_ref) -> OverlayReading:
        raise NotImplementedError


# ── Mock 1차용 Stub ──────────────────────────────────────────

def _presence_of(overlay) -> str:
    reason = overlay.observation.reason
    code = reason.code if reason else None
    if code == "readout.overlay.not_present":
        return NOT_PRESENT
    if code == "readout.overlay.presence_undetermined":
        return UNDETERMINED
    return PRESENT  # OK · ocr_failed — 화면에 찍혀 있었고 읽기를 시도한 갈래


class FixtureOcrProvider(OcrProvider):
    """Mock Pack v5 fixture를 provider 출력으로 되읽는 Stub.

    `(incident_clip_ref, source_profile)`로 대본을 찾고, 같은 키로 여러 번 부르면 fixture에 있는
    순서대로 다음 대본을 준다 — 재판독이 앞 실행과 다른 결과를 내는 상황이 fixture에 그렇게 들어
    있기 때문이다(`clip_x001`의 overlay 2회). 대본이 떨어지면 마지막 것을 반복한다.

    fixture에 없는 clip을 물으면 세우지 않고 **빈 결과**를 준다 — 「번호판을 못 찾았다」와
    「clip이 대본에 없다」를 Stub이 구분할 방법이 없고, 조용히 성공한 척하는 것보다 낫다.
    """

    label = "fixture-mock-v5"

    def __init__(self):
        self._plate = {}
        self._overlay = {}
        self._taken = {}
        for fixture in load_all().values():
            for plate in fixture.plate_readouts:
                key = (plate.input_ref.incident_clip_ref, plate.input_ref.source_profile)
                self._plate.setdefault(key, []).append(plate)
            for overlay in fixture.overlay_time_readouts:
                key = (overlay.input_ref.incident_clip_ref, overlay.input_ref.source_profile)
                self._overlay.setdefault(key, []).append(overlay)

    # 대본 진행 — 같은 키의 n번째 호출은 n번째 대본을 본다
    def _next(self, table, key):
        script = table.get(key)
        if not script:
            return None
        seen = self._taken.get(key, 0)
        self._taken[key] = seen + 1
        return script[min(seen, len(script) - 1)]

    def read_plate(self, input_ref, target_hint) -> PlateReading:
        # `scenario_infra_failure_001`의 `rr_x001_plate`는 fixture에서 역산할 수 없다 — 완전
        # 실패라 결과 객체가 없고 `ReadoutRun`에는 `input_ref`가 없다(contract-readout-run.md §3).
        if input_ref.incident_clip_ref == "clip_x001":
            raise ProviderError("INFRA", "READOUT_PROVIDER_TIMEOUT", "scripted stub failure")
        key = (input_ref.incident_clip_ref, input_ref.source_profile)
        plate = self._next(self._plate, key)

        used = target_hint is not None
        if plate is None:
            return PlateReading(
                association=AssociationReading(
                    status="NOT_PROVIDED" if not used else "FAILED",
                    target_hint_used=used,
                    track_ref=getattr(target_hint, "track_ref", None),
                    association_method="TARGET_HINT_WITH_FALLBACK" if used else "FALLBACK_ONLY",
                    evidence=[],
                ),
                frames=[],
            )

        assoc = plate.target_association
        region = assoc.associated_region
        # 대상 차량 영역이다. 번호판 영역이 아니다 — fixture가 번호판 박스를 갖고 있지 않은
        # 프레임에서만 자리를 채우는 값으로 쓴다.
        bbox = list(region.bbox_xywh) if region else [0, 0, 0, 0]
        best = plate.best_frame
        return PlateReading(
            association=AssociationReading(
                status=assoc.status,
                # fixture 값을 그대로 쓰지 않는다 — hint 없이 불렀으면 안 쓴 것이다.
                target_hint_used=used,
                track_ref=getattr(target_hint, "track_ref", None) or assoc.track_ref,
                association_method="TARGET_HINT_WITH_FALLBACK" if used else "FALLBACK_ONLY",
                evidence=[(e.kind, e.detail) for e in assoc.evidence],
                region=(region.frame_ref, list(region.bbox_xywh)) if region else None,
            ),
            frames=[
                PlateFrameReading(
                    frame_ref=f.frame_ref,
                    # 번호판 박스도 품질 지표와 같다 — fixture는 best frame 것만 갖고 있다.
                    # 나머지 프레임은 대상 차량 영역으로 자리만 채운다.
                    bbox_xywh=(list(best.plate_bbox_xywh)
                               if best and f.frame_ref == best.frame_ref
                               and best.plate_bbox_xywh else list(bbox)),
                    text=f.text,
                    confidence=f.confidence,
                    # 품질 지표는 provider 쪽 실측값이다. fixture는 best frame 것만 갖고 있다.
                    quality=dict(best.quality) if best and f.frame_ref == best.frame_ref else {},
                )
                for f in plate.frame_results
            ],
        )

    def read_overlay_time(self, input_ref) -> OverlayReading:
        key = (input_ref.incident_clip_ref, input_ref.source_profile)
        overlay = self._next(self._overlay, key)
        if overlay is None:
            return OverlayReading(presence=UNDETERMINED, samples=[])

        presence = _presence_of(overlay)
        return OverlayReading(
            presence=presence,
            samples=[
                OverlaySampleReading(
                    frame_ref=s.frame_ref, offset_sec=s.offset_sec, raw_text=s.raw_text,
                )
                for s in overlay.samples
            ],
        )


_DEFAULT_PROVIDER = None


def default_provider() -> OcrProvider:
    """1차 Mock 통합의 기본 provider. 실제 OCR이 생기면 여기가 바뀐다.

    **한 인스턴스를 돌려쓴다.** 호출마다 새로 만들면 위 대본 진행이 매번 처음으로 돌아가
    `provider=`를 넘기지 않은 호출자에게는 재판독 대본이 영영 보이지 않는다 — `clip_x001`의
    overlay 두 번째 갈래(`ocr_failed`)처럼. fixture 5개를 다시 읽는 비용도 매 호출 나간다.
    """
    global _DEFAULT_PROVIDER
    if _DEFAULT_PROVIDER is None:
        _DEFAULT_PROVIDER = FixtureOcrProvider()
    return _DEFAULT_PROVIDER


def reset_default_provider() -> None:
    """기본 provider의 대본 진행을 처음으로 되돌린다. 테스트가 서로 간섭하지 않게 하는 용도다."""
    global _DEFAULT_PROVIDER
    _DEFAULT_PROVIDER = None
