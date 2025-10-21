import typing
from datetime import datetime
from zoneinfo import ZoneInfo

from checker.configs import ManytaskConfig
from checker.configs.checker import CheckerTestingConfig
from checker.tester import Tester

# Test score percentage constants
SCORE_100_PERCENT = 1.0
SCORE_75_PERCENT = 0.75
SCORE_50_PERCENT = 0.5
SCORE_40_PERCENT = 0.4
SCORE_30_PERCENT = 0.3
SCORE_0_PERCENT = 0.0

# Test percentage rounding values
PERCENTAGE_100 = 100
PERCENTAGE_50 = 50

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
                    SCORE_50_PERCENT: "2025-03-01 00:00:00",
                    SCORE_30_PERCENT: "2025-03-16 00:00:00",
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
        assert SCORE_100_PERCENT == tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-02-16 00:00:00")
        )  # start
        assert SCORE_100_PERCENT == tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-02-20 00:00:00")
        )  # before 1st step
        assert SCORE_100_PERCENT == tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-01 00:00:00")
        )  # 1st step
        score_str = tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-01 00:01:00")
        )  # don't count 1 minute
        assert PERCENTAGE_100 == round(float(score_str) * PERCENTAGE_100)
        assert SCORE_75_PERCENT == tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-04 12:00:00")
        )  # linear
        assert SCORE_50_PERCENT == tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-08 00:00:00")
        )  # before 2nd step
        assert SCORE_50_PERCENT == tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-16 00:00:00")
        )  # 2nd step step
        score_str = tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-16 00:01:00")
        )  # don't count 1 minute
        assert PERCENTAGE_50 == round(float(score_str) * PERCENTAGE_100)
        assert SCORE_40_PERCENT == tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-19 12:00:00")
        )  # linear
        assert SCORE_30_PERCENT == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-24 00:00:00"))
        assert SCORE_30_PERCENT == tester._get_task_score_percent("task1_1", _get_timestamp("2025-04-01 00:00:00"))
        assert SCORE_0_PERCENT == tester._get_task_score_percent("task1_1", _get_timestamp("2025-04-01 00:01:00"))
