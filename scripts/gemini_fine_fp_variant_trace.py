#!/usr/bin/env python
"""고정 구간 Fine 에 오탐 원인별 지시 문장(변형)을 하나씩 붙여 판정이 바뀌는가.

search-structure-confirmation-plan-2026-10-26 §6.3(E2·E3)의 실행기다. 프롬프트는 운영
`fine_prompt_for(유형)` + 변형 문장 + 배속 안내이고, 전송은 원본 2 fps 를 0.5배속으로 늘린
영상(cv-coarse-argon-fine-2026-10-23 4단계와 같음), 박스 없음이다. 누적 비용이 --budget-krw 를
넘으면 다음 호출 전에 멈춘다. 응답 원문이 들어가므로 --out 은 저장소 밖에 둔다. 실행(유료):
uv run --extra eval-gemini python scripts/gemini_fine_fp_variant_trace.py --env <env> --out .omc/<json>
"""

from __future__ import annotations

import argparse
import importlib
import json
import tempfile
import time
from pathlib import Path

from gemini_fine_crop_hint_trace import _rescale_offsets, _slow_clip, _video_msg
from gemini_fine_image_accuracy import DEFAULT_ENV, VID

from daesingo.common import load_env_file
from daesingo.search.config import GeminiSearchConfig, api_key_from_env
from daesingo.search.prompts import fine_prompt_for, playback_note
from daesingo.search.schemas import FineResponse
from daesingo.search.scope import VisualEventType

SOLID = VisualEventType.SOLID_LINE_LANE_CHANGE
CENTER = VisualEventType.CENTER_LINE_CROSSING
DEFAULT_FPS = 2.0  # 원본 2 fps -> 0.5배속
HINT = "지정하지 않음. 영상에서 검증 대상 사건이 보이는 차량이 있으면 그 차량을 대상으로 보세요."

VARIANTS = {
    "control": "",
    "ego-v1": (
        "촬영 차량(블랙박스를 단 차량) 자신은 검증 대상이 아닙니다. 화면 전체나 차선이 함께 "
        "옆으로 흐르는 것은 촬영 차량의 움직임이므로, 대상은 화면에 보이는 다른 차량 중에서만 고르세요."
    ),
    "gore-v1": (
        "분기·합류부의 안전지대(빗금·갈매기 표시) 경계선이나 진출입로 분리선을 넘는 것은 차로 사이 "
        "경계선을 넘는 차로 변경과 구분해서 보고하세요. 넘은 선이 차로 사이 경계선인지 안전지대·분기부 "
        "경계선인지 확정할 수 없으면 UNCERTAIN을 선택하세요."
    ),
}

# (묶음, clip, 사건, 시작, 끝, 기대, 변형들)
ALL = tuple(VARIANTS)
CASES = [
    ("E2", "20260620_141628_EVT_1.avi", SOLID, 14.0, 20.0, "NOT_OBSERVED", ALL),  # 촬영 차량 오인
    ("E2", "20260620_150504_EVT_1.avi", SOLID, 2.4, 8.4, "NOT_OBSERVED", ALL),    # 분기부 안전지대
    ("E2", "20260620_141927_EVT_1.avi", SOLID, 4.0, 10.0, "OBSERVED", ALL),
    ("E2", "youtube_clip_01.mp4", SOLID, 0.0, 5.5, "OBSERVED", ALL),
    ("E2", "YT_0002_C00.mp4", CENTER, 10.5, 16.5, "OBSERVED", ALL),
    ("E2", "YT_0003_C05.mp4", SOLID, 18.0, 24.0, "OBSERVED", ALL),
    ("E3", "20260620_141927_EVT_1.avi", SOLID, 13.0, 19.0, "NOT_OBSERVED", ("control",)),  # 점선 변경
    ("E3", "20260620_141956_EVT_1.avi", SOLID, 9.0, 15.0, "NOT_OBSERVED", ("control",)),   # 점선 변경
    # §6.5 배속 비교: --groups SPD --fps 2 4 로 같은 구간을 두 프레임 밀도로 번갈아 보낸다.
    ("SPD", "20260620_141927_EVT_1.avi", SOLID, 4.0, 10.0, "OBSERVED", ("control",)),
    ("SPD", "20260620_141927_EVT_1.avi", SOLID, 13.0, 19.0, "NOT_OBSERVED", ("control",)),
    ("SPD", "20260620_141956_EVT_1.avi", SOLID, 9.0, 15.0, "NOT_OBSERVED", ("control",)),
]


def _prompt(event: VisualEventType, start: float, end: float, variant: str, fps: float) -> str:
    base = fine_prompt_for(event).render(
        event_type=event.value, target_hint=HINT, start_sec=start, end_sec=end
    ).rstrip()
    extra = VARIANTS[variant]
    return (f"{base}\n\n{extra}" if extra else base) + playback_note(1 / fps)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=DEFAULT_ENV)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--groups", nargs="+", default=["E2", "E3"])
    ap.add_argument("--fps", type=float, nargs="+", default=[DEFAULT_FPS],
                    help="원본 추출 fps. 여러 개면 같은 구간에 번갈아 보낸다(1/fps 배속)")
    ap.add_argument("--input-krw", type=float, required=True, help="입력 1M 토큰당 원화")
    ap.add_argument("--output-krw", type=float, required=True, help="출력 1M 토큰당 원화")
    ap.add_argument("--budget-krw", type=float, required=True, help="이 스크립트 누적 상한")
    args = ap.parse_args()

    env = load_env_file(args.env)
    cfg = GeminiSearchConfig.from_dotenv(env)
    client = importlib.import_module("openai").OpenAI(
        base_url=cfg.base_url, api_key=api_key_from_env(env), max_retries=0, timeout=300.0
    )
    rows: list[dict] = []
    spent = 0.0
    with tempfile.TemporaryDirectory(prefix="fpv_") as td:
        for i, (group, clip, event, start, end, expected, variants) in enumerate(CASES):
            if group not in args.groups:
                continue
            media = {fps: _slow_clip(Path(VID) / clip, start, end, fps, False,
                                     Path(td) / f"{i}_{fps}.mp4")
                     for fps in args.fps}
            for rep in range(1, args.repeat + 1):
                for fps, variant in ((f, v) for f in args.fps for v in variants):
                    if spent >= args.budget_krw:
                        print(f"budget reached: {spent:.1f} KRW — stop")
                        break
                    row = {"group": group, "clip": clip, "event": event.value,
                           "window": [start, end], "expected": expected,
                           "variant": variant, "repeat": rep, "fps": fps}
                    t0 = time.monotonic()
                    try:
                        with client.chat.completions.stream(
                            model=cfg.model,
                            messages=_video_msg(_prompt(event, start, end, variant, fps), media[fps]),
                            response_format=FineResponse,
                            reasoning_effort=cfg.reasoning_effort,
                            max_tokens=16384, stream_options={"include_usage": True},
                        ) as stream:
                            comp = stream.get_final_completion()
                        parsed = comp.choices[0].message.parsed
                        payload = parsed.model_dump(mode="json") if parsed else None
                        if payload:
                            _rescale_offsets(payload, 1 / fps)
                        usage = comp.usage
                        inp = getattr(usage, "prompt_tokens", 0) or 0
                        out = getattr(usage, "completion_tokens", 0) or 0
                        cost = inp * args.input_krw / 1e6 + out * args.output_krw / 1e6
                        spent += cost
                        row |= {"verification": payload["verification"] if payload else "NO_PARSE",
                                "response": payload, "input_tokens": inp, "output_tokens": out,
                                "krw": round(cost, 2)}
                    except Exception as exc:  # noqa: BLE001 — 실패도 한 행으로 남긴다
                        row |= {"verification": f"FAILED:{type(exc).__name__}", "error": str(exc)[:300]}
                    row["latency_sec"] = round(time.monotonic() - t0, 2)
                    row["correct"] = row["verification"] == expected
                    rows.append(row)
                    print(f"  {group} {variant:<8} {fps:g}fps r{rep} {clip:<26} {start:>4}-{end:<4} "
                          f"exp={expected:<12} got={row['verification']:<14} "
                          f"KRW {row.get('krw')} (sum {spent:.1f})")
                    args.out.write_text(json.dumps(
                        {"model": cfg.model, "fps": args.fps, "hint": HINT, "variants": VARIANTS,
                         "spent_krw": round(spent, 2), "rows": rows},
                        ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== 묶음 × 변형 ===")
    for group in args.groups:
        for variant, fps in ((v, f) for v in VARIANTS for f in args.fps):
            sub = [r for r in rows if r["group"] == group and r["variant"] == variant
                   and r["fps"] == fps]
            if not sub:
                continue
            pos = [r for r in sub if r["expected"] == "OBSERVED"]
            neg = [r for r in sub if r["expected"] == "NOT_OBSERVED"]
            print(f"  {group}/{variant}/{fps:g}fps: 양성 {sum(r['correct'] for r in pos)}/{len(pos)}, "
                  f"음성 {sum(r['correct'] for r in neg)}/{len(neg)}")
    print(f"spent {spent:.1f} KRW")


if __name__ == "__main__":
    main()
