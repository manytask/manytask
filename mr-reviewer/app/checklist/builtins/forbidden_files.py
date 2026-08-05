"""Built-in step: reject MRs introducing files with forbidden extensions."""

from __future__ import annotations

from app.checklist.result import CheckResult
from app.checklist.step import CheckContext
from app.hosting import HostingAdapter, MergeRequest


class ForbiddenFilesStep:
    name = "forbidden files"

    def __init__(self, *, hosting: HostingAdapter, extensions: list[str]) -> None:
        self._hosting = hosting
        # Normalize: accept ".pyc" and "pyc" alike, store as lowercase with leading dot.
        self._forbidden = tuple(self._normalize(ext) for ext in extensions)

    @staticmethod
    def _normalize(ext: str) -> str:
        ext = ext.strip().lower()
        return ext if ext.startswith(".") else f".{ext}"

    async def run(self, mr: MergeRequest, ctx: CheckContext) -> CheckResult:
        changes = await self._hosting.get_changes(mr)
        bad: list[str] = []
        for change in changes:
            if change.deleted_file:
                continue
            path = change.new_path.lower()
            if any(path.endswith(ext) for ext in self._forbidden):
                bad.append(change.new_path)

        if not bad:
            return CheckResult(
                name=self.name,
                passed=True,
                message="no files with forbidden extensions",
            )

        listed = ", ".join(f"`{p}`" for p in bad)
        return CheckResult(
            name=self.name,
            passed=False,
            message=f"forbidden files in MR: {listed}",
        )
