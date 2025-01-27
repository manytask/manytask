import pytest
from cachelib import BaseCache

from manytask.gdoc import GoogleDocApi
from manytask.glab import Student


@pytest.fixture
def empty_google_doc_api():
    return GoogleDocApi(
        base_url="",
        gdoc_credentials={},
        public_worksheet_id="",
        public_scoreboard_sheet=0,
        cache=BaseCache(),
        testing=True
    )


def test_get_stored_user(empty_google_doc_api):
    student1 = Student(id=0, username='user1', name='', course_admin=False)
    stored_user1 = empty_google_doc_api.get_stored_user(student1)

    assert stored_user1.username == 'user1'
    assert stored_user1.course_admin == False

    student2 = Student(id=0, username='user2', name='', course_admin=True)
    stored_user2 = empty_google_doc_api.get_stored_user(student2)

    assert stored_user2.username == 'user2'
    assert stored_user2.course_admin == False


def test_sync_stored_user(empty_google_doc_api):
    student1 = Student(id=0, username='user1', name='', course_admin=False)

    assert empty_google_doc_api.sync_stored_user(student1) == empty_google_doc_api.get_stored_user(student1)

    student2 = Student(id=0, username='user2', name='', course_admin=True)

    assert empty_google_doc_api.sync_stored_user(student2) == empty_google_doc_api.get_stored_user(student2)
