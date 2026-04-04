import typing
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from checker.configs import ManytaskConfig
from checker.configs.checker import CheckerParametersConfig, CheckerSubConfig, CheckerTestingConfig, PipelineStageConfig
from checker.course import FileSystemTask
from checker.tester import Tester

# Test constants
FULL_SCORE_PERCENT = 100
HALF_SCORE_PERCENT = 50
SCORE_075 = 0.75
SCORE_05 = 0.5
SCORE_04 = 0.4
SCORE_03 = 0.3

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
        assert FULL_SCORE_PERCENT == round(float(score_str) * 100)
        assert SCORE_075 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-04 12:00:00"))  # linear
        assert SCORE_05 == tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-08 00:00:00")
        )  # before 2nd step
        assert SCORE_05 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-16 00:00:00"))  # 2nd step
        score_str = tester._get_task_score_percent(
            "task1_1", _get_timestamp("2025-03-16 00:01:00")
        )  # don't count 1 minute
        assert HALF_SCORE_PERCENT == round(float(score_str) * 100)
        assert SCORE_04 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-19 12:00:00"))  # linear
        assert SCORE_03 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-03-24 00:00:00"))
        assert SCORE_03 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-04-01 00:00:00"))
        assert 0 == tester._get_task_score_percent("task1_1", _get_timestamp("2025-04-01 00:01:00"))

    @typing.no_type_check
    @pytest.mark.parametrize(
        "group_params, task_params, expected",
        [
            ({"b": 10, "c": 3}, {"c": 50, "d": 6}, {"a": 1, "b": 10, "c": 50, "d": 6}),
            (None, {"b": 10, "c": 3}, {"a": 1, "b": 10, "c": 3}),
            ({"b": 10, "c": 3}, None, {"a": 1, "b": 10, "c": 3}),
        ],
    )
    def test_task_context_parameters_merge(self, mocker, group_params, task_params, expected):
        mocker.patch("pkgutil.iter_modules", return_value=[])
        tester = Tester(CourseMock(), CheckerConfigMock())
        tester.default_params = CheckerParametersConfig(root={"a": 1, "b": 2})

        group_config = (
            CheckerSubConfig(version=1, parameters=CheckerParametersConfig(root=group_params)) if group_params else None
        )
        mocker.patch.object(tester, "_get_group_config", return_value=group_config)

        task_config = (
            CheckerSubConfig(version=1, parameters=CheckerParametersConfig(root=task_params))
            if task_params
            else CheckerSubConfig(version=1)
        )
        task = FileSystemTask(name="task1_1", relative_path="group1/task1_1", config=task_config)

        context = tester._build_task_context(None, {}, task, None)
        assert context["parameters"] == expected

    @typing.no_type_check
    def test_global_context_has_only_default_parameters(self, mocker):
        mocker.patch("pkgutil.iter_modules", return_value=[])
        tester = Tester(CourseMock(), CheckerConfigMock())
        tester.default_params = CheckerParametersConfig(root={"a": 1, "b": 2})

        context = tester._build_global_context(None, {})
        assert context["parameters"] == {"a": 1, "b": 2}

    @typing.no_type_check
    @pytest.mark.parametrize(
        "method_name, config_attr, global_attr",
        [
            ("_get_task_pipeline_runner", "task_pipeline", "tasks_pipeline"),
            ("_get_task_report_pipeline_runner", "report_pipeline", "report_pipeline"),
        ],
    )
    @pytest.mark.parametrize("level", ["task", "group", "global"])
    def test_pipeline_resolution_hierarchy(self, mocker, method_name, config_attr, global_attr, level):
        mocker.patch("pkgutil.iter_modules", return_value=[])
        mock_runner = mocker.patch("checker.tester.PipelineRunner")
        tester = Tester(CourseMock(), CheckerConfigMock())

        task_pipeline = [PipelineStageConfig(name="task_stage", run="echo task")]
        group_pipeline = [PipelineStageConfig(name="group_stage", run="echo group")]
        global_pipeline = [PipelineStageConfig(name="global_stage", run="echo global")]

        setattr(tester.testing_config, global_attr, global_pipeline)

        task_config = CheckerSubConfig(version=1, **{config_attr: task_pipeline if level == "task" else None})
        group_config = CheckerSubConfig(version=1, **{config_attr: group_pipeline if level == "group" else None})
        mocker.patch.object(tester, "_get_group_config", return_value=group_config if level != "global" else None)

        task = FileSystemTask(name="task1_1", relative_path="group1/task1_1", config=task_config)
        getattr(tester, method_name)(task)

        if level == "task":
            expected = task_pipeline
        elif level == "group":
            expected = group_pipeline
        else:
            expected = global_pipeline

        assert mock_runner.call_args[0][0] == expected
