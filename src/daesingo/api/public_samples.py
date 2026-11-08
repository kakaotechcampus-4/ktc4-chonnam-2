"""Bounded verified canonical->Case source copies; no DB/provider operations."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import stat
from uuid import uuid4

from daesingo.common.storage._filesystem import ordinary, pin_root, tool_directory, version
from .official_samples import SampleRejected

CHUNK_BYTES = 1024 * 1024


def discard_copies(sources):
    for source in sources:
        path = source.path
        with pin_root(path.parent) as parent:
            try:
                snapshot = parent.lstat(path.name)
            except FileNotFoundError:
                continue
            if (not ordinary(snapshot) or not stat.S_ISREG(snapshot.st_mode) or snapshot.st_nlink != 1
                    or snapshot.st_size != source.byte_size or snapshot.st_mtime_ns != source.mtime_ns):
                raise SampleRejected("INTEGRITY_MISMATCH")
            with parent.child(path.name, delete=True) as opened:
                if version(opened.stat()) != version(snapshot):
                    raise SampleRejected("INTEGRITY_MISMATCH")
                parent.remove(path.name, opened)


def copy_verified_sample(sample, media_root):
    """Caller holds the existing orphan lease through the following DB commit."""
    results = []
    try:
        with pin_root(media_root) as root:
            tool_root = tool_directory(root)
            (tool_root / "source").mkdir(exist_ok=True)
            with root.child("source", directory=True) as destination:
                for source in sample.sources:
                    with pin_root(source.path.parent) as parent, parent.child(source.path.name) as opened:
                        before = opened.stat()
                        if (not ordinary(before) or not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                                or before.st_size != source.byte_size or before.st_mtime_ns != source.mtime_ns):
                            raise SampleRejected("INTEGRITY_MISMATCH")
                        name = uuid4().hex
                        target = tool_root / "source" / name
                        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
                        fd = (os.open(target, flags, 0o600) if os.name == "nt" else
                              os.open(name, flags, 0o600, dir_fd=destination.descriptor))
                        try:
                            digest, size = hashlib.sha256(), 0
                            with os.fdopen(fd, "wb") as writer, source.path.open("rb") as reader:
                                # Windows path/CRT-handle ctime use different
                                # clocks. Match the same stable read identity as
                                # Recording._snapshot; pinned before/after still
                                # compares ctime and actual bytes/hash below.
                                current = os.fstat(reader.fileno())
                                if ((current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                                        != (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)):
                                    raise SampleRejected("INTEGRITY_MISMATCH")
                                while chunk := reader.read(CHUNK_BYTES):
                                    size += len(chunk)
                                    if size > source.byte_size:
                                        raise SampleRejected("INTEGRITY_MISMATCH")
                                    digest.update(chunk)
                                    writer.write(chunk)
                                writer.flush()
                                os.fsync(writer.fileno())
                            if (size != source.byte_size or digest.hexdigest() != source.sha256
                                    or version(opened.stat()) != version(before)
                                    or version(parent.lstat(source.path.name)) != version(before)):
                                raise SampleRejected("INTEGRITY_MISMATCH")
                            stamp = target.stat()
                            results.append(replace(source, path=target, mtime_ns=stamp.st_mtime_ns,
                                                   original_filename=source.path.name))
                        except BaseException:
                            # This exact O_EXCL file has not been offered to any DB.
                            with destination.child(name, delete=True) as created:
                                destination.remove(name, created)
                            raise
                if os.name != "nt":
                    os.fsync(destination.descriptor)
            return tuple(results)
    except BaseException:
        discard_copies(results)
        raise


class CopiedProbe:
    def __init__(self, sources):
        self.sources = {source.path: source for source in sources}

    def probe(self, path):
        source = self.sources.get(Path(path))
        if source is None:
            raise SampleRejected("INTEGRITY_MISMATCH")
        value = path.stat()
        if value.st_size != source.byte_size or value.st_mtime_ns != source.mtime_ns:
            raise SampleRejected("INTEGRITY_MISMATCH")
        return source
