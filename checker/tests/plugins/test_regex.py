from __future__ import annotations

from collections.abc import Callable
from inspect import cleandoc
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from checker.exceptions import PluginExecutionFailed
from checker.plugins.regex import CheckRegexpsPlugin

T_CREATE_TEST_FILES = Callable[[dict[str, str]], Path]


@pytest.fixture
def create_test_files(tmpdir: Path) -> T_CREATE_TEST_FILES:
    def _create_test_files(files_content: dict[str, str]) -> Path:
        for filename, content in files_content.items():
            file = Path(tmpdir / filename)
            file.parent.mkdir(parents=True, exist_ok=True)
            with open(file, "w") as f:
                f.write(cleandoc(content))
        return tmpdir

    return _create_test_files


class TestCheckRegexpsPlugin:
    # TODO: add tests with wrong patterns and regexps
    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            (
                {"origin": "/tmp/123", "patterns": ["*", "*.py"], "regexps": ["error"]},
                None,
            ),
            ({"patterns": ["*", "*.py"], "regexps": ["error"]}, ValidationError),
            ({"origin": "/tmp/123", "patterns": ["*", "*.py"]}, ValidationError),
            (
                {"origin": "/tmp/123", "patterns": None, "regexps": None},
                ValidationError,
            ),
        ],
    )
    def test_plugin_args(self, parameters: dict[str, Any], expected_exception: Exception | None) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                CheckRegexpsPlugin.Args(**parameters)
        else:
            CheckRegexpsPlugin.Args(**parameters)

    @pytest.mark.parametrize(
        "patterns, expected_exception",
        [
            (["*.txt"], PluginExecutionFailed),
            (["test2.txt", "*cpp"], None),
            (["*"], PluginExecutionFailed),
            (["*.md"], PluginExecutionFailed),
            (["test?.txt"], PluginExecutionFailed),
            (["test2.txt", "test1.txt"], PluginExecutionFailed),
        ],
    )
    def test_pattern_matching(
        self,
        create_test_files: T_CREATE_TEST_FILES,
        patterns: list[str],
        expected_exception: Exception | None,
    ) -> None:
        files_content = {
            "test1.txt": "This is a test file with forbidden content",
            "test2.txt": "This file is safe",
            "test3.md": "Markdown file with forbidden content",
            "test4.py": "Python file with forbidden content",
            "test5.cpp": "Cpp file with safe content",
        }
        origin = create_test_files(files_content)
        regexps = ["forbidden"]

        plugin = CheckRegexpsPlugin()
        args = CheckRegexpsPlugin.Args(origin=str(origin), patterns=patterns, regexps=regexps)

        if expected_exception:
            with pytest.raises(expected_exception):
                plugin._run(args)
        else:
            assert plugin._run(args).output == "No forbidden regexps found"

    @pytest.mark.parametrize(
        "regexps, expected_exception",
        [
            (["not_found"], None),
            (["forbidden"], PluginExecutionFailed),
            (["fo.*en"], PluginExecutionFailed),
            (["not_found", "fo.?bi.?den"], PluginExecutionFailed),
            (["fo.?bi.?den", "not_found"], PluginExecutionFailed),
        ],
    )
    def test_check_regexps(
        self,
        create_test_files: T_CREATE_TEST_FILES,
        regexps: list[str],
        expected_exception: Exception | None,
    ) -> None:
        files_content = {
            "test1.txt": "This is a test file with forbidden content",
            "test2.txt": "This file is safe",
            "test3.md": "Markdown file with forbidden content",
            "test4.py": "Python file with forbidden content",
            "test5.cpp": "Cpp file with safe content",
        }
        origin = create_test_files(files_content)
        patterns = ["*"]

        plugin = CheckRegexpsPlugin()
        args = CheckRegexpsPlugin.Args(origin=str(origin), patterns=patterns, regexps=regexps)

        if expected_exception:
            with pytest.raises(expected_exception) as exc_info:
                plugin._run(args)
            assert "matches regexp" in str(exc_info.value)
        else:
            assert plugin._run(args).output == "No forbidden regexps found"
            assert plugin._run(args, verbose=True).output == "No forbidden regexps found"
            assert plugin._run(args, verbose=False).output == "No forbidden regexps found"

    def test_non_existent_origin(self) -> None:
        plugin = CheckRegexpsPlugin()
        args = CheckRegexpsPlugin.Args(origin="/tmp/non_existent", patterns=["*.txt"], regexps=["forbidden"])

        with pytest.raises(PluginExecutionFailed) as exc_info:
            plugin._run(args)
        assert "does not exist" in str(exc_info.value)
