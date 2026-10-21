from __future__ import annotations

import warnings
from collections import Counter
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import git

from .configs import CheckerSubConfig, CheckerTestingConfig, ManytaskConfig
from .exceptions import BadConfig, CheckerException
from .utils import print_info


@dataclass
class FileSystemTask:
    name: str
    relative_path: str
    config: CheckerSubConfig


@dataclass
class FileSystemGroup:
    name: str
    relative_path: str
    config: CheckerSubConfig
    tasks: list[FileSystemTask]


class Course:
    """
    Class operates deadlines (filter, search etc), timezones and mapping tasks and groups to file system.
    Only operates with tasks and groups existing in file system.
    """

    TASK_CONFIG_NAME = ".task.yml"
    NAMED_TASK_CONFIG_PATTERN = ".task.*.yml"
    SHALLOW_DEEPEN_BY = 100
    GROUP_CONFIG_NAME = ".group.yml"

    def __init__(
        self,
        manytask_config: ManytaskConfig,
        repository_root: Path,
        reference_root: Path | None = None,
        branch_name: str | None = None,
        base_ref: str | None = None,
    ):
        self.manytask_config = manytask_config

        self.repository_root = repository_root
        self.reference_root = reference_root or repository_root

        self.potential_groups = {group.name: group for group in self._search_for_groups_by_configs(self.reference_root)}
        self.potential_tasks: dict[str, FileSystemTask] = {}
        for task in self._search_for_tasks_by_configs(self.reference_root):
            if task.name in self.potential_tasks:
                previous = self.potential_tasks[task.name]
                raise BadConfig(
                    f"Duplicate task name {task.name!r} in {previous.relative_path!r} and {task.relative_path!r}"
                )
            self.potential_tasks[task.name] = task

        self.branch_name = branch_name
        self.base_ref = base_ref

        self.task_to_group = {task.name: group for group in self.potential_groups.values() for task in group.tasks}

    def get_group_for_task(self, task_name: str) -> FileSystemGroup | None:
        """Get the group that contains the given task, or None if not found."""
        return self.task_to_group.get(task_name)

    def get_task_parameters(
        self,
        task: FileSystemTask,
        default_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve the same parameter inheritance for detection and grading."""
        parameters = (default_parameters or {}).copy()
        group = self.get_group_for_task(task.name)
        if group and group.config.parameters:
            parameters.update(group.config.parameters.root)
        if task.config.parameters:
            parameters.update(task.config.parameters.root)
        return parameters

    def validate(self) -> None:
        # check all groups and tasks mentioned in deadlines exists
        deadlines_groups = self.manytask_config.get_groups(enabled=True)
        for deadline_group in deadlines_groups:
            if deadline_group.name not in self.potential_groups:
                warnings.warn(f"Group {deadline_group.name} not found in repository")

        deadlines_tasks = self.manytask_config.get_tasks(enabled=True)
        for deadlines_task in deadlines_tasks:
            if deadlines_task.name not in self.potential_tasks:
                raise BadConfig(f"Task {deadlines_task.name} not found in repository")

    def get_groups(
        self,
        enabled: bool | None = None,
        started: bool | None = None,
        *,
        now: datetime | None = None,
    ) -> list[FileSystemGroup]:
        search_deadlines_groups = self.manytask_config.get_groups(enabled=enabled, started=started, now=now)

        return [
            self.potential_groups[deadline_group.name]
            for deadline_group in search_deadlines_groups
            if deadline_group.name in self.potential_groups
        ]

    def get_tasks(
        self,
        enabled: bool | None = None,
        started: bool | None = None,
        *,
        now: datetime | None = None,
    ) -> list[FileSystemTask]:
        search_deadlines_tasks = self.manytask_config.get_tasks(enabled=enabled, started=started, now=now)

        return [
            self.potential_tasks[deadline_task.name]
            for deadline_task in search_deadlines_tasks
            if deadline_task.name in self.potential_tasks
        ]

    @staticmethod
    def _load_sub_config(path: Path) -> CheckerSubConfig:
        if path.read_text().strip() == "":
            return CheckerSubConfig.default()
        return CheckerSubConfig.from_yaml(path)

    @staticmethod
    def _load_tasks_from_config(root: Path, path: Path) -> list[FileSystemTask]:
        relative_path = path.parent.relative_to(root)
        task_name = (
            path.parent.name
            if path.name == Course.TASK_CONFIG_NAME
            else path.name.removeprefix(".task.").removesuffix(".yml")
        )
        if not task_name or task_name.isspace():
            raise BadConfig(f"Empty task name in {path}")
        return [
            FileSystemTask(
                name=task_name,
                relative_path=str(relative_path),
                config=Course._load_sub_config(path),
            )
        ]

    @staticmethod
    def _search_for_tasks_by_configs(
        root: Path,
    ) -> Generator[FileSystemTask, Any, None]:
        config_paths = sorted(
            set(root.glob(f"**/{Course.TASK_CONFIG_NAME}"))
            | set(root.glob(f"**/{Course.NAMED_TASK_CONFIG_PATTERN}"))
        )
        for task_config_path in config_paths:
            yield from Course._load_tasks_from_config(root, task_config_path)

    @staticmethod
    def _search_for_groups_by_configs(
        root: Path,
    ) -> Generator[FileSystemGroup, Any, None]:
        for group_config_path in root.glob(f"**/{Course.GROUP_CONFIG_NAME}"):
            relative_group_path = group_config_path.parent.relative_to(root)

            group_config = Course._load_sub_config(group_config_path)

            group_tasks = list(
                Course._search_for_tasks_by_configs(group_config_path.parent)
            )
            for task in group_tasks:
                task.relative_path = str(relative_group_path / task.relative_path)

            yield FileSystemGroup(
                name=group_config_path.parent.name,
                relative_path=str(relative_group_path),
                config=group_config,
                tasks=group_tasks,
            )

    def _detect_by_branch_name(
        self,
        repo: git.Repo,
        potential_tasks: list[FileSystemTask],
        enabled_groups: list[Any],
        branch_name: str | None = None,
    ) -> list[FileSystemTask]:
        """Detect changes by matching branch name to task/group name."""
        branch_name = branch_name or self._get_branch_name(repo)
        if branch_name is None:
            raise CheckerException("Detached HEAD state and no branch name provided")
        print_info(f"Branch name: {branch_name}", color="grey")

        # try to get groups first
        changed_enabled_groups = [group for group in enabled_groups if group.name == branch_name]
        if changed_enabled_groups:
            return self._tasks_from_groups(changed_enabled_groups, potential_tasks, "branch name == group name")

        # if no groups found, try to get tasks
        changed_tasks = [task for task in potential_tasks if task.name == branch_name]
        print_info(
            f"Changed tasks: {[t.name for t in changed_tasks]} (branch name == task/group name)",
            color="grey",
        )
        if not changed_tasks:
            print_info(f"No active task/group found for branch {branch_name}", color="yellow")

        return changed_tasks

    def _get_branch_name(self, repo: git.Repo) -> str | None:
        if self.branch_name is not None:
            return self.branch_name
        try:
            return repo.active_branch.name
        except TypeError:
            return None

    def _detect_by_commit_message(
        self,
        repo: git.Repo,
        potential_tasks: list[FileSystemTask],
        enabled_groups: list[Any],
    ) -> list[FileSystemTask]:
        """Detect changes by matching commit message to task/group name."""
        commit_message = repo.head.commit.message
        if isinstance(commit_message, bytes):  # pragma: no cover
            commit_message = commit_message.decode("utf-8")
        print_info(f"Commit message: {commit_message}", color="grey")

        # try to get groups first
        changed_enabled_groups = [group for group in enabled_groups if group.name in commit_message]
        if changed_enabled_groups:
            return self._tasks_from_groups(changed_enabled_groups, potential_tasks, "group name in commit message")

        # if no groups found, try to get tasks
        changed_tasks = [task for task in potential_tasks if task.name in commit_message]
        print_info(
            f"Changed tasks: {[t.name for t in changed_tasks]} (task name in commit message)",
            color="grey",
        )
        if not changed_tasks:
            print_info(
                f"No active tasks/groups found for commit message {commit_message}",
                color="yellow",
            )

        return changed_tasks

    def _detect_by_last_commit_changes(
        self,
        repo: git.Repo,
        potential_tasks: list[FileSystemTask],
        task_patterns: dict[str, list[str] | None] | None = None,
    ) -> list[FileSystemTask]:
        """Detect changes by matching file changes since the base commit to task paths.

        The base is `self.base_ref` (e.g. the branch state before the push) when it is usable,
        so all commits of a multi-commit push are taken into account; otherwise HEAD~1.
        """
        head = repo.head.commit
        base = self._resolve_base_commit(repo, head)
        if base is not None:
            print_info(f"Detecting changes in range {base.hexsha[:8]}..{head.hexsha[:8]}", color="grey")
            diff = head.diff(base)
        else:
            print_info("No base commit found, using all files of HEAD", color="grey")
            diff = head.diff(git.NULL_TREE)
        changed_files = sorted(
            {
                path
                for item in diff
                for path in (item.a_path, item.b_path)
                if path is not None
            }
        )
        print_info(f"Last commit changes: {changed_files}", color="grey")

        tasks_per_path = Counter(
            task.relative_path for task in self.potential_tasks.values()
        )
        changed_tasks = []
        for task in potential_tasks:
            task_files = [
                Path(file).relative_to(task.relative_path)
                for file in changed_files
                if file is not None and Path(file).is_relative_to(task.relative_path)
            ]
            if not task_files:
                continue
            patterns = (task_patterns or {}).get(task.name)
            if (
                tasks_per_path[task.relative_path] > 1
                and patterns
                and not any(
                    self._matches_editable_pattern(
                        file.parts, Path(pattern).parts, pattern.endswith("/")
                    )
                    for file in task_files
                    for pattern in patterns
                )
            ):
                continue
            changed_tasks.append(task)
        print_info(
            f"Changed tasks: {[t.name for t in changed_tasks]} (changed files in last commit)",
            color="grey",
        )
        if not changed_tasks:
            warnings.warn(f"No active tasks found for last commit changes {changed_files}")

        return changed_tasks

    @staticmethod
    def _matches_editable_pattern(
        path: tuple[str, ...], pattern: tuple[str, ...], directory_only: bool = False
    ) -> bool:
        """Match task-relative globs, including descendants of matching folders.

        Match diff names so deleted files are detected too. Unlike Path.match,
        ** matches zero path segments, as it does with Path.glob.
        """
        if not pattern:
            return bool(path) or not directory_only
        if pattern[0] == "**":
            return Course._matches_editable_pattern(
                path, pattern[1:], directory_only
            ) or (
                bool(path)
                and Course._matches_editable_pattern(path[1:], pattern, directory_only)
            )
        return (
            bool(path)
            and fnmatchcase(path[0], pattern[0])
            and Course._matches_editable_pattern(path[1:], pattern[1:], directory_only)
        )

    def _resolve_base_commit(self, repo: git.Repo, head: git.Commit) -> git.Commit | None:
        """Find the commit to diff HEAD against.

        Uses `self.base_ref` if it is set, is not a null sha and is known to the repository
        (for shallow clones the history is deepened once). If the base is not an ancestor
        of HEAD (force-push) the merge-base is used. Falls back to HEAD~1 (None for a root commit).
        """
        fallback = head.parents[0] if head.parents else None

        base_ref = (self.base_ref or "").strip()
        if not base_ref or set(base_ref) == {"0"}:
            return fallback

        base = self._get_commit(repo, base_ref)
        if base is None and self._is_shallow(repo):
            print_info(f"Base {base_ref[:8]} not found in shallow clone, deepening history", color="grey")
            try:
                repo.git.fetch("--no-tags", f"--deepen={self.SHALLOW_DEEPEN_BY}", "origin")
            except git.GitCommandError as e:
                print_info(f"Failed to deepen history: {e}", color="yellow")
            base = self._get_commit(repo, base_ref)

        if base is None:
            warnings.warn(f"Base {base_ref} not found in repository, falling back to HEAD~1")
            return fallback

        if base == head:
            return fallback

        if not repo.is_ancestor(base, head):
            merge_bases = repo.merge_base(base, head)
            if not merge_bases:
                warnings.warn(f"Base {base_ref} has no common history with HEAD, falling back to HEAD~1")
                return fallback
            print_info(f"Base {base_ref[:8]} is not an ancestor of HEAD, using merge-base", color="grey")
            base = merge_bases[0]

        return base

    @staticmethod
    def _get_commit(repo: git.Repo, ref: str) -> git.Commit | None:
        try:
            return repo.commit(ref)
        except (git.BadName, ValueError):
            return None

    @staticmethod
    def _is_shallow(repo: git.Repo) -> bool:
        try:
            return repo.git.rev_parse("--is-shallow-repository") == "true"
        except git.GitCommandError:
            return False

    def _tasks_from_groups(
        self,
        groups: list[Any],
        potential_tasks: list[FileSystemTask],
        reason: str,
    ) -> list[FileSystemTask]:
        """Extract tasks from groups and log the change."""
        print_info(f"Changed groups: {[g.name for g in groups]} ({reason})", color="grey")
        changed_enabled_tasks_names = {task.name for group in groups for task in group.tasks}
        changed_tasks = [task for task in potential_tasks if task.name in changed_enabled_tasks_names]
        print_info(f"Changed tasks: {[t.name for t in changed_tasks]} ({reason})", color="grey")
        return changed_tasks

    def detect_changes(
        self,
        detection_type: CheckerTestingConfig.ChangesDetectionType,
        *,
        task_patterns: dict[str, list[str] | None] | None = None,
    ) -> list[FileSystemTask]:
        """
        Detects changes in the repository based on the provided detection type.

        :param detection_type: detection type, see CheckerTestingConfig.ChangesDetectionType
            - BRANCH_NAME: task name == branch name (single task/group)
            - BRANCH_NAME_OR_COMMIT_MESSAGE: compare both sources when a non-default branch matches; reject conflicts
            - COMMIT_MESSAGE: task name in commit message (can be multiple tasks/groups)
            - LAST_COMMIT_CHANGES: task relative path in changes since base_ref, or HEAD~1 (can be multiple tasks)
        :return: list of changed tasks
        :param task_patterns: optional task-relative globs supplied by a configuration adapter;
            nonempty lists narrow file-based detection for tasks sharing a folder
        :raises CheckerException: if repository is not a git repository
        """
        print_info(f"Detecting changes by {detection_type}")
        potential_tasks = self.get_tasks(enabled=True)
        enabled_groups = self.manytask_config.get_groups(
            enabled=True
        )  # 'cause we want to check no-folder groups as well

        try:
            repo = git.Repo(self.repository_root)
        except git.exc.InvalidGitRepositoryError:
            raise CheckerException(f"Git Repository in {self.repository_root} not found")

        if detection_type == CheckerTestingConfig.ChangesDetectionType.BRANCH_NAME:
            return self._detect_by_branch_name(repo, potential_tasks, enabled_groups)

        if detection_type == CheckerTestingConfig.ChangesDetectionType.BRANCH_NAME_OR_COMMIT_MESSAGE:
            branch_name = self._get_branch_name(repo)
            branch_tasks: list[FileSystemTask] = []
            if branch_name is not None and branch_name not in ("main", "master"):
                branch_tasks = self._detect_by_branch_name(repo, potential_tasks, enabled_groups, branch_name)
            commit_tasks = self._detect_by_commit_message(repo, potential_tasks, enabled_groups)

            branch_task_names = {task.name for task in branch_tasks}
            commit_task_names = {task.name for task in commit_tasks}
            if branch_task_names and commit_task_names and branch_task_names != commit_task_names:
                raise CheckerException(
                    f"Ambiguous task detection: branch {branch_name!r} selects "
                    f"{sorted(branch_task_names)}, but the commit message selects {sorted(commit_task_names)}. "
                    "Make the names agree, or select explicitly with --task/--group "
                    "(and --submit-score when reporting is needed)."
                )
            return branch_tasks or commit_tasks

        if detection_type == CheckerTestingConfig.ChangesDetectionType.COMMIT_MESSAGE:
            return self._detect_by_commit_message(repo, potential_tasks, enabled_groups)

        if detection_type == CheckerTestingConfig.ChangesDetectionType.LAST_COMMIT_CHANGES:
            if task_patterns is None:
                task_patterns = {
                    task.name: task.config.editable_patterns for task in potential_tasks
                }
            return self._detect_by_last_commit_changes(
                repo, potential_tasks, task_patterns
            )

        assert False, "Unreachable code"  # pragma: no cover
