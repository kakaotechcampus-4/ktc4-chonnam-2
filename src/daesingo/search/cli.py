import argparse
import math
import sys
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from daesingo.common import load_env_file

from . import build_gemini_search_service, search_candidates
from .errors import UnsafeGeminiBaseUrlError
from .report import render_report
from .scope import (
    AnalysisScope,
    SearchBudget,
    SearchHint,
    TimelineRef,
    TimelineRelativeTimeRange,
    TimeRangeKind,
    VisualEventType,
)
from .smoke import (
    MissingSmokeApiKeyError,
    SmokeRunOptions,
    build_smoke_service,
    failed_input_report,
    run_smoke,
)
from .smoke_fixture import SmokeProviderFixture
from .smoke_models import SmokeFailureStage, SmokeStatus
from .sources import ResolvedAnalysisSource, StaticAnalysisSourceResolver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m daesingo.search")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("coarse", "fine", "smoke"):
        command = subparsers.add_parser(name)
        command.add_argument("--source", type=Path, required=True)
        command.add_argument("--duration-sec", type=float, required=True)
        command.add_argument(
            "--event-type", action="append", choices=[e.value for e in VisualEventType]
        )
        if name == "smoke":
            command.add_argument("--provider-fixture", type=Path)
            command.add_argument("--timeout-sec", type=float, default=60.0)
            command.add_argument(
                "--max-cost-usd", type=Decimal, default=Decimal("1.00")
            )
    args = parser.parse_args(argv)
    if args.command == "smoke":
        return _run_smoke_command(args)
    api_key = load_env_file().get("GEMINI_API_KEY", "").strip()
    if args.command == "fine":
        print(
            "failure: fine requires an explicit candidate from coarse", file=sys.stderr
        )
        return 2
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
        print(
            "failure: fine requires an explicit candidate from coarse", file=sys.stderr
        )
        return 2
    print(render_report(result))
    return 0


def _run_smoke_command(args: argparse.Namespace) -> int:
    try:
        if (
            not args.source.is_file()
            or not math.isfinite(args.duration_sec)
            or not math.isfinite(args.timeout_sec)
            or not args.max_cost_usd.is_finite()
            or args.duration_sec <= 0
            or args.timeout_sec <= 0
            or args.max_cost_usd < 0
        ):
            report = failed_input_report()
        else:
            selected = tuple(
                VisualEventType(item) for item in (args.event_type or [])
            ) or tuple(VisualEventType)
            options = SmokeRunOptions(
                source=args.source,
                duration_sec=args.duration_sec,
                event_types=selected,
                timeout_sec=args.timeout_sec,
                max_cost_usd=args.max_cost_usd,
            )
            fixture = (
                SmokeProviderFixture.from_path(args.provider_fixture)
                if args.provider_fixture is not None
                else None
            )
            api_key = None
            if fixture is None:
                api_key = load_env_file().get("GEMINI_API_KEY", "").strip() or None
            service, config = build_smoke_service(options, api_key, fixture)
            report = run_smoke(options, service, config)
    except MissingSmokeApiKeyError:
        report = failed_input_report()
    except (OSError, UnicodeError, ValidationError, UnsafeGeminiBaseUrlError):
        report = failed_input_report()
    print(render_report(report))
    if report.status is SmokeStatus.SUCCEEDED:
        return 0
    return 2 if report.failure_stage is SmokeFailureStage.INPUT else 1
