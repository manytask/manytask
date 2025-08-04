from dataclasses import dataclass

import pytest
from flask import Flask

from manytask.abstract import StoredUser
from manytask.database_utils import get_database_table_data
from tests import constants


@pytest.fixture
def app():
    app = Flask(__name__)

    class MockStorageApi:
        class MockGroup:
            def __init__(self, tasks):
                self.tasks = tasks
                self.name = "test_group"

        class MockTask:
            def __init__(self, name, score, enabled, is_bonus=False, is_large=False):
                self.name = name
                self.score = score
                self.enabled = enabled
                self.is_bonus = is_bonus
                self.is_large = is_large

        def __init__(self):
            self.groups = [
                self.MockGroup(
                    [
                        # name, enabled
                        self.MockTask(constants.TASK_1, 10, True, False, False),
                        self.MockTask(constants.TASK_2, 20, True, True, False),
                        self.MockTask(constants.TASK_3, 30, False, False, False),
                        self.MockTask(constants.TASK_LARGE, 200, True, False, True),
                    ]
                )
            ]

        def get_groups(self, _course_name):
            return self.groups

        @staticmethod
        def get_stored_user(_course_name, username):
            return StoredUser(
                username=username,
                first_name=constants.STUDENT_NAMES[username][0],
                last_name=constants.STUDENT_NAMES[username][1],
                course_admin=False,
            )

        @staticmethod
        def get_all_scores_with_names(_course_name):
            return {
                constants.STUDENT_1: (
                    {
                        constants.TASK_1: constants.SCORES[constants.STUDENT_1][constants.TASK_1],
                        constants.TASK_2: constants.SCORES[constants.STUDENT_1][constants.TASK_2],
                        constants.TASK_LARGE: constants.SCORES[constants.STUDENT_1][constants.TASK_LARGE],
                    },
                    constants.STUDENT_NAMES[constants.STUDENT_1],
                ),
                constants.STUDENT_2: (
                    {
                        constants.TASK_1: constants.SCORES[constants.STUDENT_2][constants.TASK_1],
                        constants.TASK_2: constants.SCORES[constants.STUDENT_2][constants.TASK_2],
                        constants.TASK_LARGE: constants.SCORES[constants.STUDENT_2][constants.TASK_LARGE],
                    },
                    constants.STUDENT_NAMES[constants.STUDENT_2],
                ),
            }

        @staticmethod
        def get_course(_name):
            @dataclass
            class Course:
                gitlab_course_group: str = "test_course_group"
                gitlab_course_students_group: str = "test_course_students_group"

            return Course()

    class MockGitLabApi:
        def __init__(self):
            pass

    app.storage_api = MockStorageApi()
    app.rms_api = MockGitLabApi()

    return app


def test_get_database_table_data(app):
    expected_tasks_count = 3
    expected_students_count = 2

    with app.test_request_context():
        result = get_database_table_data(app, "test_course")

        assert "tasks" in result
        assert "students" in result

        tasks = result["tasks"]
        # Only enabled tasks
        assert len(tasks) == expected_tasks_count
        assert tasks[0]["name"] == constants.TASK_1
        assert tasks[1]["name"] == constants.TASK_2
        assert tasks[2]["name"] == constants.TASK_LARGE
        assert all(task["score"] == 0 for task in tasks)

        students = result["students"]
        assert len(students) == expected_students_count

        for student_id in [constants.STUDENT_1, constants.STUDENT_2]:
            student = next(s for s in students if s["username"] == student_id)
            assert student["first_name"] == constants.STUDENT_NAMES[student_id][0]
            assert student["last_name"] == constants.STUDENT_NAMES[student_id][1]
            assert student["total_score"] == constants.SCORES[student_id]["total"]
            assert student["large_count"] == constants.SCORES[student_id]["large_count"]
            assert student["scores"] == {
                constants.TASK_1: constants.SCORES[student_id][constants.TASK_1],
                constants.TASK_2: constants.SCORES[student_id][constants.TASK_2],
                constants.TASK_LARGE: constants.SCORES[student_id][constants.TASK_LARGE],
            }


def test_get_database_table_data_no_scores(app):
    expected_tasks_count = 3

    with app.test_request_context():
        app.storage_api.get_all_scores_with_names = lambda _course_name: {}
        result = get_database_table_data(app, "test_course")

        assert "tasks" in result
        assert "students" in result
        assert len(result["tasks"]) == expected_tasks_count
        assert len(result["students"]) == 0
