from contextlib import AbstractContextManager
from typing import Protocol

from .execution import RunDeadline
from .media import MediaInput, PreparedMedia


class CoarseMediaPreparer(Protocol):
    def prepare_coarse(
        self, media_input: MediaInput, deadline: RunDeadline
    ) -> AbstractContextManager[PreparedMedia]: ...
