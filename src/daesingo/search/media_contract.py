from contextlib import AbstractContextManager
from typing import Protocol

from .execution import RunDeadline
from .media import MediaInput, PreparedMedia


class CoarseMediaPreparer(Protocol):
    def prepare_coarse(
        self, media_input: MediaInput, deadline: RunDeadline
    ) -> AbstractContextManager[PreparedMedia]: ...

    def prepare_fine(
        self,
        media_input: MediaInput,
        fine_start_sec: float,
        fine_end_sec: float,
        deadline: RunDeadline,
    ) -> AbstractContextManager[PreparedMedia]: ...
