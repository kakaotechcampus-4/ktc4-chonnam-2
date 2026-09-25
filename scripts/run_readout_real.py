#!/usr/bin/env python3
"""실제 블랙박스 영상으로 readout 공개 함수를 돌려 계약 객체를 만든다.

Real Data E2E(W6)용 진입점이다. **새 schema를 만들지 않는다** — `read_plate` ·
`read_overlay_time`이 원래 돌려주는 `ReadoutRun` · `PlateReadout` ·
`OverlayTimeReadout`을 그대로 JSON으로 떨군다.

`dump_readout_evidence.py`와 다르다 — 그쪽은 **fixture**를 넣어 계약 준수를 보이는
증빙이고, 이쪽은 **실제 픽셀**을 넣는다.

## 실행

PaddleOCR 환경이 필요하다(`experiments/ocr-baseline-2026-09-15/ENVIRONMENT.md`).

    PYTHONPATH=src D:/paddle-env/Scripts/python.exe scripts/run_readout_real.py \
        --clip ~/Downloads/20260810_175721_EVT_1.avi \
        --out <출력 폴더>

픽셀이 필요 없는 판정부만 검사하려면:

    PYTHONPATH=src python scripts/run_readout_real.py --selfcheck

## 알려진 단순화 — 결과 JSON에도 같이 적힌다

1. **`frame_ref`가 임시값이다.** `FrameRef` 발급은 `recording` 소유인데
   (`contract-plate-overlay-readout.md` §「`frame_ref` 형식」) 실제 영상을
   `MediaStream`으로 등록하는 경로가 아직 없다. `recording`이 붙으면
   `.frames(clip_ref)`만 구현한 공급자로 교체한다 — provider 본체는 안 바뀐다.
2. **`tz_offset`을 `+09:00`으로 고정한다.** 정식 출처는 clip의 source 메타데이터다.
3. **`target_hint`를 넘기지 않는다.** `search`의 실제 후보와 잇기 전까지는 hint 없는
   자체 association이고, 그래서 `target_association.status`가 `LOW_CONFIDENCE`다.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from daesingo.readout import api  # noqa: E402
from daesingo.readout.contracts import InputRef  # noqa: E402
from daesingo.readout import paddle_provider  # noqa: E402
from daesingo.readout.paddle_provider import (  # noqa: E402
    LocalVideoFrameSource,
    PaddleOcrProvider,
)

DERIVED = "SOURCE_DERIVED_INCIDENT_CLIP"

KNOWN_SIMPLIFICATIONS = [
    "frame_ref는 recording이 발급한 정식 ref가 아니다 — LocalVideoFrameSource의 임시값이다",
    "tz_offset을 +09:00으로 고정했다 — 정식 출처는 clip의 source 메타데이터다",
    "target_hint 없이 실행했다 — association은 provider 자체 선택이라 LOW_CONFIDENCE다",
]


def run(clip_path, clip_ref, case_id, candidate_id):
    """실제 영상 1건 → `(ReadoutRun, PlateReadout, ReadoutRun, OverlayTimeReadout)`."""
    provider = PaddleOcrProvider(LocalVideoFrameSource({clip_ref: clip_path}))
    request = api.ReadRequest(
        case_id=case_id,
        candidate_id=candidate_id,
        input_ref=InputRef(
            incident_clip_ref=clip_ref,
            source_profile="readout-native",
            provenance=DERIVED,
        ),
    )
    # 같은 provider 인스턴스를 두 호출에 쓴다 — 모델 적재와 OCR을 한 번만 하기 위해서다.
    plate_run, plate = api.read_plate(request, provider=provider)
    overlay_run, overlay = api.read_overlay_time(request, provider=provider)
    return plate_run, plate, overlay_run, overlay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--clip", help="실제 블랙박스 영상 파일")
    parser.add_argument("--clip-ref", default=None,
                        help="이 영상에 붙일 incident_clip_ref. 기본은 파일 이름에서 만든다")
    parser.add_argument("--case-id", default="case_real_001")
    parser.add_argument("--candidate-id", default="candidate_real_001")
    parser.add_argument("--out", default=None, help="JSON을 떨굴 폴더. 없으면 stdout")
    parser.add_argument("--selfcheck", action="store_true",
                        help="PaddleOCR·영상 없이 판정부만 검사한다")
    args = parser.parse_args()

    if args.selfcheck:
        paddle_provider.selfcheck()
        return 0

    if not args.clip:
        parser.error("--clip이 필요하다 (또는 --selfcheck)")

    clip_path = os.path.expanduser(args.clip)
    if not os.path.exists(clip_path):
        parser.error(f"영상이 없다: {clip_path}")
    clip_ref = args.clip_ref or (
        "clip_" + os.path.splitext(os.path.basename(clip_path))[0].lower())

    plate_run, plate, overlay_run, overlay = run(
        clip_path, clip_ref, args.case_id, args.candidate_id)

    payload = {
        "source_video": os.path.abspath(clip_path),
        "incident_clip_ref": clip_ref,
        "provider_label": PaddleOcrProvider.label,
        "known_simplifications": KNOWN_SIMPLIFICATIONS,
        "plate_run": plate_run.to_dict(),
        "plate_readout": plate.to_dict() if plate else None,
        "overlay_run": overlay_run.to_dict(),
        "overlay_time_readout": overlay.to_dict() if overlay else None,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        path = os.path.join(args.out, f"{clip_ref}.json")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(path)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
