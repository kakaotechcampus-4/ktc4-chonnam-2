"""Private versioned storage format and detached, verified prepared-media files."""
import hashlib
import re
import shutil
from tempfile import TemporaryFile, gettempdir


MAX_CHUNK_BYTES = 256 * 1024
COMMAND_ALLOWANCE = 16 * 1024


def checked_manifest(value):
    if (not isinstance(value, dict)
            or set(value) != {"version", "chunk_size", "chunk_count", "content_type", "byte_size", "sha256"}
            or type(value["version"]) is not int or value["version"] != 1
            or type(value["chunk_size"]) is not int or not 0 < value["chunk_size"] <= MAX_CHUNK_BYTES
            or type(value["byte_size"]) is not int or value["byte_size"] <= 0
            or type(value["chunk_count"]) is not int
            or value["chunk_count"] != (value["byte_size"] + value["chunk_size"]-1)//value["chunk_size"]
            or value["content_type"] != "video/mp4"
            or not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"])):
        raise ValueError("invalid recording media manifest")
    return value


def legacy_manifest(value):
    if (not isinstance(value, dict) or set(value) != {"byte_size", "sha256", "content_type"}
            or type(value["byte_size"]) is not int or value["byte_size"] <= 0):
        raise ValueError("invalid recording stored content")
    return checked_manifest({**value, "version": 1, "chunk_size": MAX_CHUNK_BYTES,
        "chunk_count": (value["byte_size"]+MAX_CHUNK_BYTES-1)//MAX_CHUNK_BYTES})


def check_mp4(stream, size):
    # Match actual_media_type's existing container-signature boundary, without
    # allocating box contents. This does not assert decoding/codec validity.
    offset, boxes = 0, set()
    while offset + 8 <= size:
        stream.seek(offset)
        header = stream.read(8)
        length, kind = int.from_bytes(header[:4], "big"), header[4:]
        if length < 8 or offset + length > size:
            break
        if kind == b"ftyp" and (length < 16 or stream.read(4) != b"isom"):
            break
        boxes.add(kind)
        offset += length
    if offset != size or not {b"ftyp", b"moov", b"mdat"} <= boxes:
        raise ValueError("invalid recording stored content")


def detached_stream(parts, manifest, *, temp_root=None):
    info = checked_manifest(manifest)
    # Same tempfile root as Recording materializers. Anonymous files have no
    # durable locator; close/crash releases them, Unix creation mode is 0600.
    if shutil.disk_usage(temp_root or gettempdir()).free < info["byte_size"]:
        raise OSError("insufficient recording temporary space")
    stream = TemporaryFile(mode="w+b", prefix="recording-prepared-", dir=temp_root)
    try:
        digest, total, count = hashlib.sha256(), 0, 0
        for part in parts:
            expected = min(info["chunk_size"], info["byte_size"]-total)
            if count >= info["chunk_count"] or not isinstance(part, bytes) or len(part) != expected:
                raise ValueError("invalid recording media chunk")
            stream.write(part)
            digest.update(part)
            total += len(part)
            count += 1
        if count != info["chunk_count"] or total != info["byte_size"] or digest.hexdigest() != info["sha256"]:
            raise ValueError("invalid recording stored content")
        check_mp4(stream, total)
        stream.seek(0)
        return stream
    except BaseException:
        stream.close()
        raise
