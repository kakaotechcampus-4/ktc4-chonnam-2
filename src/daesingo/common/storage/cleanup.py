"""B-C1/B-C3 cleanup: aged Runtime residues only, never published media."""
from contextlib import closing, contextmanager
from contextvars import Context
from dataclasses import dataclass
import math
import os
import re
import stat
from threading import Event, Lock, Thread
import time

from ._filesystem import checked_path, configuration_path, identity, ordinary, pin_root, version
from daesingo.common.logging import log_event_best_effort

# Existing tempfile producers use these prefixes and Python's eight-character
# [a-z0-9_] suffix. Prefix lookalikes and arbitrary root files are not evidence
# of Runtime ownership. Keep this aligned if the producer naming ever changes.
_STAGING = re.compile(r'upload-[a-z0-9_]{8}\Z')
_TEMP = re.compile(r'recording-(?:analysis|chain)-[a-z0-9_]{8}\Z')


@dataclass
class ScanResult:
    # count counts files (including zero-byte files), not empty directories.
    count: int = 0
    bytes: int = 0
    failed: int = 0


@contextmanager
def _lease(root, kind, *, exclusive, blocking):
    with pin_root(root) as directory, directory.lock_file('.runtime-cleanup-' + kind + '.lock') as fd:
        acquired = False
        try:
            while True:
                try:
                    if os.name == 'nt':
                        import msvcrt
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK if exclusive else msvcrt.LK_NBRLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                    acquired = True
                    break
                except (BlockingIOError, PermissionError):
                    if not blocking:
                        break
                    time.sleep(.01)
            yield acquired
        finally:
            if acquired:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)


def _delete_file(parent, name, snapshot, cutoff):
    with parent.child(name, delete=True) as child:
        current = child.stat()
        if (not stat.S_ISREG(current.st_mode) or not ordinary(current)
                or current.st_nlink != 1 or version(current) != version(snapshot)
                or current.st_mtime_ns >= cutoff):
            return None
        # POSIX writers coordinate through the root lease. Recheck the directory
        # entry too: an external replacement must not be confused with this fd.
        if version(parent.lstat(name)) != version(current):
            return None
        parent.remove(name, child)
        size = current.st_size
    return size


class CleanupScanner:
    def __init__(self, *, root, kind, age_sec, now=time.time, lease_root=None,
                 protected_paths=(), configured_root=None):
        if kind not in ('staging', 'temp') or not math.isfinite(age_sec) or age_sec <= 0:
            raise ValueError('invalid cleanup settings')
        protected_paths = tuple(protected_paths)
        # A protected scanner must use the configuration's OS-confirmed form
        # on both sides. Never canonicalize a deletion candidate during a scan.
        path = configuration_path if protected_paths else checked_path
        self.configured_root = checked_path(root if configured_root is None else configured_root)
        self.root = path(root)
        self.lease_root = path(lease_root) if lease_root is not None else self.root
        self.protected_paths = tuple(path(value) for value in protected_paths)
        self.kind, self.age_sec, self.now = kind, age_sec, now
        self._scan_lock = Lock()

    @contextmanager
    def in_use(self):
        """Cover producer creation through final use/close; released on crash.

        Shared leases permit concurrent producers; exclusive scanners skip live
        roots. Never unlink a lease file: its inode is the cross-process identity.
        """
        with _lease(self.lease_root, self.kind, exclusive=False, blocking=True):
            yield

    def scan(self):
        result = ScanResult()
        if not self._scan_lock.acquire(blocking=False):
            return result
        try:
            cutoff = int((self.now()-self.age_sec)*1_000_000_000)
            with _lease(self.lease_root, self.kind, exclusive=True, blocking=False) as acquired:
                if acquired:
                    with pin_root(self.root) as root:
                        self._walk(root, cutoff, result, top=True)
        except FileNotFoundError:
            pass
        except OSError:
            result.failed += 1

        finally:
            self._scan_lock.release()
        return result

    def _walk(self, parent, cutoff, result, *, top=False):
        with closing(parent.entries()) as entries:
            for name, snapshot in entries:
                if snapshot is None:
                    result.failed += 1
                    continue
                if top:
                    if self.kind == 'staging':
                        eligible = _STAGING.fullmatch(name) and stat.S_ISREG(snapshot.st_mode)
                    else:
                        eligible = _TEMP.fullmatch(name) and stat.S_ISDIR(snapshot.st_mode)
                    if not eligible:
                        continue
                self._entry(parent, name, snapshot, cutoff, result)

    def _entry(self, parent, name, snapshot, cutoff, result):
        path = parent.path/name
        # A temp root may enclose media_root. Skip the complete overlapping
        # branch, including ancestors of publish, before opening or deleting it.
        # This also preserves an empty publish subtree; no registration query
        # or orphan-publish policy is involved.
        if any(path == protected or path in protected.parents or protected in path.parents
               for protected in self.protected_paths):
            return
        if not ordinary(snapshot) or snapshot.st_mtime_ns >= cutoff:
            return
        try:
            if stat.S_ISREG(snapshot.st_mode):
                size = _delete_file(parent, name, snapshot, cutoff)
                if size is not None:
                    result.count += 1
                    result.bytes += size
            elif stat.S_ISDIR(snapshot.st_mode):
                with parent.child(name, delete=True, directory=True) as child:
                    if version(child.stat()) != version(snapshot):
                        return
                    self._walk(child, cutoff, result)
                    # Our unlinks update this directory's mtime. The initial age
                    # passed above, and only our own child mutations are allowed
                    # under the exclusive root lease. Never remove a new entry.
                    if child.is_empty() and identity(parent.lstat(name)) == identity(snapshot):
                        parent.remove(name, child, directory=True)
        except FileNotFoundError:
            pass
        except OSError:
            result.failed += 1


def cleanup_emitter(logger, *, emit=None):
    """Cleanup-only catalog. Bytes use the existing integer count field.

    Run each submission in an empty context: cleanup must never inherit request
    or execution identities. API may inject its existing bounded event queue.
    """
    def record(kind, result):
        if kind not in ('staging', 'temp'):
            raise ValueError('invalid cleanup event kind')
        for suffix, value in (('count', result.count), ('bytes', result.bytes),
                              ('failed_count', result.failed)):
            event = 'storage.cleanup.' + kind + '.' + suffix
            if emit is None:
                Context().run(log_event_best_effort, logger, event, count=value)
            else:
                Context().run(emit, event, count=value)
    return record


class CleanupService:
    """Startup once, then fixed-delay scans, owned interruptible thread.

    No detached executor/future survives stop_and_join. A scan completes before
    another interval begins. Local filesystem I/O may still delay a join; no
    artificial shutdown timeout silently abandons a deletion worker.
    """
    def __init__(self, *, scanners, interval_sec, emit, wait=None):
        if not math.isfinite(interval_sec) or interval_sec <= 0:
            raise ValueError('invalid cleanup interval')
        self.scanners = tuple(scanners)
        self.interval_sec, self.emit = interval_sec, emit
        self.stop = Event()
        self.wait = wait or self.stop.wait
        self.thread = None
        self._lock = Lock()
        self._started = False
        self._failure = None

    def scan(self):
        for scanner in self.scanners:
            if self.stop.is_set():
                break
            self.emit(scanner.kind, scanner.scan())

    def start(self):
        with self._lock:
            if self._started or self.stop.is_set():
                return
            self._started = True
            try:
                self.scan()
                self.thread = Thread(target=self._run, name='runtime-cleanup')
                self.thread.start()
            except BaseException:
                self.stop.set()
                if self.thread is not None and self.thread.ident is not None:
                    self.thread.join()
                raise

    def _run(self):
        try:
            while not self.stop.is_set():
                if self.wait(self.interval_sec) or self.stop.is_set():
                    break
                self.scan()
        except BaseException as error:
            self._failure = error
            self.stop.set()

    def stop_and_join(self):
        self.stop.set()
        with self._lock:
            thread = self.thread
        if thread is not None and thread.ident is not None:
            thread.join()
        failure, self._failure = self._failure, None
        if failure is not None:
            raise failure


def configured_cleanup(config, logger, *, emit=None):
    """Composition-owned roots. Never accept/derive a publish scan target."""
    media_root = configuration_path(config.media_root)
    publish = configuration_path(media_root/'source')
    temp_root = configuration_path(config.temp_root)
    if temp_root == publish or publish in temp_root.parents:
        raise ValueError('publish root cannot be a cleanup temp target')
    temp = CleanupScanner(root=temp_root, kind='temp', age_sec=config.cleanup.temp_age_sec,
                          protected_paths=(publish,), configured_root=config.temp_root)
    scanners = [temp]
    if config.service == 'api':
        scanners.insert(0, CleanupScanner(root=configuration_path(media_root/'staging'),
            lease_root=media_root, kind='staging', age_sec=config.cleanup.staging_age_sec,
            protected_paths=(publish,)))
    return CleanupService(scanners=scanners, interval_sec=config.cleanup.interval_sec,
                          emit=cleanup_emitter(logger, emit=emit))
