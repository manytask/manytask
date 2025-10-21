from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from checker.exceptions import PluginExecutionFailed
from checker.plugins.aggregate import AggregatePlugin

# Test score constants
SCORE_100_PERCENT = 1.0
SCORE_50_PERCENT = 0.5
SCORE_10 = 10.0
SCORE_20 = 20.0
SCORE_30 = 30.0
SCORE_1 = 1.0
SCORE_2 = 2.0
SCORE_3 = 3.0
SCORE_4 = 4.0
SCORE_5 = 5.0
SCORE_6 = 6.0
SCORE_15 = 15.0
SCORE_27 = 27.0
WEIGHT_1 = 1.0
WEIGHT_2 = 2.0
WEIGHT_3 = 3.0


class TestAggregatePlugin:
    @pytest.mark.parametrize(
        "parameters, expected_exception",
        [
            (
                {
                    "scores": [SCORE_50_PERCENT, SCORE_100_PERCENT, SCORE_1],
                    "weights": [WEIGHT_1, WEIGHT_2, WEIGHT_3],
                    "strategy": "mean",
                },
                None,
            ),
            (
                {"scores": [SCORE_50_PERCENT, SCORE_100_PERCENT, SCORE_1], "weights": [WEIGHT_1, WEIGHT_2, WEIGHT_3]},
                None,
            ),
            ({"scores": [SCORE_50_PERCENT, SCORE_100_PERCENT, SCORE_1], "weights": None}, None),
            ({"scores": [SCORE_50_PERCENT, SCORE_100_PERCENT, SCORE_1], "strategy": "mean"}, None),
            ({"scores": [SCORE_50_PERCENT, SCORE_100_PERCENT, SCORE_1]}, None),
            (
                {
                    "scores": [SCORE_50_PERCENT, SCORE_100_PERCENT, SCORE_1],
                    "weights": [WEIGHT_1, WEIGHT_2, WEIGHT_3],
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
            ([SCORE_10, SCORE_20, SCORE_30], None, "mean", SCORE_20),
            ([SCORE_1, SCORE_2, SCORE_3], [SCORE_50_PERCENT, SCORE_50_PERCENT, SCORE_50_PERCENT], "sum", SCORE_3),
            ([SCORE_2, SCORE_4, SCORE_6], [WEIGHT_1, WEIGHT_2, WEIGHT_3], "min", SCORE_2),
            ([SCORE_5, SCORE_10, SCORE_15], [WEIGHT_1, WEIGHT_1, WEIGHT_1], "max", SCORE_15),
            ([SCORE_3, SCORE_3, SCORE_3], [WEIGHT_1, WEIGHT_1, WEIGHT_1], "product", SCORE_27),
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
            AggregatePlugin.Args(scores=[SCORE_1, SCORE_2, SCORE_3], strategy="invalid_strategy")

    @pytest.mark.parametrize(
        "scores, weights",
        [
            ([SCORE_1, SCORE_2, SCORE_3], [WEIGHT_1, WEIGHT_2]),
            ([SCORE_1], [WEIGHT_1, WEIGHT_2]),
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
        args = AggregatePlugin.Args(scores=[SCORE_10, SCORE_20, SCORE_30], strategy="mean")

        result = plugin._run(args)
        assert result.percentage == SCORE_20
