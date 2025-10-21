from __future__ import annotations

from io import StringIO
from typing import Any
from unittest.mock import patch

import dotenv
import pytest
from pydantic import ValidationError

from checker.exceptions import PluginExecutionFailed
from checker.plugins.scripts import RunScriptPlugin


class TestRunScriptPlugin:
    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            ({"origin": "/tmp", "script": "echo Hello"}, None),
            ({"origin": "/tmp", "script": 123}, ValidationError),
            ({"origin": "/tmp", "script": ["echo", "Hello"]}, None),
            ({"origin": "/tmp", "script": "echo Hello", "timeout": 10}, None),
            # TODO: check why timeout is not validated
            pytest.param(
                {"origin": "/tmp", "script": "echo Hello", "timeout": "10"},
                ValidationError,
                marks=pytest.mark.xfail(),
            ),
            ({"origin": "/tmp", "script": "echo Hello", "isolate": True}, None),
            (
                {
                    "origin": "/tmp",
                    "script": "echo Hello",
                    "env_whitelist": ["PATH"],
                },
                None,
            ),
        ],
    )
    def test_plugin_args(self, parameters: dict[str, Any], expected_exception: Exception | None) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                RunScriptPlugin.Args(**parameters)
        else:
            RunScriptPlugin.Args(**parameters)

    @pytest.mark.parametrize(
        "script, output, expected_exception",
        [
            ("echo Hello", "Hello", None),
            (["echo", "Hello"], "Hello", None),
            ("sleep 0.1", "", None),
            (["sleep", "0.1"], "", None),
            ("true", "", None),
            ("false", "", PluginExecutionFailed),
            ("echo Hello && false", "Hello", PluginExecutionFailed),
        ],
    )
    def test_simple_cases(self, script: str, output: str, expected_exception: Exception | None) -> None:
        plugin = RunScriptPlugin()
        args = RunScriptPlugin.Args(origin="/tmp", script=script)

        if expected_exception:
            with pytest.raises(expected_exception) as exc_info:
                plugin._run(args)
            assert output in exc_info.value.output
        else:
            result = plugin._run(args)
            assert result.output.strip() == output

    @pytest.mark.parametrize(
        "script, timeout, expected_exception",
        [
            (["echo", "Hello"], 10, None),
            (["sleep", "0.5"], 1, None),
            (["sleep", "0.5"], None, None),
            (["sleep", "1"], 0.5, PluginExecutionFailed),
        ],
    )
    def test_timeout(self, script: str, timeout: float, expected_exception: Exception | None) -> None:
        # TODO: check if timeout float
        plugin = RunScriptPlugin()
        args = RunScriptPlugin.Args(origin="/tmp", script=script, timeout=timeout)

        if expected_exception:
            with pytest.raises(expected_exception):
                plugin._run(args)
        else:
            plugin._run(args)

    @pytest.mark.parametrize("env_additional", [{}, {"A": "B"}, {"A": "C"}, {"A": "B", "C": "D"}])
    @pytest.mark.parametrize("env_whitelist", [None, [], ["A"], ["A", "C"]])
    @pytest.mark.parametrize("mocked_env", [{}, {"A": "B"}, {"A": "C"}, {"A": "B", "C": "D"}])
    def test_run_with_environment_variable(
        self, env_additional: dict[str, str], env_whitelist: list[str] | None, mocked_env: dict[str, str]
    ) -> None:
        plugin = RunScriptPlugin()
        args = RunScriptPlugin.Args(
            origin="/tmp", script="env", env_additional=env_additional, env_whitelist=env_whitelist
        )

        with patch.dict("os.environ", mocked_env, clear=True):
            result = plugin._run(args)

        env = dotenv.dotenv_values(stream=StringIO(result.output))
        assert set(env_additional.items()) <= set(env.items())

        if env_whitelist is None:
            mocked_env.update(env_additional)
            assert set(mocked_env.items()) <= set(env.items())
        else:
            assert set().union(env_additional, env_whitelist) <= set(env)
