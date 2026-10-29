"""Pinned no-follow directory traversal for local POSIX and Windows volumes.

Windows pins every ancestor without FILE_SHARE_DELETE and deletes an opened
leaf by handle. POSIX uses openat/O_NOFOLLOW and unlinkat, with Runtime writers
coordinated by the root lease. No recursive pathname deletion is used.
"""
from contextlib import contextmanager, ExitStack
import os
from pathlib import Path
import re
import stat


class UnsafePath(OSError):
    pass


def checked_path(value):
    path = Path(value)
    if '..' in path.parts:
        raise ValueError('cleanup root must not contain parent traversal')
    return Path(os.path.abspath(path))


def configuration_path(value):
    """Canonicalize through pinned existing ancestors, never resolve links.

    Missing suffixes are permitted only after validating their components. All
    configuration relationships and protected scan paths use this same form.
    Runtime traversal still pins again; deletion never resolves a candidate.
    """
    try:
        path = Path(value)
        if os.name == 'nt':
            # Win32 abspath may discard a trailing dot before it reaches the
            # missing-suffix check. Reject ambiguous raw components first.
            _windows_components(path.parts[1:] if path.anchor else path.parts)
        return _configuration_path(checked_path(path))
    except OSError:
        raise ValueError('unverifiable cleanup root') from None


def ordinary(value):
    return (not stat.S_ISLNK(value.st_mode)
            and not getattr(value, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def identity(value):
    return value.st_dev, value.st_ino


def version(value):
    return identity(value), value.st_size, value.st_mtime_ns, value.st_ctime_ns


def tool_directory(directory):
    """Return a tool-openable spelling from an already pinned directory.

    Ask Windows for its DOS name; never infer a drive from a Volume GUID.
    Volumes without a DOS name fail closed. The caller must pin and compare
    the returned path to the canonical identity before using it.
    """
    if os.name != 'nt':
        return directory.path
    size = _final_name(directory.descriptor, None, 0, 0)  # VOLUME_NAME_DOS
    if not size:
        raise UnsafePath('unverifiable tool directory')
    buffer = ctypes.create_unicode_buffer(size + 1)
    used = _final_name(directory.descriptor, buffer, len(buffer), 0)
    if not used or used >= len(buffer):
        raise UnsafePath('unverifiable tool directory')
    path = Path(buffer.value)
    if not re.fullmatch(r'\\\\\?\\[a-zA-Z]:\\', path.anchor):
        raise UnsafePath('unsupported tool namespace')
    # Only the OS-returned extended DOS prefix is removed, never a GUID.
    return Path(str(path)[4:])


if os.name == 'nt':
    import ctypes
    from ctypes import wintypes
    import msvcrt

    _kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    _create = _kernel.CreateFileW
    _create.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    _create.restype = wintypes.HANDLE
    _close = _kernel.CloseHandle
    _close.argtypes = (wintypes.HANDLE,)
    _close.restype = wintypes.BOOL
    _dispose = _kernel.SetFileInformationByHandle
    _dispose.argtypes = (wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD)
    _dispose.restype = wintypes.BOOL
    _final_name = _kernel.GetFinalPathNameByHandleW
    _final_name.argtypes = (wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD)
    _final_name.restype = wintypes.DWORD

    def _canonical_directory(directory):
        # FILE_NAME_NORMALIZED | VOLUME_NAME_GUID unifies DOS, extended and
        # short names without reopening or following a pathname. Refuse remote
        # or other namespaces rather than guessing their alias relationships.
        size = _final_name(directory.descriptor, None, 0, 1)
        if not size:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_unicode_buffer(size + 1)
        used = _final_name(directory.descriptor, buffer, len(buffer), 1)
        if not used or used >= len(buffer):
            raise UnsafePath('unverifiable canonical directory')
        path = Path(buffer.value)
        if not re.fullmatch(r'\\\\\?\\Volume\{[0-9a-fA-F-]+\}\\', path.anchor):
            raise UnsafePath('unsupported cleanup namespace')
        return path

    def _handle(path, *, delete=False, lock=False):
        # OPEN_REPARSE_POINT also opens links themselves, so inspect after pin.
        access = 0xC0000000 if lock else 0x80 | (0x10000 if delete else 0)
        # A reader with FILE_SHARE_DELETE could otherwise leave a successfully
        # marked file pending until it closes. Refuse every live leaf reader.
        share = 3 if lock or path.is_dir() else (0 if delete else 1)
        handle = _create(str(path), access, share, None, 4 if lock else 3,
                         0x02000000 | 0x00200000, None)
        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not ordinary(path.lstat()):
                raise UnsafePath('reparse point refused')
        except BaseException:
            _close(handle)
            raise
        return handle


class Pinned:
    def __init__(self, path, descriptor):
        self.path, self.descriptor = path, descriptor

    def close(self):
        if os.name == 'nt':
            _close(self.descriptor)
        else:
            os.close(self.descriptor)

    def stat(self):
        return self.path.lstat() if os.name == 'nt' else os.fstat(self.descriptor)

    def entries(self):
        """Stream one metadata result at a time; None denotes one failed stat.

        Concurrent disappearance is normal and omitted. Other metadata OSError
        is counted by the scanner without retaining raw exception text. Failure
        to enumerate the directory itself still belongs to that directory.
        """
        with os.scandir(self.path if os.name == 'nt' else self.descriptor) as entries:
            # Windows DirEntry.stat reports st_ino=0; lstat supplies the actual
            # file identity used again after opening the deletion handle.
            for item in entries:
                try:
                    snapshot = self.lstat(item.name)
                except FileNotFoundError:
                    continue
                except OSError:
                    snapshot = None
                yield item.name, snapshot

    def is_empty(self):
        # The bounded name-only check neither restats failures nor materializes
        # the remaining directory. Actual rmdir still decides atomically.
        with os.scandir(self.path if os.name == 'nt' else self.descriptor) as entries:
            return next(iter(entries), None) is None

    def lstat(self, name):
        return ((self.path/name).lstat() if os.name == 'nt'
                else os.stat(name, dir_fd=self.descriptor, follow_symlinks=False))

    @contextmanager
    def child(self, name, *, delete=False, directory=False):
        if name in ('.', '..') or Path(name).name != name:
            raise UnsafePath('invalid child name')
        path = self.path/name
        if os.name == 'nt':
            descriptor = _handle(path, delete=delete)
        else:
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if directory:
                flags |= os.O_DIRECTORY
            descriptor = os.open(name, flags, dir_fd=self.descriptor)
        child = Pinned(path, descriptor)
        try:
            value = child.stat()
            if not ordinary(value) or (directory and not stat.S_ISDIR(value.st_mode)):
                raise UnsafePath('non-directory or link refused')
            yield child
        finally:
            child.close()

    def remove(self, name, child, *, directory=False):
        if os.name == 'nt':
            delete = wintypes.BOOL(True)
            if not _dispose(child.descriptor, 4, ctypes.byref(delete), ctypes.sizeof(delete)):
                raise ctypes.WinError(ctypes.get_last_error())
        elif directory:
            os.rmdir(name, dir_fd=self.descriptor)
        else:
            os.unlink(name, dir_fd=self.descriptor)

    @contextmanager
    def lock_file(self, name):
        if os.name == 'nt':
            handle = _handle(self.path/name, lock=True)
            try:
                descriptor = msvcrt.open_osfhandle(handle, os.O_RDWR | os.O_BINARY)
            except BaseException:
                _close(handle)
                raise
        else:
            descriptor = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                                 0o600, dir_fd=self.descriptor)
        try:
            value = os.fstat(descriptor)
            if not stat.S_ISREG(value.st_mode) or value.st_nlink != 1:
                raise UnsafePath('unsafe lease file')
            yield descriptor
        finally:
            os.close(descriptor)


@contextmanager
def pin_root(path):
    path = checked_path(path)
    with ExitStack() as stack:
        if os.name == 'nt':
            descriptor = _handle(Path(path.anchor))
        else:
            descriptor = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        current = Pinned(Path(path.anchor), descriptor)
        stack.callback(current.close)
        for part in path.parts[1:]:
            current = stack.enter_context(current.child(part, directory=True))
        yield current


def _windows_components(parts):
    for part in parts:
        if (part.endswith(('.', ' ')) or any(c in part for c in '<>:"|?*\x00')
                or re.fullmatch(r'(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I)):
            raise UnsafePath('ambiguous cleanup component')


def _configuration_path(path):
    parts = path.parts[1:]
    if os.name == 'nt':
        # Network shares/device namespaces need a separate ownership model.
        # Check before opening them; no implicit network access at composition.
        if not re.fullmatch(r'(?:[a-zA-Z]:\\|\\\\\?\\[a-zA-Z]:\\|\\\\\?\\Volume\{[0-9a-fA-F-]+\}\\)', path.anchor):
            raise UnsafePath('unsupported cleanup namespace')
    with ExitStack() as stack:
        root = stack.enter_context(pin_root(Path(path.anchor)))
        if os.name != 'nt':
            # Exactly two leading slashes may have special meaning on POSIX.
            # Collapse them only after the OS proves both root handles equal.
            single = stack.enter_context(pin_root(Path('/')))
            if identity(root.stat()) != identity(single.stat()):
                raise UnsafePath('ambiguous cleanup anchor')
            root.path = Path('/')
        current = root
        remainder = ()
        for offset, part in enumerate(parts):
            try:
                current = stack.enter_context(current.child(part, directory=True))
            except FileNotFoundError:
                remainder = parts[offset:]
                break
        if os.name == 'nt':
            # An absent 8.3 component has no verified long-name identity yet.
            if any('~' in part for part in remainder):
                raise UnsafePath('unverifiable short-name suffix')
            canonical = _canonical_directory(current)
        else:
            canonical = current.path
        return canonical.joinpath(*remainder)
