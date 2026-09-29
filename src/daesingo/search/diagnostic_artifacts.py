"""Local-only artifact writing and deterministic transport fixtures."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

from .diagnostic_models import DiagnosticRunResult
from .provider import ProviderResult, StructuredInvocation
from .schemas import FineResponse, WireModel
from .smoke_errors import ProviderPayloadError
from .usage import ProviderUsage


class FixtureReply(WireModel):
    content: str | None = None
    error_code: Literal["PROVIDER_PAYLOAD"] | None = None


class DiagnosticFixture(WireModel):
    responses: tuple[FixtureReply, ...]


@dataclass(slots=True)
class FixtureInvoker:
    fixture: DiagnosticFixture
    index: int = 0

    def invoke_structured[T: BaseModel](
        self, request: StructuredInvocation[T]
    ) -> ProviderResult[T]:
        if self.index >= len(self.fixture.responses):
            raise ProviderPayloadError("fixture response missing")
        reply = self.fixture.responses[self.index]
        self.index += 1
        if reply.error_code is not None or reply.content is None:
            raise ProviderPayloadError("fixture payload failure")
        try:
            response = request.response_model.model_validate_json(reply.content)
        except ValidationError as error:
            raise ProviderPayloadError("fixture payload failure") from error
        return ProviderResult(response, ProviderUsage(10, 20, 0, 30), 0)


@dataclass(frozen=True, slots=True)
class ArtifactPaths:
    result: Path
    report: Path


class ArtifactLocationError(Exception):
    """The proposed local trace directory is not Git-ignored."""


def prepare_artifact_directory(root: Path) -> Path:
    directory = root.resolve() / ".superpowers" / "decision-trace"
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", str(directory)],
        cwd=root,
        capture_output=True,
    )
    if ignored.returncode != 0:
        raise ArtifactLocationError("local trace directory must be Git-ignored")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def store_result(result: DiagnosticRunResult, root: Path) -> ArtifactPaths:
    directory = prepare_artifact_directory(root)
    paths = ArtifactPaths(
        directory / (result.context.run_id + ".json"),
        directory / (result.context.run_id + ".md"),
    )
    with paths.result.open("x", encoding="utf-8") as stream:
        stream.write(result.model_dump_json(indent=2))
    lines = [
        "# Search 영상 판단 근거 진단",
        "",
        "이 자료는 모델이 보고한 관찰이며 사람 검증 전이다. 운영 증거와 성능 채택 근거가 아니다.",
        "",
        "## 실행 조건",
        "",
        "```json",
        result.context.model_dump_json(indent=2),
        "```",
    ]
    for case in result.cases:
        lines.extend(
            ["", "## " + case.case_id, "", "입력 SHA-256: " + case.input_sha256]
        )
        if case.input_issue_code is not None:
            lines.extend(["", "입력 오류: " + case.input_issue_code])
        for call in case.calls:
            lines.extend(
                [
                    "",
                    "### " + call.stage + " / " + str(call.candidate_index),
                    "",
                    "```json",
                    call.model_dump_json(indent=2),
                    "```",
                ]
            )
    with paths.report.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    return paths


def safe_summary(
    result: DiagnosticRunResult, paths: ArtifactPaths
) -> dict[str, str | int | dict[str, int]]:
    calls = [call for case in result.cases for call in case.calls]
    invoked = [call for call in calls if call.invocation_started]
    states: dict[str, int] = {}
    for call in calls:
        if isinstance(call.response, FineResponse):
            key = call.response.verification.value
            states[key] = states.get(key, 0) + 1
    return {
        "schema_version": result.schema_version,
        "mode": result.context.mode,
        "profile": result.context.profile.value,
        "cases": len(result.cases),
        "invocations": len(invoked),
        "failures": sum(call.status == "FAILED" for call in calls)
        + sum(case.input_issue_code is not None for case in result.cases),
        "diagnostic_issues": sum(len(call.issue_codes) for call in calls),
        "fine_verification_counts": states,
        "reported_total_tokens": sum(
            call.usage.total_tokens or 0 for call in invoked if call.usage is not None
        ),
        "usage_unknown_invocations": sum(
            call.usage is None or call.usage.total_tokens is None for call in invoked
        ),
        "result_file": str(paths.result),
        "report_file": str(paths.report),
    }
