"""Runtime-owned injection into existing synchronous media constructors.

No Recording profile/encoding policy lives here. Composition supplies the
existing factory and arguments when a real media capability is registered.
"""
from functools import wraps


class MediaRoot:
    def __init__(self, scanner):
        if scanner.kind != 'temp':
            raise ValueError('temp scanner required')
        self.scanner = scanner
        self.root = scanner.root

    def materializer(self, factory, /, *args, **kwargs):
        # Override rather than allow an invocation to silently use global /tmp.
        delegate = factory(*args, **kwargs, temp_root=self.root)
        return _LeasedMaterializer(delegate, self.scanner)


class _LeasedMaterializer:
    def __init__(self, delegate, scanner):
        self._delegate, self._scanner = delegate, scanner

    def __getattr__(self, name):
        value = getattr(self._delegate, name)
        if not callable(value):
            return value
        @wraps(value)
        def invoke(*args, **kwargs):
            # The explicit root is provisioned by deployment. Never mkdir an
            # arbitrary configured ancestor or silently fall back to global tmp.
            with self._scanner.in_use():
                return value(*args, **kwargs)
        return invoke
