from __future__ import annotations

import shutil
from pathlib import Path

import git
import pytest

from checker.configs import CheckerTestingConfig
from checker.configs.manytask import ManytaskConfig
from checker.course import Course, FileSystemGroup, FileSystemTask
from checker.exceptions import BadConfig, CheckerException

from .conftest import T_GENERATE_FILE_STRUCTURE

# Test constants
TEST_TIMEZONE = "Europe/Berlin"
TASK_SCORE_10 = 10
TASK_SCORE_20 = 20
TASK_SCORE_30 = 30
TASK_SCORE_40 = 40
TASK_SCORE_50 = 50
EXPECTED_NUM_GROUPS_4 = 4
EXPECTED_NUM_GROUPS_3 = 3
EXPECTED_NUM_GROUPS_1 = 1
EXPECTED_NUM_TASKS_7 = 7
EXPECTED_NUM_TASKS_6 = 6
EXPECTED_NUM_TASKS_4 = 4
EXPECTED_NUM_TASKS_3 = 3
TEST_FILE_STRUCTURE = {
    "group1": {
        "task1_1": {".task.yml": "version: 1", "file1_1_1": "", "file1_1_2": "", "extra_file3": ""},
        "task1_2": {".task.yml": "", "file1_2_1": "", "file1_2_2": ""},
        "random_folder": {"file1": "", "file2": ""},
        "extra_file2": "",
        ".group.yml": "",
    },
    "group2": {
        "task2_1": {".task.yml": "", "file2_1_1": "", "file2_1_2": ""},
        "task2_2": {".task.yml": "version: 1"},
        "task2_3": {".task.yml": " \n  \n", "file2_3_1": "", "file2_3_2": "", "file2_3_3": "", "file2_3_4": ""},
        "random_folder": {"file1": "", "file2": ""},
        ".group.yml": "version: 1",
    },
    "group3": {".group.yml": ""},
    "group4": {
        "task4_1": {".task.yml": "version: 1"},
        ".group.yml": "",
    },
    "random_folder": {"file1": "", "file2": ""},
    "root_task_1": {".task.yml": "version: 1", "file1": "", "file2": ""},
    "extra_file1": "",
}
TEST_MANYTASK_CONFIG = ManytaskConfig(
    version=1,
    settings={
        "course_name": "test",
        "gitlab_base_url": "https://google.com",
        "public_repo": "public",
        "students_group": "students",
    },
    ui={"task_url_template": "https://example.com/$GROUP_NAME/$TASK_NAME"},
    deadlines={
        "timezone": TEST_TIMEZONE,
        "schedule": [
            {
                "group": "group1",
                "start": "2020-10-10 00:00:00",
                "end": "200d",
                "enabled": True,
                "tasks": [
                    {"task": "task1_1", "score": TASK_SCORE_10},
                    {"task": "task1_2", "score": TASK_SCORE_20},
                ],
            },
            {
                "group": "group2",
                "start": "2020-10-10 00:00:00",
                "end": "200d",
                "enabled": False,
                "tasks": [
                    {"task": "task2_1", "score": TASK_SCORE_30},
                    {"task": "task2_2", "score": TASK_SCORE_40},
                    {"task": "task2_3", "score": TASK_SCORE_50},
                ],
            },
            {
                "group": "group3",
                "start": "2020-10-10 00:00:00",
                "end": "200d",
                "enabled": True,
                "tasks": [],
            },
            {
                "group": "group4",
                "start": "2020-10-10 00:00:00",
                "end": "200d",
                "enabled": True,
                "tasks": [{"task": "task4_1", "score": TASK_SCORE_50}],
            },
            {
                "group": "group_without_folder",
                "start": "2020-10-10 00:00:00",
                "end": "200d",
                "enabled": True,
                "tasks": [{"task": "root_task_1", "score": TASK_SCORE_50}],
            },
        ],
    },
)


@pytest.fixture()
def repository_root(generate_file_structure: T_GENERATE_FILE_STRUCTURE) -> Path:
    return generate_file_structure(TEST_FILE_STRUCTURE)


@pytest.fixture()
def git_init_repository_root(repository_root: Path) -> Path:
    # init git repo
    repo = git.Repo.init(repository_root)
    # setup local config
    repo.config_writer().set_value("user", "name", "test_user").release()
    repo.config_writer().set_value("user", "email", "not@val.id").release()
    # commit changes
    repo.git.add(".")
    repo.git.commit("-m", "initial commit")
    return repository_root


class TestCourse:
    def test_init(self, repository_root: Path) -> None:
        test_course = Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=repository_root)
        assert test_course.repository_root == repository_root
        assert test_course.manytask_config == TEST_MANYTASK_CONFIG

    def test_validate(self, repository_root: Path) -> None:
        test_course = Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=repository_root)

        try:
            test_course.validate()
        except Exception as e:
            pytest.fail(f"Validation failed: {e}")

    def test_search_for_groups_by_configs(self, repository_root: Path) -> None:
        potential_groups = list(Course._search_for_groups_by_configs(repository_root))
        assert len(potential_groups) == EXPECTED_NUM_GROUPS_4
        assert sum(len(group.tasks) for group in potential_groups) == EXPECTED_NUM_TASKS_6
        for group in potential_groups:
            assert isinstance(group, FileSystemGroup)
            assert (repository_root / group.relative_path).exists()

    def test_search_for_tasks_by_configs(self, repository_root: Path) -> None:
        tasks = list(Course._search_for_tasks_by_configs(repository_root))
        assert len(tasks) == EXPECTED_NUM_TASKS_7
        for task in tasks:
            assert isinstance(task, FileSystemTask)
            assert (repository_root / task.relative_path).exists()

    def test_validate_missing_task(self, repository_root: Path) -> None:
        shutil.rmtree(repository_root / "group1" / "task1_1")
        with pytest.raises(BadConfig):
            Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=repository_root).validate()

    def test_validate_missing_group(self, repository_root: Path) -> None:
        shutil.rmtree(repository_root / "group3")
        with pytest.warns():
            Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=repository_root).validate()

    def test_init_task_bad_config(self, repository_root: Path) -> None:
        with open(repository_root / "group1" / "task1_1" / Course.TASK_CONFIG_NAME, "w") as f:
            f.write("bad_config")

        with pytest.raises(BadConfig):
            Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=repository_root)

    @pytest.mark.parametrize(
        "enabled, expected_num_groups",
        [
            (None, EXPECTED_NUM_GROUPS_4),
            (True, EXPECTED_NUM_GROUPS_3),
            (False, EXPECTED_NUM_GROUPS_1),
        ],
    )
    def test_get_groups(self, enabled: bool | None, expected_num_groups, repository_root: Path) -> None:
        test_course = Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=repository_root)

        groups = test_course.get_groups(enabled=enabled)
        assert isinstance(groups, list)
        assert all(isinstance(group, FileSystemGroup) for group in groups)
        assert len(groups) == expected_num_groups

    @pytest.mark.parametrize(
        "enabled, expected_num_tasks",
        [
            (None, EXPECTED_NUM_TASKS_7),
            (True, EXPECTED_NUM_TASKS_4),
            (False, EXPECTED_NUM_TASKS_3),
        ],
    )
    def test_get_tasks(self, enabled: bool | None, expected_num_tasks, repository_root: Path) -> None:
        test_course = Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=repository_root)

        tasks = test_course.get_tasks(enabled=enabled)
        assert isinstance(tasks, list)
        assert all(isinstance(task, FileSystemTask) for task in tasks)
        assert len(tasks) == expected_num_tasks

    def test_detect_changes_not_a_repo(self, repository_root: Path) -> None:
        test_course = Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=repository_root)
        with pytest.raises(CheckerException):
            test_course.detect_changes(CheckerTestingConfig.ChangesDetectionType.COMMIT_MESSAGE)

    @pytest.mark.parametrize(
        "branch_name, changed_files, expected_changed_tasks",
        [
            ("task1_1", ["group1/task1_1/file1_1_1"], ["task1_1"]),
            ("task1_1", ["group1/task1_1/file1_1_1", "random_file.txt", "group1/task1_1/file1_1_1"], ["task1_1"]),
            ("task2_1", ["group2/task2_1/file1_1_1"], []),  # not enabled
            ("not_a_task", ["group2/task2_1/file2_1_1"], []),
            ("root_task_1", ["root_task_1/file1"], ["root_task_1"]),
            ("root_task_1", [], ["root_task_1"]),
            # group names
            ("group1", ["group1/task1_1/file1_1_1"], ["task1_1", "task1_2"]),
            ("group1", ["group2/task2_1/file1_1_1"], ["task1_1", "task1_2"]),
            ("group1", [], ["task1_1", "task1_2"]),
            ("group2", ["group2/task2_1/file1_1_1"], []),  # not enabled
            ("group3", ["group1/task1_1/file1_1_1"], []),  # empty group
            ("group_without_folder", [], ["root_task_1"]),
        ],
    )
    def test_detect_changes_by_branch_name(
        self,
        git_init_repository_root: Path,
        branch_name: str,
        changed_files: list[str],
        expected_changed_tasks: list[str],
    ) -> None:
        test_course = Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=git_init_repository_root)
        repo = git.Repo(git_init_repository_root)

        # create new branch
        repo.git.checkout("-b", branch_name)
        # create or change files
        for filename in changed_files:
            Path(git_init_repository_root / filename).write_text(f"random_text_to_write_in_file {filename}")
        # commit changes (allow empty commit)
        repo.git.add(".")
        repo.git.commit("-m", "random commit message", "--allow-empty")

        changed_tasks = test_course.detect_changes(CheckerTestingConfig.ChangesDetectionType.BRANCH_NAME)
        assert isinstance(changed_tasks, list)
        assert all(isinstance(task, FileSystemTask) for task in changed_tasks)
        assert len(changed_tasks) == len(expected_changed_tasks)
        assert sorted(task.name for task in changed_tasks) == sorted(expected_changed_tasks)

    @pytest.mark.parametrize(
        "commit_message, changed_files, expected_changed_tasks",
        [
            ("task1_1", ["group1/task1_1/file1_1_1"], ["task1_1"]),
            ("fixses in task1_1", ["group1/task1_1/file1_1_1"], ["task1_1"]),
            (
                "task1_1 some commit",
                ["group1/task1_1/file1_1_1", "random_file.txt", "group1/task1_1/file1_1_1"],
                ["task1_1"],
            ),
            ("add fixes for task2_1", ["group2/task2_1/file1_1_1"], []),  # not enabled
            ("    not_a_task", ["group2/task2_1/file2_1_1"], []),
            ("root_task_1", ["root_task_1/file1"], ["root_task_1"]),
            ("my root_task_1 is really cool", [], ["root_task_1"]),
            (
                "my root_task_1 and task1_1 and not enabled task2_1",
                ["group2/task2_1/file2_1_1"],
                ["root_task_1", "task1_1"],
            ),
            ("commit root_task_1", [], ["root_task_1"]),
            ("commit root_task_1 and some more", [], ["root_task_1"]),
            # group names
            ("commit with group1 group1 group1 group1", ["group1/task1_1/file1_1_1"], ["task1_1", "task1_2"]),
            ("commit with group1", ["group2/task2_1/file1_1_1"], ["task1_1", "task1_2"]),
            ("my solutions for group1 and group_without_folder", [], ["task1_1", "task1_2", "root_task_1"]),
            ("group2 and group22", ["group2/task2_1/file1_1_1"], []),  # not enabled
            ("group3", ["group1/task1_1/file1_1_1"], []),  # empty group
            ("group_without_folder", [], ["root_task_1"]),
        ],
    )
    def test_detect_changes_by_commit_message(
        self,
        git_init_repository_root: Path,
        commit_message: str,
        changed_files: list[str],
        expected_changed_tasks: list[str],
    ) -> None:
        test_course = Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=git_init_repository_root)
        repo = git.Repo(git_init_repository_root)

        # create or change files
        for filename in changed_files:
            Path(git_init_repository_root / filename).write_text(f"random_text_to_write_in_file {filename}")
        # commit changes (allow empty commit)
        repo.git.add(".")
        repo.git.commit("-m", commit_message, "--allow-empty")

        changed_tasks = test_course.detect_changes(CheckerTestingConfig.ChangesDetectionType.COMMIT_MESSAGE)
        assert isinstance(changed_tasks, list)
        assert all(isinstance(task, FileSystemTask) for task in changed_tasks)
        assert len(changed_tasks) == len(expected_changed_tasks)
        assert sorted(task.name for task in changed_tasks) == sorted(expected_changed_tasks)

    @pytest.mark.parametrize(
        "changed_files, expected_changed_tasks",
        [
            (["group1/task1_1/file.txt"], ["task1_1"]),
            (["group1/task1_1/file.txt", "random_file.txt", "group1/task1_1/file.txt"], ["task1_1"]),
            (["group2/task2_1/file.txt"], []),  # not enabled
            (["group2/task2_1/file2_1_1.txt"], []),  # not enabled
            (["some_root_file", "random_folder/random_file.txt"], []),
            (
                ["group2/task2_1/file2_1_1.txt", "group1/task1_1/file.txt", "root_task_1/some.txt"],
                ["task1_1", "root_task_1"],
            ),
            (["root_task_1/file1.txt"], ["root_task_1"]),
            ([], []),
        ],
    )
    def test_detect_changes_by_last_commit_changes(
        self, git_init_repository_root: Path, changed_files: list[str], expected_changed_tasks: list[str]
    ) -> None:
        test_course = Course(manytask_config=TEST_MANYTASK_CONFIG, repository_root=git_init_repository_root)
        repo = git.Repo(git_init_repository_root)

        # create or change files
        for filename in changed_files:
            Path(git_init_repository_root / filename).write_text(f"random_text_to_write_in_file {filename}")
        # commit changes (allow empty commit)
        repo.git.add(".")
        repo.git.commit("-m", "random commit message", "--allow-empty")

        changed_tasks = test_course.detect_changes(CheckerTestingConfig.ChangesDetectionType.LAST_COMMIT_CHANGES)
        assert isinstance(changed_tasks, list)
        assert all(isinstance(task, FileSystemTask) for task in changed_tasks)
        assert len(changed_tasks) == len(expected_changed_tasks)
        assert sorted(task.name for task in changed_tasks) == sorted(expected_changed_tasks)
