import argparse
import os
import sys
from pathlib import Path

from . import build_gemini_search_service, search_candidates, verify_visual
from .report import render_report
from .runs import ContractRef
from .scope import (
    AnalysisScope,
    SearchBudget,
    SearchHint,
    TimelineRef,
    TimelineRelativeTimeRange,
    TimeRangeKind,
    VisualEventType,
)
from .sources import ResolvedAnalysisSource, StaticAnalysisSourceResolver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m daesingo.search")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("coarse", "fine"):
        command = subparsers.add_parser(name)
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--duration-sec", type=float, required=True)
        command.add_argument(
            "--event-type", action="append", choices=[e.value for e in VisualEventType]
        )
    args = parser.parse_args(argv)
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("실패: GEMINI_API_KEY is not set", file=sys.stderr)
        return 2
    if not args.source.is_file():
        print(f"실패: source file does not exist ({args.source})", file=sys.stderr)
        return 2

    source = ResolvedAnalysisSource("cli", args.source, args.duration_sec, "cli", 1)
    resolver = StaticAnalysisSourceResolver({"cli": (source,)}, {"cli": source})
    service = build_gemini_search_service(api_key, resolver)
    selected = tuple(
        VisualEventType(item) for item in (args.event_type or [])
    ) or tuple(VisualEventType)
    if args.command == "coarse":
        scope = AnalysisScope(
            scope_id="cli",
            time_ranges=(
                TimelineRelativeTimeRange(
                    kind=TimeRangeKind.TIMELINE_RELATIVE,
                    timeline_ref=TimelineRef(timeline_id="cli", revision=1),
                    start_ms=0,
                    end_ms=round(args.duration_sec * 1000),
                ),
            ),
            target_event_types=selected,
            hint=SearchHint(vehicle=None, free_text=None),
            budget=SearchBudget(max_cost_krw=100_000, max_latency_sec=3600),
            contract_version="1.1.0",
        )
        result = search_candidates(scope, service=service)
    else:
        result = verify_visual(
            ContractRef(kind="analysis_source", ref="cli"),
            service=service,
            event_type=selected[0],
        )
    print(render_report(result))
    return 0
