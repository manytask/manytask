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
            "by_score": TaskScore(score=330, is_solved=False),  # reaches min_score
            "not_solved": TaskScore(score=319, is_solved=False),
        },
    )

    assert student.count_solved_large_tasks([("solved_flag", 320)]) == 1
    assert student.count_solved_large_tasks([("by_score", 320)]) == 1
    assert student.count_solved_large_tasks([("not_solved", 320)]) == 0
    # raising min_score does not take away a task marked as solved
    assert student.count_solved_large_tasks([("solved_flag", 10000), ("by_score", 10000)]) == 1
    # no score at all: counted only when min_score is 0, as before
    assert student.count_solved_large_tasks([("missing", 0), ("missing2", 1)]) == 1
