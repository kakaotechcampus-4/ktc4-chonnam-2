from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class UploadedFile:
    name: str
    uri: str


class UploadCache(Protocol):
    def get(self, key: str) -> UploadedFile | None: ...

    def put(self, key: str, value: UploadedFile) -> None: ...


@dataclass(slots=True)
class MemoryUploadCache:
    _entries: dict[str, UploadedFile] = field(default_factory=dict)

    def get(self, key: str) -> UploadedFile | None:
        return self._entries.get(key)

    def put(self, key: str, value: UploadedFile) -> None:
        self._entries[key] = value
