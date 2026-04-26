"""Generic interface every checklist step implements (implementation TBD)."""

from typing import Protocol


class CheckStep(Protocol):
    name: str

    async def run(self) -> None: ...
