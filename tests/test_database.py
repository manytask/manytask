from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from manytask.models import Course, Task, TaskGroup
from manytask.config import ManytaskDeadlinesConfig


# ruff: noqa
from tests.test_db_api import first_course_db_api, second_course_db_api


def create_test_config(tasks_config):
    """Helper function to create a valid config with all required fields"""
    return {
        "version": 1,
        "settings": {
            "timezone": "UTC",
            "course_name": "Test Course",
            "gitlab_base_url": "https://gitlab.test.com",
            "public_repo": "test-repo",
            "students_group": "students",
        },
        "ui": {
            "task_url_template": "https://gitlab.test.com/{course}/{student}/{task}",
        },
        "deadlines": {"timezone": "UTC", "schedule": [tasks_config]},
    }


def create_base_task_config(group_name: str, enabled: bool = True):
    """Helper function to create a base task config with standard fields"""
    return {
        "group": group_name,
        "start": datetime.now(ZoneInfo("UTC")),
        "end": datetime.now(ZoneInfo("UTC")) + timedelta(days=1),
        "enabled": enabled,
    }


def create_task_entry(task_name: str, enabled: bool = True, score: int = 100):
    """Helper function to create a task entry for the config"""
    return {"task": task_name, "enabled": enabled, "score": score}


def setup_course_with_tasks(
    session, course_name: str, tasks_data: list[tuple[str, str, str]]
) -> tuple[Course, list[Task]]:
    """Helper function to set up a course with tasks

    Args:
        session: SQLAlchemy session
        course_name: Name of the course
        tasks_data: List of (task_name, group_name, course_name) tuples

    Returns:
        Tuple of (course, list of created tasks)
    """
    course = session.query(Course).filter_by(name=course_name).one()
    tasks = []
    groups = {}

    for task_name, group_name, _ in tasks_data:
        if group_name not in groups:
            groups[group_name] = TaskGroup(name=group_name, course=course)
            session.add(groups[group_name])

        task = Task(name=task_name, group=groups[group_name])
        tasks.append(task)
        session.add(task)

    session.commit()
    return course, tasks


def test_move_task_between_groups(first_course_db_api, session):
    """Test moving a task from one group to another"""

    _, tasks = setup_course_with_tasks(session, "Test Course", [("task1", "group1", "Test Course")])

    tasks_config = create_base_task_config("group2")
    tasks_config["tasks"] = [create_task_entry("task1")]

    first_course_db_api.update_task_groups_from_config(
        ManytaskDeadlinesConfig(**create_test_config(tasks_config)["deadlines"])
    )

    task = session.query(Task).filter_by(name="task1").one()
    assert task.group.name == "group2"


def test_create_missing_group(first_course_db_api, session):
    """Test creating a new group when moving task to non-existent group"""

    _, tasks = setup_course_with_tasks(session, "Test Course", [("task1", "group1", "Test Course")])

    tasks_config = create_base_task_config("new_group")
    tasks_config["tasks"] = [create_task_entry("task1")]

    first_course_db_api.update_task_groups_from_config(
        ManytaskDeadlinesConfig(**create_test_config(tasks_config)["deadlines"])
    )

    task = session.query(Task).filter_by(name="task1").one()
    assert task.group.name == "new_group"
    assert session.query(TaskGroup).filter_by(name="new_group").count() == 1


def test_multiple_courses(first_course_db_api, second_course_db_api, session):
    """Test that tasks are only moved in the correct course"""

    tasks_data = [("task1", "group1", "Test Course"), ("task1", "group1", "Another Test Course")]

    _, tasks1 = setup_course_with_tasks(session, "Test Course", [tasks_data[0]])

    _, tasks2 = setup_course_with_tasks(session, "Another Test Course", [tasks_data[1]])

    course1 = session.query(Course).filter_by(name="Test Course").one()
    group2_c1 = TaskGroup(name="group2", course=course1)
    session.add(group2_c1)
    session.commit()

    tasks_config = create_base_task_config("group2")
    tasks_config["tasks"] = [create_task_entry("task1")]

    first_course_db_api.update_task_groups_from_config(
        ManytaskDeadlinesConfig(**create_test_config(tasks_config)["deadlines"])
    )

    task1_c1 = session.query(Task).join(TaskGroup).filter(Task.name == "task1", TaskGroup.course_id == course1.id).one()
    task1_c2 = session.query(Task).join(TaskGroup).filter(Task.name == "task1", TaskGroup.course_id != course1.id).one()

    assert task1_c1.group.name == "group2"
    assert task1_c2.group.name == "group1"


def test_multiple_task_moves(first_course_db_api, session):
    """Test moving multiple tasks between groups"""

    tasks_data = [
        ("task1", "group1", "Test Course"),
        ("task2", "group2", "Test Course"),
        ("task3", "group2", "Test Course"),
    ]
    _, tasks = setup_course_with_tasks(session, "Test Course", tasks_data)

    course = session.query(Course).filter_by(name="Test Course").one()
    group3 = TaskGroup(name="group3", course=course)
    session.add(group3)
    session.commit()

    tasks_config = create_base_task_config("group3")
    tasks_config["tasks"] = [create_task_entry("task1"), create_task_entry("task2"), create_task_entry("task3")]

    first_course_db_api.update_task_groups_from_config(
        ManytaskDeadlinesConfig(**create_test_config(tasks_config)["deadlines"])
    )

    tasks = session.query(Task).filter(Task.name.in_(["task1", "task2", "task3"])).all()
    for task in tasks:
        assert task.group.name == "group3"
