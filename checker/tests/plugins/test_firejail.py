from __future__ import annotations

import re
from io import StringIO
from pathlib import Path
from random import randrange
from typing import Any
from unittest.mock import patch

import dotenv
import pytest
from pydantic import ValidationError

from checker.exceptions import PluginExecutionFailed
from checker.plugins.firejail import SafeRunScriptPlugin

PATTERN_ENV = re.compile(r"(?P<name>\S+)=.*")
PATH = "PATH"
PYTHONPATH = "PYTHONPATH"
HOME = Path.home()
RANDOM_CONTENT = "### random content ###"
RANDOM_LINES = [
    "some words ",
    "new line\n",
    "\t\t\ttabbed block",
]


def in_home(path: str) -> Path:
    return HOME.joinpath(path)


@pytest.mark.firejail
class TestSafeRunScriptPlugin:
    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            ({"origin": "/tmp/123", "script": "echo Hello"}, None),
            ({"origin": "/tmp/123", "script": 123}, ValidationError),
            ({"origin": "/tmp/123", "script": ["echo", "Hello"]}, None),
            ({"origin": "/tmp/123", "script": "echo Hello", "timeout": 10}, None),
        ],
    )
    def test_plugin_args(self, parameters: dict[str, Any], expected_exception: Exception | None) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                SafeRunScriptPlugin.Args(**parameters)
        else:
            SafeRunScriptPlugin.Args(**parameters)

    @pytest.mark.parametrize(
        "script, output, expected_exception",
        [
            ("echo Hello", "Hello", None),
            ("sleep 0.1", "", None),
            ("true", "", None),
            ("false", "", PluginExecutionFailed),
            ("echo Hello && false", "Hello", PluginExecutionFailed),
        ],
    )
    def test_run_script(self, script: str, output: str, expected_exception: Exception | None) -> None:
        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(origin="/tmp", script=script)

        if expected_exception:
            with pytest.raises(expected_exception) as exc_info:
                plugin._run(args)
            assert output in exc_info.value.output
        else:
            res = plugin._run(args)
            assert res.output.strip() == output

    @pytest.mark.parametrize(
        "script, timeout, expected_exception",
        [
            ("echo Hello", 10, None),
            ("sleep 0.5", 1, None),
            ("sleep 1", None, None),
            ("sleep 2", 1, PluginExecutionFailed),
        ],
    )
    def test_timeout(self, script: str, timeout: float, expected_exception: Exception | None) -> None:
        # TODO: check if timeout float
        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(origin="/tmp", script=script, timeout=timeout)

        if expected_exception:
            with pytest.raises(expected_exception):
                plugin._run(args)
        else:
            plugin._run(args)

    @pytest.mark.parametrize(
        "env_whitelist",
        [
            ([]),
            ([PATH]),
            ([PATH, PYTHONPATH]),
        ],
    )
    def test_hide_evns(self, env_whitelist) -> None:
        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(origin="/tmp", script="printenv", env_whitelist=env_whitelist)

        res_lines = [line.strip() for line in plugin._run(args).output.splitlines()]
        envs: list[str] = []
        for line in res_lines:
            match = PATTERN_ENV.match(line)
            if match and not match.group("name").startswith("-"):
                envs.append(match.group("name"))

        # check if environment has only two items: PATH and PYTHONPATH
        assert len(envs) == len(env_whitelist)
        for env in envs:
            assert env in env_whitelist

    @pytest.mark.parametrize(
        "query",
        [
            ("curl -i -X GET https://www.example.org"),
            ("curl --user daniel:secret ftp://example.com/download"),
        ],
    )
    def test_allow_network_access(self, query: str) -> None:
        # TODO: have to mock network and check if lock_network = False allows access to the Internet
        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(origin="/tmp", script=query, lock_network=True)

        with pytest.raises(PluginExecutionFailed):
            plugin._run(args)

    @pytest.mark.parametrize(
        "origin, paths_whitelist, access_file, expected_exception",
        [
            (Path("/tmp"), [], Path("/tmp/tmp.txt"), None),
            (Path("/tmp"), [], in_home("tmp/tmp.txt"), None),  # this is a trick!!! origin /tmp is replaced by ~/tmp
            (Path("/tmp"), [], in_home("tmp.txt"), PluginExecutionFailed),
            (Path("/tmp"), [HOME], in_home("tmp.txt"), None),
            (HOME, [], in_home("tmp.txt"), None),
            (Path("/tmp"), [], in_home("not_tmp/tmp.txt"), PluginExecutionFailed),
            (Path("/tmp"), [in_home("not_tmp")], in_home("not_tmp/tmp.txt"), None),
            (in_home("not_tmp"), [], in_home("not_tmp/tmp.txt"), None),
            (HOME, [], in_home("tmp.txt"), None),
            (in_home("not_tmp"), [], in_home("tmp.txt"), PluginExecutionFailed),
            (in_home("not_tmp"), [HOME], in_home("tmp.txt"), None),
            (HOME, [], in_home("tmp/tmp.txt"), None),
            (in_home("not_tmp"), [HOME], in_home("tmp/tmp.txt"), None),
            (HOME, [], in_home("not_tmp/tmp.txt"), None),
            (in_home("tmp"), [], in_home("tmp/tmp.txt"), None),
            (in_home("not_tmp"), [in_home("tmp")], in_home("tmp/tmp.txt"), None),
            (in_home("tmp"), [], in_home("tmp.txt"), PluginExecutionFailed),
            (in_home("not_tmp"), [in_home("tmp")], in_home("tmp.txt"), PluginExecutionFailed),
            (in_home("tmp"), [], in_home("not_tmp/tmp.txt"), PluginExecutionFailed),
            (Path("/tmp"), [in_home("tmp")], in_home("not_tmp/tmp.txt"), PluginExecutionFailed),
        ],
    )
    def test_file_system_access(
        self,
        origin: Path,
        paths_whitelist: list[Path],
        access_file: Path,
        expected_exception: Exception | None,
    ) -> None:
        access_file_path = access_file
        access_file_path.parent.mkdir(parents=True, exist_ok=True)
        access_file_path.touch()

        origin.mkdir(parents=True, exist_ok=True)

        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(
            origin=str(origin),
            paths_whitelist=[str(path) for path in paths_whitelist],
            script=f"cat {str(access_file)}",
        )

        if expected_exception:
            with pytest.raises(expected_exception):
                plugin._run(args)
        else:
            plugin._run(args)

        access_file_path.unlink()

    @pytest.mark.parametrize(
        "test_file_content",
        [
            "",
            "       ",
            "\n",
            "single line",
            "single line\n",
            "multiple lines\n" * 3,
            "many maltiple lines\n" * 100,
            RANDOM_CONTENT,
        ],
    )
    def test_no_extra_output(self, test_file_content: str) -> None:
        def _generate_random_content() -> str:
            return "".join([RANDOM_LINES[randrange(0, len(RANDOM_LINES))] for _ in range(0, randrange(0, 100))])

        tmp_dir = in_home("tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        file_path = tmp_dir.joinpath("tmp.txt")
        file_content = test_file_content if test_file_content != RANDOM_CONTENT else _generate_random_content()
        with open(file_path, "w") as f:
            f.write(file_content)

        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(
            origin=str(tmp_dir),
            path_whitelist=[],
            script=f"cat {str(file_path)}",
        )
        assert plugin._run(args).output == file_content

        file_path.unlink()

    @pytest.mark.parametrize("env_additional", [{}, {"A": "B"}, {"A": "C"}, {"A": "B", "C": "D"}])
    @pytest.mark.parametrize("env_whitelist", [[], ["A"], ["A", "C"]])
    @pytest.mark.parametrize("mocked_env", [{}, {"A": "B"}, {"A": "C"}, {"A": "B", "C": "D"}])
    def test_run_with_environment_variable(
        self, env_additional: dict[str, str], env_whitelist: list[str], mocked_env: dict[str, str]
    ) -> None:
        plugin = SafeRunScriptPlugin()
        args = SafeRunScriptPlugin.Args(
            origin="/tmp", script="env", env_additional=env_additional, env_whitelist=env_whitelist
        )

        with patch.dict("os.environ", mocked_env, clear=True):
            result = plugin._run(args)

        env = dotenv.dotenv_values(stream=StringIO(result.output))
        for e, v in env_additional.items():
            assert env[e] == v

        diff = set(env) - set(env_additional) - set(env_whitelist)
        assert not diff
