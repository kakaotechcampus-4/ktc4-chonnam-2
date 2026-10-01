#!/usr/bin/env python
"""실제 coarse->fine 구조(run_case)를 느린 영상으로 돌린다. 기본: Coarse 0.5x(원본 2fps) / Fine 0.25x(원본 4fps).

프록시는 영상을 재생 시간 1초당 1프레임·low(66토큰)로 재샘플링한다
(gemini-video-slowdown-token-probe-2026-09-29). 영상을 speed 배로 늘리면 원본 1초에
1/speed 프레임이 모델에 들어간다. 이미지 전송(프레임당 1,100토큰)보다 싸게 시간 밀도를 올린다.

구조: image trace 와 같이 run_case 의 provider seam 에 invoker 를 끼운다. MediaPreparer 가
fps=1/speed 로 준비한 MP4 를 invoker 가 setpts 로 늘려 영상(`type: file`)으로 보낸다.
모델은 늘어난 영상 기준 시각으로 답하고, invoker 가 speed 를 곱해 원본 시각으로 되돌린 뒤
run_case 에 넘긴다. 프롬프트·스키마·후보 핸드오프·padding·clamp 는 그대로다(p3).

1x 도 같은 invoker(재인코딩 없음)로 같은 실행에서 돌려 통제 비교한다.

--transport image 는 같은 조건을 이미지로 보낸다(gemini_coarse_fine_image_trace.ImageInvoker).
이때 배속 s 는 준비 fps 1/s 를 뜻한다(0.5:0.25 = Coarse 2fps / Fine 4fps).
--profiles 로 diagnostic-v1·diagnostic-handoff-v1 등을 같은 실행에서 비교한다.

실행(유료): uv run --extra eval-gemini python scripts/gemini_coarse_fine_slowdown_trace.py --out <json>
"""

from __future__ import annotations

import argparse
import base64
import importlib
import json
import shutil
import subprocess
import tempfile
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

from daesingo.common import load_env_file
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.decision_trace import DiagnosticCoarseResponse, DiagnosticFineResponse
from daesingo.search.diagnostic import run_case
from daesingo.search.diagnostic_call import DiagnosticDependencies
from daesingo.search.diagnostic_models import DiagnosticCase, DiagnosticProfile
from daesingo.search.media import MediaPreparer
from daesingo.search.provider import (
    ProviderResult,
    StructuredInvocation,
    _usage_from_completion,
)
from daesingo.search.schemas import CoarseResponse, FineResponse
from daesingo.search.smoke_errors import ProviderApiError, ProviderPayloadError

VID = "C:/Users/User/orca/ktc4-chonnam-2/src/daesingo/search/video"
DEFAULT_ENV = "C:/Users/User/orca/ktc4-chonnam-2/.env"

# 정답지.md: (case_id, file, duration, event, 기대, 정답 구간(원본 초) 또는 None)
CASES = [
    ("20260620_141628_EVT_1", "20260620_141628_EVT_1.avi", 20.023, "SOLID_LINE_LANE_CHANGE", "NOT_OBSERVED", None),
    ("20260620_141927_EVT_1", "20260620_141927_EVT_1.avi", 20.025, "SOLID_LINE_LANE_CHANGE", "OBSERVED", (4.0, 10.0)),
    ("20260620_141956_EVT_1", "20260620_141956_EVT_1.avi", 20.025, "SOLID_LINE_LANE_CHANGE", "NOT_OBSERVED", None),
    ("20260620_150504_EVT_1", "20260620_150504_EVT_1.avi", 20.025, "SOLID_LINE_LANE_CHANGE", "NOT_OBSERVED", None),
    ("youtube_clip_01", "youtube_clip_01.mp4", 5.533, "SOLID_LINE_LANE_CHANGE", "OBSERVED", (2.0, 5.0)),
    ("YT_0003_C05", "YT_0003_C05.mp4", 60.0, "SOLID_LINE_LANE_CHANGE", "OBSERVED", (10.0, 13.0)),
    ("YT_0002_C00", "YT_0002_C00.mp4", 20.079, "CENTER_LINE_CROSSING", "OBSERVED", (11.0, 14.0)),
]


def _ffmpeg() -> str:
    p = shutil.which("ffmpeg")
    if p is None:
        raise SystemExit("ffmpeg not found")
    return p


def _slow(src: Path, dest: Path, speed: float) -> None:
    """준비된 MP4(fps=1/speed)를 speed 배로 늘려 재생 1초 = 원본 프레임 1장이 되게 한다."""
    r = subprocess.run(
        [_ffmpeg(), "-y", "-i", str(src), "-vf", f"setpts=PTS/{speed}",
         "-c:v", "libx264", "-an", "-movflags", "+faststart", str(dest)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    if r.returncode != 0:
        raise ProviderPayloadError(f"slowdown failed: {r.stderr.decode(errors='replace')[-200:]}")


def _note(speed: float, handoff: bool) -> str:
    factor = round(1 / speed)
    extra = (
        f" Coarse 핵심 시각도 원본 기준이므로 제공 영상에서는 그 {factor}배 위치입니다."
        if handoff else ""
    )
    return (
        f"\n\n주의: 제공 영상은 원본을 {factor}배 느리게 재생하도록 늘린 것입니다. "
        f"위에 적힌 길이·구간은 원본 기준이고, 제공 영상의 길이는 그 {factor}배입니다. "
        "모든 시각은 제공 영상(느려진 영상) 기준으로 답하세요. "
        "움직임이 느려 보이는 것은 재생 속도 때문이며 판단 근거가 아닙니다."
        + extra
    )


def _to_origin(parsed, speed: float):
    """느려진 영상 기준 시각 -> 원본 기준 시각."""
    if speed == 1.0:
        return parsed
    if isinstance(parsed, (CoarseResponse, DiagnosticCoarseResponse)):
        cands = [
            c.model_copy(update={
                "at_sec": c.at_sec * speed,
                "span": c.span.model_copy(update={
                    "start_sec": c.span.start_sec * speed,
                    "end_sec": c.span.end_sec * speed,
                }),
            })
            for c in parsed.candidates
        ]
        update: dict = {"candidates": cands}
        if isinstance(parsed, DiagnosticCoarseResponse):
            update["window_reviews"] = [
                w.model_copy(update={"start_sec": w.start_sec * speed,
                                     "end_sec": w.end_sec * speed})
                for w in parsed.window_reviews
            ]
        return parsed.model_copy(update=update)
    if isinstance(parsed, FineResponse):
        def scale(items):
            return [i.model_copy(update={"at_offset_ms": None if i.at_offset_ms is None
                                         else round(i.at_offset_ms * speed)})
                    for i in items]
        update = {"temporal_facts": scale(parsed.temporal_facts)}
        if isinstance(parsed, DiagnosticFineResponse):
            update["decision_basis"] = scale(parsed.decision_basis)
        return parsed.model_copy(update=update)
    raise ProviderPayloadError(f"unexpected response type {type(parsed).__name__}")


class SlowVideoInvoker:
    """StructuredInvoker: 준비 미디어를 speed 배로 늘려 영상으로 보내고 시각을 원본으로 환산."""

    def __init__(self, client, config: GeminiSearchConfig,
                 coarse_speed: float, fine_speed: float) -> None:
        self._client = client
        self._cfg = config
        self._coarse_speed = coarse_speed
        self._fine_speed = fine_speed

    def invoke_structured(self, request: StructuredInvocation) -> ProviderResult:
        coarse = issubclass(request.response_model, (CoarseResponse, DiagnosticCoarseResponse))
        speed = self._coarse_speed if coarse else self._fine_speed
        with tempfile.TemporaryDirectory(prefix="cf_slow_") as td:
            path = request.media.path
            prompt = request.prompt
            if speed != 1.0:
                # MediaPreparer 가 이미 1/fps 배로 늘려 준다(2026-10-01 운영 반영). 그때는 다시 늘리지 않는다.
                if request.media.playback_speed == 1.0:
                    path = Path(td) / "slow.mp4"
                    _slow(request.media.path, path, speed)
                prompt += _note(speed, "Coarse 핵심 시각" in prompt)
            url = "data:video/mp4;base64," + base64.b64encode(path.read_bytes()).decode()
            messages = [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "file", "file": {"file_data": url}},
            ]}]
            started = time.monotonic()
            try:
                comp = self._client.chat.completions.parse(
                    model=self._cfg.model, messages=messages,
                    response_format=request.response_model,
                    reasoning_effort=self._cfg.reasoning_effort,
                    timeout=request.timeout_sec,
                )
            except Exception as exc:  # noqa: BLE001
                from openai import APIError, BadRequestError
                if isinstance(exc, BadRequestError):
                    raise ProviderPayloadError("provider rejected the request") from exc
                if isinstance(exc, APIError):
                    raise ProviderApiError("provider API error") from exc
                raise ProviderPayloadError(f"invoke failed: {exc}") from exc
            latency = round((time.monotonic() - started) * 1000)
            parsed = comp.choices[0].message.parsed
            if parsed is None:
                raise ProviderPayloadError("provider returned no parsed content")
            return ProviderResult(
                _to_origin(parsed, speed),
                _usage_from_completion(getattr(comp, "usage", None)),
                latency,
            )


def _overlaps(span: tuple[float, float], truth: tuple[float, float] | None) -> bool:
    return truth is not None and span[0] < truth[1] and truth[0] < span[1]


def run_condition(client, base_cfg: GeminiSearchConfig, coarse_speed: float,
                  fine_speed: float, timeout: float,
                  profile: DiagnosticProfile = DiagnosticProfile.P3,
                  transport: str = "video") -> dict:
    # 준비 fps = 1/speed -> 늘린 뒤 재생 1초당 원본 프레임 1장(프록시 샘플링과 1:1).
    # image 는 늘리지 않고 그 fps 프레임을 전량 image_url 로 보낸다.
    cfg = replace(base_cfg, coarse_fps=1 / coarse_speed, fine_fps=1 / fine_speed, max_retries=0)
    if transport == "image":
        from gemini_coarse_fine_image_trace import ImageInvoker
        invoker = ImageInvoker(client, cfg)
    else:
        invoker = SlowVideoInvoker(client, cfg, coarse_speed, fine_speed)
    deps = DiagnosticDependencies(invoker, MediaPreparer(cfg), cfg, profile, timeout)
    tag = f"{profile.value}/{transport}/{coarse_speed}x/{fine_speed}x"
    verifs: Counter[str] = Counter()
    cases = []
    invocations = prompt_tok = total_tok = 0
    for cid, fname, dur, event, expected, truth in CASES:
        case = DiagnosticCase(case_id=cid, source=Path(VID) / fname,
                              duration_sec=dur, event_types=(event,))
        res = run_case(case, deps)
        cands, fine = [], []
        for call in res.calls:
            if call.status == "SUCCEEDED":
                invocations += 1
                if call.usage:
                    prompt_tok += call.usage.input_tokens or 0
                    total_tok += call.usage.total_tokens or 0
            if call.stage == "COARSE" and isinstance(call.response, (CoarseResponse, DiagnosticCoarseResponse)):
                for c in sorted(call.response.candidates, key=lambda c: (-c.score, c.at_sec)):
                    span = (round(c.span.start_sec, 2), round(c.span.end_sec, 2))
                    cands.append({"span": span, "at_sec": round(c.at_sec, 2),
                                  "hits_truth": _overlaps(span, truth)})
            if call.stage == "FINE":
                v = getattr(call.response, "verification", None) if call.response else None
                label = v.value if v is not None else f"FAILED:{','.join(call.issue_codes)}"
                verifs[label if v is not None else "FAILED"] += 1
                fine.append(label)
        # 클립 판정: 정답 구간과 겹친 후보가 OBSERVED 면 검출. 음성 클립은 OBSERVED 가 하나라도 있으면 오탐.
        if expected == "OBSERVED":
            detected = any(c["hits_truth"] and i < len(fine) and fine[i] == "OBSERVED"
                           for i, c in enumerate(cands))
            verdict = "HIT" if detected else "MISS"
        else:
            verdict = "FALSE_POSITIVE" if "OBSERVED" in fine else "CORRECT_REJECT"
        cases.append({"case_id": cid, "event": event, "expected": expected, "truth": truth,
                      "candidates": cands, "fine": fine, "verdict": verdict,
                      "issue_codes": sorted({ic for c in res.calls for ic in c.issue_codes})})
        print(f"  [{tag}] {cid:<24} cand={[c['span'] for c in cands]} fine={fine} -> {verdict}")
    return {
        "profile": profile.value, "transport": transport,
        "coarse_speed": coarse_speed, "fine_speed": fine_speed,
        "coarse_fps_prepared": cfg.coarse_fps, "fine_fps_prepared": cfg.fine_fps,
        "invocations": invocations, "verification_counts": dict(verifs),
        "reported_input_tokens": prompt_tok, "reported_total_tokens": total_tok,
        "positives_hit": sum(c["verdict"] == "HIT" for c in cases),
        "negatives_correct": sum(c["verdict"] == "CORRECT_REJECT" for c in cases),
        "cases": cases,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=DEFAULT_ENV)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--timeout-sec", type=float, default=300.0)
    # coarse:fine 배속. 기본 = 1x 기준 + 이미지 trace(coarse 2fps / fine 4fps)와 같은 밀도.
    ap.add_argument("--conditions", default="1:1,0.5:0.25")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--profiles", default="p3")
    ap.add_argument("--transport", choices=("video", "image"), default="video")
    args = ap.parse_args()

    env = load_env_file(args.env)
    base_cfg = GeminiSearchConfig.from_dotenv(env)
    key = env.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit(f"no GEMINI_API_KEY in {args.env}")
    client = importlib.import_module("openai").OpenAI(
        base_url=base_cfg.base_url, api_key=key, max_retries=0, timeout=args.timeout_sec
    )
    runs = []
    for rep in range(args.repeats):
        for cond, prof in ((c, p) for c in args.conditions.split(",")
                           for p in args.profiles.split(",")):
            cs, fs = (float(x) for x in cond.split(":"))
            print(f"=== repeat {rep + 1} / {prof} / {args.transport} / coarse {cs}x, fine {fs}x ===")
            r = run_condition(client, base_cfg, cs, fs, args.timeout_sec,
                              DiagnosticProfile(prof), args.transport)
            r["repeat"] = rep + 1
            runs.append(r)
            print(f"  -> positives {r['positives_hit']}/4, negatives {r['negatives_correct']}/3, "
                  f"fine {r['verification_counts']}, input_tok {r['reported_input_tokens']}, "
                  f"total_tok {r['reported_total_tokens']}")
            if args.out:  # 조건마다 저장해 중간에 끊겨도 남긴다
                args.out.write_text(json.dumps({
                    "config": {"profiles": args.profiles, "transport": args.transport, "model": base_cfg.model,
                               "reasoning_effort": base_cfg.reasoning_effort,
                               "fine_padding_sec": base_cfg.fine_padding_sec},
                    "runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
