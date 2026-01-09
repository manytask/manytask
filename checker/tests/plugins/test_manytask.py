from __future__ import annotations

from datetime import datetime
from os.path import basename
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Type

import pytest
from pydantic import HttpUrl, ValidationError
from pytest_mock import MockFixture
from requests_mock import Mocker

from checker.plugins.manytask import ManytaskPlugin, PluginExecutionFailed


class TestManytaskPlugin:
    REPORT_URL = HttpUrl("https://app.manytask.org/api/test/report")
    REPORT_TOKEN = "report_token"
    TEST_TASK_NAME = "some_task"
    TEST_USERNAME = "username"
    TEST_SCORE = 1.0
    TEST_ORIGIN = "./"
    TEST_PATTERNS = ["*"]
    TEST_NOW_DATETIME = datetime(2023, 12, 21, 0, 52, 36, 166028).astimezone()
    TEST_NOW_DATETIME_STR = "2023-12-21 00:52:36+0600"
    TEST_CHECK_DEADLINE = True

    @staticmethod
    def get_default_args_dict() -> dict[str, Any]:
        return {
            "username": TestManytaskPlugin.TEST_USERNAME,
            "task_name": TestManytaskPlugin.TEST_TASK_NAME,
            "score": TestManytaskPlugin.TEST_SCORE,
            "report_url": TestManytaskPlugin.REPORT_URL,
            "report_token": TestManytaskPlugin.REPORT_TOKEN,
            "check_deadline": TestManytaskPlugin.TEST_CHECK_DEADLINE,
        }

    @staticmethod
    def get_default_full_args_dict() -> dict[str, Any]:
        args_dict = TestManytaskPlugin.get_default_args_dict()
        args_dict.update(
            {
                "origin": TestManytaskPlugin.TEST_ORIGIN,
                "patterns": TestManytaskPlugin.TEST_PATTERNS,
                "send_time": TestManytaskPlugin.TEST_NOW_DATETIME_STR,
            }
        )
        return args_dict

    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            ({}, None),
            (
                {
                    "origin": "test/",
                    "patterns": ["*.py"],
                },
                None,
            ),
            (
                {
                    "origin": "/test/test/test",
                    "patterns": ["*.py", "**.*", "test"],
                },
                None,
            ),
            (
                {
                    "origin": "./",
                },
                None,
            ),
            (
                {
                    "origin": "",
                    "patterns": [],
                },
                None,
            ),
            (
                {
                    "score": 0.01,
                },
                None,
            ),
            (
                {
                    "score": 1.0,
                },
                None,
            ),
            (
                {
                    "score": 1.5,
                },
                None,
            ),
            ({"send_time": TEST_NOW_DATETIME}, None),
            ({"send_time": TEST_NOW_DATETIME_STR}, None),
            ({"send_time": "invalidtime"}, ValidationError),
            ({"report_url": "invalidurl"}, ValidationError),
        ],
    )
    def test_plugin_args(self, parameters: dict[str, Any], expected_exception: Type[BaseException] | None) -> None:
        args = self.get_default_args_dict()
        args.update(parameters)
        if expected_exception:
            with pytest.raises(expected_exception):
                ManytaskPlugin.Args(**args)
        else:
            ManytaskPlugin.Args(**args)

    def test_empty_args_raise_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ManytaskPlugin.Args(**{})

    def test_date_without_timezone_throws_warning(self) -> None:
        plugin = ManytaskPlugin()
        args = self.get_default_args_dict()
        args["send_time"] = self.TEST_NOW_DATETIME.replace(tzinfo=None)

        with Mocker() as mocker:
            mocker.post(f"{self.REPORT_URL}", status_code=200, text='{"score": 1.0}')

            output = plugin.run(args)

        assert "Warning: No timezone" in output.output

    def test_date_with_timezone_doesnt_throw_warning(self) -> None:
        plugin = ManytaskPlugin()
        args = self.get_default_args_dict()
        args["send_time"] = self.TEST_NOW_DATETIME.astimezone()

        with Mocker() as mocker:
            mocker.post(f"{self.REPORT_URL}", status_code=200, text='{"score": 1.0}')

            output = plugin.run(args)

        assert "Warning: No timezone" not in output.output

    @pytest.mark.parametrize(
        "extensions_to_create, patterns_to_take, taken_files_num",
        [
            ([".py", ".yml", ".txt"], ["*"], 3),
            ([".py", ".yml", ".txt"], ["*.py"], 1),
            ([".py", ".yml", ".py", ".yml", ".txt"], ["*.py", "*.yml"], 4),
            ([".py", ".yml", ".txt"], ["*.not"], 0),
        ],
    )
    def test_collect_files_to_send(
        self,
        mocker: MockFixture,
        extensions_to_create: list[str],
        patterns_to_take: list[str],
        taken_files_num: int,
    ) -> None:
        with TemporaryDirectory() as tdir:
            tempfiles = []
            expected_filenames = []

            for extension in extensions_to_create:
                ntfile = NamedTemporaryFile(dir=tdir, suffix=extension)
                tempfiles.append(ntfile)
                if f"*{extension}" in patterns_to_take or "*" in patterns_to_take:
                    expected_filenames.append(basename(tempfiles[-1].name))

            mocker.patch("builtins.open", mocker.mock_open(read_data=b"File content"))
            result = ManytaskPlugin._collect_files_to_send(tdir, patterns_to_take)

            assert result is not None, "Didn't collect files"
            assert len(result) == taken_files_num, "Wrong file quantity are collected"
            assert sorted(result.keys()) == sorted(expected_filenames), "Wrong files are collected"

            if taken_files_num:
                open.assert_called_with(mocker.ANY, "rb")  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "response_status_code, response_text, expected_exception",
        [
            (200, "Success", None),
            (408, "Request Timeout", PluginExecutionFailed),
            (503, "Service Unavailable", PluginExecutionFailed),
        ],
    )
    def test_post_with_retries(
        self,
        response_status_code: int,
        response_text: str,
        expected_exception: Type[BaseException],
    ) -> None:
        with Mocker() as mocker:
            mocker.post(
                f"{self.REPORT_URL}",
                status_code=response_status_code,
                text=response_text,
            )

            if expected_exception:
                with pytest.raises(expected_exception) as exc:
                    ManytaskPlugin._post_with_retries(self.REPORT_URL, {"key": "value"}, None)
                assert str(response_status_code) in str(exc.value), "Status code wasn't provided in exception message"
                assert response_text in str(exc.value), "Error text wasn't provided in exception message"
            else:
                result = ManytaskPlugin._post_with_retries(self.REPORT_URL, {"key": "value"}, None)
                assert result.status_code == 200
                assert result.text == "Success"

    def test_plugin_run(self, mocker: MockFixture) -> None:
        args_dict = self.get_default_full_args_dict()
        result_score = 1.0
        expected_files = {"files": "good"}
        expected_data = {
            "token": self.REPORT_TOKEN,
            "task": self.TEST_TASK_NAME,
            "username": self.TEST_USERNAME,
            "score": self.TEST_SCORE,
            "check_deadline": self.TEST_CHECK_DEADLINE,
            "submit_time": self.TEST_NOW_DATETIME_STR,
        }

        mocker.patch.object(ManytaskPlugin, "_collect_files_to_send")
        ManytaskPlugin._collect_files_to_send.return_value = expected_files  # type: ignore[attr-defined]
        mocker.patch.object(ManytaskPlugin, "_post_with_retries")
        ManytaskPlugin._post_with_retries.return_value.json.return_value = {"score": result_score}  # type: ignore[attr-defined]
        result = ManytaskPlugin().run(args_dict)

        assert result.output == (
            f"Report for task '{self.TEST_TASK_NAME}' for user '{self.TEST_USERNAME}', "
            f"requested score: {self.TEST_SCORE}, result score: {result_score}"
        )

        ManytaskPlugin._post_with_retries.assert_called_once_with(self.REPORT_URL, expected_data, expected_files)  # type: ignore[attr-defined]

    def test_verbose(self, mocker: MockFixture) -> None:
        args_dict = self.get_default_full_args_dict()
        expected_files = {"files": "good"}
        result_score = 1.0

        mocker.patch.object(ManytaskPlugin, "_collect_files_to_send")
        ManytaskPlugin._collect_files_to_send.return_value = expected_files  # type: ignore[attr-defined]
        mocker.patch.object(ManytaskPlugin, "_post_with_retries")
        ManytaskPlugin._post_with_retries.return_value.json.return_value = {"score": result_score}  # type: ignore[attr-defined]
        result = ManytaskPlugin().run(args_dict, verbose=True)

        assert str(expected_files) in result.output

    def test_bad_response(self, mocker: MockFixture) -> None:
        args_dict = self.get_default_args_dict()

        mocker.patch.object(ManytaskPlugin, "_post_with_retries")
        ManytaskPlugin._post_with_retries.return_value.json.return_value = {}  # type: ignore[attr-defined]

        with pytest.raises(PluginExecutionFailed) as exc:
            ManytaskPlugin().run(args_dict)

        assert str(exc.value) == "Unable to decode response"
