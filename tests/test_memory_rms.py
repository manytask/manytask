import pytest

from manytask.memory_rms import MemoryRmsApi, MemoryRmsApiException
from manytask.abstract import RmsUser


def test_register_new_user():
    api = MemoryRmsApi("https://memory.example.com")
    api.register_new_user("testuser", "Test", "User", "test@example.com", "password")
    
    user = api.get_rms_user_by_username("testuser")
    assert user.username == "testuser"
    assert user.name == "Test User"
    
    with pytest.raises(MemoryRmsApiException):
        api.get_rms_user_by_username("unknown")

def test_create_public_repo():
    api = MemoryRmsApi("https://memory.example.com")
    api.create_public_repo("course-group", "public-repo")
    
    assert api.check_project_exists("public-repo", "course-group") is True
    assert api.check_project_exists("unknown", "course-group") is False

def test_create_students_group():
    api = MemoryRmsApi("https://memory.example.com")
    api.create_students_group("students-group")
    
    # Just verify no exception is raised
    assert True

def test_create_project():
    api = MemoryRmsApi("https://memory.example.com")
    api.register_new_user("student1", "Student", "One", "s1@example.com", "pass")
    user = api.get_rms_user_by_username("student1")
    
    api.create_public_repo("course-group", "public-repo")
    api.create_students_group("students-group")
    api.create_project(user, "students-group", "public-repo")
    
    assert api.check_project_exists("student1", "students-group") is True
    assert api.get_url_for_repo("student1", "students-group") == "https://memory.example.com/students-group/student1"

def test_authenticated_user():
    api = MemoryRmsApi("https://memory.example.com")
    api.check_authenticated_rms_user("dummy-token")  # Should not raise
    user = api.get_authenticated_rms_user("dummy-token")
    assert user.username == "testuser"