from manytask.abstract import StoredUser


def test_stored_user():
    stored_user1 = StoredUser("user1", "user", "1")

    assert not stored_user1.course_admin
    assert repr(stored_user1) == "StoredUser(username=user1)"

    stored_user2 = StoredUser("user2", "user", "2", True)

    assert stored_user2.course_admin
    assert repr(stored_user2) == "StoredUser(username=user2)"
