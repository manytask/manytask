"""Built-in step: every (non-deleted) change must live inside required_path."""

from __future__ import annotations

from app.checklist.result import CheckResult
from app.checklist.step import CheckContext
from app.hosting import HostingAdapter, MergeRequest


class FolderStructureStep:
    name = "folder structure"

    def __init__(self, *, hosting: HostingAdapter, required_path: str) -> None:
        self._hosting = hosting
        # Normalize: strip trailing slash, then ensure prefix matches full path segments.
        self._prefix = required_path.rstrip("/")

    def _inside_prefix(self, path: str) -> bool:
        if path == self._prefix:
            return True
        return path.startswith(self._prefix + "/")

    async def run(self, mr: MergeRequest, ctx: CheckContext) -> CheckResult:
        changes = await self._hosting.get_changes(mr)
        outside: list[str] = []
        for change in changes:
            if change.deleted_file:
                continue
            if not self._inside_prefix(change.new_path):
                outside.append(change.new_path)

        if not outside:
            return CheckResult(
                name=self.name,
                passed=True,
                message=f"all changes are inside `{self._prefix}`",
            )

        listed = ", ".join(f"`{p}`" for p in outside)
        return CheckResult(
            name=self.name,
            passed=False,
            message=f"changes outside `{self._prefix}`: {listed}",
        )
