from manytask.abstract import StoredUser, StudentCourseScores, TaskScore
from tests.constants import (
    TEST_AUTH_ID_1,
    TEST_AUTH_ID_2,
    TEST_FIRST_NAME_1,
    TEST_FIRST_NAME_2,
    TEST_LAST_NAME_1,
    TEST_LAST_NAME_2,
    TEST_RMS_ID_1,
    TEST_RMS_ID_2,
    TEST_USER_ID_1,
    TEST_USER_ID_2,
    TEST_USERNAME_1,
    TEST_USERNAME_2,
)


def test_stored_user():
    stored_user1 = StoredUser(
        TEST_USERNAME_1,
        TEST_FIRST_NAME_1,
        TEST_LAST_NAME_1,
        rms_id=TEST_RMS_ID_1,
        auth_id=TEST_AUTH_ID_1,
        user_id=TEST_USER_ID_1,
    )

    assert not stored_user1.instance_admin
    assert repr(stored_user1) == f"StoredUser(username={TEST_USERNAME_1})"

    stored_user2 = StoredUser(
        TEST_USERNAME_2,
        TEST_FIRST_NAME_2,
        TEST_LAST_NAME_2,
        rms_id=TEST_RMS_ID_2,
        auth_id=TEST_AUTH_ID_2,
        user_id=TEST_USER_ID_2,
        instance_admin=True,
    )

    assert stored_user2.instance_admin
    assert repr(stored_user2) == f"StoredUser(username={TEST_USERNAME_2})"


def test_count_solved_large_tasks_uses_is_solved():
    student = StudentCourseScores(
        username="u",
        first_name="f",
        last_name="l",
        task_scores={
            "solved_flag": TaskScore(score=300, is_solved=True),  # below min_score, but marked solved
            "by_score": TaskScore(score=330, is_solved=False),  # manually marked unsolved despite reaching min_score
            "not_solved": TaskScore(score=319, is_solved=False),
        },
    )

    assert student.count_solved_large_tasks(["solved_flag"]) == 1
    assert student.count_solved_large_tasks(["by_score"]) == 0
    assert student.count_solved_large_tasks(["not_solved"]) == 0
    # Completion flags remain authoritative after threshold changes or manual overrides.
    assert student.count_solved_large_tasks(["solved_flag", "by_score"]) == 1
    # A missing submission has no persisted completion flag.
    assert student.count_solved_large_tasks(["missing", "missing2"]) == 0


def test_large_count_uses_completion_flags() -> None:
    student = StudentCourseScores(
        username="student",
        first_name="First",
        last_name="Last",
        task_scores={"low": TaskScore(0, True), "high": TaskScore(100, False), "small": TaskScore(100, True)},
    )
    assert student.count_solved_large_tasks(["low", "high", "missing"]) == 1
