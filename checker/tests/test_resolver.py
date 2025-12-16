from __future__ import annotations

import copy
from typing import Any

import pytest

from checker.exceptions import BadConfig
from checker.pipeline import ParametersResolver


class TestParametersResolver:
    @pytest.mark.parametrize(
        "template, context, expected",
        [
            ("${{ a }}", {"a": 2}, 2),
            pytest.param("${{ b }}", {"b": "2"}, "2", marks=pytest.mark.xfail()),  # TODO: check why returned as int
            ("${{ c }}", {"c": [1, 2, "4"]}, [1, 2, "4"]),
            ("    ${{ d }}", {"d": 2}, 2),
            ("${{ e }}   ", {"e": 2}, 2),
            ("${{ f }} some string", {"f": 2}, "2 some string"),
            ("${{ g }} + ${{ g }}", {"g": 2}, "2 + 2"),
            ("${{ h }}", {"h": 2.1}, 2.1),
            ("${{ i }}", {"i": 2.0}, 2.0),
        ],
    )
    def test_keep_native_type(self, template: str, context: dict[str, Any], expected: Any) -> None:
        resolver = ParametersResolver()
        assert resolver.resolve(template, context) == expected

    @pytest.mark.parametrize(
        "template, context, expected",
        [
            ("${{ a }}", {"a": 2}, 2),
            ("Hello, ${{ name }}!", {"name": "World"}, "Hello, World!"),
            ("${{ a }} + ${{ b }} = ${{ a + b }}", {"a": 2, "b": 3}, "2 + 3 = 5"),
            ("${{ a }}", {"a": 2, "b": 3}, 2),
        ],
    )
    def test_string_input(self, template: str, context: dict[str, Any], expected: Any) -> None:
        resolver = ParametersResolver()
        assert resolver.resolve(template, context) == expected

    @pytest.mark.parametrize(
        "template, context, expected",
        [
            (["${{ item }}", "${{ item }}2"], {"item": "test"}, ["test", "test2"]),
            (["${{ a }}", "${{ b }}"], {"a": 1, "b": 2}, [1, 2]),
            (
                ["${{ a }}", ["${{ b }}", "${{ c }}"]],
                {"a": 1, "b": 2, "c": 3},
                [1, [2, 3]],
            ),
        ],
    )
    def test_list_input(self, template: list[Any], context: dict[str, Any], expected: list[Any]) -> None:
        resolver = ParametersResolver()
        assert resolver.resolve(template, context) == expected

    @pytest.mark.parametrize(
        "template, context, expected",
        [
            (
                {"key1": "${{ a }}", "key2": "${{ b }}"},
                {"a": "x", "b": "y"},
                {"key1": "x", "key2": "y"},
            ),
            (
                {"name": "Hello, ${{ name }}!"},
                {"name": "Alice"},
                {"name": "Hello, Alice!"},
            ),
            (
                {"key1": "${{ a }}", "key2": {"key3": "${{ b }}"}},
                {"a": 1, "b": 2},
                {"key1": 1, "key2": {"key3": 2}},
            ),
        ],
    )
    def test_dict_input(
        self,
        template: dict[str, Any],
        context: dict[str, Any],
        expected: dict[str, Any],
    ) -> None:
        resolver = ParametersResolver()
        assert resolver.resolve(template, context) == expected

    @pytest.mark.parametrize(
        "template, context",
        [
            (1, {}),
            (1, {"a": 1}),
            (1.0, {"a": 1}),
            ("some string", {"a": 1}),
            ("a", {"a": 1}),
            ("{a}", {"a": 1}),
            ({}, {"a": 1}),
            ([None, {1, 2, 3}, ["a", "b"]], {"a": 1}),
        ],
    )
    def test_non_template(self, template: Any, context: dict[str, Any]) -> None:
        resolver = ParametersResolver()
        template_copy = copy.deepcopy(template)
        assert resolver.resolve(template, context) == template_copy

    @pytest.mark.parametrize(
        "template, context",
        [
            ("${{ invalid_syntax", {"invalid_syntax": 2}),
            pytest.param(
                "${{ valid_var.invalid_field }}",
                {"valid_var": {"valid_field": 1}},
                marks=pytest.mark.xfail(),
            ),
            pytest.param("${{ not_existing }} ${{ a }}", {"a": 2}, marks=pytest.mark.xfail()),
            pytest.param("${{ not_existing }}", {"a": 2}, marks=pytest.mark.xfail()),
            pytest.param("invalid_syntax }}", {"invalid_syntax": 2}, marks=pytest.mark.xfail()),
        ],
    )
    def test_invalid_template(self, template: Any, context: dict[str, Any]) -> None:
        resolver = ParametersResolver()
        with pytest.raises(BadConfig):
            a = resolver.resolve(template, context)
            print(a)
