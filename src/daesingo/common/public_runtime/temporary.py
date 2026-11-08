"""Owned per-Case temp scope; its token comes from durable server ownership."""
from contextlib import closing, contextmanager
from contextvars import ContextVar
import os
from pathlib import Path
import re
import stat
from itertools import islice

from daesingo.common.storage._filesystem import pin_root, tool_directory, ordinary, version

temporary_root: ContextVar[Path | None] = ContextVar("public_temporary_root", default=None)


def public_temp_root(media_root):
    """Both services use this one child of their existing shared media mount."""
    with pin_root(media_root) as parent:
        root = tool_directory(parent) / "public-temp"
        try:
            root.mkdir(mode=0o700)
        except FileExistsError:
            pass
        with parent.child("public-temp", directory=True):
            return root


def name(token):
    if not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{32}", token) is None:
        raise ValueError("invalid owned temp token")
    return "a1-" + token


@contextmanager
def case_temp_scope(root, token):
    with pin_root(root) as parent:
        target = tool_directory(parent) / name(token)
        try:
            target.mkdir(mode=0o700)
            with (target / ".owned").open("xb") as marker:
                marker.write(token.encode())
                marker.flush()
                os.fsync(marker.fileno())
        except FileExistsError:
            pass
        with parent.child(name(token), directory=True) as owned:
            with owned.child(".owned") as marker:
                if marker.stat().st_size != 32 or (target / ".owned").read_bytes() != token.encode():
                    raise ValueError("unowned temp directory")
            context = temporary_root.set(target)
            try:
                yield target
            finally:
                temporary_root.reset(context)


def delete_case_temp(root, token):
    """Caller holds exclusive temp/orphan leases. No arbitrary recursive path API."""
    with pin_root(root) as parent:
        try:
            snapshot = parent.lstat(name(token))
        except FileNotFoundError:
            return
        target = tool_directory(parent) / name(token)
        with parent.child(name(token), directory=True, delete=True) as owned:
            # Crash between final marker unlink and rmdir: only the exact empty
            # directory selected by the durable token is safe to finish.
            if owned.is_empty():
                if (owned.stat().st_dev, owned.stat().st_ino) != (snapshot.st_dev, snapshot.st_ino):
                    raise ValueError("owned temp directory changed")
                parent.remove(name(token), owned, directory=True)
                return
        with parent.child(name(token), directory=True) as owned, owned.child(".owned") as marker:
            snapshot_marker = marker.stat()
            if snapshot_marker.st_size > 32 or snapshot_marker.st_nlink != 1:
                raise ValueError("unowned temp directory")
            raw_marker = (target / ".owned").read_bytes()
            if raw_marker != token.encode():
                # Creation may have crashed before completing the marker. The
                # durable token plus its sole, regular prefix marker proves only
                # this empty initialization residue, never any arbitrary files.
                with closing(owned.entries()) as children:
                    if [entry[0] for entry in islice(children, 2)] != [".owned"] or not token.encode().startswith(raw_marker):
                        raise ValueError("unowned temp directory")
                if version(marker.stat()) != version(snapshot_marker):
                    raise ValueError("ownership marker changed")
        count = [0]
        def remove(directory, *, top=False):
            with closing(directory.entries()) as children:
              for child_name, info in children:
                if top and child_name == ".owned":
                    continue
                count[0] += 1
                if count[0] > 10000 or info is None or not ordinary(info):
                    raise ValueError("unverifiable owned residue")
                if stat.S_ISDIR(info.st_mode):
                    with directory.child(child_name, directory=True, delete=True) as child:
                        remove(child)
                        if not child.is_empty():
                            raise ValueError("owned temp directory changed")
                        directory.remove(child_name, child, directory=True)
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    with directory.child(child_name, delete=True) as child:
                        if version(child.stat()) != version(info):
                            raise ValueError("owned residue changed")
                        directory.remove(child_name, child)
                else:
                    raise ValueError("unverifiable owned residue")
        with parent.child(name(token), directory=True, delete=True) as owned:
            if (owned.stat().st_dev, owned.stat().st_ino) != (snapshot.st_dev, snapshot.st_ino):
                raise ValueError("owned temp directory changed")
            remove(owned, top=True)
            # Keep the ownership marker until every other removal succeeded;
            # interrupted cleanup can then safely retry the same durable token.
            with owned.child(".owned") as marker:
                if marker.stat().st_size != len(raw_marker) or (target / ".owned").read_bytes() != raw_marker:
                    raise ValueError("ownership marker changed")
                marker_version = version(marker.stat())
            with owned.child(".owned", delete=True) as marker:
                if version(marker.stat()) != marker_version:
                    raise ValueError("ownership marker changed")
                owned.remove(".owned", marker)
            parent.remove(name(token), owned, directory=True)
