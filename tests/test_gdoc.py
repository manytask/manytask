import pytest
from cachelib import BaseCache

from manytask.gdoc import GDocConfig, GoogleDocApi
from manytask.glab import Student


@pytest.fixture
def empty_google_doc_api():
    return GoogleDocApi(
        GDocConfig(
            base_url="",
            gdoc_credentials={},
            public_worksheet_id="",
            public_scoreboard_sheet=0,
            cache=BaseCache(),
            testing=True,
        )
    )


def test_get_stored_user(empty_google_doc_api):
    student1 = Student(id=0, username="user1", name="", course_admin=False)
    stored_user1 = empty_google_doc_api.get_stored_user(student1)

    assert stored_user1.username == "user1"
    assert not stored_user1.course_admin

    student2 = Student(id=0, username="user2", name="", course_admin=True)
    stored_user2 = empty_google_doc_api.get_stored_user(student2)

    assert stored_user2.username == "user2"
    assert not stored_user2.course_admin


def test_sync_stored_user(empty_google_doc_api):
    student1 = Student(id=0, username="user1", name="", course_admin=False)

    assert empty_google_doc_api.sync_stored_user(student1) == empty_google_doc_api.get_stored_user(student1)

    student2 = Student(id=0, username="user2", name="", course_admin=True)

    assert empty_google_doc_api.sync_stored_user(student2) == empty_google_doc_api.get_stored_user(student2)


def test_update_cached_scores_not_implemented(empty_google_doc_api):
    with pytest.raises(NotImplementedError) as e:
        empty_google_doc_api.update_cached_scores()

    assert str(e.value) == "Deprecated api class"


def test_sync_columns_not_implemented(empty_google_doc_api):
    with pytest.raises(NotImplementedError) as e:
        empty_google_doc_api.sync_columns(None)

    assert str(e.value) == "Deprecated api class"


def test_find_task_not_implemented(empty_google_doc_api):
    with pytest.raises(NotImplementedError) as e:
        empty_google_doc_api.find_task("")

    assert str(e.value) == "Deprecated api class"


def test_get_groups_not_implemented(empty_google_doc_api):
    with pytest.raises(NotImplementedError) as e:
        empty_google_doc_api.get_groups()

    assert str(e.value) == "Deprecated api class"


def test_get_now_with_timezone_not_implemented(empty_google_doc_api):
    with pytest.raises(NotImplementedError) as e:
        empty_google_doc_api.get_now_with_timezone()

    assert str(e.value) == "Deprecated api class"


def test_max_score_not_implemented(empty_google_doc_api):
    with pytest.raises(NotImplementedError) as e:
        empty_google_doc_api.max_score()

    assert str(e.value) == "Deprecated api class"


def test_max_score_started_not_implemented(empty_google_doc_api):
    with pytest.raises(NotImplementedError) as e:
        empty_google_doc_api.max_score_started

    assert str(e.value) == "Deprecated api class"
