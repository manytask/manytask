from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from checker.exceptions import PluginExecutionFailed
from checker.plugins.aggregate import AggregatePlugin


class TestAggregatePlugin:
    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            ({"scores": [0.5, 1.0, 1], "weights": [1, 2, 3], "strategy": "mean"}, None),
            ({"scores": [0.5, 1.0, 1], "weights": [1, 2, 3]}, None),
            ({"scores": [0.5, 1.0, 1], "weights": None}, None),
            ({"scores": [0.5, 1.0, 1], "strategy": "mean"}, None),
            ({"scores": [0.5, 1.0, 1]}, None),
            (
                {
                    "scores": [0.5, 1.0, 1],
                    "weights": [1, 2, 3],
                    "strategy": "invalid_strategy",
                },
                ValidationError,
            ),
            ({}, ValidationError),
        ],
    )
    def test_plugin_args(self, parameters: dict[str, Any], expected_exception: Exception | None) -> None:
        if expected_exception:
            with pytest.raises(expected_exception):
                AggregatePlugin.Args(**parameters)
        else:
            AggregatePlugin.Args(**parameters)

    @pytest.mark.parametrize(
        "scores, weights, strategy, expected",
        [
            ([10, 20, 30], None, "mean", 20.0),
            ([1, 2, 3], [0.5, 0.5, 0.5], "sum", 3.0),
            ([2, 4, 6], [1, 2, 3], "min", 2.0),
            ([5, 10, 15], [1, 1, 1], "max", 15.0),
            ([3, 3, 3], [1, 1, 1], "product", 27.0),
        ],
    )
    def test_aggregate_strategies(
        self,
        scores: list[float],
        weights: list[float] | None,
        strategy: str,
        expected: float,
    ) -> None:
        plugin = AggregatePlugin()
        args = AggregatePlugin.Args(scores=scores, weights=weights, strategy=strategy)

        result = plugin._run(args)
        assert expected == result.percentage
        assert f"Score: {expected:.2f}" in result.output

    def test_wrong_strategy(self) -> None:
        with pytest.raises(ValidationError):
            AggregatePlugin.Args(scores=[1, 2, 3], strategy="invalid_strategy")

    @pytest.mark.parametrize(
        "scores, weights",
        [
            ([1, 2, 3], [1, 2]),
            ([1], [1, 2]),
            ([], []),
        ],
    )
    def test_length_mismatch(self, scores: list[float], weights: list[float]) -> None:
        # TODO: move to args validation
        plugin = AggregatePlugin()
        args = AggregatePlugin.Args(scores=scores, weights=weights)

        with pytest.raises(PluginExecutionFailed) as exc_info:
            plugin._run(args)
        assert "Length of scores" in str(exc_info.value)

    def test_default_weights(self) -> None:
        plugin = AggregatePlugin()
        args = AggregatePlugin.Args(scores=[10, 20, 30], strategy="mean")

        result = plugin._run(args)
        assert result.percentage == 20.0
