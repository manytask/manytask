from __future__ import annotations

import warnings
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime
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
    GROUP_CONFIG_NAME = ".group.yml"

    def __init__(
        self,
        manytask_config: ManytaskConfig,
        repository_root: Path,
        reference_root: Path | None = None,
        branch_name: str | None = None,
    ):
        self.manytask_config = manytask_config

        self.repository_root = repository_root
        self.reference_root = reference_root or repository_root

        self.potential_groups = {group.name: group for group in self._search_for_groups_by_configs(self.reference_root)}
        self.potential_tasks = {task.name: task for task in self._search_for_tasks_by_configs(self.reference_root)}

        self.branch_name = branch_name

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
    def _search_for_tasks_by_configs(
        root: Path,
    ) -> Generator[FileSystemTask, Any, None]:
        for task_config_path in root.glob(f"**/{Course.TASK_CONFIG_NAME}"):
            relative_task_path = task_config_path.parent.relative_to(root)

            # if empty file - use default
            if task_config_path.read_text().strip() == "":
                task_config = CheckerSubConfig.default()
            # if any content - read yml
            else:
                task_config = CheckerSubConfig.from_yaml(task_config_path)

            yield FileSystemTask(
                name=task_config_path.parent.name,
                relative_path=str(relative_task_path),
                config=task_config,
            )

    @staticmethod
    def _search_for_groups_by_configs(
        root: Path,
    ) -> Generator[FileSystemGroup, Any, None]:
        for group_config_path in root.glob(f"**/{Course.GROUP_CONFIG_NAME}"):
            relative_group_path = group_config_path.parent.relative_to(root)

            # if empty file - use default
            if group_config_path.read_text().strip() == "" or group_config_path.read_text().strip() == "\n":
                group_config = CheckerSubConfig.default()
            # if any content - read yml
            else:
                group_config = CheckerSubConfig.from_yaml(group_config_path)

            group_tasks = list(Course._search_for_tasks_by_configs(group_config_path.parent))
            for task in group_tasks:
                task.relative_path = str(relative_group_path / task.relative_path)

            yield FileSystemGroup(
                name=group_config_path.parent.name,
                relative_path=str(relative_group_path),
                config=group_config,
                tasks=group_tasks,
            )

    @staticmethod
    def _is_parent(path: Path, files: list[Any]) -> bool:
        return any(Path(file).is_relative_to(path) for file in files)

    def _get_branch_name(self, repo: git.Repo) -> str:
        """Extract branch name, handling detached HEAD state."""
        try:
            return repo.active_branch.name
        except TypeError:
            if self.branch_name is None:
                raise CheckerException("Detached HEAD state and no branch name provided")
            return self.branch_name

    def _find_tasks_by_identifier(
        self,
        identifier: str,
        potential_tasks: list[FileSystemTask],
        enabled_groups: list[Any],
        context: str,
    ) -> list[FileSystemTask]:
        """
        Find tasks by identifier (branch name or commit message substring).
        Checks groups first, then falls back to individual tasks.
        """
        # Try to get groups first
        changed_enabled_groups = [
            group for group in enabled_groups if group.name == identifier or group.name in identifier
        ]
        if changed_enabled_groups:
            print_info(
                f"Changed groups: {[g.name for g in changed_enabled_groups]} ({context})",
                color="grey",
            )
            changed_enabled_tasks_names = {task.name for group in changed_enabled_groups for task in group.tasks}
            changed_tasks = [task for task in potential_tasks if task.name in changed_enabled_tasks_names]
            print_info(
                f"Changed tasks: {[t.name for t in changed_tasks]} ({context})",
                color="grey",
            )
            return changed_tasks

        # If no groups found, try to get tasks
        changed_tasks = [task for task in potential_tasks if task.name == identifier or task.name in identifier]
        print_info(
            f"Changed tasks: {[t.name for t in changed_tasks]} ({context})",
            color="grey",
        )
        if not changed_tasks:
            print_info(f"No active task/group found for {context}", color="yellow")

        return changed_tasks

    def detect_changes(
        self,
        detection_type: CheckerTestingConfig.ChangesDetectionType,
    ) -> list[FileSystemTask]:
        """
        Detects changes in the repository based on the provided detection type.

        :param detection_type: detection type, see CheckerTestingConfig.ChangesDetectionType
            - BRANCH_NAME: task name == branch name (single task/group)
            - COMMIT_MESSAGE: task name in commit message (can be multiple tasks/groups)
            - LAST_COMMIT_CHANGES: task relative path in last commit changes (can be multiple tasks)
        :return: list of changed tasks
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
            branch_name = self._get_branch_name(repo)
            print_info(f"Branch name: {branch_name}", color="grey")
            return self._find_tasks_by_identifier(
                branch_name,
                potential_tasks,
                enabled_groups,
                f"branch name: {branch_name}",
            )

        elif detection_type == CheckerTestingConfig.ChangesDetectionType.COMMIT_MESSAGE:
            commit_message = repo.head.commit.message
            if isinstance(commit_message, bytes):  # pragma: no cover
                commit_message = commit_message.decode("utf-8")
            print_info(f"Commit message: {commit_message}", color="grey")
            return self._find_tasks_by_identifier(
                commit_message,
                potential_tasks,
                enabled_groups,
                f"commit message: {commit_message}",
            )

        elif detection_type == CheckerTestingConfig.ChangesDetectionType.LAST_COMMIT_CHANGES:
            last_commit = repo.head.commit
            changed_files = [item.a_path for item in last_commit.diff("HEAD~1")]
            print_info(f"Last commit changes: {changed_files}", color="grey")

            changed_tasks = [
                task
                for task in potential_tasks
                if any(file is not None and Path(file).is_relative_to(task.relative_path) for file in changed_files)
            ]
            print_info(
                f"Changed tasks: {[t.name for t in changed_tasks]} (changed files in last commit)",
                color="grey",
            )
            if not changed_tasks:
                warnings.warn(f"No active tasks found for last commit changes {changed_files}")

            return changed_tasks

        else:  # pragma: no cover
            assert False, "Unreachable code"
