"""B-C1/B-C3 residues and a separate fail-closed B-C2 orphan boundary."""
from contextlib import closing, contextmanager
from contextvars import Context
from dataclasses import dataclass
import math
import os
import sys
import re
import stat
from threading import Event, Lock, Thread
import time

from ._filesystem import UnsafePath, checked_path, configuration_path, identity, ordinary, pin_root, version
from daesingo.common.logging import log_event_best_effort

# Existing tempfile producers use these prefixes and Python's eight-character
# [a-z0-9_] suffix. Prefix lookalikes and arbitrary root files are not evidence
# of Runtime ownership. Keep this aligned if the producer naming ever changes.
_STAGING = re.compile(r'upload-[a-z0-9_]{8}\Z')
_TEMP = re.compile(r'recording-(?:analysis|chain)-[a-z0-9_]{8}\Z')
_PUBLISH = re.compile(r'[0-9a-f]{32}\Z')


@dataclass
class ScanResult:
    # count counts files (including zero-byte files), not empty directories.
    count: int = 0
    bytes: int = 0
    failed: int = 0


@contextmanager
def _lease(root, kind, *, exclusive, blocking, with_root=False):
    with pin_root(root) as directory, directory.lock_file('.runtime-cleanup-' + kind + '.lock') as fd:
        acquired = False
        try:
            while True:
                try:
                    if sys.platform == 'win32':
                        import msvcrt
                        if kind == 'orphan':
                            from ._filesystem import publish_lock
                            publish_lock(fd, exclusive=exclusive)
                        else:
                            os.lseek(fd, 0, os.SEEK_SET)
                            msvcrt.locking(fd, msvcrt.LK_NBLCK if exclusive else msvcrt.LK_NBRLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
                    acquired = True
                    break
                except (BlockingIOError, PermissionError) as error:
                    if kind == 'orphan' and not isinstance(error, BlockingIOError):
                        # Native orphan locks classify contention explicitly;
                        # access failures must not spin forever as a busy lease.
                        raise
                    if not blocking:
                        break
                    time.sleep(.01)
            yield (directory if acquired else None) if with_root else acquired
        finally:
            if acquired:
                if sys.platform == 'win32':
                    import msvcrt
                    if kind == 'orphan':
                        from ._filesystem import publish_unlock
                        publish_unlock(fd)
                    else:
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
        if kind not in ('staging', 'temp', 'orphan'):
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


def configured_cleanup(config, logger, *, emit=None, registration=None):
    """Keep staging/temp protection; opt in through a public registration port."""
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
        if registration is not None:
            scanners.append(OrphanPublishScanner(root=publish, lease_root=media_root,
                age_sec=config.cleanup.orphan_age_sec, registration=registration))
    return CleanupService(scanners=scanners, interval_sec=config.cleanup.interval_sec,
                          emit=cleanup_emitter(logger, emit=emit))


class OrphanPublishScanner(CleanupScanner):
    """Direct managed source files only. True/False/None port, exact bool checks.

    Composition translates Recording's enum. None or exceptions fail closed.
    Filesystem identity is checked independently, before and after the query.
    Root lease remains exclusive until deletion; DB resources do not.
    """
    def __init__(self, *, root, lease_root, age_sec, registration, now=time.time):
        super().__init__(root=configuration_path(root), lease_root=configuration_path(lease_root),
                         kind='staging', age_sec=age_sec, now=now)
        if self.root != self.lease_root / 'source':
            raise ValueError('orphan root must be managed source')
        self.kind = 'orphan'
        self.registration = registration

    def _verify_root(self, directory):
        with pin_root(self.lease_root) as current:
            if identity(current.stat()) != identity(directory.stat()):
                raise UnsafePath('publish root changed')

    @contextmanager
    def in_use(self):
        with _lease(self.lease_root, self.kind, exclusive=False, blocking=True,
                    with_root=True) as directory:
            def verify():
                self._verify_root(directory)
            verify()
            yield verify

    def scan(self):
        result = ScanResult()
        if not self._scan_lock.acquire(blocking=False):
            return result
        try:
            cutoff = int((self.now()-self.age_sec)*1_000_000_000)
            with _lease(self.lease_root, self.kind, exclusive=True, blocking=False,
                        with_root=True) as media:
                if media is not None:
                    self._verify_root(media)
                    # POSIX openat anchors traversal to the SAME directory as
                    # the lease. Never reopen a potentially replaced pathname.
                    with media.child('source', directory=True) as source:
                        self._walk(source, cutoff, result, root_identity=identity(media.stat()))
        except FileNotFoundError:
            pass
        except OSError:
            result.failed += 1
        finally:
            self._scan_lock.release()
        return result

    def _verify_source(self, parent, root_identity):
        with pin_root(self.lease_root) as media:
            if root_identity is not None and identity(media.stat()) != root_identity:
                raise UnsafePath('publish root changed')
            with media.child('source', directory=True) as source:
                if identity(source.stat()) != identity(parent.stat()):
                    raise UnsafePath('publish source changed')

    def _walk(self, parent, cutoff, result, *, top=False, root_identity=None):
        with closing(parent.entries()) as entries:
            for name, snapshot in entries:
                if snapshot is None:
                    result.failed += 1
                    continue
                if (not _PUBLISH.fullmatch(name) or not stat.S_ISREG(snapshot.st_mode)
                        or not ordinary(snapshot) or snapshot.st_nlink != 1
                        or snapshot.st_mtime_ns >= cutoff):
                    continue
                try:
                    # Validate before spending a DB checkout. Do not keep the
                    # leaf handle across lookup: reopen and compare its version.
                    with parent.child(name) as child:
                        if version(child.stat()) != version(snapshot):
                            continue
                    try:
                        registered = self.registration('source/' + name)
                    except Exception:
                        # A lookup FileNotFoundError is a failed lookup, not a
                        # concurrently vanished filesystem candidate.
                        result.failed += 1
                        continue
                    if registered is True:
                        continue
                    if registered is not False:
                        result.failed += 1
                        continue
                    self._verify_source(parent, root_identity)
                    size = _delete_file(parent, name, snapshot, cutoff)
                    if size is not None:
                        result.count += 1
                        result.bytes += size
                except FileNotFoundError:
                    pass
                except Exception:
                    # Query/metadata/deletion failures are item-local, with no
                    # path, locator, exception text or request context retained.
                    result.failed += 1
