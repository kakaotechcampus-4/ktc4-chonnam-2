"""Recording 공개 capability의 machine-readable 오류."""

from __future__ import annotations


class RecordingCapabilityError(Exception):
    """실패 taxonomy의 kind 확정 전에도 code를 보존하는 공개 오류."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
