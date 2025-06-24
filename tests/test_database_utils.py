from dataclasses import dataclass

import pytest
from flask import Flask

from manytask.database_utils import get_database_table_data
from manytask.abstract import Student

TASK_1 = "task1"
TASK_2 = "task2"
TASK_3 = "task3"
TASK_LARGE = "task_large"

STUDENT_1 = "student1"
STUDENT_2 = "student2"

STUDENT_NAMES = {STUDENT_1: "Student Oneich", STUDENT_2: "Student Twoich"}

SCORES = {
    STUDENT_1: {TASK_1: 100, TASK_2: 90, TASK_LARGE: 200, "total": 390, "large_count": 1},
    STUDENT_2: {TASK_1: 80, TASK_2: 85, TASK_LARGE: 0, "total": 165, "large_count": 0},
}


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
                        self.MockTask(TASK_1, 10, True, False, False),
                        self.MockTask(TASK_2, 20, True, True, False),
                        self.MockTask(TASK_3, 30, False, False, False),
                        self.MockTask(TASK_LARGE, 200, True, False, True),
                    ]
                )
            ]

        def get_groups(self, _course_name):
            return self.groups

        @staticmethod
        def get_all_scores(_course_name):
            return {
                STUDENT_1: {
                    TASK_1: SCORES[STUDENT_1][TASK_1],
                    TASK_2: SCORES[STUDENT_1][TASK_2],
                    TASK_LARGE: SCORES[STUDENT_1][TASK_LARGE],
                },
                STUDENT_2: {
                    TASK_1: SCORES[STUDENT_2][TASK_1],
                    TASK_2: SCORES[STUDENT_2][TASK_2],
                    TASK_LARGE: SCORES[STUDENT_2][TASK_LARGE],
                },
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

        def get_student_by_username(self, username: str) -> Student:
            return Student(
                id=1,
                username=username,
                name=STUDENT_NAMES[username],
            )

    app.storage_api = MockStorageApi()
    app.gitlab_api = MockGitLabApi()

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
        assert tasks[0]["name"] == TASK_1
        assert tasks[1]["name"] == TASK_2
        assert tasks[2]["name"] == TASK_LARGE
        assert all(task["score"] == 0 for task in tasks)

        students = result["students"]
        assert len(students) == expected_students_count

        for student_id in [STUDENT_1, STUDENT_2]:
            student = next(s for s in students if s["username"] == student_id)
            assert student["student_name"] == STUDENT_NAMES[student_id]
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
        app.storage_api.get_all_scores = lambda _course_name: {}
        result = get_database_table_data(app, "test_course")

        assert "tasks" in result
        assert "students" in result
        assert len(result["tasks"]) == expected_tasks_count
        assert len(result["students"]) == 0
