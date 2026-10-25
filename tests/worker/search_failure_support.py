"""Port double while #403 is unmerged; no Search taxonomy implementation here."""


class SuccessfulSearchPolicy:
    """Only successful capability fixtures are allowed to use this double."""

    def failure_kind_for_intent(self, result):
        assert result.status in {"OK", "ABSTAINED"}
        return None

    def failure_kind_for_run(self, run):
        assert run.outcome in {"SUCCEEDED", "PARTIAL"}
        return None

    def failure_kind_for_error(self, error):
        raise AssertionError("success-only fixture unexpectedly failed") from error
