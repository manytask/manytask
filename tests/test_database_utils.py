import datetime
from dataclasses import dataclass

import pytest
from flask import Flask

from manytask.course import CourseStatus
from manytask.mock_rms import MockRmsApi
from manytask.utils.database import get_database_table_data
from tests.constants import MAX_SCORE, SCORES, STUDENT_1, STUDENT_2, STUDENT_DATA, TASK_1, TASK_2, TASK_3, TASK_LARGE


@pytest.fixture
def app():  # noqa: C901
    app = Flask(__name__)

    class MockStorageApi:
        class MockGroup:
            def __init__(self, tasks):
                self.tasks = tasks
                self.name = "test_group"
                self.start = datetime.datetime.now()

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
                        self.MockTask(TASK_1, 10, 0, True, False, False),
                        self.MockTask(TASK_2, 20, 0, True, True, False),
                        self.MockTask(TASK_3, 30, 0, False, False, False),
                        self.MockTask(TASK_LARGE, 200, 100, True, False, True),
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

        def get_groups(self, _course_name, enabled, started):
            return self.groups

        def get_grades(self, _course_name):
            return self.grades_config

        def get_now_with_timezone(self, course_name):
            return datetime.datetime.now() + datetime.timedelta(hours=1)

        @staticmethod
        def get_all_scores_with_names(_course_name):
            return {
                STUDENT_1: (
                    {
                        TASK_1: (SCORES[STUDENT_1][TASK_1], False),
                        TASK_2: (SCORES[STUDENT_1][TASK_2], False),
                        TASK_LARGE: (SCORES[STUDENT_1][TASK_LARGE], True),
                    },
                    (STUDENT_DATA[STUDENT_1][0], STUDENT_DATA[STUDENT_1][1]),
                    None,  # final_grade
                    None,  # final_grade_override
                    None,  # comment
                ),
                STUDENT_2: (
                    {
                        TASK_1: (SCORES[STUDENT_2][TASK_1], False),
                        TASK_2: (SCORES[STUDENT_2][TASK_2], False),
                        TASK_LARGE: (SCORES[STUDENT_2][TASK_LARGE], False),
                    },
                    (STUDENT_DATA[STUDENT_2][0], STUDENT_DATA[STUDENT_2][1]),
                    None,  # final_grade
                    None,  # final_grade_override
                    None,  # comment
                ),
            }

        @staticmethod
        def get_course(_name):
            @dataclass
            class Course:
                course_name: str = "test_course"
                gitlab_course_group: str = "test_course_group"
                gitlab_course_students_group: str = "test_course_students_group"
                status: CourseStatus = CourseStatus.IN_PROGRESS

            return Course()

    app.storage_api = MockStorageApi()
    app.rms_api = MockRmsApi(base_url="https://gitlab.com")

    return app


def test_get_database_table_data(app):
    """Test database table data without admin data (non-admin view)"""
    expected_tasks_count = 3
    expected_students_count = 2

    with app.test_request_context():
        test_course = app.storage_api.get_course("test_course")
        result = get_database_table_data(app, test_course, include_admin_data=False)

        assert result["max_score"] == MAX_SCORE
        assert "tasks" in result
        assert "students" in result

        tasks = result["tasks"]
        # Only enabled tasks
        assert len(tasks) == expected_tasks_count
        assert tasks[0]["name"] == TASK_1
        assert tasks[1]["name"] == TASK_2
        assert tasks[2]["name"] == TASK_LARGE
        assert all(task["score"] == 0 for task in tasks)

        students = result["students"]
        assert len(students) == expected_students_count

        for student_id in [STUDENT_1, STUDENT_2]:
            student = next(s for s in students if s["username"] == student_id)
            # Personal data should NOT be included for non-admins
            assert "first_name" not in student
            assert "last_name" not in student
            assert "repo_url" not in student
            assert "comment" not in student
            assert student["total_score"] == SCORES[student_id]["total"]
            assert student["large_count"] == SCORES[student_id]["large_count"]
            assert student["scores"] == {
                TASK_1: SCORES[student_id][TASK_1],
                TASK_2: SCORES[student_id][TASK_2],
                TASK_LARGE: SCORES[student_id][TASK_LARGE],
            }


def test_get_database_table_data_with_admin_data(app):
    """Test database table data with admin data (admin view)"""
    expected_tasks_count = 3
    expected_students_count = 2

    with app.test_request_context():
        test_course = app.storage_api.get_course("test_course")
        result = get_database_table_data(app, test_course, include_admin_data=True)

        assert result["max_score"] == MAX_SCORE
        assert "tasks" in result
        assert "students" in result

        tasks = result["tasks"]
        # Only enabled tasks
        assert len(tasks) == expected_tasks_count
        assert tasks[0]["name"] == TASK_1
        assert tasks[1]["name"] == TASK_2
        assert tasks[2]["name"] == TASK_LARGE
        assert all(task["score"] == 0 for task in tasks)

        students = result["students"]
        assert len(students) == expected_students_count

        for student_id in [STUDENT_1, STUDENT_2]:
            student = next(s for s in students if s["username"] == student_id)
            # Personal data SHOULD be included for admins
            assert student["first_name"] == STUDENT_DATA[student_id][0]
            assert student["last_name"] == STUDENT_DATA[student_id][1]
            assert "repo_url" in student
            assert "comment" in student
            assert student["total_score"] == SCORES[student_id]["total"]
            assert student["large_count"] == SCORES[student_id]["large_count"]
            assert student["scores"] == {
                TASK_1: SCORES[student_id][TASK_1],
                TASK_2: SCORES[student_id][TASK_2],
                TASK_LARGE: SCORES[student_id][TASK_LARGE],
            }


def test_get_database_table_data_no_scores(app):
    expected_tasks_count = 3

    with app.test_request_context():
        app.storage_api.get_all_scores_with_names = lambda _course_name: {}
        test_course = app.storage_api.get_course("test_course")
        result = get_database_table_data(app, test_course)

        assert "max_score" not in result
        assert "tasks" in result
        assert "students" in result
        assert len(result["tasks"]) == expected_tasks_count
        assert len(result["students"]) == 0
