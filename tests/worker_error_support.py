"""Adversarial exceptions shared by Worker log-boundary tests."""

PRIVATE = (
    "/private/worker/input.mp4", "SELECT secret FROM private_jobs",
    "PRIVATE_PROVIDER_PAYLOAD", "credential_SENTINEL_464",
    "PRIVATE_CAUSE", "PRIVATE_CONTEXT", "private.module.path",
)

NAMES = [
    ("RuntimeError", "RuntimeError"), ("InvalidTransition", "InvalidTransition"),
    ("_FrameCoverageError", "_FrameCoverageError"), ("_", "_"),
    ("A" + "9_" * 31 + "Z", "A" + "9_" * 31 + "Z"),
    ("", None), ("A" * 65, None), ("A" * 128, None),
    ("Outer.Inner", None), ("local.<locals>.Error", None),
    ("Bad Name", None), ("Bad\nName", None), ("Error\n", None),
    ("오류", None), ("Érror", None), ("1Error", None),
    ("/private/Error", None), ("Error-Name", None),
]


def private_error(qualname="_FrameCoverageError"):
    def forbidden(self):
        raise AssertionError("exception text must never be inspected")

    cls = type("PrivateError", (Exception,), {
        "__qualname__": qualname, "__module__": PRIVATE[-1],
        "__str__": forbidden, "__repr__": forbidden,
    })
    error = cls(*PRIVATE[:4])
    error.__cause__ = RuntimeError(PRIVATE[4])
    error.__context__ = ValueError(PRIVATE[5])
    return error


def assert_private_absent(raw):
    assert all(value not in raw for value in PRIVATE)
