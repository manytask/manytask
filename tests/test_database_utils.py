import pytest
from flask import Flask

from manytask.database_utils import get_database_table_data

TASK_1 = "task1"
TASK_2 = "task2"
TASK_3 = "task3"

STUDENT_1 = "student1"
STUDENT_2 = "student2"

SCORES = {STUDENT_1: {TASK_1: 100, TASK_2: 90, "total": 190}, STUDENT_2: {TASK_1: 80, TASK_2: 85, "total": 165}}


@pytest.fixture
def app():
    app = Flask(__name__)
    return app


@pytest.fixture
def mock_course():
    class MockCourse:
        def __init__(self):
            self.storage_api = MockStorageApi()

    class MockStorageApi:
        class MockGroup:
            def __init__(self, tasks):
                self.tasks = tasks
                self.name = "test_group"

        class MockTask:
            def __init__(self, name, enabled):
                self.name = name
                self.enabled = enabled

        def __init__(self):
            self.groups = [
                self.MockGroup(
                    [
                        # name, enabled
                        self.MockTask(TASK_1, True),
                        self.MockTask(TASK_2, True),
                        self.MockTask(TASK_3, False),
                    ]
                )
            ]

        def get_groups(self):
            return self.groups

        @staticmethod
        def get_all_scores():
            return {
                STUDENT_1: {TASK_1: SCORES[STUDENT_1][TASK_1], TASK_2: SCORES[STUDENT_1][TASK_2]},
                STUDENT_2: {TASK_1: SCORES[STUDENT_2][TASK_1], TASK_2: SCORES[STUDENT_2][TASK_2]},
            }

    return MockCourse()


def test_get_database_table_data(app, mock_course):
    expected_tasks_count = 2
    expected_students_count = 2

    with app.test_request_context():
        app.course = mock_course
        result = get_database_table_data()

        assert "tasks" in result
        assert "students" in result

        tasks = result["tasks"]
        # Only enabled tasks
        assert len(tasks) == expected_tasks_count
        assert tasks[0]["name"] == TASK_1
        assert tasks[1]["name"] == TASK_2
        assert all(task["score"] == 0 for task in tasks)

        students = result["students"]
        assert len(students) == expected_students_count

        for student_id in [STUDENT_1, STUDENT_2]:
            student = next(s for s in students if s["username"] == student_id)
            assert student["total_score"] == SCORES[student_id]["total"]
            assert student["scores"] == {TASK_1: SCORES[student_id][TASK_1], TASK_2: SCORES[student_id][TASK_2]}


def test_get_database_table_data_no_scores(app, mock_course):
    expected_tasks_count = 2

    with app.test_request_context():
        mock_course.storage_api.get_all_scores = lambda: {}
        app.course = mock_course
        result = get_database_table_data()

        assert "tasks" in result
        assert "students" in result
        assert len(result["tasks"]) == expected_tasks_count
        assert len(result["students"]) == 0
