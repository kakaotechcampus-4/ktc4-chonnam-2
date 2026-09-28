"""Search 실행 경로의 호출 지연 baseline을 잰다 (#72).

제품과 같은 `build_gemini_search_service()` 경로로 클립별 Coarse를 반복 호출하고,
상위 k개 후보에 Fine을 부른다. 한 줄에 호출 하나씩 JSONL로 남긴다.

- `latency_ms`(ledger)는 마지막으로 성공한 provider 시도 하나의 시간이다.
- `wall_ms`는 호출 바깥에서 잰 시간이다. ffmpeg 전처리·재시도·backoff가 모두 들어간다.
  둘의 차이가 timeout 설계에서 빠지면 안 되는 몫이다.

예외 메시지·provider 응답 본문·API 키는 기록하지 않는다(에러는 type 이름과 issue code만).

    uv run python examples/search_latency_baseline.py \\
        --clip doc/latency/clip_020s.mp4 --repeats 1 --fine-top-k 1 \\
        --out docs/modules/search/experiments/latency-baseline-72/dry-run.jsonl
"""

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from daesingo.common import load_env_file
from daesingo.search import build_gemini_search_service
from daesingo.search.config import GeminiSearchConfig
from daesingo.search.ledger import UsageRecord
from daesingo.search.runs import ContractRef
from daesingo.search.scope import (
    AnalysisScope,
    SearchBudget,
    SearchHint,
    TimelineRef,
    TimelineRelativeTimeRange,
    TimeRangeKind,
    VisualEventType,
)
from daesingo.search.service import SearchService
from daesingo.search.sources import LocalAnalysisSourceResolver, ResolvedAnalysisSource

ServiceBuilder = Callable[[LocalAnalysisSourceResolver], SearchService]


@dataclass(frozen=True, slots=True)
class Clip:
    label: str
    path: Path
    duration_sec: float
    byte_size: int


def probe_clip(path: Path) -> Clip:
    run = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return Clip(path.stem, path, float(run.stdout.strip()), path.stat().st_size)


def _resolver(clip: Clip) -> LocalAnalysisSourceResolver:
    source = ResolvedAnalysisSource(
        ContractRef(kind="analysis_source", ref=clip.label), clip.duration_sec, clip.label, 1
    )
    return LocalAnalysisSourceResolver(
        {clip.label: (source,)}, {clip.label: source}, {clip.label: clip.path}
    )


def _scope(clip: Clip, max_latency_sec: int) -> AnalysisScope:
    return AnalysisScope(
        scope_id=clip.label,
        time_ranges=(
            TimelineRelativeTimeRange(
                kind=TimeRangeKind.TIMELINE_RELATIVE,
                timeline_ref=TimelineRef(timeline_id=clip.label, revision=1),
                start_ms=0,
                end_ms=round(clip.duration_sec * 1000),
            ),
        ),
        target_event_types=tuple(VisualEventType),
        hint=SearchHint(vehicle=None, free_text=None),
        # 비용 상한은 Search가 아직 집행하지 않는다(KRW↔USD 미결). 측정 규모로 통제한다.
        budget=SearchBudget(max_cost_krw=100_000, max_latency_sec=max_latency_sec),
        contract_version="1.1.0",
    )


def _usage(records: tuple[UsageRecord, ...]) -> dict[str, object]:
    """이번 호출이 ledger에 남긴 기록. 실패하면 0건일 수 있다."""
    if not records:
        return {"ledger_records": 0}
    (record, *rest) = records
    fact = record.as_eval_fact()
    return {
        "ledger_records": 1 + len(rest),
        "latency_ms": fact["latency_ms"],
        "prepared_media_bytes": fact["prepared_media_bytes"],
        "prepared_duration_ms": fact["prepared_duration_ms"],
        "input_tokens": fact["input_tokens"],
        "output_tokens": fact["output_tokens"],
        "thought_tokens": fact["thought_tokens"],
        "prompt_version": fact["prompt_version"],
    }


def measure(
    clips: list[Clip],
    repeats: int,
    fine_top_k: int,
    max_latency_sec: int,
    build_service: ServiceBuilder,
    clock: Callable[[], float] = perf_counter,
) -> Iterator[dict[str, object]]:
    """반복 × 클립마다 새 service로 Coarse 1회 + 상위 k개 Fine을 부르고 호출별 행을 낸다.

    회차 안에서 클립을 번갈아 돌린다 — 시간대에 따른 provider 편차가 길이 차이로
    보이지 않게 하려는 것이다.
    """
    for repeat in range(1, repeats + 1):
        for clip in clips:
            base = {
                "clip": clip.label,
                "clip_duration_sec": clip.duration_sec,
                "clip_bytes": clip.byte_size,
                "repeat": repeat,
            }
            service = build_service(_resolver(clip))
            seen = 0
            started_at = datetime.now(UTC).isoformat()
            t0 = clock()
            try:
                result = service.search_candidates(_scope(clip, max_latency_sec))
            except Exception as error:  # noqa: BLE001 — 측정은 실패 종류를 기록하고 계속한다
                yield {**base, "stage": "coarse", "started_at": started_at,
                       "wall_ms": round((clock() - t0) * 1000),
                       "error_type": type(error).__name__,
                       **_usage(service.ledger.records())}
                continue
            wall_ms = round((clock() - t0) * 1000)
            records = service.ledger.records()
            seen = len(records)
            run = result.analysis_run
            yield {**base, "stage": "coarse", "started_at": started_at, "wall_ms": wall_ms,
                   "outcome": run.outcome.value,
                   "issues": [f"{issue.kind.value}:{issue.code}" for issue in run.issues],
                   "candidates": len(result.candidates), **_usage(records)}

            input_ref = ContractRef(kind="analysis_source", ref=clip.label)
            for candidate in sorted(result.candidates, key=lambda c: c.rank)[:fine_top_k]:
                row = {**base, "stage": "fine", "rank": candidate.rank,
                       "span_ms": candidate.span.end_ms - candidate.span.start_ms,
                       "started_at": datetime.now(UTC).isoformat()}
                t1 = clock()
                try:
                    visual = service.verify_visual(
                        input_ref,
                        candidate,
                        event_type=candidate.event_type_hint
                        or VisualEventType.SOLID_LINE_LANE_CHANGE,
                    )
                    row["verification"] = visual.visual_evidence.verification.value
                except Exception as error:  # noqa: BLE001
                    row["error_type"] = type(error).__name__
                row["wall_ms"] = round((clock() - t1) * 1000)
                records = service.ledger.records()
                row.update(_usage(records[seen:]))
                seen = len(records)
                yield row


def _git_commit() -> str:
    run = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True, timeout=10, check=False)
    return run.stdout.strip() or "unknown"


def meta(config: GeminiSearchConfig, args: argparse.Namespace) -> dict[str, object]:
    return {
        "stage": "meta",
        "recorded_at": datetime.now(UTC).isoformat(),
        "commit": _git_commit(),
        "model": config.model,
        "reasoning_effort": config.reasoning_effort,
        "coarse_fps": config.coarse_fps,
        "fine_fps": config.fine_fps,
        "fine_padding_sec": config.fine_padding_sec,
        "max_retries": config.max_retries,
        "retry_base_sec": config.retry_base_sec,
        "max_inline_media_bytes": config.max_inline_media_bytes,
        "repeats": args.repeats,
        "fine_top_k": args.fine_top_k,
        "max_latency_sec": args.max_latency_sec,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--clip", type=Path, action="append", required=True)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--fine-top-k", type=int, default=1)
    parser.add_argument("--max-latency-sec", type=int, default=600)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    api_key = load_env_file().get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("GEMINI_API_KEY is not set", file=sys.stderr)
        return 2
    clips = [probe_clip(path) for path in args.clip]
    config = GeminiSearchConfig.from_dotenv()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("a", encoding="utf-8") as out:
        out.write(json.dumps(meta(config, args), ensure_ascii=False) + "\n")
        out.write(json.dumps({"stage": "clips", "clips": [
            {**asdict(clip), "path": clip.path.name} for clip in clips
        ]}, ensure_ascii=False) + "\n")
        for row in measure(clips, args.repeats, args.fine_top_k, args.max_latency_sec,
                           lambda resolver: build_gemini_search_service(api_key, resolver)):
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"{row['clip']} r{row['repeat']} {row['stage']}"
                  f" wall={row.get('wall_ms')}ms latency={row.get('latency_ms')}ms"
                  f" {row.get('outcome') or row.get('verification') or row.get('error_type')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
