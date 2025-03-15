from manytask.abstract import StoredUser
from manytask.role import Role


def test_stored_user():
    stored_user1 = StoredUser("user1")

    assert not stored_user1.course_admin
    assert repr(stored_user1) == "StoredUser(username=user1, role=Role.STUDENT)"

    stored_user2 = StoredUser("user2", course_admin=True)

    assert stored_user2.course_admin
    assert repr(stored_user2) == "StoredUser(username=user2, role=Role.STUDENT)"

    stored_user3 = StoredUser("user3", role=Role.ADMIN)

    assert not stored_user3.course_admin
    assert stored_user3.role == Role.ADMIN
    assert repr(stored_user3) == "StoredUser(username=user3, role=Role.ADMIN)"