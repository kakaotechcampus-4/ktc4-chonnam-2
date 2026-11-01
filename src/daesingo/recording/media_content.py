"""Private persistence metadata; none of these fields extend canonical contracts."""
from dataclasses import dataclass
import hashlib
import re
from typing import BinaryIO


@dataclass(frozen=True)
class FrameImage:
    content: bytes
    content_type: str
    image_format: str


@dataclass(frozen=True)
class OpenedDerivedAsset:
    stream: BinaryIO
    content_type: str
    byte_size: int


def identity(value: str) -> str:
    try:
        if not isinstance(value, str) or not value:
            raise ValueError
        value.encode("utf-8")
    except (ValueError, UnicodeError):
        raise ValueError("invalid recording identity") from None
    return value


def media_type(value: str) -> str:
    # Bare RFC media-type tokens. Parameters, whitespace and header injection
    # are not accepted. No Contract codec/format allowlist is implied.
    token = r"[A-Za-z0-9!#$%&'*+.^_`|~-]+"
    if not isinstance(value, str) or re.fullmatch(token + "/" + token, value) is None:
        raise ValueError("invalid recording content type")
    return value


def png(content) -> bool:
    # Same encoded-image boundary as the existing PNG extractor. This is not
    # a full image decoder and reads never invoke ffmpeg or original media.
    return (isinstance(content, bytes) and content.startswith(b"\x89PNG\r\n\x1a\n")
            and content.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"))


def actual_media_type(content: bytes) -> str:
    """Identify the current Recording PNG / ISO MP4 outputs without a decoder.

    A container signature is a format check, not a codec/decodability guarantee.
    Unknown output formats require an explicit adapter extension, not a guessed
    MIME header. MP4 checks use the ftyp/isom output of our existing encoder.
    """
    if png(content):
        return "image/png"
    if isinstance(content, bytes):
        cursor, boxes = 0, set()
        while cursor + 8 <= len(content):
            size = int.from_bytes(content[cursor:cursor+4], "big")
            kind = content[cursor+4:cursor+8]
            if size < 8 or cursor + size > len(content):
                break
            if kind == b"ftyp" and (size < 16 or content[cursor+8:cursor+12] != b"isom"):
                break
            boxes.add(kind)
            cursor += size
        if cursor == len(content) and {b"ftyp", b"moov", b"mdat"} <= boxes:
            return "video/mp4"
    raise ValueError("unsupported recording content format")


def frame_format(content, image_format):
    if image_format is not None and (image_format != "png" or not png(content)):
        raise ValueError("invalid recording image format or content")


def derived_content(asset, content, content_type, case_id):
    identity(asset.derived_asset_ref)
    if case_id is not None:
        identity(case_id)
    if content is None and content_type is None:
        return
    if (not isinstance(content, bytes) or content_type is None
            or asset.availability != "AVAILABLE" or asset.byte_size != len(content)):
        raise ValueError("inconsistent recording content metadata")
    media_type(content_type)
    if actual_media_type(content) != content_type:
        raise ValueError("recording content type does not match bytes")


def descriptor(content: bytes, content_type: str) -> dict:
    return {"content_type": media_type(content_type), "byte_size": len(content),
            "sha256": hashlib.sha256(content).hexdigest()}


def checked_content(content, metadata):
    try:
        if (not isinstance(content, bytes) or not isinstance(metadata, dict)
                or metadata != descriptor(content, metadata["content_type"])):
            raise ValueError
        if actual_media_type(content) != metadata["content_type"]:
            raise ValueError
        return content, metadata["content_type"]
    except (ValueError, TypeError, KeyError):
        raise ValueError("invalid recording stored content") from None
