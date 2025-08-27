from datetime import datetime
from zoneinfo import ZoneInfo

# common
TEST_USERNAME = "username"
TEST_FIRST_NAME = "First"
TEST_LAST_NAME = "Last"
TEST_RMS_ID = 1

TEST_USERNAME_1 = "user1"
TEST_FIRST_NAME_1 = "First"
TEST_LAST_NAME_1 = "Last1"
TEST_RMS_ID_1 = 2

TEST_USERNAME_2 = "user2"
TEST_FIRST_NAME_2 = "First2"
TEST_LAST_NAME_2 = "Last2"
TEST_RMS_ID_2 = 3

TEST_NAME = "Ivan Ivanov"
TEST_COURSE_NAME = "Test_Course"
TEST_USER_ID = 123
TEST_SECRET_KEY = "test_key"


# test_api
INVALID_TASK_NAME = "invalid_task"
TASK_NAME_WITH_DISABLED_TASK_OR_GROUP = "disabled_task"
TEST_TASK_NAME = "test_task"
TEST_TASK_GROUP_NAME = "test_task_group"
TEST_INVALID_USER_ID = 321
TEST_INVALID_USERNAME = "invalid_user"


# test_auth
TEST_SECRET = "test_secret"
TEST_TOKEN = "test_token"
GITLAB_BASE_URL = "https://gitlab.com"
TEST_VERSION = 1.5


# test_database_utils
TASK_1 = "task1"
TASK_2 = "task2"
TASK_3 = "task3"
MAX_SCORE = 210
TASK_LARGE = "task_large"
STUDENT_1 = "student1"
STUDENT_2 = "student2"
STUDENT_DATA = {
    STUDENT_1: [TEST_FIRST_NAME_1, TEST_LAST_NAME_1, 1],
    STUDENT_2: [TEST_FIRST_NAME_2, TEST_LAST_NAME_2, 2],
}
SCORES = {
    STUDENT_1: {TASK_1: 100, TASK_2: 90, TASK_LARGE: 200, "total": 390, "large_count": 1},
    STUDENT_2: {TASK_1: 80, TASK_2: 85, TASK_LARGE: 0, "total": 165, "large_count": 0},
}


# test_db_api
DEADLINES_CONFIG_FILES = [
    "tests/.deadlines.test.yml",
    "tests/.deadlines.test2.yml",
]
GRADE_CONFIG_FILES = [
    "tests/.grades.test.yml",
    "tests/.grades.test2.yml",
]
FIXED_CURRENT_TIME = datetime(2025, 4, 1, 12, 0, tzinfo=ZoneInfo("Europe/Berlin"))
FIRST_COURSE_NAME = "Test Course"
SECOND_COURSE_NAME = "Another Test Course"
FIRST_COURSE_EXPECTED_STATS_KEYS = {
    "task_0_0",
    "task_0_1",
    "task_0_2",
    "task_0_3",
    "task_1_0",
    "task_1_1",
    "task_1_2",
    "task_1_3",
    "task_1_4",
    "task_2_2",
    "task_2_3",
    "task_3_0",
    "task_3_1",
    "task_3_2",
    "task_5_0",
}
SECOND_COURSE_EXPECTED_STATS_KEYS = {
    "task_0_0",
    "task_0_1",
    "task_0_2",
    "task_0_3",
    "task_0_4",
    "task_0_5",
    "task_1_0",
    "task_1_1",
    "task_1_2",
    "task_1_3",
    "task_1_4",
    "task_2_0",
    "task_2_1",
    "task_2_3",
    "task_3_0",
    "task_3_1",
    "task_3_2",
    "task_3_3",
    "task_4_0",
    "task_4_1",
    "task_4_2",
    "task_5_0",
    "task_5_1",
    "task_5_2",
}
FIRST_COURSE_EXPECTED_MAX_SCORE_STARTED = 250
SECOND_COURSE_EXPECTED_MAX_SCORE_STARTED = 540
USER_EXPECTED = 2


# test_glab
TEST_USER_EMAIL = "test-email@test.ru"
TEST_USER_PASSWORD = "testpassword"
TEST_USER_FIRSTNAME = "testfirstname"
TEST_USER_LASTNAME = "testlastname"
TEST_USER_URL = "example_repo"

TEST_PROJECT_ID = 1
TEST_PROJECT_NAME = "TestProject"
TEST_PROJECT_FULL_NAME = "some/TestGroup/TestProject"

TEST_GROUP_ID = 1
TEST_GROUP_NAME = "some/TestGroup"
TEST_GROUP_NAME_SHORT = "TestGroup"
TEST_GROUP_NAME_FULL = "some / TestGroup"

TEST_GROUP_ID_PUBLIC = 2
TEST_GROUP_PUBLIC_NAME = "some/TestGroup/TestProject/Public"
TEST_GROUP_PUBLIC_NAME_SHORT = "Public"
TEST_GROUP_PUBLIC_NAME_FULL = "some / TestGroup / TestProject / Public"
TEST_GROUP_PUBLIC_DEFAULT_BRANCH = "main"

TEST_GROUP_ID_STUDENT = 3
TEST_GROUP_STUDENT_NAME = "some/TestGroup/TestProject/Students"
TEST_GROUP_STUDENT_NAME_SHORT = "Students"
TEST_GROUP_STUDENT_NAME_FULL = "some / TestGroup / TestProject / Students"

TEST_FORK_ID = 1


# test_main
TEST_STUDENTS_GROUP = "test_students"
TEST_PUBLIC_REPO = "test_public_repo"
TEST_CACHE_DIR = "/tmp/manytask_test_cache"


# test_models
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
TEST_DEADLINE_DATA_INT = 12345
TEST_GRADE_SCORE = 77
TEST_TASK_COUNT = 2
TEST_TASK_COUNT_LARGE = 3
TEST_GRADE_COUNT = 4
TEST_DEADLINE_ID = 12345
TEST_GRADE_SCORE_2 = 123456
TEST_GRADE_SCORE_3 = 1234567
TEST_GRADE_SCORE_4 = 12345678
TEST_TASK_SCORE = 100
TEST_TASK_POSITION = 7
TEST_TASK_GROUP_POSITION = 5
TEST_MAX_SUBMISSIONS = 10
TEST_SUBMISSION_PENALTY = 0.1
TEST_DEADLINE_STEPS = {0.4: datetime(2000, 1, 2, 3, 4, 5, 6, tzinfo=ZoneInfo("Europe/Berlin"))}
