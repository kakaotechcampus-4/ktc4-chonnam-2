#!/usr/bin/env python3
"""Run one shared Mock Pack scenario through the evidence public API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daesingo.evidence import assemble  # noqa: E402
from evidence_fixture_support import load_evidence_request  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=("happy_001", "partial_001"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    outputs = assemble(load_evidence_request(args.scenario))
    args.output.mkdir(parents=True, exist_ok=True)
    written = []
    for name, value in outputs.items():
        if value is None:
            continue
        path = args.output / f"{name}.{args.scenario}.json"
        with path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        written.append(path.name)
    print(
        json.dumps(
            {
                "scenario": f"scenario_{args.scenario}",
                "written": written,
                "report_package_generated": outputs["report_package"] is not None,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
