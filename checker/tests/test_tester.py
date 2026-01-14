import typing
from datetime import datetime
from zoneinfo import ZoneInfo

from checker.configs import ManytaskConfig
from checker.configs.checker import CheckerTestingConfig
from checker.tester import Tester

TEST_MANYTASK_CONFIG = ManytaskConfig(
    version=1,
    settings={
        "course_name": "test",
        "gitlab_base_url": "https://google.com",
        "public_repo": "public",
        "students_group": "students",
    },
    ui={"task_url_template": "https://example.com/$GROUP_NAME/$TASK_NAME"},
    deadlines={
        "timezone": "Europe/Moscow",
        "deadlines": "interpolate",
        "window": 7,
        "schedule": [
            {
                "group": "group1",
                "start": "2025-02-16 00:00:00",
                "end": "2025-04-01 00:00:00",
                "enabled": True,
                "tasks": [
                    {"task": "task1_1", "score": 100},
                ],
                "steps": {
                    0.5: "2025-03-01 00:00:00",
                    0.3: "2025-03-16 00:00:00",
                },
            },
        ],
    },
)


class PipelineRunnerMock:
    def __init__(self, *args, **kwargs):
        pass


class CourseMock:
    def __init__(self):
        self.repository_root = ""
        self.reference_root = ""
        self.manytask_config = TEST_MANYTASK_CONFIG


class CheckerConfigMock:
    def __init__(self):
        pass

    @property
    def structure(self):
        return {}

    @property
    def default_parameters(self):
        return {}

    @property
    def testing(self):
        return CheckerTestingConfig()


def _get_timestamp(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("Europe/Moscow"))


class TestTester:
    @typing.no_type_check
    def test_task_score_percent(self, mocker):
        mock_load_plugins = mocker.patch("pkgutil.iter_modules")  # disable load_plugins typecheck
        mock_load_plugins.return_value = []
        tester = Tester(CourseMock(), CheckerConfigMock())
        assert 1 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-02-16 00:00:00"))  # start
        assert 1 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-02-20 00:00:00"))  # before 1st step
        assert 1 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-01 00:00:00"))  # 1st step
        score_str = tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-01 00:01:00")
        )  # don't count 1 minute
        assert 100 == round(float(score_str) * 100)
        assert 0.75 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-04 12:00:00"))  # linear
        assert 0.5 == tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-08 00:00:00")
        )  # before 2nd step
        assert 0.5 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-16 00:00:00"))  # 2nd step step
        score_str = tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-16 00:01:00")
        )  # don't count 1 minute
        assert 50 == round(float(score_str) * 100)
        assert 0.4 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-19 12:00:00"))  # linear
        assert 0.3 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-24 00:00:00"))
        assert 0.3 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-04-01 00:00:00"))
        assert 0 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-04-01 00:01:00"))
