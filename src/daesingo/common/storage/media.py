"""Runtime-owned injection into existing synchronous media constructors.

No Recording profile/encoding policy lives here. Composition supplies the
existing factory and arguments when a real media capability is registered.
"""
from contextlib import contextmanager, ExitStack
from functools import wraps
import re

from ._filesystem import (
    UnsafePath, configuration_path, identity, pin_root, tool_directory,
)


class MediaRoot:
    def __init__(self, scanner, *, public_root=None):
        if scanner.kind != 'temp':
            raise ValueError('temp scanner required')
        self.scanner = scanner
        self.root = scanner.root
        self._configured_root = scanner.configured_root
        self._identity_root = configuration_path(scanner.root)
        self.public_root = public_root

    @contextmanager
    def _pinned_tool_root(self):
        with ExitStack() as stack:
            try:
                configured = stack.enter_context(pin_root(self._configured_root))
                canonical = stack.enter_context(pin_root(self._identity_root))
                if identity(configured.stat()) != identity(canonical.stat()):
                    raise UnsafePath('different media roots')
                path = tool_directory(configured)
                tool = stack.enter_context(pin_root(path))
                if identity(tool.stat()) != identity(canonical.stat()):
                    raise UnsafePath('different tool root')
            except (OSError, ValueError):
                raise UnsafePath('unverifiable media root') from None
            # Keep every ancestor pinned through tool execution and temp I/O.
            from daesingo.common.public_runtime.temporary import temporary_root
            scoped = temporary_root.get()
            if scoped is not None:
                with pin_root(self.public_root if self.public_root is not None else path) as expected, pin_root(scoped.parent) as actual:
                    if (identity(expected.stat()) != identity(actual.stat())
                            or re.fullmatch(r"a1-[0-9a-f]{32}", scoped.name) is None):
                        raise UnsafePath("invalid scoped temp root")
                    with actual.child(scoped.name, directory=True) as owned:
                        yield tool_directory(owned)
            else:
                yield path

    def materializer(self, factory, /, *args, **kwargs):
        # Override rather than allow an invocation to silently use global /tmp.
        with self._pinned_tool_root() as tool_root:
            delegate = factory(*args, **kwargs, temp_root=tool_root)
        return _LeasedMaterializer(delegate, self, tool_root)

    @contextmanager
    def detached_temp(self):
        """Pin/lease the configured root while creating an anonymous media file."""
        with self._pinned_tool_root() as tool_root, self.scanner.in_use():
            yield tool_root


class _LeasedMaterializer:
    def __init__(self, delegate, media, tool_root):
        self._delegate, self._media, self._tool_root = delegate, media, tool_root

    def __getattr__(self, name):
        value = getattr(self._delegate, name)
        if not callable(value):
            return value
        @wraps(value)
        def invoke(*args, **kwargs):
            # The explicit root is provisioned by deployment. Never mkdir an
            # arbitrary configured ancestor or silently fall back to global tmp.
            with self._media._pinned_tool_root() as tool_root, self._media.scanner.in_use():
                if tool_root != self._tool_root:
                    raise UnsafePath('unverifiable media root')
                return value(*args, **kwargs)
        return invoke
