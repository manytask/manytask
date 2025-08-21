from dataclasses import dataclass

import pytest
from flask import Flask

from manytask.abstract import StoredUser
from manytask.database_utils import get_database_table_data
from tests import constants


@pytest.fixture
def app():  # noqa: C901
    app = Flask(__name__)

    class MockStorageApi:
        class MockGroup:
            def __init__(self, tasks):
                self.tasks = tasks
                self.name = "test_group"

        class MockTask:
            def __init__(self, name, score, min_score, enabled, is_bonus=False, is_large=False):
                self.name = name
                self.score = score
                self.min_score = min_score
                self.enabled = enabled
                self.is_bonus = is_bonus
                self.is_large = is_large

        class MockFinalGradeConfig:
            def __init__(self, grade_config):
                self.grade_config = grade_config
                self.grade_order = sorted(self.grade_config.keys(), reverse=True)

            def evaluate(self, row):
                for grade in self.grade_order:
                    if self.grade_config[grade].evaluate(row):
                        return grade

        class MockGradeConfig:
            def __init__(self, formulas):
                self.formulas = formulas

            def evaluate(self, row):
                return all(row[key] >= value for key, value in self.formulas.items())

        def __init__(self):
            self.groups = [
                self.MockGroup(
                    [
                        # name, enabled
                        self.MockTask(constants.TASK_1, 10, 0, True, False, False),
                        self.MockTask(constants.TASK_2, 20, 0, True, True, False),
                        self.MockTask(constants.TASK_3, 30, 0, False, False, False),
                        self.MockTask(constants.TASK_LARGE, 200, 100, True, False, True),
                    ]
                )
            ]

            self.grades_config = self.MockFinalGradeConfig(
                {
                    5: self.MockGradeConfig(
                        {
                            "total_score": 300,
                            "large_count": 1,
                        }
                    ),
                    4: self.MockGradeConfig({"total_score": 250, "large_count": 1}),
                    3: self.MockGradeConfig(
                        {
                            "total_score": 200,
                        }
                    ),
                    2: self.MockGradeConfig(
                        {
                            "total_score": 0,
                        }
                    ),
                }
            )

        def get_groups(self, _course_name):
            return self.groups

        def get_grades(self, _course_name):
            return self.grades_config

        @staticmethod
        def get_stored_user(username):
            return StoredUser(
                username=username,
                first_name=constants.STUDENT_DATA[username][0],
                last_name=constants.STUDENT_DATA[username][1],
                rms_id=constants.STUDENT_DATA[username][2],
                instance_admin=False,
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
                    (constants.STUDENT_DATA[constants.STUDENT_1][0], constants.STUDENT_DATA[constants.STUDENT_1][1]),
                ),
                constants.STUDENT_2: (
                    {
                        constants.TASK_1: constants.SCORES[constants.STUDENT_2][constants.TASK_1],
                        constants.TASK_2: constants.SCORES[constants.STUDENT_2][constants.TASK_2],
                        constants.TASK_LARGE: constants.SCORES[constants.STUDENT_2][constants.TASK_LARGE],
                    },
                    (constants.STUDENT_DATA[constants.STUDENT_2][0], constants.STUDENT_DATA[constants.STUDENT_2][1]),
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
            assert student["first_name"] == constants.STUDENT_DATA[student_id][0]
            assert student["last_name"] == constants.STUDENT_DATA[student_id][1]
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
