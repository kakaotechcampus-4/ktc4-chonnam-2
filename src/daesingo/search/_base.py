from typing import ClassVar

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")
