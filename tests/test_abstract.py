from manytask.abstract import StoredUser


def test_stored_user():
    stored_user1 = StoredUser("user1", "Ivan", "Ivanov")

    assert not stored_user1.course_admin
    assert repr(stored_user1) == "StoredUser(username=user1)"

    stored_user2 = StoredUser("user2", "Ivan", "Ivanov", True)

    assert stored_user2.course_admin
    assert repr(stored_user2) == "StoredUser(username=user2)"
