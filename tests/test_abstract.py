from manytask.abstract import StoredUser
from tests.constants import (
    TEST_AUTH_ID_1,
    TEST_AUTH_ID_2,
    TEST_FIRST_NAME_1,
    TEST_FIRST_NAME_2,
    TEST_LAST_NAME_1,
    TEST_LAST_NAME_2,
    TEST_RMS_ID_1,
    TEST_RMS_ID_2,
    TEST_USERNAME_1,
    TEST_USERNAME_2,
)


def test_stored_user():
    stored_user1 = StoredUser(
        TEST_USERNAME_1, TEST_FIRST_NAME_1, TEST_LAST_NAME_1, rms_id=TEST_RMS_ID_1, auth_id=TEST_AUTH_ID_1
    )

    assert not stored_user1.instance_admin
    assert repr(stored_user1) == f"StoredUser(username={TEST_USERNAME_1})"

    stored_user2 = StoredUser(
        TEST_USERNAME_2,
        TEST_FIRST_NAME_2,
        TEST_LAST_NAME_2,
        rms_id=TEST_RMS_ID_2,
        auth_id=TEST_AUTH_ID_2,
        instance_admin=True,
    )

    assert stored_user2.instance_admin
    assert repr(stored_user2) == f"StoredUser(username={TEST_USERNAME_2})"
